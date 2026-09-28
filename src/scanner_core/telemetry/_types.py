"""Telemetry envelope public model types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ._fields import DIAGNOSTIC_FIELDS, IDENTITY_FIELDS
from ._records import _validate_telemetry_record


class TelemetryEnvelopeError(ValueError):
    """Raised when telemetry violates the software-only envelope contract."""


@dataclass(frozen=True)
class TelemetryEnvelope:
    """Validated structured telemetry event envelope."""

    schema_id: str
    schema_version: str
    event_name: str
    source_component: str
    severity: str
    hardware_outputs_enabled: bool
    live_hardware_access_used: bool
    payload: Mapping[str, Any]
    run_id: str | None = None
    scan_id: str | None = None
    frame_id: int | None = None
    stripe_id: int | None = None
    stripe_frame_index: int | None = None
    command_id: str | None = None
    calibration_id: str | None = None
    host_monotonic_ns: int | None = None
    host_wall_time_iso8601: str | None = None
    mcu_time_us: int | None = None
    camera_sensor_timestamp_ns: int | None = None
    camera_sequence: int | None = None

    def __post_init__(self) -> None:
        errors, _, _ = _validate_telemetry_record(self.as_dict(), "$source[0]")
        if errors:
            raise TelemetryEnvelopeError("; ".join(errors))

    def as_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "event_name": self.event_name,
            "source_component": self.source_component,
            "severity": self.severity,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "payload": dict(self.payload),
        }
        for field in sorted(IDENTITY_FIELDS | DIAGNOSTIC_FIELDS):
            value = getattr(self, field)
            if value is not None:
                record[field] = value
        return record
