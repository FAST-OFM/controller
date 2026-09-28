"""Multi-stripe scanner-sync dry-run session runner.

This module executes already-loaded scanner-sync dry-run plans using injected
position samples. It does not import Klipper, open serial/network connections,
toggle GPIO, command motion, drive LEDs or trigger cameras.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from scanner_firmware.foundation.protocol.events import ProtocolRecord
from scanner_firmware.planning.scan_preflight.axes import REQUIRED_SCAN_AXES
from scanner_firmware.planning.scan_preflight.decisions import ScanPreflightInput
from scanner_firmware.planning.scanner_sync.interfaces import PositionSampleSource
from scanner_firmware.planning.scanner_sync.service import DryRunScannerSyncService


SessionStatus = Literal["completed", "stopped", "fault"]
StripeRunStatus = Literal["completed", "stopped", "fault"]


@dataclass(frozen=True)
class StripeRunControl:
    """Optional terminal injection for one dry-run stripe."""

    stop_after_events: int | None = None
    fault_after_events: int | None = None
    fault_message: str = "simulated scheduler fault"

    def __post_init__(self) -> None:
        if self.stop_after_events is not None and self.stop_after_events < 0:
            raise ScannerSyncSessionError("stop_after_events must be non-negative")
        if self.fault_after_events is not None and self.fault_after_events < 0:
            raise ScannerSyncSessionError("fault_after_events must be non-negative")
        if self.stop_after_events is not None and self.fault_after_events is not None:
            raise ScannerSyncSessionError(
                "stop_after_events and fault_after_events are mutually exclusive"
            )


@dataclass(frozen=True)
class StripeSessionSummary:
    stripe_index: int
    stripe_id: int
    status: StripeRunStatus
    frame_event_count: int
    first_frame_id: int | None
    last_frame_id: int | None
    terminal_reason_code: str | None = None
    terminal_message: str | None = None

    def to_json_dict(self) -> dict[str, object]:
        return {
            "stripe_index": self.stripe_index,
            "stripe_id": self.stripe_id,
            "status": self.status,
            "frame_event_count": self.frame_event_count,
            "first_frame_id": self.first_frame_id,
            "last_frame_id": self.last_frame_id,
            "terminal_reason_code": self.terminal_reason_code,
            "terminal_message": self.terminal_message,
        }


@dataclass(frozen=True)
class ScannerSyncSessionResult:
    scan_id: str
    stripe_count: int
    started_stripe_count: int
    status: SessionStatus
    records: tuple[ProtocolRecord, ...]
    stripes: tuple[StripeSessionSummary, ...]
    first_frame_id: int
    next_frame_id: int
    hardware_outputs_enabled: bool = False

    @property
    def frame_event_count(self) -> int:
        return sum(1 for record in self.records if record.type == "FRAME_EVENT")

    @property
    def terminal_record_count(self) -> int:
        return sum(1 for record in self.records if record.type == "SCHEDULER_TERMINAL")

    @property
    def json_lines(self) -> tuple[str, ...]:
        return tuple(
            record.to_json(separators=(",", ":"), sort_keys=True)
            for record in self.records
        )

    def to_summary_json_dict(self) -> dict[str, object]:
        return {
            "scan_id": self.scan_id,
            "stripe_count": self.stripe_count,
            "started_stripe_count": self.started_stripe_count,
            "status": self.status,
            "frame_event_count": self.frame_event_count,
            "terminal_record_count": self.terminal_record_count,
            "first_frame_id": self.first_frame_id,
            "next_frame_id": self.next_frame_id,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "stripes": [stripe.to_json_dict() for stripe in self.stripes],
        }


class ScannerSyncSessionError(ValueError):
    """Raised when a scanner-sync session plan is malformed."""


def run_scanner_sync_dry_run_session(
    scan_recipe: Mapping[str, object],
    source: PositionSampleSource,
    *,
    first_frame_id: int = 0,
    protocol_version: int = 1,
    controls: Mapping[int, StripeRunControl] | None = None,
    preflight: ScanPreflightInput | None = None,
) -> ScannerSyncSessionResult:
    """Execute all stripes from ``scan_recipe`` with injected position samples."""

    service = DryRunScannerSyncService(
        first_frame_id=first_frame_id,
        protocol_version=protocol_version,
    )
    loaded = service.load_scan_recipe(scan_recipe)
    decision = service.run_preflight(
        preflight
        if preflight is not None
        else ScanPreflightInput(
            required_axes=REQUIRED_SCAN_AXES,
            homed_axes=(),
            dry_run=True,
            hardware_outputs_enabled=False,
        )
    )
    if not decision.accepted:
        raise ScannerSyncSessionError("dry-run session preflight was not accepted")

    resolved_controls = dict(controls or {})
    _validate_control_indexes(resolved_controls, stripe_count=loaded.stripe_count)
    records: list[ProtocolRecord] = []
    stripe_summaries: list[StripeSessionSummary] = []
    status: SessionStatus = "completed"

    for stripe_index in range(loaded.stripe_count):
        control = resolved_controls.get(stripe_index, StripeRunControl())
        stripe_records = tuple(
            service.start_stripe_from_source(
                stripe_index,
                source,
                stop_after_events=control.stop_after_events,
                fault_after_events=control.fault_after_events,
                fault_message=control.fault_message,
            )
        )
        records.extend(stripe_records)
        stripe_summary = _stripe_summary(stripe_index, stripe_records)
        stripe_summaries.append(stripe_summary)
        if stripe_summary.status in ("stopped", "fault"):
            status = stripe_summary.status
            break

    return ScannerSyncSessionResult(
        scan_id=loaded.scan_id,
        stripe_count=loaded.stripe_count,
        started_stripe_count=len(stripe_summaries),
        status=status,
        records=tuple(records),
        stripes=tuple(stripe_summaries),
        first_frame_id=first_frame_id,
        next_frame_id=service.next_frame_id,
    )


def _validate_control_indexes(
    controls: Mapping[int, StripeRunControl],
    *,
    stripe_count: int,
) -> None:
    for stripe_index, control in controls.items():
        if not isinstance(stripe_index, int):
            raise ScannerSyncSessionError("control stripe indexes must be integers")
        if stripe_index < 0 or stripe_index >= stripe_count:
            raise ScannerSyncSessionError("control stripe index is outside loaded plan")
        if not isinstance(control, StripeRunControl):
            raise ScannerSyncSessionError("controls must contain StripeRunControl values")


def _stripe_summary(
    stripe_index: int,
    records: tuple[ProtocolRecord, ...],
) -> StripeSessionSummary:
    frame_events = tuple(record for record in records if record.type == "FRAME_EVENT")
    terminal_records = tuple(
        record for record in records if record.type == "SCHEDULER_TERMINAL"
    )
    if len(terminal_records) > 1:
        raise ScannerSyncSessionError("a stripe emitted more than one terminal record")
    if frame_events:
        stripe_id = frame_events[0].stripe_id
        first_frame_id = frame_events[0].frame_id
        last_frame_id = frame_events[-1].frame_id
    elif terminal_records:
        stripe_id = terminal_records[0].stripe_id
        first_frame_id = None
        last_frame_id = terminal_records[0].last_frame_id
    else:
        raise ScannerSyncSessionError("a stripe emitted no records")

    if terminal_records:
        terminal = terminal_records[0]
        return StripeSessionSummary(
            stripe_index=stripe_index,
            stripe_id=stripe_id,
            status=terminal.status,
            frame_event_count=len(frame_events),
            first_frame_id=first_frame_id,
            last_frame_id=last_frame_id,
            terminal_reason_code=terminal.reason_code,
            terminal_message=terminal.message,
        )

    return StripeSessionSummary(
        stripe_index=stripe_index,
        stripe_id=stripe_id,
        status="completed",
        frame_event_count=len(frame_events),
        first_frame_id=first_frame_id,
        last_frame_id=last_frame_id,
    )
