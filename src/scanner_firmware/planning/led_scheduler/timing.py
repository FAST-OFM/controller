"""Frame-synchronous logical LED timing plan builder."""

from __future__ import annotations

from scanner_firmware.planning.led_scheduler.constants import (
    ACTIVE_HIGH,
    LED_POLARITIES,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError
from scanner_firmware.planning.led_scheduler.patterns import (
    LogicalLedPatternResolver,
    validate_logical_gate_name,
)
from scanner_firmware.planning.led_scheduler.types import (
    LedBaselineTransition,
    DisabledOutputLedTimingContract,
    LedBrightnessSetpoint,
    LedExposureWindow,
    LedGateWindow,
    LedPattern,
    LedTimingPlan,
)


class LogicalLedTimingModel:
    """Build simulator-only LED timing plans using logical gate aliases."""

    def __init__(self, patterns: dict[str, LedPattern] | None = None):
        self._resolver = LogicalLedPatternResolver(patterns)

    def plan_frame(
        self,
        *,
        pattern: str,
        frame_start_us: int,
        exposure_start_us: int,
        exposure_us: int,
        gate_pulse_us: int,
        settle_us: int = 0,
        frame_period_us: int | None = None,
        trigger_pulse_us: int | None = None,
        gate_pre_trigger_us: int | None = None,
        gate_post_exposure_us: int | None = None,
        baseline_gate_names: tuple[str, ...] = (),
        baseline_suppress_pre_gate_us: int = 0,
        baseline_restore_post_gate_us: int = 0,
        polarity: str = ACTIVE_HIGH,
        brightness_by_gate: dict[str, float] | None = None,
    ) -> LedTimingPlan:
        led_pattern = self._resolver.resolve(pattern)
        self._validate_pattern(led_pattern)
        self._validate_common_timing(
            frame_start_us=frame_start_us,
            exposure_start_us=exposure_start_us,
            exposure_us=exposure_us,
            gate_pulse_us=gate_pulse_us,
            settle_us=settle_us,
            frame_period_us=frame_period_us,
            trigger_pulse_us=trigger_pulse_us,
            gate_pre_trigger_us=gate_pre_trigger_us,
            gate_post_exposure_us=gate_post_exposure_us,
            baseline_gate_names=baseline_gate_names,
            baseline_suppress_pre_gate_us=baseline_suppress_pre_gate_us,
            baseline_restore_post_gate_us=baseline_restore_post_gate_us,
            polarity=polarity,
            has_gates=bool(led_pattern.gate_names),
        )

        exposure = LedExposureWindow(
            start_us=exposure_start_us,
            end_us=exposure_start_us + exposure_us,
        )
        brightness_setpoints = self._brightness_setpoints(
            led_pattern.gate_names,
            brightness_by_gate or {},
        )
        gate_windows = self._gate_windows(
            gate_names=led_pattern.gate_names,
            frame_start_us=frame_start_us,
            exposure=exposure,
            gate_pulse_us=gate_pulse_us,
            settle_us=settle_us,
            gate_pre_trigger_us=gate_pre_trigger_us,
            gate_post_exposure_us=gate_post_exposure_us,
            polarity=polarity,
        )
        baseline_transitions = self._baseline_transitions(
            baseline_gate_names=baseline_gate_names,
            gate_windows=gate_windows,
            baseline_suppress_pre_gate_us=baseline_suppress_pre_gate_us,
            baseline_restore_post_gate_us=baseline_restore_post_gate_us,
        )

        trigger_end_us = None
        if trigger_pulse_us is not None:
            trigger_end_us = frame_start_us + trigger_pulse_us
        return LedTimingPlan(
            pattern=led_pattern,
            frame_start_us=frame_start_us,
            exposure=exposure,
            brightness_setpoints=brightness_setpoints,
            gate_windows=gate_windows,
            baseline_gate_names=baseline_gate_names,
            baseline_transitions=baseline_transitions,
            frame_period_us=frame_period_us,
            trigger_start_us=frame_start_us,
            trigger_end_us=trigger_end_us,
        )

    def _validate_pattern(self, pattern: LedPattern) -> None:
        for gate_name in pattern.gate_names:
            validate_logical_gate_name(gate_name)

    def _validate_common_timing(
        self,
        *,
        frame_start_us: int,
        exposure_start_us: int,
        exposure_us: int,
        gate_pulse_us: int,
        settle_us: int,
        frame_period_us: int | None,
        trigger_pulse_us: int | None,
        gate_pre_trigger_us: int | None,
        gate_post_exposure_us: int | None,
        baseline_gate_names: tuple[str, ...],
        baseline_suppress_pre_gate_us: int,
        baseline_restore_post_gate_us: int,
        polarity: str,
        has_gates: bool,
    ) -> None:
        _require_non_negative("frame_start_us", frame_start_us)
        _require_non_negative("exposure_start_us", exposure_start_us)
        _require_non_negative("settle_us", settle_us)
        if exposure_start_us < frame_start_us:
            raise LedTimingError("exposure_start_us must be at or after frame_start_us")
        if frame_period_us is not None and frame_period_us <= 0:
            raise LedTimingError("frame_period_us must be positive")
        if trigger_pulse_us is not None and trigger_pulse_us <= 0:
            raise LedTimingError("trigger_pulse_us must be positive")
        if gate_pre_trigger_us is not None and gate_pre_trigger_us < 0:
            raise LedTimingError("gate_pre_trigger_us must be non-negative")
        if gate_post_exposure_us is not None and gate_post_exposure_us < 0:
            raise LedTimingError("gate_post_exposure_us must be non-negative")
        if exposure_us <= 0:
            raise LedTimingError("exposure_us must be positive")
        if not isinstance(baseline_gate_names, tuple):
            raise LedTimingError("baseline_gate_names must be a tuple")
        for gate_name in baseline_gate_names:
            validate_logical_gate_name(gate_name)
        _require_non_negative("baseline_suppress_pre_gate_us", baseline_suppress_pre_gate_us)
        _require_non_negative("baseline_restore_post_gate_us", baseline_restore_post_gate_us)
        uses_pattern_window = (
            gate_pre_trigger_us is not None or gate_post_exposure_us is not None
        )
        if has_gates and not uses_pattern_window and gate_pulse_us <= 0:
            raise LedTimingError("gate_pulse_us must be positive when gates are enabled")
        if (not has_gates or uses_pattern_window) and gate_pulse_us < 0:
            raise LedTimingError("gate_pulse_us must be non-negative")
        if polarity not in LED_POLARITIES:
            raise LedTimingError(f"unsupported LED polarity: {polarity}")

    def _brightness_setpoints(
        self,
        gate_names: tuple[str, ...],
        brightness_by_gate: dict[str, float],
    ) -> tuple[LedBrightnessSetpoint, ...]:
        gate_name_set = set(gate_names)
        for gate_name in brightness_by_gate:
            validate_logical_gate_name(gate_name)
            if gate_name not in gate_name_set:
                raise LedTimingError(f"brightness setpoint for inactive gate: {gate_name}")

        setpoints = []
        for gate_name in gate_names:
            brightness = brightness_by_gate.get(gate_name, 1.0)
            if brightness < 0.0 or brightness > 1.0:
                raise LedTimingError(
                    f"brightness for {gate_name} must be between 0.0 and 1.0"
                )
            setpoints.append(
                LedBrightnessSetpoint(gate_name=gate_name, brightness=brightness)
            )
        return tuple(setpoints)

    def _gate_windows(
        self,
        *,
        gate_names: tuple[str, ...],
        frame_start_us: int,
        exposure: LedExposureWindow,
        gate_pulse_us: int,
        settle_us: int,
        gate_pre_trigger_us: int | None,
        gate_post_exposure_us: int | None,
        polarity: str,
    ) -> tuple[LedGateWindow, ...]:
        if gate_pre_trigger_us is not None or gate_post_exposure_us is not None:
            start_us = frame_start_us - (gate_pre_trigger_us or 0)
            if start_us < 0:
                raise LedTimingError("LED gate window starts before frame time zero")
            end_us = exposure.end_us + (gate_post_exposure_us or 0)
            if end_us <= start_us:
                raise LedTimingError("LED gate window end_us must be after start_us")
            return tuple(
                LedGateWindow(
                    gate_name=gate_name,
                    start_us=start_us,
                    end_us=end_us,
                    polarity=polarity,
                )
                for gate_name in gate_names
            )

        windows = []
        cursor_us = exposure.start_us + settle_us
        for gate_name in gate_names:
            gate_end_us = cursor_us + gate_pulse_us
            if gate_end_us > exposure.end_us:
                raise LedTimingError(
                    "LED gate pulses plus settle time exceed exposure window"
                )
            windows.append(
                LedGateWindow(
                    gate_name=gate_name,
                    start_us=cursor_us,
                    end_us=gate_end_us,
                    polarity=polarity,
                )
            )
            cursor_us = gate_end_us
        return tuple(windows)

    def _baseline_transitions(
        self,
        *,
        baseline_gate_names: tuple[str, ...],
        gate_windows: tuple[LedGateWindow, ...],
        baseline_suppress_pre_gate_us: int,
        baseline_restore_post_gate_us: int,
    ) -> tuple[LedBaselineTransition, ...]:
        if not baseline_gate_names:
            return ()
        if not gate_windows:
            return ()
        start_us = min(window.start_us for window in gate_windows) - baseline_suppress_pre_gate_us
        if start_us < 0:
            raise LedTimingError("baseline suppression starts before frame time zero")
        end_us = max(window.end_us for window in gate_windows) + baseline_restore_post_gate_us
        transitions: list[LedBaselineTransition] = []
        for gate_name in baseline_gate_names:
            transitions.extend(
                (
                    LedBaselineTransition(
                        gate_name=gate_name,
                        time_us=start_us,
                        state="inactive",
                        reason="suppress_preview_baseline_for_af_window",
                    ),
                    LedBaselineTransition(
                        gate_name=gate_name,
                        time_us=end_us,
                        state="active",
                        reason="restore_preview_baseline_after_af_window",
                    ),
                )
            )
        return tuple(transitions)


def build_disabled_output_led_timing_contract(
    plan: LedTimingPlan,
) -> DisabledOutputLedTimingContract:
    """Build protocol-safe LED timing metadata from a simulator timing plan."""

    return DisabledOutputLedTimingContract(
        pattern=plan.pattern.pattern,
        frame_use=plan.pattern.frame_use,
        logical_channel_names=plan.pattern.gate_names,
        frame_start_us=plan.frame_start_us,
        exposure_start_us=plan.exposure.start_us,
        exposure_end_us=plan.exposure.end_us,
        brightness_setpoints=plan.brightness_setpoints,
        gate_windows=plan.gate_windows,
        baseline_gate_names=plan.baseline_gate_names,
        baseline_transitions=plan.baseline_transitions,
        frame_period_us=plan.frame_period_us,
        trigger_start_us=plan.trigger_start_us,
        trigger_end_us=plan.trigger_end_us,
        hardware_outputs_enabled=False,
    )


def validate_frame_event_led_timing_contract(
    frame_event: object,
) -> DisabledOutputLedTimingContract:
    """Validate that a FRAME_EVENT carries matching LED timing metadata."""

    if getattr(frame_event, "type", None) != "FRAME_EVENT":
        raise LedTimingError("expected FRAME_EVENT for LED timing contract")
    if getattr(frame_event, "hardware_outputs_enabled", None) is not False:
        raise LedTimingError("FRAME_EVENT hardware_outputs_enabled must be false")

    led_timing = getattr(frame_event, "led_timing", None)
    if led_timing is None:
        raise LedTimingError("FRAME_EVENT is missing led_timing contract metadata")
    if not isinstance(led_timing, dict):
        raise LedTimingError("FRAME_EVENT led_timing must be a JSON object")

    contract = DisabledOutputLedTimingContract.from_json_dict(led_timing)
    frame_pattern = getattr(frame_event, "pattern", None)
    if contract.pattern != frame_pattern:
        raise LedTimingError("LED timing contract pattern does not match FRAME_EVENT")
    led_gate_names = tuple(getattr(frame_event, "led_gate_names", ()))
    if contract.logical_channel_names != led_gate_names:
        raise LedTimingError(
            "LED timing contract logical channels do not match FRAME_EVENT"
        )
    if contract.frame_start_us != getattr(frame_event, "mcu_time_us", None):
        raise LedTimingError("LED timing contract frame_start_us must match mcu_time_us")

    for gate_name in contract.logical_channel_names:
        validate_logical_gate_name(gate_name)
    if tuple(window.gate_name for window in contract.gate_windows) != led_gate_names:
        raise LedTimingError("LED gate windows must follow FRAME_EVENT logical channels")
    if tuple(
        setpoint.gate_name for setpoint in contract.brightness_setpoints
    ) != led_gate_names:
        raise LedTimingError(
            "LED brightness setpoints must follow FRAME_EVENT logical channels"
        )
    for window in contract.gate_windows:
        validate_logical_gate_name(window.gate_name)
        if window.start_us < 0:
            raise LedTimingError("LED gate window start_us must be non-negative")
        if window.end_us <= window.start_us:
            raise LedTimingError("LED gate window end_us must be after start_us")
    for gate_name in contract.baseline_gate_names:
        validate_logical_gate_name(gate_name)
    for transition in contract.baseline_transitions:
        validate_logical_gate_name(transition.gate_name)
        if transition.gate_name not in contract.baseline_gate_names:
            raise LedTimingError("baseline transition gate must be listed in baseline_gate_names")
    return contract


def _require_non_negative(name: str, value: int) -> None:
    if value < 0:
        raise LedTimingError(f"{name} must be non-negative")
