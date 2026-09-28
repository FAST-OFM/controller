"""Dry-run trigger scheduler records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Union

from scanner_firmware.domain.coordinate_source.types import CoordinateSourceMode
from scanner_firmware.planning.led_scheduler.types import LedPatternTimingSet


Axis = Literal["X", "Y"]
CoordinateSource = CoordinateSourceMode
TerminalReasonCode = Literal[
    "host_stop",
    "scheduler_fault",
    "coordinate_source_error",
    "position_stream_exhausted",
]
TerminalStatus = Literal["stopped", "fault"]


@dataclass(frozen=True)
class StripeSchedule:
    scan_id: str
    stripe_id: int
    axis: Axis
    start_position: int
    end_position: int
    first_event_position: int
    event_pitch: int
    event_count: int
    pattern_sequence: tuple[str, ...]
    coordinate_source: CoordinateSource = "step_indexed"
    dry_run: bool = True
    hardware_outputs_enabled: bool = False
    pattern_led_timing: LedPatternTimingSet | None = None


@dataclass(frozen=True)
class PositionSample:
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int = 0
    x_encoder_count: int | None = None
    y_encoder_count: int | None = None
    mcu_time_us: int = 0


@dataclass(frozen=True)
class FrameEvent:
    type: Literal["FRAME_EVENT"]
    protocol_version: int
    scan_id: str
    stripe_id: int
    frame_id: int
    stripe_frame_index: int
    pattern: str
    led_gate_names: tuple[str, ...]
    trigger_output_name: str
    coordinate_source_used: CoordinateSource
    position_axis: Axis
    event_position: int
    sample_position: int
    position_overshoot_count: int
    x_count: int
    y_count: int
    z_count: int
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int
    x_encoder_count: int | None
    y_encoder_count: int | None
    coordinate_flags: tuple[str, ...]
    mcu_time_us: int
    hardware_outputs_enabled: bool
    status: Literal["ok"]
    led_timing: dict[str, Any] | None = None

    def to_protocol_record(self):
        """Convert this scheduler event into the external protocol DTO."""

        from scanner_firmware.foundation.protocol.events import FrameEventRecord

        return FrameEventRecord.from_scheduler_frame_event(self)


@dataclass(frozen=True)
class SchedulerTerminalEvent:
    type: Literal["SCHEDULER_TERMINAL"]
    protocol_version: int
    scan_id: str
    stripe_id: int
    status: TerminalStatus
    reason_code: TerminalReasonCode
    emitted_frame_count: int
    expected_frame_count: int
    last_frame_id: int | None
    next_frame_id: int
    next_stripe_frame_index: int
    mcu_time_us: int
    hardware_outputs_enabled: bool
    message: str


SchedulerEvent = Union[FrameEvent, SchedulerTerminalEvent]


class ScheduleError(ValueError):
    """Raised when a schedule cannot be executed safely even in dry-run."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: TerminalReasonCode = "scheduler_fault",
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
