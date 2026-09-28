"""Decoding helpers for MCU-to-host scanner-sync events."""

from __future__ import annotations

from typing import Any

from scanner_firmware.adapters.klipper_adapter.sync_codec.tables import (
    AXIS_CODES,
    FRAME_STATUS_CODES,
    STATUS_CODES,
    TARGET_KIND_CODES,
    TERMINAL_REASON_CODES,
    TIMED_OUTPUT_SEQUENCE_REASON_CODES,
    TIMED_OUTPUT_SEQUENCE_STATUS_CODES,
    Z_APPLIED_STATUS_CODES,
    Z_REJECT_REASON_CODES,
    Z_REJECTED_STATUS_CODES,
    Z_SCHEDULED_STATUS_CODES,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (
    ScannerSyncCodecError,
    ScannerSyncDecodeContext,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    ProtocolEventType,
)
from scanner_firmware.foundation.protocol.events import (
    FrameEventRecord,
    ProtocolRecord,
    SchedulerTerminalRecord,
    TIMED_OUTPUT_SEQUENCE_KNOWN_FLAGS,
    TimedOutputSequenceStatusRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
    timed_output_sequence_event_flag_names,
)


def decode_scanner_sync_response(
    event_type: ProtocolEventType,
    params: dict[str, Any],
    *,
    context: ScannerSyncDecodeContext,
) -> ProtocolRecord:
    """Decode local scanner-sync response params into project protocol records."""

    if event_type == "FRAME_EVENT":
        return _decode_frame_event(params, context)
    if event_type == "SCHEDULER_TERMINAL":
        return _decode_scheduler_terminal(params, context)
    if event_type == "Z_SCHEDULED":
        return ZScheduledRecord(
            seq=_required_int(params, "seq"),
            scan_id=context.scan_id,
            stripe_id=_optional_int(params, "stripe_id"),
            command_id=_optional_str(params, "command_id"),
            hardware_outputs_enabled=False,
            status=_decode_z_scheduled_status(params.get("status")),  # type: ignore[arg-type]
        )
    if event_type == "Z_APPLIED":
        return ZAppliedRecord(
            seq=_required_int(params, "seq"),
            scan_id=context.scan_id,
            stripe_id=_optional_int(params, "stripe_id"),
            command_id=_optional_str(params, "command_id"),
            apply_target_kind=_decode_optional_target_kind(
                params.get("apply_target_kind")
            ),  # type: ignore[arg-type]
            apply_at_frame_id=_optional_int(params, "apply_at_frame_id"),
            apply_at_position_count=_optional_int(params, "apply_at_position_count"),
            frame_id=_required_int(params, "frame_id"),
            position=_optional_int(params, "position"),
            z_target_steps=_required_int_alias(
                params,
                canonical_key="z_target_steps",
                legacy_key="z_cmd_count",
            ),
            hardware_outputs_enabled=False,
            status=_decode_z_applied_status(params.get("status")),  # type: ignore[arg-type]
        )
    if event_type == "Z_REJECTED":
        return ZRejectedRecord(
            seq=_required_int(params, "seq"),
            scan_id=context.scan_id,
            stripe_id=_optional_int(params, "stripe_id"),
            command_id=_optional_str(params, "command_id"),
            reason=_decode_z_reject_reason(params.get("reason")),
            hardware_outputs_enabled=False,
            status=_decode_z_rejected_status(params.get("status")),  # type: ignore[arg-type]
        )
    if event_type == "TIMED_OUTPUT_SEQUENCE_STATUS":
        return TimedOutputSequenceStatusRecord(
            protocol_version=context.protocol_version,
            scan_id=context.scan_id,
            seq=_required_int(params, "seq"),
            stripe_id=_optional_int(params, "stripe_id"),
            seq_id=_required_int(params, "seq_id"),
            status=_decode_timed_output_sequence_status(params.get("status")),  # type: ignore[arg-type]
            reason=_decode_timed_output_sequence_reason(params.get("reason")),
            repeat_index=_optional_int(params, "repeat_index"),
            step_index=_optional_int(params, "step_index"),
            mcu_time_us=_optional_int(params, "mcu_time_us"),
            hardware_outputs_enabled=False,
        )
    raise ScannerSyncCodecError(f"unsupported scanner-sync event type: {event_type}")


def _decode_frame_event(
    params: dict[str, Any],
    context: ScannerSyncDecodeContext,
) -> FrameEventRecord:
    pattern_id = _required_int(params, "pattern_id")
    pattern = _pattern_name(context, pattern_id)
    axis = _decode_axis(params.get("position_axis"))
    event_position = _required_int(params, "event_position")
    x_count = _required_int(params, "x_count")
    y_count = _required_int(params, "y_count")
    z_count = _required_int(params, "z_count")
    sample_position, position_overshoot_count = _decode_sample_position(
        params,
        event_position=event_position,
    )
    event_flags = _required_int(params, "flags")
    if event_flags & ~TIMED_OUTPUT_SEQUENCE_KNOWN_FLAGS:
        raise ScannerSyncCodecError(
            f"unsupported frame event flags: 0x{event_flags:04x}"
        )

    return FrameEventRecord(
        protocol_version=context.protocol_version,
        scan_id=context.scan_id,
        stripe_id=_required_int(params, "stripe_id"),
        frame_id=_required_int(params, "frame_id"),
        stripe_frame_index=_required_int(params, "stripe_frame_index"),
        pattern=pattern,
        coordinate_source_used=context.coordinate_source_used,  # type: ignore[arg-type]
        position_axis=axis,  # type: ignore[arg-type]
        event_position=event_position,
        sample_position=sample_position,
        position_overshoot_count=position_overshoot_count,
        x_count=x_count,
        y_count=y_count,
        z_count=z_count,
        x_step_commanded=_optional_int_default(params, "x_step_commanded", x_count),
        y_step_commanded=_optional_int_default(params, "y_step_commanded", y_count),
        z_step_commanded=_optional_int_default(params, "z_step_commanded", z_count),
        x_encoder_count=_optional_int(params, "x_encoder_count"),
        y_encoder_count=_optional_int(params, "y_encoder_count"),
        coordinate_flags=_optional_str_tuple(params, "coordinate_flags"),
        mcu_time_us=_required_int(params, "mcu_time_us"),
        led_gate_names=_led_gate_names(context, pattern_id),
        trigger_output_name=context.trigger_output_name,
        event_flags=event_flags,
        event_flag_names=timed_output_sequence_event_flag_names(event_flags),
        hardware_outputs_enabled=False,
        status=_decode_frame_status(params.get("status")),  # type: ignore[arg-type]
    )


def _decode_scheduler_terminal(
    params: dict[str, Any],
    context: ScannerSyncDecodeContext,
) -> SchedulerTerminalRecord:
    return SchedulerTerminalRecord(
        protocol_version=context.protocol_version,
        scan_id=context.scan_id,
        stripe_id=_optional_int(params, "stripe_id") or 0,
        status=_decode_status(params.get("status"), expected=("stopped", "fault")),  # type: ignore[arg-type]
        reason_code=_decode_terminal_reason(params.get("reason")),  # type: ignore[arg-type]
        emitted_frame_count=_required_int(params, "emitted_frame_count"),
        expected_frame_count=_required_int(params, "expected_frame_count"),
        last_frame_id=_optional_nonnegative_int(params, "last_frame_id"),
        next_frame_id=_required_int(params, "next_frame_id"),
        next_stripe_frame_index=_optional_int(params, "next_stripe_frame_index") or 0,
        mcu_time_us=_required_int(params, "mcu_time_us"),
        message=str(params.get("message", "")),
        hardware_outputs_enabled=False,
    )


def _required_int(params: dict[str, Any], key: str) -> int:
    if key not in params:
        raise ScannerSyncCodecError(f"missing required scanner-sync field: {key}")
    try:
        return int(params[key])
    except (TypeError, ValueError) as exc:
        raise ScannerSyncCodecError(f"scanner-sync field must be int: {key}") from exc


def _required_int_alias(
    params: dict[str, Any],
    *,
    canonical_key: str,
    legacy_key: str,
) -> int:
    if canonical_key in params:
        return _required_int(params, canonical_key)
    return _required_int(params, legacy_key)


def _optional_int(params: dict[str, Any], key: str) -> int | None:
    if key not in params or params[key] is None:
        return None
    return _required_int(params, key)


def _optional_int_default(params: dict[str, Any], key: str, default: int) -> int:
    value = _optional_int(params, key)
    if value is None:
        return default
    return value


def _decode_sample_position(
    params: dict[str, Any],
    *,
    event_position: int,
) -> tuple[int, int]:
    sample_position = _optional_int(params, "sample_position")
    position_overshoot_count = _optional_int(params, "position_overshoot_count")
    if sample_position is None and position_overshoot_count is None:
        return event_position, 0
    if sample_position is None:
        assert position_overshoot_count is not None
        return event_position + position_overshoot_count, position_overshoot_count
    if position_overshoot_count is None:
        return sample_position, sample_position - event_position
    if sample_position - event_position != position_overshoot_count:
        raise ScannerSyncCodecError(
            "sample_position and position_overshoot_count disagree"
        )
    return sample_position, position_overshoot_count


def _optional_str_tuple(params: dict[str, Any], key: str) -> tuple[str, ...]:
    if key not in params or params[key] is None:
        return ()
    value = params[key]
    if isinstance(value, str):
        if value == "":
            return ()
        values = tuple(item.strip() for item in value.split(","))
    elif isinstance(value, (list, tuple)):
        values = tuple(value)
    else:
        raise ScannerSyncCodecError(f"scanner-sync field must be string tuple: {key}")
    if not all(isinstance(item, str) and item for item in values):
        raise ScannerSyncCodecError(f"scanner-sync field must be string tuple: {key}")
    return values


def _optional_nonnegative_int(params: dict[str, Any], key: str) -> int | None:
    value = _optional_int(params, key)
    if value is None or value < 0:
        return None
    return value


def _optional_str(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    return str(value)


def _decode_status(value: Any, *, expected: tuple[str, ...]) -> str:
    status = STATUS_CODES.get(value)
    if status not in expected:
        raise ScannerSyncCodecError(f"unsupported scanner-sync status: {value!r}")
    return status


def _decode_frame_status(value: Any) -> str:
    status = FRAME_STATUS_CODES.get(value)
    if status != "ok":
        raise ScannerSyncCodecError(f"unsupported frame event status: {value!r}")
    return status


def _decode_z_scheduled_status(value: Any) -> str:
    status = Z_SCHEDULED_STATUS_CODES.get(value)
    if status != "accepted":
        raise ScannerSyncCodecError(f"unsupported Z scheduled status: {value!r}")
    return status


def _decode_z_applied_status(value: Any) -> str:
    status = Z_APPLIED_STATUS_CODES.get(value)
    if status != "ok":
        raise ScannerSyncCodecError(f"unsupported Z applied status: {value!r}")
    return status


def _decode_z_rejected_status(value: Any) -> str:
    status = Z_REJECTED_STATUS_CODES.get(value)
    if status != "rejected":
        raise ScannerSyncCodecError(f"unsupported Z rejected status: {value!r}")
    return status


def _decode_timed_output_sequence_status(value: Any) -> str:
    status = TIMED_OUTPUT_SEQUENCE_STATUS_CODES.get(value)
    if status is None:
        raise ScannerSyncCodecError(
            f"unsupported timed output sequence status: {value!r}"
        )
    return status


def _decode_timed_output_sequence_reason(value: Any) -> str:
    reason = TIMED_OUTPUT_SEQUENCE_REASON_CODES.get(value)
    if reason is None:
        raise ScannerSyncCodecError(
            f"unsupported timed output sequence reason: {value!r}"
        )
    return reason


def _decode_terminal_reason(value: Any) -> str:
    reason = TERMINAL_REASON_CODES.get(value)
    if reason is None:
        raise ScannerSyncCodecError(f"unsupported scheduler terminal reason: {value!r}")
    return reason


def _decode_z_reject_reason(value: Any) -> str:
    if isinstance(value, str):
        return value
    reason = Z_REJECT_REASON_CODES.get(value)
    if reason is None:
        raise ScannerSyncCodecError(f"unsupported Z reject reason: {value!r}")
    return reason


def _decode_optional_target_kind(value: Any) -> str | None:
    if value is None:
        return None
    if value in ("frame", "position"):
        return value
    target_kind = TARGET_KIND_CODES.get(value)
    if target_kind not in ("frame", "position"):
        raise ScannerSyncCodecError(f"unsupported Z apply target kind: {value!r}")
    return target_kind


def _decode_axis(value: Any) -> str:
    axis = AXIS_CODES.get(value)
    if axis is None:
        raise ScannerSyncCodecError(f"unsupported frame event axis: {value!r}")
    return axis


def _pattern_name(context: ScannerSyncDecodeContext, pattern_id: int) -> str:
    if 0 <= pattern_id < len(context.pattern_names):
        return context.pattern_names[pattern_id]
    return f"pattern_{pattern_id}"


def _led_gate_names(
    context: ScannerSyncDecodeContext, pattern_id: int
) -> tuple[str, ...]:
    if 0 <= pattern_id < len(context.pattern_led_gate_names):
        return context.pattern_led_gate_names[pattern_id]
    return context.led_gate_names
