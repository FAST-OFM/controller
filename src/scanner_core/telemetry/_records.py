"""Private telemetry envelope record validation and replay helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ._fields import (
    DIAGNOSTIC_FIELDS,
    IDENTITY_FIELDS,
    NON_NEGATIVE_INT_FIELDS as _NON_NEGATIVE_INT_FIELDS,
    REQUIRED_ENVELOPE_FIELDS,
    STRING_FIELDS as _STRING_FIELDS,
    TELEMETRY_REPLAY_SUMMARY_KEYS,
    TELEMETRY_SEVERITIES,
)
from ._payload_safety import _validate_payload
from ._validation import _copy_jsonable, _non_negative_int, _require_literal, _string
from .names import (
    TELEMETRY_EVENT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_VERSION,
    _validate_telemetry_event_name,
)


@dataclass(frozen=True)
class TelemetryEnvelopeValidation:
    """Validation result for one telemetry envelope."""

    errors: tuple[str, ...]
    normalized: Mapping[str, Any]
    summary: Mapping[str, int]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "normalized": _copy_jsonable(self.normalized),
            "summary": dict(self.summary),
        }


@dataclass(frozen=True)
class TelemetryReplaySummary:
    """Replay projection for saved telemetry JSONL records."""

    errors: tuple[str, ...]
    event_names: tuple[str, ...]
    event_counts: Mapping[str, int]
    run_ids: tuple[str, ...]
    scan_ids: tuple[str, ...]
    frame_ids: tuple[int, ...]
    summary: Mapping[str, int]
    records: tuple[Mapping[str, Any], ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "schema_id": TELEMETRY_EVENT_SCHEMA_ID,
            "schema_version": TELEMETRY_EVENT_SCHEMA_VERSION,
            "event_names": list(self.event_names),
            "event_counts": dict(self.event_counts),
            "run_ids": list(self.run_ids),
            "scan_ids": list(self.scan_ids),
            "frame_ids": list(self.frame_ids),
            "summary": dict(self.summary),
            "records": [_copy_jsonable(record) for record in self.records],
        }


def validate_telemetry_records(
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> TelemetryReplaySummary:
    """Validate and summarize saved software-only telemetry records by value."""

    errors: list[str] = []
    normalized_records: list[dict[str, Any]] = []
    event_names: list[str] = []
    run_ids: set[str] = set()
    scan_ids: set[str] = set()
    frame_ids: set[int] = set()
    summary = _empty_summary()
    summary["record_count"] = len(records)

    for index, record in enumerate(records):
        record_errors, normalized, counts = _validate_telemetry_record(record, f"$source[{index}]")
        errors.extend(record_errors)
        for key, value in counts.items():
            summary[key] += value
        if record_errors:
            summary["invalid_record_count"] += 1
            continue
        normalized_records.append(_copy_jsonable(normalized))
        event_names.append(normalized["event_name"])
        if isinstance(normalized.get("run_id"), str):
            run_ids.add(normalized["run_id"])
        if isinstance(normalized.get("scan_id"), str):
            scan_ids.add(normalized["scan_id"])
        if isinstance(normalized.get("frame_id"), int):
            frame_ids.add(normalized["frame_id"])

    if not records:
        errors.append("$source: telemetry fixture is empty")

    return TelemetryReplaySummary(
        errors=tuple(errors),
        event_names=tuple(event_names),
        event_counts={event_name: event_names.count(event_name) for event_name in sorted(set(event_names))},
        run_ids=tuple(sorted(run_ids)),
        scan_ids=tuple(sorted(scan_ids)),
        frame_ids=tuple(sorted(frame_ids)),
        summary=summary,
        records=tuple(normalized_records),
    )


def _validate_telemetry_record(
    record: Mapping[str, Any],
    path: str,
) -> tuple[list[str], dict[str, Any], dict[str, int]]:
    errors: list[str] = []
    counts = _empty_summary()

    if not isinstance(record, Mapping):
        errors.append(f"{path}: expected object")
        return errors, {}, counts

    missing = sorted(REQUIRED_ENVELOPE_FIELDS.difference(record))
    if missing:
        errors.append(f"{path}: missing telemetry envelope fields: {', '.join(missing)}")
        return errors, {}, counts

    allowed_fields = REQUIRED_ENVELOPE_FIELDS | IDENTITY_FIELDS | DIAGNOSTIC_FIELDS
    unknown = sorted(set(record).difference(allowed_fields))
    if unknown:
        errors.append(f"{path}: unknown telemetry envelope fields: {', '.join(unknown)}")

    _require_literal(record, "schema_id", TELEMETRY_EVENT_SCHEMA_ID, path, errors)
    _require_literal(record, "schema_version", TELEMETRY_EVENT_SCHEMA_VERSION, path, errors)

    event_name = _string(record.get("event_name"), f"{path}.event_name", errors)
    if event_name:
        try:
            _validate_telemetry_event_name(event_name)
        except ValueError as exc:
            counts["unknown_event_name_count"] = 1
            errors.append(f"{path}.event_name: {exc}")

    severity = _string(record.get("severity"), f"{path}.severity", errors)
    if severity and severity not in TELEMETRY_SEVERITIES:
        errors.append(f"{path}.severity: invalid telemetry severity {severity!r}")

    for field in _STRING_FIELDS:
        if field in record:
            _string(record.get(field), f"{path}.{field}", errors)
    for field in _NON_NEGATIVE_INT_FIELDS:
        if field in record:
            _non_negative_int(record.get(field), f"{path}.{field}", errors)

    if record.get("hardware_outputs_enabled") is not False:
        counts["hardware_output_enabled_count"] = 1
        errors.append(f"{path}.hardware_outputs_enabled: expected false")
    if record.get("live_hardware_access_used") is not False:
        counts["live_hardware_access_count"] = 1
        errors.append(f"{path}.live_hardware_access_used: expected false")

    event_payload = record.get("payload")
    if not isinstance(event_payload, Mapping):
        errors.append(f"{path}.payload: expected object")
        payload: dict[str, Any] = {}
    else:
        payload = dict(event_payload)
        payload_errors, unsafe_count, diagnostic_count = _validate_payload(payload, f"{path}.payload")
        errors.extend(payload_errors)
        counts["unsafe_payload_field_count"] = unsafe_count
        counts["diagnostic_identity_source_count"] = diagnostic_count
        try:
            json.dumps(payload, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            errors.append(f"{path}.payload: must be JSON serializable: {exc}")

    normalized: dict[str, Any] = {
        "schema_id": record.get("schema_id"),
        "schema_version": record.get("schema_version"),
        "event_name": event_name,
        "source_component": record.get("source_component"),
        "severity": severity,
        "hardware_outputs_enabled": False,
        "live_hardware_access_used": False,
        "payload": payload,
    }
    for field in sorted(IDENTITY_FIELDS | DIAGNOSTIC_FIELDS):
        if field in record:
            normalized[field] = record[field]
    return errors, normalized, counts


def _empty_summary() -> dict[str, int]:
    return {key: 0 for key in TELEMETRY_REPLAY_SUMMARY_KEYS}
