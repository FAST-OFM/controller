"""Passive live scanner-sync metadata ingest backend.

This module composes Klipper scanner-sync metadata primitives behind the
scanner-sync backend boundary. It only accepts already-received callback
payloads. It does not import Klipper, open serial ports, send commands, toggle
GPIO, command motion, trigger cameras, drive LEDs or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from scanner_firmware.adapters.klipper_adapter.event_streaming.dispatch import (
    ProtocolRecordSink,
    ScannerSyncProtocolDispatcher,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    ScannerSyncStreamValidation,
)
from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (
    LiveKlipperScannerSyncObservation,
    LiveMetadataReadiness,
    evaluate_live_metadata_readiness,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    ProtocolEventType,
)
from scanner_firmware.foundation.protocol.events import ProtocolRecord


class PassiveLiveMetadataBackendError(ValueError):
    """Raised when passive metadata ingest is used before readiness is met."""


@dataclass(frozen=True)
class PassiveLiveMetadataBackendStatus:
    readiness: LiveMetadataReadiness
    record_count: int
    last_event_type: str | None
    validate_before_forward: bool


class PassiveLiveMetadataBackend:
    """Decode and validate live scanner-sync metadata callbacks.

    The backend intentionally has no command-sending, GPIO, motion, camera or
    LED methods. It is suitable only after a passive readiness observation has
    already shown that metadata-only scanner-sync support is present.
    """

    def __init__(
        self,
        *,
        observation: LiveKlipperScannerSyncObservation,
        context: ScannerSyncDecodeContext,
        validate_before_forward: bool = True,
        sink: ProtocolRecordSink | None = None,
    ):
        readiness = evaluate_live_metadata_readiness(observation)
        if not readiness.can_enable_scanner_sync:
            raise PassiveLiveMetadataBackendError(
                "live metadata backend requires ready scanner-sync observation: "
                + ",".join(readiness.blockers or (readiness.stage,))
            )
        self._readiness = readiness
        self._validate_before_forward = validate_before_forward
        self._dispatcher = ScannerSyncProtocolDispatcher(
            context=context,
            sink=sink,
            validate_before_sink=validate_before_forward,
        )

    @property
    def records(self) -> tuple[ProtocolRecord, ...]:
        return self._dispatcher.records

    @property
    def status(self) -> PassiveLiveMetadataBackendStatus:
        stats = self._dispatcher.stats
        return PassiveLiveMetadataBackendStatus(
            readiness=self._readiness,
            record_count=stats.record_count,
            last_event_type=stats.last_event_type,
            validate_before_forward=self._validate_before_forward,
        )

    def ingest_response(
        self,
        event_type: ProtocolEventType,
        params: Mapping[str, object],
    ) -> ProtocolRecord:
        return self._dispatcher.handle_response(event_type, dict(params))

    def validate_sequence(self) -> ScannerSyncStreamValidation:
        return self._dispatcher.validate_sequence()
