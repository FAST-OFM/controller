"""Software-only firmware telemetry report producers.

These producers convert already-captured simulator/readiness records into
canonical telemetry envelopes. They do not open devices, flash firmware, access
serial ports, toggle GPIO, move motors or drive LEDs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Iterable, Literal, Mapping

from scanner_core.telemetry import (
    FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID,
    FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_VERSION,
    TELEMETRY_SEVERITIES,
    validate_telemetry_event_name,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (
    build_scanner_sync_capture_report,
)
from scanner_firmware.foundation.protocol.events import (
    ProtocolRecord,
    ProtocolSerializationError,
    scheduler_event_to_protocol_record,
    to_canonical_v1_json_dict,
    to_json_dict,
)
from scanner_firmware.planning.readiness.result import PlatformReadinessResult


EVENT_SCHEMA_ID = FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID
REPORT_SCHEMA_ID = FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID
SCHEMA_VERSION = TELEMETRY_EVENT_SCHEMA_VERSION

Severity = Literal["debug", "info", "warning", "error", "critical"]


@dataclass(frozen=True)
class TelemetryEvent:
    event_name: str
    source_component: str
    severity: Severity
    payload: Mapping[str, Any]
    run_id: str | None = None
    scan_id: str | None = None
    frame_id: int | None = None
    stripe_id: int | None = None
    stripe_frame_index: int | None = None
    command_id: str | None = None
    mcu_time_us: int | None = None
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False
    schema_id: str = EVENT_SCHEMA_ID
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_id != EVENT_SCHEMA_ID:
            raise ValueError(f"schema_id must be {EVENT_SCHEMA_ID}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        validate_telemetry_event_name(self.event_name)
        _require_severity(self.severity)
        _require_non_empty("source_component", self.source_component)
        if self.hardware_outputs_enabled is not False:
            raise ValueError("hardware_outputs_enabled must be false")
        if self.live_hardware_access_used is not False:
            raise ValueError("live_hardware_access_used must be false")
        _json_safe(dict(self.payload))

    def to_json_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "event_name": self.event_name,
            "source_component": self.source_component,
            "severity": self.severity,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "payload": _json_safe(dict(self.payload)),
        }
        for key in (
            "run_id",
            "scan_id",
            "frame_id",
            "stripe_id",
            "stripe_frame_index",
            "command_id",
            "mcu_time_us",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class TelemetryReport:
    report_id: str
    generated_at: str
    source_component: str
    events: tuple[TelemetryEvent, ...]
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False
    schema_id: str = REPORT_SCHEMA_ID
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_id != REPORT_SCHEMA_ID:
            raise ValueError(f"schema_id must be {REPORT_SCHEMA_ID}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        _require_non_empty("report_id", self.report_id)
        _require_non_empty("generated_at", self.generated_at)
        _require_non_empty("source_component", self.source_component)
        if self.hardware_outputs_enabled is not False:
            raise ValueError("hardware_outputs_enabled must be false")
        if self.live_hardware_access_used is not False:
            raise ValueError("live_hardware_access_used must be false")
        if not self.events:
            raise ValueError("events must not be empty")

    def to_json_dict(self) -> dict[str, Any]:
        event_names = tuple(event.event_name for event in self.events)
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "source_component": self.source_component,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "event_count": len(self.events),
            "event_names": list(event_names),
            "events": [event.to_json_dict() for event in self.events],
        }

    def to_json(self, **json_kwargs: Any) -> str:
        return json.dumps(self.to_json_dict(), **json_kwargs)


def build_controller_decode_telemetry_report(
    records: Iterable[ProtocolRecord],
    *,
    report_id: str,
    generated_at: str,
    run_id: str | None = None,
    source_component: str = "scanner-firmware.telemetry.report.controller_decode",
) -> TelemetryReport:
    """Build a telemetry report for a decoded controller event capture."""

    decoded_records = tuple(records)
    _require_software_only_protocol_records(decoded_records)
    capture_report = build_scanner_sync_capture_report(decoded_records)
    scan_ids = sorted(
        {
            str(getattr(record, "scan_id"))
            for record in decoded_records
            if getattr(record, "scan_id", None) is not None
        }
    )
    event = TelemetryEvent(
        event_name="controller_event_decoded",
        source_component=source_component,
        severity="info",
        run_id=run_id,
        scan_id=scan_ids[0] if len(scan_ids) == 1 else None,
        payload={
            "report_kind": "controller_decode_summary",
            "capture": capture_report.to_json_dict(),
            "scan_ids": scan_ids,
        },
    )
    return TelemetryReport(
        report_id=report_id,
        generated_at=generated_at,
        source_component=source_component,
        events=(event,),
    )


def build_readiness_check_telemetry_report(
    readiness: PlatformReadinessResult,
    *,
    report_id: str,
    generated_at: str,
    run_id: str | None = None,
    source_component: str = "scanner-firmware.telemetry.report.readiness",
) -> TelemetryReport:
    """Build one telemetry event per platform readiness check."""

    readiness_payload = readiness.to_json_dict()
    _require_false(readiness_payload, "hardware_outputs_enabled")
    events = tuple(
        TelemetryEvent(
            event_name="readiness_check_result",
            source_component=source_component,
            severity=_severity_for_check(check["status"]),
            run_id=run_id,
            payload={
                "report_kind": "readiness_check_result",
                "target": readiness_payload["target"],
                "readiness_state": readiness_payload["readiness_state"],
                "check": check,
                "blocker_count": len(readiness_payload["blockers"]),
                "unknown_count": len(readiness_payload["unknowns"]),
            },
        )
        for check in readiness_payload["checks"]
    )
    return TelemetryReport(
        report_id=report_id,
        generated_at=generated_at,
        source_component=source_component,
        events=events,
    )


def build_dry_run_scheduler_telemetry_report(
    outcomes: Iterable[Any],
    *,
    report_id: str,
    generated_at: str,
    run_id: str | None = None,
    source_component: str = "scanner-firmware.telemetry.report.dry_run_scheduler",
) -> TelemetryReport:
    """Build telemetry for dry-run frame, terminal and predictive-Z outcomes."""

    events: list[TelemetryEvent] = []
    for outcome in outcomes:
        events.extend(
            _events_for_scheduler_outcome(
                outcome,
                source_component=source_component,
                run_id=run_id,
            )
        )
    return TelemetryReport(
        report_id=report_id,
        generated_at=generated_at,
        source_component=source_component,
        events=tuple(events),
    )


def _events_for_scheduler_outcome(
    outcome: Any,
    *,
    source_component: str,
    run_id: str | None,
) -> tuple[TelemetryEvent, ...]:
    z_outcome = getattr(outcome, "outcome", None)
    if z_outcome in ("accepted", "rejected", "applied"):
        return _events_for_z_scheduler_outcome(
            outcome,
            source_component=source_component,
            run_id=run_id,
        )

    event_type = getattr(outcome, "type", None)
    if event_type in ("FRAME_EVENT", "SCHEDULER_TERMINAL", "Z_SCHEDULED", "Z_REJECTED", "Z_APPLIED"):
        record = (
            outcome
            if _is_protocol_record(outcome)
            else scheduler_event_to_protocol_record(outcome)
        )
        _require_software_only_protocol_records((record,))
        payload = to_canonical_v1_json_dict(record)
        event_names = _event_names_for_protocol_type(str(payload["type"]))
        return tuple(
            TelemetryEvent(
                event_name=event_name,
                source_component=source_component,
                severity=_severity_for_protocol_payload(payload, event_name=event_name),
                run_id=run_id,
                scan_id=_optional_str(payload.get("scan_id")),
                frame_id=_optional_int(payload.get("frame_id")),
                stripe_id=_optional_int(payload.get("stripe_id")),
                stripe_frame_index=_optional_int(payload.get("stripe_frame_index")),
                command_id=_optional_str(payload.get("command_id")),
                mcu_time_us=_optional_int(payload.get("mcu_time_us")),
                payload={
                    "report_kind": "dry_run_scheduler_outcome",
                    "protocol_record": payload,
                },
            )
            for event_name in event_names
        )

    raise TypeError(f"unsupported dry-run scheduler outcome: {type(outcome).__name__}")


def _events_for_z_scheduler_outcome(
    outcome: Any,
    *,
    source_component: str,
    run_id: str | None,
) -> tuple[TelemetryEvent, ...]:
    if getattr(outcome, "hardware_outputs_enabled", None) is not False:
        raise ValueError("hardware_outputs_enabled must be false")
    payload = _json_safe(asdict(outcome) if is_dataclass(outcome) else dict(outcome))
    command_id = _optional_str(payload.get("command_id"))
    common = {
        "source_component": source_component,
        "run_id": run_id,
        "scan_id": _optional_str(payload.get("scan_id")),
        "stripe_id": _optional_int(payload.get("stripe_id")),
        "command_id": command_id,
        "payload": {
            "report_kind": "dry_run_z_scheduler_outcome",
            "outcome": payload,
        },
    }
    if payload["outcome"] == "accepted":
        return (
            TelemetryEvent(
                event_name="z_command_enqueued",
                severity="debug",
                **common,
            ),
            TelemetryEvent(
                event_name="z_command_accepted",
                severity="info",
                **common,
            ),
        )
    if payload["outcome"] == "rejected":
        return (
            TelemetryEvent(
                event_name="z_command_rejected",
                severity="warning",
                **common,
            ),
        )
    return (
        TelemetryEvent(
            event_name="z_command_applied",
            severity="info",
            frame_id=_optional_int(payload.get("applied_frame_id")),
            **common,
        ),
    )


def _event_names_for_protocol_type(protocol_type: str) -> tuple[str, ...]:
    if protocol_type == "FRAME_EVENT":
        return ("frame_event_received",)
    if protocol_type == "SCHEDULER_TERMINAL":
        return ("z_scheduler_terminal",)
    if protocol_type == "Z_SCHEDULED":
        return ("z_command_enqueued", "z_command_accepted")
    if protocol_type == "Z_REJECTED":
        return ("z_command_rejected",)
    if protocol_type == "Z_APPLIED":
        return ("z_command_applied",)
    raise ProtocolSerializationError(f"unsupported protocol record type: {protocol_type}")


def _severity_for_protocol_payload(
    payload: Mapping[str, Any],
    *,
    event_name: str,
) -> Severity:
    if event_name == "z_command_enqueued":
        return "debug"
    if event_name == "z_command_rejected":
        return "warning"
    if payload.get("type") == "SCHEDULER_TERMINAL" and payload.get("status") == "fault":
        return "error"
    return "info"


def _severity_for_check(status: str) -> Severity:
    if status == "pass":
        return "info"
    if status == "skipped":
        return "debug"
    if status == "blocked":
        return "warning"
    return "error"


def _is_protocol_record(value: Any) -> bool:
    return value.__class__.__name__ in {
        "FrameEventRecord",
        "SchedulerTerminalRecord",
        "ZScheduledRecord",
        "ZAppliedRecord",
        "ZRejectedRecord",
    }


def _require_software_only_protocol_records(records: tuple[Any, ...]) -> None:
    if not records:
        raise ValueError("records must not be empty")
    for record in records:
        payload = to_json_dict(record)
        _require_false(payload, "hardware_outputs_enabled")


def _require_false(payload: Mapping[str, Any], key: str) -> None:
    if payload.get(key) is not False:
        raise ValueError(f"{key} must be false")


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"{type(value).__name__} is not JSON-safe for telemetry")


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _require_severity(value: str) -> None:
    if value not in TELEMETRY_SEVERITIES:
        raise ValueError(f"severity is not canonical: {value}")


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
