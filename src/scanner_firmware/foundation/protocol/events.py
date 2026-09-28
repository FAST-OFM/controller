"""Protocol record models and JSON serialization helpers.

These dataclasses describe scanner protocol payloads only. They do not touch
firmware backends, GPIO, motion, cameras or LEDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Literal,
    Optional,
    Tuple,
    Union,
)

from scanner_firmware.foundation.protocol.canonical import (
    CANONICAL_PROTOCOL_VERSION as CANONICAL_PROTOCOL_VERSION,
    PROTOTYPE_PROTOCOL_VERSION as PROTOTYPE_PROTOCOL_VERSION,
    canonicalize_protocol_v1_payload as canonicalize_protocol_v1_payload,
    require_canonical_protocol_v1_payload as require_canonical_protocol_v1_payload,
    to_canonical_v1_json as to_canonical_v1_json,
    to_canonical_v1_json_dict as to_canonical_v1_json_dict,
)
from scanner_firmware.foundation.protocol.serialization import (
    JsonDict,
    JsonRecordMixin,
    JsonScalar as JsonScalar,
    JsonValue as JsonValue,
    ProtocolSerializationError,
    _json_safe,
    to_json as to_json,
    to_json_dict as to_json_dict,
)

if TYPE_CHECKING:
    from scanner_firmware.planning.frame_counter.publishing.records import (
        PublishedFrameEvent,
    )
    from scanner_firmware.planning.trigger_scheduler.types import (
        FrameEvent as SchedulerFrameEvent,
    )


ProtocolVersion = Union[int, str]
CoordinateSource = Literal["step_indexed", "encoder_indexed", "hybrid"]
PositionAxis = Literal["X", "Y"]
TerminalReasonCode = Literal[
    "host_stop",
    "scheduler_fault",
    "coordinate_source_error",
    "position_stream_exhausted",
]
TerminalStatus = Literal["stopped", "fault"]
ZTargetKind = Literal["frame", "position"]
TimedOutputSequenceMode = Literal["diagnostic_immediate", "position_armed"]
TimedOutputSequenceStartCondition = Literal["immediate", "position_count"]
TimedOutputSequenceStatus = Literal[
    "accepted",
    "rejected",
    "started",
    "completed",
    "stopped",
    "fault",
]
START_COMMAND: Literal["scanner_sync_start"] = "scanner_sync_start"
STOP_COMMAND: Literal["scanner_sync_stop"] = "scanner_sync_stop"
SCHEDULE_Z_COMMAND: Literal["scanner_sync_schedule_z"] = "scanner_sync_schedule_z"
ARM_AF_WINDOW_COMMAND: Literal["scanner_sync_arm_af_window"] = (
    "scanner_sync_arm_af_window"
)
FIRE_AF_WINDOW_NOW_COMMAND: Literal["scanner_sync_fire_af_window_now"] = (
    "scanner_sync_fire_af_window_now"
)
RUN_STATIONARY_AF_TEST_COMMAND: Literal["scanner_sync_run_stationary_af_test"] = (
    "scanner_sync_run_stationary_af_test"
)
RUN_TIMED_OUTPUT_SEQUENCE_COMMAND: Literal["scanner_sync_run_timed_output_sequence"] = (
    "scanner_sync_run_timed_output_sequence"
)
TERMINAL_REASON_CODES: frozenset[str] = frozenset(
    (
        "host_stop",
        "scheduler_fault",
        "coordinate_source_error",
        "position_stream_exhausted",
    )
)
TERMINAL_STATUSES: frozenset[str] = frozenset(("stopped", "fault"))
TIMED_OUTPUT_SEQUENCE_MAX_STEPS = 32
TIMED_OUTPUT_SEQUENCE_MAX_MASK = 0xFF
TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT = 0x01
TIMED_OUTPUT_SEQUENCE_LED_RED_BIT = 0x02
TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT = 0x04
TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT = 0x08
TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK = (
    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT
    | TIMED_OUTPUT_SEQUENCE_LED_RED_BIT
    | TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT
    | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT
)
TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG = 0x0001
TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG = 0x0002
TIMED_OUTPUT_SEQUENCE_XVS_FALLING_FLAG = 0x0004
TIMED_OUTPUT_SEQUENCE_END_FLAG = 0x0008
TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG = 0x0010
TIMED_OUTPUT_SEQUENCE_EXPOSURE_END_FLAG = 0x0020
TIMED_OUTPUT_SEQUENCE_KNOWN_FLAGS = (
    TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG
    | TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG
    | TIMED_OUTPUT_SEQUENCE_XVS_FALLING_FLAG
    | TIMED_OUTPUT_SEQUENCE_END_FLAG
    | TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG
    | TIMED_OUTPUT_SEQUENCE_EXPOSURE_END_FLAG
)
TIMED_OUTPUT_SEQUENCE_STATUSES: frozenset[str] = frozenset(
    ("accepted", "rejected", "started", "completed", "stopped", "fault")
)
TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US = 100_000
TIMED_OUTPUT_SEQUENCE_EVENT_FLAG_NAMES: tuple[tuple[int, str], ...] = (
    (TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG, "frame_event"),
    (TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG, "xvs_rising"),
    (TIMED_OUTPUT_SEQUENCE_XVS_FALLING_FLAG, "xvs_falling"),
    (TIMED_OUTPUT_SEQUENCE_END_FLAG, "end"),
    (TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG, "exposure_start"),
    (TIMED_OUTPUT_SEQUENCE_EXPOSURE_END_FLAG, "exposure_end"),
)


def timed_output_sequence_event_flag_names(event_flags: int) -> Tuple[str, ...]:
    _require_flag_mask("event_flags", event_flags)
    return tuple(
        name
        for flag, name in TIMED_OUTPUT_SEQUENCE_EVENT_FLAG_NAMES
        if event_flags & flag
    )


@dataclass(frozen=True)
class FrameEventRecord(JsonRecordMixin):
    """External protocol DTO for a serialized ``FRAME_EVENT`` payload."""

    protocol_version: ProtocolVersion
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
    led_timing: Optional[JsonDict] = None
    trigger_output_name: str = "camera_or_sync_trigger"
    event_flags: int = 0
    event_flag_names: Tuple[str, ...] = ()
    hardware_outputs_enabled: bool = False
    status: Literal["ok", "OK"] = "ok"
    type: Literal["FRAME_EVENT"] = field(default="FRAME_EVENT", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "coordinate_flags", _tuple_of_str(self.coordinate_flags))
        object.__setattr__(self, "led_gate_names", _tuple_of_str(self.led_gate_names))
        _require_flag_mask("event_flags", self.event_flags)
        event_flag_names = _tuple_of_str(self.event_flag_names)
        expected_names = timed_output_sequence_event_flag_names(self.event_flags)
        if event_flag_names and event_flag_names != expected_names:
            raise ValueError("event_flag_names must match event_flags")
        object.__setattr__(self, "event_flag_names", expected_names)
        if self.led_timing is not None:
            if not isinstance(self.led_timing, dict):
                raise TypeError("led_timing must be a JSON object")
            object.__setattr__(self, "led_timing", _json_safe(self.led_timing))
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)

    def to_json_dict(self) -> JsonDict:
        payload = super().to_json_dict()
        if payload.get("led_timing") is None:
            del payload["led_timing"]
        if payload.get("event_flags") == 0:
            del payload["event_flags"]
        if payload.get("event_flag_names") == []:
            del payload["event_flag_names"]
        return payload

    @classmethod
    def from_scheduler_frame_event(
        cls, event: "SchedulerFrameEvent"
    ) -> "FrameEventRecord":
        """Build a protocol frame record from the dry-run scheduler event shape."""

        return cls._from_frame_event_shape(event, source_name="scheduler")

    @classmethod
    def from_published_frame_event(
        cls, event: "PublishedFrameEvent"
    ) -> "FrameEventRecord":
        """Build a protocol frame record from the frame publisher event shape."""

        return cls._from_frame_event_shape(event, source_name="published")

    @classmethod
    def from_scheduler_event(cls, event: Any) -> "FrameEventRecord":
        """Build a protocol frame record from the dry-run scheduler event shape."""

        return cls._from_frame_event_shape(event, source_name="scheduler")

    @classmethod
    def _from_frame_event_shape(
        cls, event: Any, *, source_name: str
    ) -> "FrameEventRecord":
        if getattr(event, "type", None) != "FRAME_EVENT":
            raise ProtocolSerializationError(f"expected FRAME_EVENT {source_name} event")
        if getattr(event, "hardware_outputs_enabled", None) is not False:
            raise ProtocolSerializationError("hardware_outputs_enabled must be false")
        return cls(
            protocol_version=event.protocol_version,
            scan_id=event.scan_id,
            stripe_id=event.stripe_id,
            frame_id=event.frame_id,
            stripe_frame_index=event.stripe_frame_index,
            pattern=event.pattern,
            led_gate_names=tuple(getattr(event, "led_gate_names", ())),
            led_timing=getattr(event, "led_timing", None),
            trigger_output_name=getattr(
                event, "trigger_output_name", "camera_or_sync_trigger"
            ),
            coordinate_source_used=event.coordinate_source_used,
            position_axis=event.position_axis,
            event_position=event.event_position,
            sample_position=event.sample_position,
            position_overshoot_count=event.position_overshoot_count,
            x_count=event.x_count,
            y_count=event.y_count,
            z_count=event.z_count,
            x_step_commanded=event.x_step_commanded,
            y_step_commanded=event.y_step_commanded,
            z_step_commanded=event.z_step_commanded,
            x_encoder_count=event.x_encoder_count,
            y_encoder_count=event.y_encoder_count,
            coordinate_flags=tuple(event.coordinate_flags),
            mcu_time_us=event.mcu_time_us,
            event_flags=getattr(event, "event_flags", 0),
            event_flag_names=tuple(getattr(event, "event_flag_names", ())),
            hardware_outputs_enabled=False,
            status=event.status,
        )


@dataclass(frozen=True)
class SchedulerTerminalRecord(JsonRecordMixin):
    protocol_version: ProtocolVersion
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
    message: str
    hardware_outputs_enabled: bool = False
    type: Literal["SCHEDULER_TERMINAL"] = field(
        default="SCHEDULER_TERMINAL", init=False
    )

    def __post_init__(self) -> None:
        if self.status not in TERMINAL_STATUSES:
            raise ValueError("SCHEDULER_TERMINAL status must be stopped or fault")
        if self.reason_code not in TERMINAL_REASON_CODES:
            raise ValueError("unsupported SCHEDULER_TERMINAL reason_code")
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)

    @classmethod
    def from_scheduler_event(cls, event: Any) -> "SchedulerTerminalRecord":
        """Build a protocol terminal record from the dry-run scheduler event shape."""

        if getattr(event, "type", None) != "SCHEDULER_TERMINAL":
            raise ProtocolSerializationError("expected SCHEDULER_TERMINAL scheduler event")
        return cls(
            protocol_version=event.protocol_version,
            scan_id=event.scan_id,
            stripe_id=event.stripe_id,
            status=event.status,
            reason_code=event.reason_code,
            emitted_frame_count=event.emitted_frame_count,
            expected_frame_count=event.expected_frame_count,
            last_frame_id=event.last_frame_id,
            next_frame_id=event.next_frame_id,
            next_stripe_frame_index=event.next_stripe_frame_index,
            mcu_time_us=event.mcu_time_us,
            hardware_outputs_enabled=event.hardware_outputs_enabled,
            message=event.message,
        )


@dataclass(frozen=True)
class ScannerSyncStartCommand(JsonRecordMixin):
    seq: int
    scan_id: str
    stripe_id: int
    next_frame_id: int
    cmd: Literal["scanner_sync_start"] = field(default=START_COMMAND, init=False)

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_non_negative_int("next_frame_id", self.next_frame_id)

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "ScannerSyncStartCommand":
        if payload.get("cmd") != START_COMMAND:
            raise ProtocolSerializationError("expected scanner_sync_start command")
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            next_frame_id=payload["next_frame_id"],
        )


@dataclass(frozen=True)
class ScannerSyncStopCommand(JsonRecordMixin):
    seq: int
    scan_id: str
    stripe_id: int
    reason: TerminalReasonCode = "host_stop"
    cmd: Literal["scanner_sync_stop"] = field(default=STOP_COMMAND, init=False)

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        if self.reason not in TERMINAL_REASON_CODES:
            raise ValueError("unsupported scanner_sync_stop reason")

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "ScannerSyncStopCommand":
        if payload.get("cmd") != STOP_COMMAND:
            raise ProtocolSerializationError("expected scanner_sync_stop command")
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            reason=payload["reason"],
        )


@dataclass(frozen=True)
class ScheduleZCommand(JsonRecordMixin):
    seq: int
    scan_id: str
    stripe_id: int
    z_target_um: float
    apply_at_position_count: Optional[int] = None
    apply_at_position_um: Optional[float] = None
    apply_at_frame_id: Optional[int] = None
    source: Optional[str] = None
    confidence: Optional[float] = None
    latency_model_id: Optional[str] = None
    cmd: Literal["scanner_sync_schedule_z"] = field(
        default=SCHEDULE_Z_COMMAND, init=False
    )

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_number_value("z_target_um", self.z_target_um)
        if (
            self.apply_at_position_count is None
            and self.apply_at_position_um is None
            and self.apply_at_frame_id is None
        ):
            raise ValueError("scanner_sync_schedule_z requires at least one apply target")
        if self.apply_at_position_count is not None:
            _require_non_negative_int(
                "apply_at_position_count",
                self.apply_at_position_count,
            )
        if self.apply_at_position_um is not None:
            _require_number_value("apply_at_position_um", self.apply_at_position_um)
        if self.apply_at_frame_id is not None:
            _require_non_negative_int("apply_at_frame_id", self.apply_at_frame_id)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "ScheduleZCommand":
        if payload.get("cmd") != SCHEDULE_Z_COMMAND:
            raise ProtocolSerializationError("expected scanner_sync_schedule_z command")
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            apply_at_position_count=payload.get("apply_at_position_count"),
            apply_at_position_um=payload.get("apply_at_position_um"),
            apply_at_frame_id=payload.get("apply_at_frame_id"),
            z_target_um=payload["z_target_um"],
            source=payload.get("source"),
            confidence=payload.get("confidence"),
            latency_model_id=payload.get("latency_model_id"),
        )


@dataclass(frozen=True)
class ArmAfWindowCommand(JsonRecordMixin):
    """Arm a position-indexed autofocus illumination window on the MCU.

    The command target is a future commanded step or encoder count. Timing
    fields are MCU-local offsets inside that position event, not Linux-time
    scheduling inputs.
    """

    seq: int
    scan_id: str
    stripe_id: int
    frame_id: int
    stripe_frame_index: int
    trigger_position_count: int
    settle_us: int
    xvs_trigger_pulse_us: int
    exposure_hold_us: int
    pattern_id: int = 1
    position_axis: PositionAxis = "X"
    cmd: Literal["scanner_sync_arm_af_window"] = field(
        default=ARM_AF_WINDOW_COMMAND,
        init=False,
    )

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_non_negative_int("frame_id", self.frame_id)
        _require_non_negative_int("stripe_frame_index", self.stripe_frame_index)
        _require_non_negative_int(
            "trigger_position_count",
            self.trigger_position_count,
        )
        _require_positive_int("settle_us", self.settle_us)
        _require_positive_int("xvs_trigger_pulse_us", self.xvs_trigger_pulse_us)
        _require_positive_int("exposure_hold_us", self.exposure_hold_us)
        if self.xvs_trigger_pulse_us > self.exposure_hold_us:
            raise ValueError("xvs_trigger_pulse_us must fit inside exposure_hold_us")
        _require_non_negative_int("pattern_id", self.pattern_id)
        if self.position_axis not in ("X", "Y"):
            raise ValueError("position_axis must be X or Y")

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "ArmAfWindowCommand":
        if payload.get("cmd") != ARM_AF_WINDOW_COMMAND:
            raise ProtocolSerializationError(
                "expected scanner_sync_arm_af_window command"
            )
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            frame_id=payload["frame_id"],
            stripe_frame_index=payload["stripe_frame_index"],
            trigger_position_count=payload["trigger_position_count"],
            settle_us=payload["settle_us"],
            xvs_trigger_pulse_us=payload["xvs_trigger_pulse_us"],
            exposure_hold_us=payload["exposure_hold_us"],
            pattern_id=payload.get("pattern_id", 1),
            position_axis=payload.get("position_axis", "X"),
        )


@dataclass(frozen=True)
class FireAfWindowNowCommand(JsonRecordMixin):
    """Fire an autofocus illumination window immediately for bench tests.

    This command is diagnostic-only. It still carries the position count that
    the host is asserting for traceability, but it is not a scan scheduling
    primitive and must not replace position-indexed ``arm_af_window`` commands.
    """

    seq: int
    scan_id: str
    stripe_id: int
    frame_id: int
    stripe_frame_index: int
    event_position_count: int
    settle_us: int
    xvs_trigger_pulse_us: int
    exposure_hold_us: int
    pattern_id: int = 1
    position_axis: PositionAxis = "X"
    diagnostic_only: bool = True
    cmd: Literal["scanner_sync_fire_af_window_now"] = field(
        default=FIRE_AF_WINDOW_NOW_COMMAND,
        init=False,
    )

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_non_negative_int("frame_id", self.frame_id)
        _require_non_negative_int("stripe_frame_index", self.stripe_frame_index)
        _require_non_negative_int("event_position_count", self.event_position_count)
        _require_positive_int("settle_us", self.settle_us)
        _require_positive_int("xvs_trigger_pulse_us", self.xvs_trigger_pulse_us)
        _require_positive_int("exposure_hold_us", self.exposure_hold_us)
        if self.xvs_trigger_pulse_us > self.exposure_hold_us:
            raise ValueError("xvs_trigger_pulse_us must fit inside exposure_hold_us")
        _require_non_negative_int("pattern_id", self.pattern_id)
        if self.position_axis not in ("X", "Y"):
            raise ValueError("position_axis must be X or Y")
        _require_bool("diagnostic_only", self.diagnostic_only)
        if not self.diagnostic_only:
            raise ValueError("scanner_sync_fire_af_window_now is diagnostic-only")

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "FireAfWindowNowCommand":
        if payload.get("cmd") != FIRE_AF_WINDOW_NOW_COMMAND:
            raise ProtocolSerializationError(
                "expected scanner_sync_fire_af_window_now command"
            )
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            frame_id=payload["frame_id"],
            stripe_frame_index=payload["stripe_frame_index"],
            event_position_count=payload["event_position_count"],
            settle_us=payload["settle_us"],
            xvs_trigger_pulse_us=payload["xvs_trigger_pulse_us"],
            exposure_hold_us=payload["exposure_hold_us"],
            pattern_id=payload.get("pattern_id", 1),
            position_axis=payload.get("position_axis", "X"),
            diagnostic_only=payload.get("diagnostic_only", True),
        )


@dataclass(frozen=True)
class RunStationaryAfTestCommand(JsonRecordMixin):
    """Run a no-motion AF timing test sequence on the timing MCU.

    This is a bench diagnostic command for tuning LED and XVS delays while the
    stage is stationary. It must not be used as the production fly-scan
    primitive; scan execution must arm future position-indexed windows.
    """

    seq: int
    scan_id: str
    stripe_id: int
    first_frame_id: int
    frame_count: int
    frame_period_us: int
    event_position_count: int
    settle_us: int
    xvs_trigger_pulse_us: int
    exposure_hold_us: int
    pattern_id: int = 1
    position_axis: PositionAxis = "X"
    diagnostic_only: bool = True
    cmd: Literal["scanner_sync_run_stationary_af_test"] = field(
        default=RUN_STATIONARY_AF_TEST_COMMAND,
        init=False,
    )

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_non_negative_int("first_frame_id", self.first_frame_id)
        _require_positive_int("frame_count", self.frame_count)
        _require_positive_int("frame_period_us", self.frame_period_us)
        _require_non_negative_int("event_position_count", self.event_position_count)
        _require_positive_int("settle_us", self.settle_us)
        _require_positive_int("xvs_trigger_pulse_us", self.xvs_trigger_pulse_us)
        _require_positive_int("exposure_hold_us", self.exposure_hold_us)
        if self.xvs_trigger_pulse_us > self.exposure_hold_us:
            raise ValueError("xvs_trigger_pulse_us must fit inside exposure_hold_us")
        if self.settle_us + self.exposure_hold_us > self.frame_period_us:
            raise ValueError("AF timing window must fit inside frame_period_us")
        _require_non_negative_int("pattern_id", self.pattern_id)
        if self.position_axis not in ("X", "Y"):
            raise ValueError("position_axis must be X or Y")
        _require_bool("diagnostic_only", self.diagnostic_only)
        if not self.diagnostic_only:
            raise ValueError("scanner_sync_run_stationary_af_test is diagnostic-only")

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "RunStationaryAfTestCommand":
        if payload.get("cmd") != RUN_STATIONARY_AF_TEST_COMMAND:
            raise ProtocolSerializationError(
                "expected scanner_sync_run_stationary_af_test command"
            )
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            first_frame_id=payload["first_frame_id"],
            frame_count=payload["frame_count"],
            frame_period_us=payload["frame_period_us"],
            event_position_count=payload["event_position_count"],
            settle_us=payload["settle_us"],
            xvs_trigger_pulse_us=payload["xvs_trigger_pulse_us"],
            exposure_hold_us=payload["exposure_hold_us"],
            pattern_id=payload.get("pattern_id", 1),
            position_axis=payload.get("position_axis", "X"),
            diagnostic_only=payload.get("diagnostic_only", True),
        )


@dataclass(frozen=True)
class TimedOutputSequenceStep(JsonRecordMixin):
    """One MCU-timed logical output transition step.

    `output_mask` selects the logical outputs affected by this step.
    `output_values` supplies their post-step logical values and must not contain
    bits outside `output_mask`. `delay_us` is the MCU-local duration after the
    state change before the next step, repeat boundary or stop decision.
    """

    output_mask: int
    output_values: int
    delay_us: int
    event_flags: int = 0

    def __post_init__(self) -> None:
        _require_output_mask("output_mask", self.output_mask)
        _require_byte_mask("output_values", self.output_values)
        if self.output_values & ~self.output_mask:
            raise ValueError("output_values must not set bits outside output_mask")
        _require_positive_int("delay_us", self.delay_us)
        if self.delay_us > TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US:
            raise ValueError(
                "delay_us must be <= "
                f"{TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US} for V1 timed-output steps"
            )
        _require_flag_mask("event_flags", self.event_flags)


@dataclass(frozen=True)
class RunTimedOutputSequenceCommand(JsonRecordMixin):
    """Run a compact generic MCU-timed output sequence.

    This command is the software contract for low-level XVS/illumination timing
    diagnostics. It is intentionally generic: AF windows, continuous XVS preview
    trains and delay sweeps are encoded as output-state steps instead of adding
    one custom command per experiment.

    `repeat_count == 0` means repeat until an explicit stop/safe-state command.
    """

    seq: int
    scan_id: str
    stripe_id: int
    seq_id: int
    repeat_count: int
    steps: Tuple[TimedOutputSequenceStep, ...]
    mode: TimedOutputSequenceMode = "diagnostic_immediate"
    start_condition: TimedOutputSequenceStartCondition = "immediate"
    start_position_count: Optional[int] = None
    frame_id_base: Optional[int] = None
    pattern_id: int = 0
    safe_output_mask: int = TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK
    safe_output_values: int = 0
    idle_output_mask: int = TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK
    idle_output_values: int = 0
    diagnostic_only: bool = True
    cmd: Literal["scanner_sync_run_timed_output_sequence"] = field(
        default=RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
        init=False,
    )

    def __post_init__(self) -> None:
        _require_non_negative_int("seq", self.seq)
        _require_non_empty_str_value("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_non_negative_int("seq_id", self.seq_id)
        _require_non_negative_int("repeat_count", self.repeat_count)
        _require_timed_output_sequence_mode(self.mode)
        _require_timed_output_sequence_start_condition(self.start_condition)
        if self.mode != "diagnostic_immediate":
            raise ValueError(
                "scanner_sync_run_timed_output_sequence supports only "
                "diagnostic_immediate mode in V1"
            )
        if self.start_condition != "immediate":
            raise ValueError(
                "scanner_sync_run_timed_output_sequence supports only immediate "
                "start_condition in V1"
            )
        if self.start_position_count is not None:
            _require_non_negative_int("start_position_count", self.start_position_count)
        if self.frame_id_base is not None:
            _require_non_negative_int("frame_id_base", self.frame_id_base)
        _require_non_negative_int("pattern_id", self.pattern_id)
        _require_output_state("safe_output", self.safe_output_mask, self.safe_output_values)
        _require_output_state("idle_output", self.idle_output_mask, self.idle_output_values)
        object.__setattr__(self, "steps", _tuple_of_steps(self.steps))
        if not self.steps:
            raise ValueError("scanner_sync_run_timed_output_sequence requires steps")
        if len(self.steps) > TIMED_OUTPUT_SEQUENCE_MAX_STEPS:
            raise ValueError("scanner_sync_run_timed_output_sequence has too many steps")
        _require_bool("diagnostic_only", self.diagnostic_only)
        if not self.diagnostic_only:
            raise ValueError(
                "scanner_sync_run_timed_output_sequence is diagnostic-only until "
                "position-indexed arming is implemented"
            )

    @classmethod
    def from_json_dict(cls, payload: Dict[str, Any]) -> "RunTimedOutputSequenceCommand":
        if payload.get("cmd") != RUN_TIMED_OUTPUT_SEQUENCE_COMMAND:
            raise ProtocolSerializationError(
                "expected scanner_sync_run_timed_output_sequence command"
            )
        return cls(
            seq=payload["seq"],
            scan_id=payload["scan_id"],
            stripe_id=payload["stripe_id"],
            seq_id=payload["seq_id"],
            repeat_count=payload["repeat_count"],
            steps=tuple(
                TimedOutputSequenceStep(
                    output_mask=step["output_mask"],
                    output_values=step["output_values"],
                    delay_us=step["delay_us"],
                    event_flags=step.get("event_flags", 0),
                )
                for step in payload["steps"]
            ),
            mode=payload.get("mode", "diagnostic_immediate"),
            start_condition=payload.get("start_condition", "immediate"),
            start_position_count=payload.get("start_position_count"),
            frame_id_base=payload.get("frame_id_base"),
            pattern_id=payload.get("pattern_id", 0),
            safe_output_mask=payload.get(
                "safe_output_mask", TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK
            ),
            safe_output_values=payload.get("safe_output_values", 0),
            idle_output_mask=payload.get(
                "idle_output_mask", TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK
            ),
            idle_output_values=payload.get("idle_output_values", 0),
            diagnostic_only=payload.get("diagnostic_only", True),
        )


ScannerSyncCommand = Union[
    ScannerSyncStartCommand,
    ScannerSyncStopCommand,
    ScheduleZCommand,
    ArmAfWindowCommand,
    FireAfWindowNowCommand,
    RunStationaryAfTestCommand,
    RunTimedOutputSequenceCommand,
]


@dataclass(frozen=True)
class ZScheduledRecord(JsonRecordMixin):
    seq: int
    protocol_version: Optional[ProtocolVersion] = None
    scan_id: Optional[str] = None
    stripe_id: Optional[int] = None
    command_id: Optional[str] = None
    hardware_outputs_enabled: bool = False
    status: Literal["accepted"] = "accepted"
    type: Literal["Z_SCHEDULED"] = field(default="Z_SCHEDULED", init=False)

    def __post_init__(self) -> None:
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)

    def to_json_dict(self) -> JsonDict:
        payload = super().to_json_dict()
        _omit_missing_protocol_version(payload)
        return payload

    @classmethod
    def from_scheduler_decision(cls, decision: Any, *, seq: int) -> "ZScheduledRecord":
        if not getattr(decision, "accepted", False):
            raise ProtocolSerializationError("expected accepted Z scheduler decision")
        command = decision.command
        return cls(
            seq=seq,
            scan_id=command.scan_id,
            stripe_id=command.stripe_id,
            command_id=getattr(command, "command_id", None),
            hardware_outputs_enabled=decision.hardware_outputs_enabled,
            status=decision.status,
        )


@dataclass(frozen=True)
class ZRejectedRecord(JsonRecordMixin):
    seq: int
    reason: str
    protocol_version: Optional[ProtocolVersion] = None
    scan_id: Optional[str] = None
    stripe_id: Optional[int] = None
    command_id: Optional[str] = None
    hardware_outputs_enabled: bool = False
    status: Literal["rejected"] = "rejected"
    type: Literal["Z_REJECTED"] = field(default="Z_REJECTED", init=False)

    def __post_init__(self) -> None:
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)

    def to_json_dict(self) -> JsonDict:
        payload = super().to_json_dict()
        _omit_missing_protocol_version(payload)
        return payload

    @classmethod
    def from_scheduler_decision(cls, decision: Any, *, seq: int) -> "ZRejectedRecord":
        if getattr(decision, "accepted", False):
            raise ProtocolSerializationError("expected rejected Z scheduler decision")
        command = decision.command
        return cls(
            seq=seq,
            reason=decision.reason,
            scan_id=command.scan_id,
            stripe_id=command.stripe_id,
            command_id=getattr(command, "command_id", None),
            hardware_outputs_enabled=decision.hardware_outputs_enabled,
            status=decision.status,
        )


@dataclass(frozen=True)
class ZAppliedRecord(JsonRecordMixin):
    seq: int
    frame_id: int
    z_target_steps: int
    protocol_version: Optional[ProtocolVersion] = None
    scan_id: Optional[str] = None
    stripe_id: Optional[int] = None
    command_id: Optional[str] = None
    apply_target_kind: Optional[ZTargetKind] = None
    apply_at_frame_id: Optional[int] = None
    apply_at_position_count: Optional[int] = None
    position: Optional[int] = None
    hardware_outputs_enabled: bool = False
    status: Literal["ok"] = "ok"
    type: Literal["Z_APPLIED"] = field(default="Z_APPLIED", init=False)

    def __post_init__(self) -> None:
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)

    @property
    def z_cmd_count(self) -> int:
        """Protocol v1 wire alias for ``z_target_steps``."""

        return self.z_target_steps

    def to_json_dict(self) -> JsonDict:
        payload = super().to_json_dict()
        _omit_missing_protocol_version(payload)
        payload["z_cmd_count"] = self.z_target_steps
        return payload

    @classmethod
    def from_scheduler_event(cls, event: Any, *, seq: int) -> "ZAppliedRecord":
        if getattr(event, "type", None) != "Z_APPLIED":
            raise ProtocolSerializationError("expected Z_APPLIED scheduler event")
        return cls(
            seq=seq,
            scan_id=event.scan_id,
            stripe_id=event.stripe_id,
            command_id=getattr(event, "command_id", None),
            apply_target_kind=event.apply_target_kind,
            apply_at_frame_id=event.apply_at_frame_id,
            apply_at_position_count=event.apply_at_position_count,
            frame_id=event.frame_id,
            position=event.position,
            z_target_steps=event.z_target_steps,
            hardware_outputs_enabled=event.hardware_outputs_enabled,
            status=event.status,
        )


@dataclass(frozen=True)
class TimedOutputSequenceStatusRecord(JsonRecordMixin):
    """MCU-originated status metadata for a timed output sequence."""

    seq_id: int
    status: TimedOutputSequenceStatus
    protocol_version: Optional[ProtocolVersion] = None
    scan_id: Optional[str] = None
    stripe_id: Optional[int] = None
    seq: Optional[int] = None
    repeat_index: Optional[int] = None
    step_index: Optional[int] = None
    mcu_time_us: Optional[int] = None
    hardware_outputs_enabled: bool = False
    reason: Optional[str] = None
    type: Literal["TIMED_OUTPUT_SEQUENCE_STATUS"] = field(
        default="TIMED_OUTPUT_SEQUENCE_STATUS",
        init=False,
    )

    def __post_init__(self) -> None:
        _require_non_negative_int("seq_id", self.seq_id)
        _require_timed_output_sequence_status(self.status)
        _require_optional_non_negative_int("seq", self.seq)
        _require_optional_non_negative_int("stripe_id", self.stripe_id)
        _require_optional_non_negative_int("repeat_index", self.repeat_index)
        _require_optional_non_negative_int("step_index", self.step_index)
        _require_optional_non_negative_int("mcu_time_us", self.mcu_time_us)
        if self.scan_id is not None:
            _require_non_empty_str_value("scan_id", self.scan_id)
        if self.reason is not None:
            _require_non_empty_str_value("reason", self.reason)
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)

    def to_json_dict(self) -> JsonDict:
        payload = super().to_json_dict()
        _omit_missing_protocol_version(payload)
        return payload


ProtocolRecord = Union[
    FrameEventRecord,
    SchedulerTerminalRecord,
    ZScheduledRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    TimedOutputSequenceStatusRecord,
]


def scheduler_event_to_protocol_record(event: Any) -> ProtocolRecord:
    event_type = getattr(event, "type", None)
    if event_type == "FRAME_EVENT":
        return FrameEventRecord.from_scheduler_frame_event(event)
    if event_type == "SCHEDULER_TERMINAL":
        return SchedulerTerminalRecord.from_scheduler_event(event)
    raise ProtocolSerializationError("unsupported scheduler event type: %r" % event_type)


def _tuple_of_str(values: Iterable[str]) -> Tuple[str, ...]:
    result = tuple(values)
    if not all(isinstance(value, str) for value in result):
        raise TypeError("expected string values")
    return result


def _require_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError("%s must be a boolean" % name)


def _require_non_empty_str_value(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty string" % name)


def _require_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be an integer" % name)
    if value < 0:
        raise ValueError("%s must be non-negative" % name)


def _require_positive_int(name: str, value: int) -> None:
    _require_non_negative_int(name, value)
    if value == 0:
        raise ValueError("%s must be positive" % name)


def _require_byte_mask(name: str, value: int) -> None:
    _require_non_negative_int(name, value)
    if value > TIMED_OUTPUT_SEQUENCE_MAX_MASK:
        raise ValueError("%s must fit in one byte" % name)


def _require_output_mask(name: str, value: int) -> None:
    _require_byte_mask(name, value)
    if value & ~TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK:
        raise ValueError("%s contains unknown timed-output-sequence outputs" % name)


def _require_output_state(name: str, output_mask: int, output_values: int) -> None:
    _require_output_mask(f"{name}_mask", output_mask)
    _require_byte_mask(f"{name}_values", output_values)
    if output_values & ~output_mask:
        raise ValueError(f"{name}_values must not set bits outside {name}_mask")


def _require_flag_mask(name: str, value: int) -> None:
    _require_non_negative_int(name, value)
    if value & ~TIMED_OUTPUT_SEQUENCE_KNOWN_FLAGS:
        raise ValueError("%s contains unknown timed-output-sequence flags" % name)


def _require_timed_output_sequence_mode(value: str) -> None:
    if value not in ("diagnostic_immediate", "position_armed"):
        raise ValueError("mode must be diagnostic_immediate or position_armed")


def _require_timed_output_sequence_start_condition(value: str) -> None:
    if value not in ("immediate", "position_count"):
        raise ValueError("start_condition must be immediate or position_count")


def _require_timed_output_sequence_status(value: str) -> None:
    if value not in TIMED_OUTPUT_SEQUENCE_STATUSES:
        raise ValueError("unsupported timed output sequence status")


def _require_optional_non_negative_int(name: str, value: Optional[int]) -> None:
    if value is not None:
        _require_non_negative_int(name, value)


def _require_number_value(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be numeric" % name)


def _tuple_of_steps(
    values: Iterable[TimedOutputSequenceStep],
) -> Tuple[TimedOutputSequenceStep, ...]:
    result = tuple(values)
    if not all(isinstance(value, TimedOutputSequenceStep) for value in result):
        raise TypeError("expected timed output sequence steps")
    return result


def _omit_missing_protocol_version(payload: JsonDict) -> None:
    if payload.get("protocol_version") is None:
        del payload["protocol_version"]
