"""Host-side scanner-sync response dispatch helpers.

This module converts already-decoded Klipper response callback payloads into
project protocol records. It does not import Klipper, open serial ports, send
MCU commands, toggle outputs, command motion, trigger cameras, drive LEDs or
flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    ScannerSyncStreamValidation,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.decode import (
    decode_scanner_sync_response,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    ProtocolEventType,
)
from scanner_firmware.foundation.protocol.events import ProtocolRecord


class ProtocolRecordSink(Protocol):
    def append(self, record: ProtocolRecord) -> None:
        """Store or forward one decoded protocol record."""


@dataclass(frozen=True)
class DispatchStats:
    record_count: int
    last_event_type: str | None


class ScannerSyncProtocolDispatcher:
    """Decode scanner-sync response callbacks into protocol records."""

    def __init__(
        self,
        *,
        context: ScannerSyncDecodeContext,
        sink: ProtocolRecordSink | None = None,
        validate_before_sink: bool = False,
    ):
        self._context = context
        self._sink = sink
        self._validate_before_sink = validate_before_sink
        self._records: list[ProtocolRecord] = []
        self._last_event_type: str | None = None

    @property
    def records(self) -> tuple[ProtocolRecord, ...]:
        return tuple(self._records)

    @property
    def stats(self) -> DispatchStats:
        return DispatchStats(
            record_count=len(self._records),
            last_event_type=self._last_event_type,
        )

    def handle_response(
        self,
        event_type: ProtocolEventType,
        params: dict[str, object],
    ) -> ProtocolRecord:
        record = decode_scanner_sync_response(event_type, params, context=self._context)
        if self._validate_before_sink:
            validate_scanner_sync_event_sequence(
                (*self._records, record),
                require_z_terminal_outcomes=False,
                require_timed_output_sequence_terminal_outcomes=False,
            )
        self._records.append(record)
        self._last_event_type = record.type
        if self._sink is not None:
            self._sink.append(record)
        return record

    def validate_sequence(self) -> ScannerSyncStreamValidation:
        """Validate decoded record ordering and counters."""

        return validate_scanner_sync_event_sequence(self._records)
