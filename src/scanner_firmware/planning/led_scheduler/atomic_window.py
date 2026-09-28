"""Software-only atomic illumination windows for scanner-sync planning."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.planning.led_scheduler.constants import (
    ACTIVE_HIGH,
    LED_GREEN_GATE,
    LED_RED_GATE,
    LED_WHITE_GATE,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError
from scanner_firmware.planning.led_scheduler.timing import (
    LogicalLedTimingModel,
    build_disabled_output_led_timing_contract,
    validate_frame_event_led_timing_contract,
)
from scanner_firmware.planning.led_scheduler.types import (
    DisabledOutputLedTimingContract,
    LedBaselineTransition,
    LedGateWindow,
)


MKS_V1_ATOMIC_ILLUMINATION_WINDOW_ID = "mks_v1_atomic_illumination_window"
MKS_V1_AF_PATTERN = "AF_RED_GREEN"


@dataclass(frozen=True)
class MksV1AtomicIlluminationWindowConfig:
    """V1 MKS AF window timing, represented as metadata only.

    `frame_start_us` is the MCU time recorded when the position-indexed
    trigger fires. It is not a Linux-wall-clock scheduling input.
    """

    frame_start_us: int
    settle_us: int
    exposure_hold_us: int
    xvs_trigger_pulse_us: int
    trigger_position_count: int | None = None
    frame_period_us: int | None = None
    red_brightness: float = 1.0
    green_brightness: float = 1.0
    polarity: str = ACTIVE_HIGH


@dataclass(frozen=True)
class MksV1AtomicIlluminationWindow:
    """Validated logical timing envelope for the MKS V1 AF window.

    The contract names logical gates only. Current MKS pins remain documented
    board facts and are not emitted by this software-only model.
    """

    contract: DisabledOutputLedTimingContract
    window_id: str = MKS_V1_ATOMIC_ILLUMINATION_WINDOW_ID
    trigger_position_count: int | None = None

    @property
    def red_green_on_us(self) -> int:
        return self.contract.gate_windows[0].start_us

    @property
    def xvs_trigger_us(self) -> int:
        trigger_start_us = self.contract.trigger_start_us
        if trigger_start_us is None:
            raise LedTimingError("atomic illumination window requires trigger_start_us")
        return trigger_start_us

    @property
    def red_green_off_us(self) -> int:
        return self.contract.gate_windows[0].end_us

    @property
    def white_restore_us(self) -> int:
        restore = _restore_transition(self.contract.baseline_transitions)
        return restore.time_us

    @property
    def settle_us(self) -> int:
        return self.xvs_trigger_us - self.red_green_on_us

    @property
    def exposure_hold_us(self) -> int:
        return self.red_green_off_us - self.xvs_trigger_us


def build_mks_v1_no_motion_af_window(
    config: MksV1AtomicIlluminationWindowConfig,
    *,
    timing_model: LogicalLedTimingModel | None = None,
) -> MksV1AtomicIlluminationWindow:
    """Build the V1 MKS AF window without enabling physical outputs.

    Sequence represented by the returned metadata:
    white off; red+green on together; settle; XVS trigger; exposure hold;
    red+green off together; white restore.
    """

    _validate_config(config)
    model = timing_model or LogicalLedTimingModel()
    plan = model.plan_frame(
        pattern=MKS_V1_AF_PATTERN,
        frame_start_us=config.frame_start_us,
        exposure_start_us=config.frame_start_us,
        exposure_us=config.exposure_hold_us,
        gate_pulse_us=0,
        frame_period_us=config.frame_period_us,
        trigger_pulse_us=config.xvs_trigger_pulse_us,
        gate_pre_trigger_us=config.settle_us,
        gate_post_exposure_us=0,
        baseline_gate_names=(LED_WHITE_GATE,),
        baseline_suppress_pre_gate_us=0,
        baseline_restore_post_gate_us=0,
        polarity=config.polarity,
        brightness_by_gate={
            LED_RED_GATE: config.red_brightness,
            LED_GREEN_GATE: config.green_brightness,
        },
    )
    contract = build_disabled_output_led_timing_contract(plan)
    return validate_mks_v1_atomic_illumination_window(
        contract,
        trigger_position_count=config.trigger_position_count,
    )


def validate_mks_v1_atomic_illumination_window(
    contract: DisabledOutputLedTimingContract,
    *,
    trigger_position_count: int | None = None,
) -> MksV1AtomicIlluminationWindow:
    """Validate a disabled-output contract as the V1 MKS atomic AF window."""

    _validate_trigger_position_count(trigger_position_count)
    if contract.hardware_outputs_enabled is not False:
        raise LedTimingError("atomic illumination window must keep hardware outputs disabled")
    if contract.pattern != MKS_V1_AF_PATTERN:
        raise LedTimingError("atomic illumination window requires AF_RED_GREEN")
    if contract.logical_channel_names != (LED_RED_GATE, LED_GREEN_GATE):
        raise LedTimingError("atomic illumination window requires red and green logical gates")
    if contract.baseline_gate_names != (LED_WHITE_GATE,):
        raise LedTimingError("atomic illumination window must suppress led_white baseline")

    red_window, green_window = _red_green_windows(contract.gate_windows)
    if red_window.start_us != green_window.start_us:
        raise LedTimingError("red and green gates must turn on atomically")
    if red_window.end_us != green_window.end_us:
        raise LedTimingError("red and green gates must turn off atomically")
    if red_window.polarity != ACTIVE_HIGH or green_window.polarity != ACTIVE_HIGH:
        raise LedTimingError("MKS V1 atomic illumination window requires active-high gates")

    trigger_start_us = contract.trigger_start_us
    trigger_end_us = contract.trigger_end_us
    if trigger_start_us is None or trigger_end_us is None:
        raise LedTimingError("atomic illumination window requires XVS trigger timing")
    if trigger_start_us != contract.frame_start_us:
        raise LedTimingError("XVS trigger must start at FRAME_EVENT mcu_time_us")
    if red_window.start_us >= trigger_start_us:
        raise LedTimingError("red and green gates must settle before XVS trigger")
    if contract.exposure_start_us != trigger_start_us:
        raise LedTimingError("exposure hold must start at XVS trigger time")
    if contract.exposure_end_us != red_window.end_us:
        raise LedTimingError("red and green gates must turn off at exposure hold end")
    if trigger_end_us > contract.exposure_end_us:
        raise LedTimingError("XVS trigger pulse must fit inside exposure hold")

    suppress = _suppress_transition(contract.baseline_transitions)
    restore = _restore_transition(contract.baseline_transitions)
    if suppress.time_us != red_window.start_us:
        raise LedTimingError("led_white must turn off when red and green turn on")
    if restore.time_us != red_window.end_us:
        raise LedTimingError("led_white must restore when red and green turn off")

    return MksV1AtomicIlluminationWindow(
        contract=contract,
        trigger_position_count=trigger_position_count,
    )


def validate_frame_event_mks_v1_atomic_illumination_window(
    frame_event: object,
) -> MksV1AtomicIlluminationWindow:
    """Validate a FRAME_EVENT LED timing payload as the V1 MKS AF window."""

    return validate_mks_v1_atomic_illumination_window(
        validate_frame_event_led_timing_contract(frame_event)
    )


def _validate_config(config: MksV1AtomicIlluminationWindowConfig) -> None:
    _validate_trigger_position_count(config.trigger_position_count)
    if config.settle_us <= 0:
        raise LedTimingError("settle_us must be positive for atomic AF window")
    if config.exposure_hold_us <= 0:
        raise LedTimingError("exposure_hold_us must be positive")
    if config.xvs_trigger_pulse_us <= 0:
        raise LedTimingError("xvs_trigger_pulse_us must be positive")
    if config.xvs_trigger_pulse_us > config.exposure_hold_us:
        raise LedTimingError("xvs_trigger_pulse_us must fit inside exposure_hold_us")


def _validate_trigger_position_count(trigger_position_count: int | None) -> None:
    if trigger_position_count is None:
        return
    if isinstance(trigger_position_count, bool) or not isinstance(
        trigger_position_count,
        int,
    ):
        raise LedTimingError("trigger_position_count must be an integer")
    if trigger_position_count < 0:
        raise LedTimingError("trigger_position_count must be non-negative")


def _red_green_windows(
    gate_windows: tuple[LedGateWindow, ...],
) -> tuple[LedGateWindow, LedGateWindow]:
    if tuple(window.gate_name for window in gate_windows) != (LED_RED_GATE, LED_GREEN_GATE):
        raise LedTimingError("atomic illumination window gate order must be red then green")
    return gate_windows[0], gate_windows[1]


def _suppress_transition(
    transitions: tuple[LedBaselineTransition, ...],
) -> LedBaselineTransition:
    if len(transitions) != 2:
        raise LedTimingError("atomic illumination window requires white off and restore")
    transition = transitions[0]
    if transition.gate_name != LED_WHITE_GATE or transition.state != "inactive":
        raise LedTimingError("atomic illumination window requires led_white inactive transition")
    return transition


def _restore_transition(
    transitions: tuple[LedBaselineTransition, ...],
) -> LedBaselineTransition:
    if len(transitions) != 2:
        raise LedTimingError("atomic illumination window requires white off and restore")
    transition = transitions[1]
    if transition.gate_name != LED_WHITE_GATE or transition.state != "active":
        raise LedTimingError("atomic illumination window requires led_white restore transition")
    return transition
