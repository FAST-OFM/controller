"""Synthetic scanner-sync callback payload conversion for dry-run fixtures."""

from __future__ import annotations

from typing import Any

from scanner_firmware.foundation.protocol.events import (
    FrameEventRecord,
    ProtocolRecord,
    SchedulerTerminalRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
)


def synthetic_callback_payload(
    record: ProtocolRecord,
    *,
    pattern_names: tuple[str, ...] = (),
) -> dict[str, object]:
    """Encode a protocol record as the current Phase 1 host callback wrapper."""

    if isinstance(record, FrameEventRecord):
        return {
            "event_type": "FRAME_EVENT",
            "params": {
                "frame_id": record.frame_id,
                "stripe_id": record.stripe_id,
                "stripe_frame_index": record.stripe_frame_index,
                "pattern_id": _pattern_id(record.pattern, pattern_names),
                "position_axis": _axis_id(record.position_axis),
                "event_position": record.event_position,
                "x_count": record.x_count,
                "y_count": record.y_count,
                "z_count": record.z_count,
                "mcu_time_us": record.mcu_time_us,
                "status": 0,
                "flags": 0,
            },
        }
    if isinstance(record, SchedulerTerminalRecord):
        return {
            "event_type": "SCHEDULER_TERMINAL",
            "params": {
                "stripe_id": record.stripe_id,
                "status": _terminal_status_id(record.status),
                "reason": _terminal_reason_id(record.reason_code),
                "emitted_frame_count": record.emitted_frame_count,
                "expected_frame_count": record.expected_frame_count,
                "last_frame_id": record.last_frame_id,
                "next_frame_id": record.next_frame_id,
                "next_stripe_frame_index": record.next_stripe_frame_index,
                "mcu_time_us": record.mcu_time_us,
            },
        }
    if isinstance(record, ZScheduledRecord):
        params: dict[str, object] = {
            "seq": record.seq,
            "stripe_id": record.stripe_id or 0,
            "status": 0,
        }
        if record.command_id is not None:
            params["command_id"] = record.command_id
        return {
            "event_type": "Z_SCHEDULED",
            "params": params,
        }
    if isinstance(record, ZAppliedRecord):
        params = {
            "seq": record.seq,
            "frame_id": record.frame_id,
            "z_target_steps": record.z_target_steps,
            "z_cmd_count": record.z_cmd_count,
            "status": 0,
        }
        if record.stripe_id is not None:
            params["stripe_id"] = record.stripe_id
        if record.command_id is not None:
            params["command_id"] = record.command_id
        if record.apply_target_kind is not None:
            params["apply_target_kind"] = _target_kind_id(record.apply_target_kind)
        if record.apply_at_frame_id is not None:
            params["apply_at_frame_id"] = record.apply_at_frame_id
        if record.apply_at_position_count is not None:
            params["apply_at_position_count"] = record.apply_at_position_count
        if record.position is not None:
            params["position"] = record.position
        return {
            "event_type": "Z_APPLIED",
            "params": params,
        }
    if isinstance(record, ZRejectedRecord):
        params = {
            "seq": record.seq,
            "reason": _z_reject_reason_id(record.reason),
            "status": 1,
        }
        if record.stripe_id is not None:
            params["stripe_id"] = record.stripe_id
        if record.command_id is not None:
            params["command_id"] = record.command_id
        return {
            "event_type": "Z_REJECTED",
            "params": params,
        }
    raise TypeError(f"unsupported protocol record type: {type(record).__name__}")


def pattern_names_from_recipe(scan_recipe: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for stripe in scan_recipe.get("stripes", ()):
        for pattern in stripe.get("pattern_sequence", ()):
            if pattern not in seen:
                seen.add(pattern)
                names.append(pattern)
    return tuple(names)


def _pattern_id(pattern: str, pattern_names: tuple[str, ...]) -> int:
    try:
        return pattern_names.index(pattern)
    except ValueError:
        if not pattern_names:
            return 0
        raise ValueError(f"pattern is not present in loaded recipe: {pattern!r}") from None


def _axis_id(axis: str) -> int:
    if axis == "X":
        return 0
    if axis == "Y":
        return 1
    raise ValueError(f"unsupported axis: {axis!r}")


def _terminal_status_id(status: str) -> int:
    if status == "stopped":
        return 0
    if status == "fault":
        return 1
    raise ValueError(f"unsupported terminal status: {status!r}")


def _terminal_reason_id(reason: str) -> int:
    reasons = {
        "host_stop": 0,
        "scheduler_fault": 1,
        "coordinate_source_error": 2,
        "position_stream_exhausted": 3,
    }
    if reason not in reasons:
        raise ValueError(f"unsupported terminal reason: {reason!r}")
    return reasons[reason]


def _target_kind_id(kind: str) -> int:
    kinds = {
        "frame": 0,
        "position": 1,
    }
    if kind not in kinds:
        raise ValueError(f"unsupported Z target kind: {kind!r}")
    return kinds[kind]


def _z_reject_reason_id(reason: str) -> int:
    reasons = {
        "invalid_target": 0,
        "scan_or_stripe_mismatch": 1,
        "target_already_passed": 2,
        "insufficient_lookahead": 3,
        "z_limit_exceeded": 4,
        "target_outside_stripe": 5,
        "no_correction_window": 6,
    }
    if reason not in reasons:
        raise ValueError(f"unsupported Z reject reason: {reason!r}")
    return reasons[reason]
