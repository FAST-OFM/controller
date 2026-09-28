"""Private firmware telemetry report projection helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ._fields import (
    DIAGNOSTIC_FIELDS,
    IDENTITY_FIELDS,
    NON_NEGATIVE_INT_FIELDS as _NON_NEGATIVE_INT_FIELDS,
    REQUIRED_ENVELOPE_FIELDS,
    REQUIRED_FIRMWARE_REPORT_FIELDS as _REQUIRED_FIRMWARE_REPORT_FIELDS,
    STRING_FIELDS as _STRING_FIELDS,
    TELEMETRY_SEVERITIES,
)
from ._validation import _non_negative_int, _require_literal, _string
from .names import (
    FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID,
    FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_VERSION,
    _validate_telemetry_event_name,
)


def _project_firmware_telemetry_report_events(
    report: Mapping[str, Any],
    path: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    if not isinstance(report, Mapping):
        return [f"{path}: expected object"], []

    missing = sorted(_REQUIRED_FIRMWARE_REPORT_FIELDS.difference(report))
    if missing:
        return [f"{path}: missing firmware telemetry report fields: {', '.join(missing)}"], []

    _require_literal(report, "schema_id", FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID, path, errors)
    _require_literal(report, "schema_version", TELEMETRY_EVENT_SCHEMA_VERSION, path, errors)
    _string(report.get("report_id"), f"{path}.report_id", errors)
    _string(report.get("generated_at"), f"{path}.generated_at", errors)
    _string(report.get("source_component"), f"{path}.source_component", errors)
    if report.get("hardware_outputs_enabled") is not False:
        errors.append(f"{path}.hardware_outputs_enabled: expected false")
    if report.get("live_hardware_access_used") is not False:
        errors.append(f"{path}.live_hardware_access_used: expected false")

    events_value = report.get("events")
    if not isinstance(events_value, list):
        errors.append(f"{path}.events: expected list")
        return errors, []
    if not events_value:
        errors.append(f"{path}.events: expected at least one event")

    event_count = report.get("event_count")
    if not isinstance(event_count, int) or isinstance(event_count, bool) or event_count < 0:
        errors.append(f"{path}.event_count: expected non-negative integer")
    elif event_count != len(events_value):
        errors.append(f"{path}.event_count: expected {len(events_value)}, got {event_count}")

    event_names = report.get("event_names")
    actual_event_names = [event.get("event_name") for event in events_value if isinstance(event, Mapping)]
    if not isinstance(event_names, list) or not all(isinstance(name, str) for name in event_names):
        errors.append(f"{path}.event_names: expected list of strings")
    elif event_names != actual_event_names:
        errors.append(f"{path}.event_names: expected {actual_event_names!r}, got {event_names!r}")

    if errors:
        return errors, []

    projected: list[dict[str, Any]] = []
    for index, event in enumerate(events_value):
        event_errors, projected_event = _project_firmware_telemetry_report_event(
            event,
            f"{path}.events[{index}]",
        )
        errors.extend(event_errors)
        if not event_errors:
            projected.append(projected_event)
    return errors, [] if errors else projected


def _project_firmware_telemetry_report_event(
    event: Any,
    path: str,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(event, Mapping):
        return [f"{path}: expected object"], {}

    missing = sorted(REQUIRED_ENVELOPE_FIELDS.difference(event))
    if missing:
        return [f"{path}: missing telemetry envelope fields: {', '.join(missing)}"], {}

    allowed_fields = REQUIRED_ENVELOPE_FIELDS | IDENTITY_FIELDS | DIAGNOSTIC_FIELDS
    unknown = sorted(set(event).difference(allowed_fields))
    if unknown:
        errors.append(f"{path}: unknown telemetry envelope fields: {', '.join(unknown)}")

    _require_literal(event, "schema_id", FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID, path, errors)
    _require_literal(event, "schema_version", TELEMETRY_EVENT_SCHEMA_VERSION, path, errors)
    event_name = _string(event.get("event_name"), f"{path}.event_name", errors)
    if event_name:
        try:
            _validate_telemetry_event_name(event_name)
        except ValueError as exc:
            errors.append(f"{path}.event_name: {exc}")
    severity = _string(event.get("severity"), f"{path}.severity", errors)
    if severity and severity not in TELEMETRY_SEVERITIES:
        errors.append(f"{path}.severity: invalid telemetry severity {severity!r}")
    _string(event.get("source_component"), f"{path}.source_component", errors)

    for field in _STRING_FIELDS - {"schema_id", "schema_version", "event_name", "severity"}:
        if field in event:
            _string(event.get(field), f"{path}.{field}", errors)
    for field in _NON_NEGATIVE_INT_FIELDS:
        if field in event:
            _non_negative_int(event.get(field), f"{path}.{field}", errors)

    if event.get("hardware_outputs_enabled") is not False:
        errors.append(f"{path}.hardware_outputs_enabled: expected false")
    if event.get("live_hardware_access_used") is not False:
        errors.append(f"{path}.live_hardware_access_used: expected false")

    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        errors.append(f"{path}.payload: expected object")
        report_kind = None
    else:
        report_kind = payload.get("report_kind")
        if not isinstance(report_kind, str) or not report_kind:
            errors.append(f"{path}.payload.report_kind: expected non-empty string")
        try:
            json.dumps(payload, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            errors.append(f"{path}.payload: must be JSON serializable: {exc}")

    if errors:
        return errors, {}

    projected: dict[str, Any] = {
        "schema_id": TELEMETRY_EVENT_SCHEMA_ID,
        "schema_version": TELEMETRY_EVENT_SCHEMA_VERSION,
        "event_name": event_name,
        "source_component": event["source_component"],
        "severity": severity,
        "hardware_outputs_enabled": False,
        "live_hardware_access_used": False,
        "payload": {"report_kind": report_kind},
    }
    for field in sorted(IDENTITY_FIELDS | DIAGNOSTIC_FIELDS):
        if field in event:
            projected[field] = event[field]
    return errors, projected
