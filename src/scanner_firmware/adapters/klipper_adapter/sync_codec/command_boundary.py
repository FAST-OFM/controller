"""Software-only validation for host-originated scanner-sync command records.

This module validates command payloads as plain data before they are converted
to typed protocol commands. It intentionally does not import Klipper runtime
objects, open devices, send commands, toggle outputs or command motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from scanner_firmware.adapters.klipper_adapter.sync_codec._errors import (
    ScannerSyncCommandBoundaryError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._scalar_validation import (
    require_bool as _require_bool,
    require_int as _require_int,
    require_int_field as _require_int_field,
    require_non_empty_str as _require_non_empty_str,
    require_non_negative_int_field as _require_non_negative_int_field,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._command_boundary.correlation import (
    CommandSeqCorrelation as _CommandSeqCorrelation,
    validate_common_command_record as _validate_common_command_record,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._command_boundary.schedule_z import (
    canonicalized_schedule_z_record as _canonicalized_schedule_z_record,
    validate_schedule_z_record as _validate_schedule_z_record,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._command_boundary.start_stop import (
    validate_start_record as _validate_start_record,
    validate_stop_record as _validate_stop_record,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec import (
    _unsafe_policy as _command_boundary_policy,
)
from scanner_firmware.foundation.protocol.events import (
    RUN_STATIONARY_AF_TEST_COMMAND,
    RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
    SCHEDULE_Z_COMMAND,
    START_COMMAND,
    STOP_COMMAND,
    TIMED_OUTPUT_SEQUENCE_KNOWN_FLAGS,
    TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK,
    TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US,
    TIMED_OUTPUT_SEQUENCE_MAX_MASK,
    TIMED_OUTPUT_SEQUENCE_MAX_STEPS,
    RunStationaryAfTestCommand,
    RunTimedOutputSequenceCommand,
    ScannerSyncCommand,
    ScannerSyncStartCommand,
    ScannerSyncStopCommand,
    ScheduleZCommand,
)
from scanner_firmware.planning.z_scheduler.predictive import (
    ApplyPositionCountBasis,
)


ScannerSyncCommandBoundaryError.__module__ = __name__
POLICY_ARTIFACT_ID = _command_boundary_policy.POLICY_ARTIFACT_ID
POLICY = _command_boundary_policy.POLICY
CANONICAL_COMMANDS = _command_boundary_policy.CANONICAL_COMMANDS
COMMAND_ALIASES = _command_boundary_policy.COMMAND_ALIASES
ALIAS_CONTEXT_FIELDS = _command_boundary_policy.ALIAS_CONTEXT_FIELDS
FORBIDDEN_COMMANDS = _command_boundary_policy.FORBIDDEN_COMMANDS
FORBIDDEN_RECORD_KEYS = _command_boundary_policy.FORBIDDEN_RECORD_KEYS
BOOLEAN_SAFETY_FIELDS = _command_boundary_policy.BOOLEAN_SAFETY_FIELDS
STOP_REASONS = _command_boundary_policy.STOP_REASONS
PROTOCOL_VERSION = _command_boundary_policy.PROTOCOL_VERSION
_reject_unsafe_fields = _command_boundary_policy.reject_unsafe_fields
_validate_hardware_output_policy = _command_boundary_policy.validate_hardware_outputs


@dataclass(frozen=True)
class ScannerSyncCommandBoundaryContext:
    """Policy for validating command records in replay or dry-run contexts."""

    dry_run: bool = True
    replay: bool = True
    expected_scan_id: str | None = None
    expected_stripe_id: int | None = None
    expected_first_seq: int | None = None
    require_contiguous_seq: bool = True
    allow_hardware_outputs: bool = False
    allow_legacy_alias_at_adapter_boundary: bool = False
    current_frame_id: int | None = None
    current_position_count: int | None = None
    position_direction: int | None = None
    apply_position_count_basis: ApplyPositionCountBasis | None = None

    def __post_init__(self) -> None:
        _require_bool("dry_run", self.dry_run)
        _require_bool("replay", self.replay)
        _require_bool("require_contiguous_seq", self.require_contiguous_seq)
        _require_bool("allow_hardware_outputs", self.allow_hardware_outputs)
        _require_bool(
            "allow_legacy_alias_at_adapter_boundary",
            self.allow_legacy_alias_at_adapter_boundary,
        )
        if self.expected_scan_id is not None and not self.expected_scan_id:
            raise ScannerSyncCommandBoundaryError("expected_scan_id must be non-empty")
        if self.expected_stripe_id is not None:
            _require_int("expected_stripe_id", self.expected_stripe_id)
            if self.expected_stripe_id < 0:
                raise ScannerSyncCommandBoundaryError(
                    "expected_stripe_id must be non-negative"
                )
        if self.expected_first_seq is not None:
            _require_int("expected_first_seq", self.expected_first_seq)
        if self.current_frame_id is not None:
            _require_int("current_frame_id", self.current_frame_id)
            if self.current_frame_id < 0:
                raise ScannerSyncCommandBoundaryError(
                    "current_frame_id must be non-negative"
                )
        if self.current_position_count is not None:
            _require_int("current_position_count", self.current_position_count)
        if self.position_direction is not None and self.position_direction not in (-1, 1):
            raise ScannerSyncCommandBoundaryError("position_direction must be -1 or 1")


@dataclass(frozen=True)
class ScannerSyncCommandBoundaryReport:
    """Compact report for a batch of accepted host command records."""

    accepted: bool
    record_count: int
    command_names: tuple[str, ...]
    seqs: tuple[int, ...]
    start_count: int
    stop_count: int
    schedule_z_count: int
    stationary_af_test_count: int
    timed_output_sequence_count: int
    dry_run: bool
    replay: bool
    hardware_outputs_enabled: bool

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "record_count": self.record_count,
            "command_names": list(self.command_names),
            "seqs": list(self.seqs),
            "start_count": self.start_count,
            "stop_count": self.stop_count,
            "schedule_z_count": self.schedule_z_count,
            "stationary_af_test_count": self.stationary_af_test_count,
            "timed_output_sequence_count": self.timed_output_sequence_count,
            "dry_run": self.dry_run,
            "replay": self.replay,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
        }


def validate_host_command_records(
    records: Iterable[Mapping[str, Any]],
    *,
    context: ScannerSyncCommandBoundaryContext | None = None,
) -> ScannerSyncCommandBoundaryReport:
    """Validate host command records without touching firmware or hardware.

    The current accepted host command surface is intentionally narrow:
    ``scanner_sync_start``, ``scanner_sync_stop`` and
    ``scanner_sync_schedule_z`` records must provide a sequence id and
    scan/stripe identity. Schedule-Z records also require exactly one future
    target field and a Z target. The documented legacy ``schedule_z`` alias is
    accepted only here and normalized before typed command parsing. Immediate
    ``move_z_now`` records are rejected at this boundary.
    """

    active_context = context or ScannerSyncCommandBoundaryContext()
    decoded_records = tuple(records)
    command_names: list[str] = []
    seqs: list[int] = []
    start_count = 0
    stop_count = 0
    schedule_z_count = 0
    stationary_af_test_count = 0
    timed_output_sequence_count = 0
    seq_correlation = _CommandSeqCorrelation(active_context)
    hardware_outputs_enabled = False

    for record_index, record in enumerate(decoded_records):
        if not isinstance(record, Mapping):
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: expected object payload"
            )
        _reject_unsafe_fields(record, f"record {record_index}")
        command_name = _require_non_empty_str(record, "cmd", record_index)
        if command_name in FORBIDDEN_COMMANDS:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {command_name} is not allowed in dry-run boundary"
            )
        command_name = _canonical_command_name(command_name, active_context, record_index)
        if command_name is None:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: unsupported command "
                f"{record['cmd']!r}"
            )

        _validate_hardware_outputs(record, record_index, active_context)
        hardware_outputs_enabled = (
            hardware_outputs_enabled or record.get("hardware_outputs_enabled") is True
        )
        seq = _validate_common_command_record(record, record_index, active_context)
        if command_name == START_COMMAND:
            _validate_start_record(record, record_index)
            start_count += 1
        elif command_name == STOP_COMMAND:
            _validate_stop_record(record, record_index)
            stop_count += 1
        elif command_name == SCHEDULE_Z_COMMAND:
            _validate_schedule_z_record(record, record_index, active_context)
            schedule_z_count += 1
        elif command_name == RUN_STATIONARY_AF_TEST_COMMAND:
            _validate_stationary_af_test_record(record, record_index)
            stationary_af_test_count += 1
        elif command_name == RUN_TIMED_OUTPUT_SEQUENCE_COMMAND:
            _validate_timed_output_sequence_record(record, record_index)
            timed_output_sequence_count += 1
        else:
            raise AssertionError(f"unhandled scanner-sync command {command_name!r}")
        seq_correlation.accept(seq, record_index)
        command_names.append(command_name)
        seqs.append(seq)

    return ScannerSyncCommandBoundaryReport(
        accepted=True,
        record_count=len(decoded_records),
        command_names=tuple(command_names),
        seqs=tuple(seqs),
        start_count=start_count,
        stop_count=stop_count,
        schedule_z_count=schedule_z_count,
        stationary_af_test_count=stationary_af_test_count,
        timed_output_sequence_count=timed_output_sequence_count,
        dry_run=active_context.dry_run,
        replay=active_context.replay,
        hardware_outputs_enabled=hardware_outputs_enabled,
    )


def parse_validated_schedule_z_commands(
    records: Iterable[Mapping[str, Any]],
    *,
    context: ScannerSyncCommandBoundaryContext | None = None,
) -> tuple[ScheduleZCommand, ...]:
    """Validate records and return typed ``ScheduleZCommand`` objects."""

    decoded_records = tuple(records)
    validate_host_command_records(decoded_records, context=context)
    active_context = context or ScannerSyncCommandBoundaryContext()
    return tuple(
        ScheduleZCommand.from_json_dict(
            _canonicalized_schedule_z_record(record, active_context)
        )
        for record in decoded_records
    )


def parse_validated_scanner_sync_commands(
    records: Iterable[Mapping[str, Any]],
    *,
    context: ScannerSyncCommandBoundaryContext | None = None,
) -> tuple[ScannerSyncCommand, ...]:
    """Validate records and return typed scanner-sync command DTOs."""

    decoded_records = tuple(records)
    validate_host_command_records(decoded_records, context=context)
    active_context = context or ScannerSyncCommandBoundaryContext()
    return tuple(_typed_scanner_sync_command(record, active_context) for record in decoded_records)


def _canonical_command_name(
    command_name: str,
    context: ScannerSyncCommandBoundaryContext,
    record_index: int,
) -> str | None:
    if command_name in CANONICAL_COMMANDS:
        return command_name
    if command_name in COMMAND_ALIASES:
        context_field = ALIAS_CONTEXT_FIELDS[command_name]
        if getattr(context, context_field) is True:
            return COMMAND_ALIASES[command_name]
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {command_name} alias is stale outside adapter boundary"
        )
    return None


def _typed_scanner_sync_command(
    record: Mapping[str, Any],
    context: ScannerSyncCommandBoundaryContext,
) -> ScannerSyncCommand:
    command_name = _canonical_command_name(str(record.get("cmd", "")), context, 0)
    if command_name == START_COMMAND:
        return ScannerSyncStartCommand.from_json_dict(dict(record))
    if command_name == STOP_COMMAND:
        return ScannerSyncStopCommand.from_json_dict(dict(record))
    if command_name == SCHEDULE_Z_COMMAND:
        return ScheduleZCommand.from_json_dict(
            _canonicalized_schedule_z_record(record, context)
        )
    if command_name == RUN_STATIONARY_AF_TEST_COMMAND:
        return RunStationaryAfTestCommand.from_json_dict(dict(record))
    if command_name == RUN_TIMED_OUTPUT_SEQUENCE_COMMAND:
        return RunTimedOutputSequenceCommand.from_json_dict(dict(record))
    raise ScannerSyncCommandBoundaryError(f"unsupported command {record.get('cmd')!r}")


def _validate_stationary_af_test_record(
    record: Mapping[str, Any],
    record_index: int,
) -> None:
    for key in (
        "first_frame_id",
        "frame_count",
        "frame_period_us",
        "event_position_count",
        "settle_us",
        "xvs_trigger_pulse_us",
        "exposure_hold_us",
    ):
        value = _require_int_field(record, key, record_index)
        if key in ("first_frame_id", "event_position_count") and value < 0:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {key} must be non-negative"
            )
        if key not in ("first_frame_id", "event_position_count") and value <= 0:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {key} must be positive"
            )
    xvs_trigger_pulse_us = int(record["xvs_trigger_pulse_us"])
    exposure_hold_us = int(record["exposure_hold_us"])
    settle_us = int(record["settle_us"])
    frame_period_us = int(record["frame_period_us"])
    if xvs_trigger_pulse_us > exposure_hold_us:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: xvs_trigger_pulse_us must fit inside exposure_hold_us"
        )
    if settle_us + exposure_hold_us > frame_period_us:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: AF timing window must fit inside frame_period_us"
        )
    if "pattern_id" in record and _require_int_field(record, "pattern_id", record_index) < 0:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: pattern_id must be non-negative"
        )
    if "position_axis" in record and record["position_axis"] not in ("X", "Y"):
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: position_axis must be X or Y"
        )
    if record.get("diagnostic_only", True) is not True:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: scanner_sync_run_stationary_af_test is diagnostic-only"
        )


def _validate_timed_output_sequence_record(
    record: Mapping[str, Any],
    record_index: int,
) -> None:
    _require_non_negative_int_field(record, "seq_id", record_index)
    _require_non_negative_int_field(record, "repeat_count", record_index)
    _require_optional_non_negative_int_field(record, "start_position_count", record_index)
    _require_optional_non_negative_int_field(record, "frame_id_base", record_index)
    _require_optional_non_negative_int_field(record, "pattern_id", record_index)

    mode = record.get("mode", "diagnostic_immediate")
    if mode != "diagnostic_immediate":
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: mode must be diagnostic_immediate in V1"
        )
    start_condition = record.get("start_condition", "immediate")
    if start_condition != "immediate":
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: start_condition must be immediate in V1"
        )
    if "diagnostic_only" in record:
        _require_bool("diagnostic_only", record["diagnostic_only"], record_index=record_index)
    if record.get("diagnostic_only", True) is not True:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: scanner_sync_run_timed_output_sequence is diagnostic-only"
        )

    _validate_output_state(
        "safe_output",
        record.get("safe_output_mask", TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK),
        record.get("safe_output_values", 0),
        record_index,
    )
    _validate_output_state(
        "idle_output",
        record.get("idle_output_mask", TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK),
        record.get("idle_output_values", 0),
        record_index,
    )
    _validate_timed_output_sequence_steps(record.get("steps"), record_index)


def _require_optional_non_negative_int_field(
    record: Mapping[str, Any],
    key: str,
    record_index: int,
) -> None:
    if key not in record or record[key] is None:
        return
    value = _require_int_field(record, key, record_index)
    if value < 0:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {key} must be non-negative"
        )


def _validate_timed_output_sequence_steps(value: Any, record_index: int) -> None:
    if not isinstance(value, (list, tuple)):
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: steps must be a non-empty list"
        )
    if not value:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: scanner_sync_run_timed_output_sequence requires steps"
        )
    if len(value) > TIMED_OUTPUT_SEQUENCE_MAX_STEPS:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: scanner_sync_run_timed_output_sequence has too many steps"
        )
    for step_index, step in enumerate(value):
        if not isinstance(step, Mapping):
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: steps[{step_index}] must be an object"
            )
        path = f"steps[{step_index}]"
        _validate_output_state(
            f"{path}.output",
            _require_timed_output_step_int_field(step, "output_mask", record_index, path),
            _require_timed_output_step_int_field(step, "output_values", record_index, path),
            record_index,
        )
        delay_us = _require_timed_output_step_int_field(
            step,
            "delay_us",
            record_index,
            path,
        )
        if delay_us <= 0:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {path}.delay_us must be positive"
            )
        if delay_us > TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {path}.delay_us must be <= "
                f"{TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US}"
            )
        event_flags = step.get("event_flags", 0)
        _require_int(f"{path}.event_flags", event_flags, record_index=record_index)
        if event_flags < 0:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {path}.event_flags must be non-negative"
            )
        if event_flags & ~TIMED_OUTPUT_SEQUENCE_KNOWN_FLAGS:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: {path}.event_flags contains unknown "
                "timed-output-sequence flags"
            )


def _require_timed_output_step_int_field(
    step: Mapping[str, Any],
    key: str,
    record_index: int,
    path: str,
) -> int:
    if key not in step:
        raise ScannerSyncCommandBoundaryError(f"record {record_index}: missing {path}.{key}")
    value = step[key]
    _require_int(f"{path}.{key}", value, record_index=record_index)
    return value


def _validate_output_state(
    name: str,
    output_mask: Any,
    output_values: Any,
    record_index: int,
) -> None:
    _require_int(f"{name}_mask", output_mask, record_index=record_index)
    _require_int(f"{name}_values", output_values, record_index=record_index)
    if output_mask < 0 or output_mask > TIMED_OUTPUT_SEQUENCE_MAX_MASK:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {name}_mask must fit in one byte"
        )
    if output_values < 0 or output_values > TIMED_OUTPUT_SEQUENCE_MAX_MASK:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {name}_values must fit in one byte"
        )
    if output_mask & ~TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {name}_mask contains unknown timed-output-sequence outputs"
        )
    if output_values & ~output_mask:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {name}_values must not set bits outside {name}_mask"
        )


def _validate_hardware_outputs(
    record: Mapping[str, Any],
    record_index: int,
    context: ScannerSyncCommandBoundaryContext,
) -> None:
    _validate_hardware_output_policy(
        record,
        record_index,
        dry_run=context.dry_run,
        replay=context.replay,
        allow_hardware_outputs=context.allow_hardware_outputs,
    )
