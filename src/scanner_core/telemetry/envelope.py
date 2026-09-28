"""Shared software-only telemetry envelope contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ._fields import (
    DIAGNOSTIC_FIELDS as DIAGNOSTIC_FIELDS,
    IDENTITY_FIELDS as IDENTITY_FIELDS,
    REQUIRED_ENVELOPE_FIELDS as REQUIRED_ENVELOPE_FIELDS,
    TELEMETRY_REPLAY_SUMMARY_KEYS as TELEMETRY_REPLAY_SUMMARY_KEYS,
    TELEMETRY_SEVERITIES as TELEMETRY_SEVERITIES,
)
from ._firmware_reports import _project_firmware_telemetry_report_events
from ._records import (
    TelemetryEnvelopeValidation,
    TelemetryReplaySummary,
    _empty_summary,
    _validate_telemetry_record,
    validate_telemetry_records,
)
from ._types import TelemetryEnvelope, TelemetryEnvelopeError
from ._validation import _copy_jsonable
from .names import (
    CANONICAL_TELEMETRY_EVENT_NAMES as CANONICAL_TELEMETRY_EVENT_NAMES,
    FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID as FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID,
    FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID as FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID,
    OBSERVABILITY_CONTRACT_EVENT_NAMES as OBSERVABILITY_CONTRACT_EVENT_NAMES,
    OBSERVABILITY_TELEMETRY_CONTRACT_ID as OBSERVABILITY_TELEMETRY_CONTRACT_ID,
    TELEMETRY_EVENT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_VERSION,
    _validate_telemetry_event_name,
)


TelemetryEnvelope.__module__ = __name__
TelemetryEnvelopeError.__module__ = __name__


def make_telemetry_envelope(
    event_name: str,
    *,
    source_component: str,
    severity: str = "info",
    payload: Mapping[str, Any] | None = None,
    schema_id: str = TELEMETRY_EVENT_SCHEMA_ID,
    schema_version: str = TELEMETRY_EVENT_SCHEMA_VERSION,
    hardware_outputs_enabled: bool = False,
    live_hardware_access_used: bool = False,
    **metadata: Any,
) -> TelemetryEnvelope:
    """Create a validated telemetry envelope with software-only defaults."""

    fields = {
        "schema_id": schema_id,
        "schema_version": schema_version,
        "event_name": event_name,
        "source_component": source_component,
        "severity": severity,
        "hardware_outputs_enabled": hardware_outputs_enabled,
        "live_hardware_access_used": live_hardware_access_used,
        "payload": {} if payload is None else payload,
        **metadata,
    }
    return telemetry_envelope_from_mapping(fields)


def telemetry_envelope_from_mapping(record: Mapping[str, Any]) -> TelemetryEnvelope:
    """Return a validated envelope model from a mapping."""

    normalized = normalize_telemetry_envelope(record)
    return TelemetryEnvelope(**normalized)


def validate_telemetry_envelope(
    record: Mapping[str, Any],
    *,
    path: str = "$source[0]",
) -> TelemetryEnvelopeValidation:
    """Validate one telemetry envelope without raising."""

    errors, normalized, counts = _validate_telemetry_record(record, path)
    return TelemetryEnvelopeValidation(tuple(errors), normalized, counts)


def validate_telemetry_event_name(
    event_name: object,
    *,
    observability_only: bool = True,
) -> str:
    """Return a canonical telemetry event name, otherwise raise."""

    try:
        return _validate_telemetry_event_name(
            event_name,
            observability_only=observability_only,
        )
    except ValueError as exc:
        raise TelemetryEnvelopeError(str(exc)) from None


def normalize_telemetry_envelope(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic normalized form of one valid telemetry envelope."""

    validation = validate_telemetry_envelope(record)
    if validation.errors:
        raise TelemetryEnvelopeError("; ".join(validation.errors))
    return _copy_jsonable(validation.normalized)


def project_firmware_telemetry_report_events(report: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Project one firmware telemetry report to shared event-envelope values.

    The projection is intentionally value-only: it accepts already-saved report
    dictionaries and never imports or executes scanner-firmware runtime code.
    """

    errors, records = _project_firmware_telemetry_report_events(report, "$reports[0]")
    if errors:
        raise TelemetryEnvelopeError("; ".join(errors))
    replay = validate_telemetry_records(records)
    if replay.errors:
        raise TelemetryEnvelopeError("; ".join(replay.errors))
    return replay.records


def validate_firmware_telemetry_reports(
    reports: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> TelemetryReplaySummary:
    """Validate saved firmware telemetry reports through the shared envelope contract."""

    errors: list[str] = []
    projected_records: list[dict[str, Any]] = []
    if not reports:
        errors.append("$reports: firmware telemetry report fixture is empty")

    for index, report in enumerate(reports):
        report_errors, records = _project_firmware_telemetry_report_events(report, f"$reports[{index}]")
        errors.extend(report_errors)
        if report_errors:
            continue
        projected_records.extend(records)

    if not projected_records:
        return TelemetryReplaySummary(
            errors=tuple(errors),
            event_names=(),
            event_counts={},
            run_ids=(),
            scan_ids=(),
            frame_ids=(),
            summary=_empty_summary(),
            records=(),
        )

    replay = validate_telemetry_records(tuple(projected_records))
    return TelemetryReplaySummary(
        errors=tuple([*errors, *replay.errors]),
        event_names=replay.event_names,
        event_counts=replay.event_counts,
        run_ids=replay.run_ids,
        scan_ids=replay.scan_ids,
        frame_ids=replay.frame_ids,
        summary=replay.summary,
        records=replay.records,
    )


def telemetry_canonical_sha256(value: Any) -> str:
    """Return the deterministic canonical JSON SHA-256 for telemetry parity fixtures."""

    encoded = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
