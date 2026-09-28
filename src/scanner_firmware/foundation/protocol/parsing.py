"""Parsing helpers for serialized protocol JSONL evidence."""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any, Iterable

from scanner_firmware.foundation.protocol.events import (
    FrameEventRecord,
    ProtocolRecord,
    ProtocolSerializationError,
    SchedulerTerminalRecord,
    TimedOutputSequenceStatusRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
    require_canonical_protocol_v1_payload,
)


PROTOCOL_RECORD_TYPES: dict[str, type[ProtocolRecord]] = {
    "FRAME_EVENT": FrameEventRecord,
    "SCHEDULER_TERMINAL": SchedulerTerminalRecord,
    "Z_SCHEDULED": ZScheduledRecord,
    "Z_APPLIED": ZAppliedRecord,
    "Z_REJECTED": ZRejectedRecord,
    "TIMED_OUTPUT_SEQUENCE_STATUS": TimedOutputSequenceStatusRecord,
}


def decode_protocol_json_lines(lines: Iterable[str]) -> list[ProtocolRecord]:
    """Decode newline-delimited protocol records into typed DTOs."""

    records: list[ProtocolRecord] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ProtocolSerializationError(
                f"line {line_number}: invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ProtocolSerializationError(
                f"line {line_number}: expected JSON object"
            )
        try:
            records.append(decode_protocol_record(payload))
        except (TypeError, ValueError) as exc:
            raise ProtocolSerializationError(f"line {line_number}: {exc}") from exc
    return records


def decode_protocol_record(payload: dict[str, Any]) -> ProtocolRecord:
    """Decode one serialized protocol record into its dataclass model."""

    require_canonical_protocol_v1_payload(payload)
    record_type = payload.get("type")
    if record_type not in PROTOCOL_RECORD_TYPES:
        raise ProtocolSerializationError(
            f"unsupported protocol record type: {record_type!r}"
        )
    record_class = PROTOCOL_RECORD_TYPES[record_type]
    init_field_names = {field.name for field in fields(record_class) if field.init}
    return record_class(
        **{key: value for key, value in payload.items() if key in init_field_names}
    )
