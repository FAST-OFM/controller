"""Frame counter publication records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Tuple

from scanner_firmware.planning.frame_counter.publishing.errors import (
    FrameEventPublishError,
    FramePublishTerminalError,
)
from scanner_firmware.planning.frame_counter.common.validation import (
    require_bool,
    require_non_empty,
    require_non_negative,
    tuple_of_str,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError
from scanner_firmware.planning.led_scheduler.types import DisabledOutputLedTimingContract


CoordinateSource = Literal["step_indexed", "encoder_indexed", "hybrid"]
FramePublishKey = Tuple[str, int, int]
PositionAxis = Literal["X", "Y"]
TerminalReasonCode = Literal[
    "host_stop",
    "scheduler_fault",
    "coordinate_source_error",
    "position_stream_exhausted",
]
TerminalStatus = Literal["stopped", "fault"]


@dataclass(frozen=True)
class PlannedFrameTrigger:
    """One planned acquisition trigger in metadata/dry-run mode."""

    scan_id: str
    stripe_id: int
    stripe_frame_index: int
    pattern: str
    coordinate_source_used: CoordinateSource
    position_axis: PositionAxis
    event_position: int
    sample_position: int
    position_overshoot_count: int
    x_count: int
    y_count: int
    z_count: int
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int
    mcu_time_us: int
    x_encoder_count: Optional[int] = None
    y_encoder_count: Optional[int] = None
    coordinate_flags: Tuple[str, ...] = ()
    led_gate_names: Tuple[str, ...] = ()
    led_timing: dict[str, Any] | None = None
    trigger_output_name: str = "camera_or_sync_trigger"
    dry_run: bool = True
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        require_non_empty("scan_id", self.scan_id)
        require_non_empty("pattern", self.pattern)
        require_non_empty("trigger_output_name", self.trigger_output_name)
        require_non_negative("stripe_id", self.stripe_id)
        require_non_negative("stripe_frame_index", self.stripe_frame_index)
        require_non_negative("mcu_time_us", self.mcu_time_us)
        require_bool("dry_run", self.dry_run)
        require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)
        if not self.dry_run:
            raise FrameEventPublishError(
                "planned FRAME_EVENT publishing is metadata/dry-run only"
            )
        if self.hardware_outputs_enabled:
            raise FrameEventPublishError(
                "hardware_outputs_enabled must be false for metadata/dry-run publishing"
            )
        object.__setattr__(self, "coordinate_flags", tuple_of_str(self.coordinate_flags))
        object.__setattr__(self, "led_gate_names", tuple_of_str(self.led_gate_names))
        _validate_led_timing_contract(
            self.led_timing,
            pattern=self.pattern,
            led_gate_names=self.led_gate_names,
            mcu_time_us=self.mcu_time_us,
        )

    @property
    def key(self) -> FramePublishKey:
        return (self.scan_id, self.stripe_id, self.stripe_frame_index)


@dataclass(frozen=True)
class PublishedFrameEvent:
    """Published metadata event for exactly one planned trigger."""

    protocol_version: int
    scan_id: str
    stripe_id: int
    frame_id: int
    stripe_frame_index: int
    pattern: str
    coordinate_source_used: CoordinateSource
    position_axis: PositionAxis
    event_position: int
    sample_position: int
    position_overshoot_count: int
    x_count: int
    y_count: int
    z_count: int
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int
    mcu_time_us: int
    x_encoder_count: Optional[int] = None
    y_encoder_count: Optional[int] = None
    coordinate_flags: Tuple[str, ...] = ()
    led_gate_names: Tuple[str, ...] = ()
    led_timing: dict[str, Any] | None = None
    trigger_output_name: str = "camera_or_sync_trigger"
    hardware_outputs_enabled: bool = False
    status: Literal["ok"] = "ok"
    type: Literal["FRAME_EVENT"] = field(default="FRAME_EVENT", init=False)

    def to_protocol_record(self):
        """Convert this publisher event into the external protocol DTO."""

        from scanner_firmware.foundation.protocol.events import FrameEventRecord

        return FrameEventRecord.from_published_frame_event(self)

    def __post_init__(self) -> None:
        object.__setattr__(self, "coordinate_flags", tuple_of_str(self.coordinate_flags))
        object.__setattr__(self, "led_gate_names", tuple_of_str(self.led_gate_names))
        _validate_led_timing_contract(
            self.led_timing,
            pattern=self.pattern,
            led_gate_names=self.led_gate_names,
            mcu_time_us=self.mcu_time_us,
        )
        require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)
        if self.hardware_outputs_enabled:
            raise FrameEventPublishError(
                "hardware_outputs_enabled must be false for metadata/dry-run publishing"
            )


@dataclass(frozen=True)
class FramePublisherTerminal:
    """Terminal summary for one published scan/stripe stream."""

    protocol_version: int
    scan_id: str
    stripe_id: int
    status: TerminalStatus
    reason_code: TerminalReasonCode
    emitted_frame_count: int
    expected_frame_count: int
    last_frame_id: Optional[int]
    next_frame_id: int
    next_stripe_frame_index: int
    mcu_time_us: int
    message: str = ""
    hardware_outputs_enabled: bool = False
    type: Literal["SCHEDULER_TERMINAL"] = field(
        default="SCHEDULER_TERMINAL", init=False
    )

    def __post_init__(self) -> None:
        require_non_empty("scan_id", self.scan_id)
        require_non_empty("reason_code", self.reason_code)
        require_non_negative("stripe_id", self.stripe_id)
        require_non_negative("emitted_frame_count", self.emitted_frame_count)
        require_non_negative("expected_frame_count", self.expected_frame_count)
        require_non_negative("next_frame_id", self.next_frame_id)
        require_non_negative("next_stripe_frame_index", self.next_stripe_frame_index)
        require_non_negative("mcu_time_us", self.mcu_time_us)
        require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)
        if self.last_frame_id is not None:
            require_non_negative("last_frame_id", self.last_frame_id)
        if self.emitted_frame_count > self.expected_frame_count:
            raise FramePublishTerminalError(
                "emitted_frame_count cannot exceed expected_frame_count"
            )
        if self.emitted_frame_count == self.expected_frame_count:
            raise FramePublishTerminalError(
                "clean completion emits no SCHEDULER_TERMINAL record"
            )
        if self.status not in ("stopped", "fault"):
            raise FramePublishTerminalError("terminal status must be stopped or fault")
        if self.reason_code not in (
            "host_stop",
            "scheduler_fault",
            "coordinate_source_error",
            "position_stream_exhausted",
        ):
            raise FramePublishTerminalError("unsupported terminal reason_code")
        if self.hardware_outputs_enabled:
            raise FramePublishTerminalError(
                "hardware_outputs_enabled must be false for metadata/dry-run terminal"
            )


def _validate_led_timing_contract(
    payload: dict[str, Any] | None,
    *,
    pattern: str,
    led_gate_names: tuple[str, ...],
    mcu_time_us: int,
) -> None:
    if payload is None:
        return
    if not isinstance(payload, dict):
        raise FrameEventPublishError("led_timing must be a JSON object")
    try:
        contract = DisabledOutputLedTimingContract.from_json_dict(payload)
    except (KeyError, TypeError, LedTimingError) as exc:
        raise FrameEventPublishError(f"invalid led_timing contract: {exc}") from exc
    if contract.pattern != pattern:
        raise FrameEventPublishError("led_timing pattern must match frame pattern")
    if contract.logical_channel_names != led_gate_names:
        raise FrameEventPublishError(
            "led_timing logical channels must match led_gate_names"
        )
    if contract.frame_start_us != mcu_time_us:
        raise FrameEventPublishError("led_timing frame_start_us must match mcu_time_us")
