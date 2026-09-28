"""Software-only no-motion illumination timing diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.planning.led_scheduler.errors import LedTimingError
from scanner_firmware.planning.led_scheduler.timing import (
    LogicalLedTimingModel,
    build_disabled_output_led_timing_contract,
)
from scanner_firmware.planning.led_scheduler.types import (
    DisabledOutputLedTimingContract,
    LedPatternTimingProfile,
)


@dataclass(frozen=True)
class LedTimingDiagnosticConfig:
    """No-motion diagnostic sequence for oscilloscope timing checks."""

    timing_profile: LedPatternTimingProfile
    frame_start_us: int
    repeat_period_us: int
    repeat_count: int
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        _require_non_negative("frame_start_us", self.frame_start_us)
        _require_positive("repeat_period_us", self.repeat_period_us)
        _require_positive("repeat_count", self.repeat_count)
        if self.hardware_outputs_enabled is not False:
            raise LedTimingError("diagnostic contracts must keep hardware outputs disabled")


class LedTimingDiagnosticPlanner:
    """Build repeated disabled-output timing contracts without commanding hardware."""

    def __init__(self, timing_model: LogicalLedTimingModel | None = None) -> None:
        self._timing_model = timing_model or LogicalLedTimingModel()

    def plan(
        self,
        config: LedTimingDiagnosticConfig,
    ) -> tuple[DisabledOutputLedTimingContract, ...]:
        contracts: list[DisabledOutputLedTimingContract] = []
        previous_end_us: int | None = None
        for index in range(config.repeat_count):
            frame_start_us = config.frame_start_us + index * config.repeat_period_us
            timing_profile = config.timing_profile
            plan = self._timing_model.plan_frame(
                pattern=timing_profile.pattern,
                frame_start_us=frame_start_us,
                exposure_start_us=frame_start_us + timing_profile.exposure_start_offset_us,
                exposure_us=timing_profile.exposure_us,
                gate_pulse_us=timing_profile.gate_pulse_us,
                settle_us=timing_profile.settle_us,
                frame_period_us=config.repeat_period_us,
                trigger_pulse_us=timing_profile.trigger_pulse_us,
                gate_pre_trigger_us=timing_profile.gate_pre_trigger_us,
                gate_post_exposure_us=timing_profile.gate_post_exposure_us,
                baseline_gate_names=timing_profile.baseline_gate_names,
                baseline_suppress_pre_gate_us=timing_profile.baseline_suppress_pre_gate_us,
                baseline_restore_post_gate_us=timing_profile.baseline_restore_post_gate_us,
                polarity=timing_profile.polarity,
                brightness_by_gate=timing_profile.brightness_by_gate,
            )
            contract = build_disabled_output_led_timing_contract(plan)
            contract_start_us = _contract_start_us(contract)
            if previous_end_us is not None and contract_start_us < previous_end_us:
                raise LedTimingError(
                    "diagnostic repeat_period_us overlaps the previous LED timing window"
                )
            previous_end_us = _contract_end_us(contract)
            contracts.append(contract)
        return tuple(contracts)


def _require_non_negative(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedTimingError(f"{name} must be an integer")
    if value < 0:
        raise LedTimingError(f"{name} must be non-negative")


def _require_positive(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedTimingError(f"{name} must be an integer")
    if value <= 0:
        raise LedTimingError(f"{name} must be positive")


def _contract_start_us(contract: DisabledOutputLedTimingContract) -> int:
    starts = [
        contract.frame_start_us,
        contract.exposure_start_us,
        contract.trigger_start_us
        if contract.trigger_start_us is not None
        else contract.frame_start_us,
    ]
    starts.extend(window.start_us for window in contract.gate_windows)
    starts.extend(transition.time_us for transition in contract.baseline_transitions)
    return min(starts)


def _contract_end_us(contract: DisabledOutputLedTimingContract) -> int:
    ends = [
        contract.exposure_end_us,
        contract.trigger_end_us
        if contract.trigger_end_us is not None
        else contract.frame_start_us,
    ]
    ends.extend(window.end_us for window in contract.gate_windows)
    ends.extend(transition.time_us for transition in contract.baseline_transitions)
    return max(ends)
