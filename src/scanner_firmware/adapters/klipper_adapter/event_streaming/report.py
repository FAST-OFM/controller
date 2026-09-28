"""Scanner-sync capture reporting helpers."""

from __future__ import annotations

from typing import Iterable

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import ScannerSyncCaptureReport
from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.foundation.protocol.events import ProtocolRecord


def build_scanner_sync_capture_report(
    records: Iterable[ProtocolRecord],
) -> ScannerSyncCaptureReport:
    """Validate a decoded capture and return a compact acceptance report."""

    decoded_records = tuple(records)
    validation = validate_scanner_sync_event_sequence(decoded_records)
    return ScannerSyncCaptureReport(
        accepted=True,
        record_count=len(decoded_records),
        event_types=tuple(record.type for record in decoded_records),
        validation=validation,
    )
