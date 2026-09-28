"""Scanner-sync backend implementations.

Backends are substitution points for simulator and future live implementations.
The dry-run backend delegates to `DryRunScannerSyncService` and remains
hardware-free.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from scanner_firmware.adapters.klipper_adapter.harness.payloads import synthetic_callback_payload
from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    ScannerSyncStreamValidation,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.parsing import (
    decode_scanner_sync_json_lines,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext
from scanner_firmware.foundation.protocol.events import ProtocolRecord
from scanner_firmware.planning.scanner_sync.interfaces import (
    LoadedScanPlan,
    PositionSampleSource,
    ScanPreflightDecision,
    ScanPreflightInput,
)
from scanner_firmware.planning.scanner_sync.service import DryRunScannerSyncService


@dataclass(frozen=True)
class ValidatedCapture:
    records: tuple[ProtocolRecord, ...]
    callback_json_lines: tuple[str, ...]
    decoded_records: tuple[ProtocolRecord, ...]
    validation: ScannerSyncStreamValidation


@dataclass
class DryRunScannerSyncBackend:
    service: DryRunScannerSyncService
    pattern_names: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        first_frame_id: int = 0,
        protocol_version: int = 1,
    ) -> "DryRunScannerSyncBackend":
        return cls(
            DryRunScannerSyncService(
                first_frame_id=first_frame_id,
                protocol_version=protocol_version,
            )
        )

    def load_scan_recipe(self, scan_recipe: Mapping[str, Any]) -> LoadedScanPlan:
        self.pattern_names = _pattern_names_from_recipe(scan_recipe)
        return self.service.load_scan_recipe(scan_recipe)

    def run_preflight(self, preflight: ScanPreflightInput) -> ScanPreflightDecision:
        return self.service.run_preflight(preflight)

    def start_stripe_from_source(
        self,
        stripe_index: int,
        source: PositionSampleSource,
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[ProtocolRecord]:
        return self.service.start_stripe_from_source(
            stripe_index,
            source,
            stop_after_events=stop_after_events,
            fault_after_events=fault_after_events,
            fault_message=fault_message,
        )

    def start_validated_capture_from_source(
        self,
        stripe_index: int,
        source: PositionSampleSource,
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> ValidatedCapture:
        records = self.start_stripe_from_source(
            stripe_index,
            source,
            stop_after_events=stop_after_events,
            fault_after_events=fault_after_events,
            fault_message=fault_message,
        )
        callback_json_lines = tuple(
            _json_line_for_callback(record, pattern_names=self.pattern_names)
            for record in records
        )
        if self.service.loaded_scan_id is None:
            raise ValueError("load_scan_recipe must be called before capture replay")
        decoded_records = tuple(
            decode_scanner_sync_json_lines(
                callback_json_lines,
                context=ScannerSyncDecodeContext(
                    scan_id=self.service.loaded_scan_id,
                    pattern_names=self.pattern_names,
                ),
            )
        )
        validation = validate_scanner_sync_event_sequence(decoded_records)
        return ValidatedCapture(
            records=tuple(records),
            callback_json_lines=callback_json_lines,
            decoded_records=decoded_records,
            validation=validation,
        )


def _json_line_for_callback(
    record: ProtocolRecord,
    *,
    pattern_names: tuple[str, ...],
) -> str:
    return json.dumps(
        synthetic_callback_payload(record, pattern_names=pattern_names),
        separators=(",", ":"),
        sort_keys=True,
    )


def _pattern_names_from_recipe(scan_recipe: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for stripe in scan_recipe.get("stripes", ()):
        if not isinstance(stripe, Mapping):
            continue
        for pattern in stripe.get("pattern_sequence", ()):
            if isinstance(pattern, str) and pattern not in seen:
                seen.add(pattern)
                names.append(pattern)
    return tuple(names)
