"""End-to-end dry-run harness for the future Klipper scanner-sync path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from scanner_firmware.adapters.klipper_adapter.sync_codec.decode import (
    decode_scanner_sync_response,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.encode import (
    encode_schedule_z_command,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (
    EncodedKlipperCommand,
    ScannerSyncDecodeContext,
)
from scanner_firmware.adapters.klipper_adapter.testing.fake import DryRunKlipperMcu
from scanner_firmware.adapters.klipper_adapter.harness.payloads import (
    pattern_names_from_recipe,
    synthetic_callback_payload,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    COMMAND_BINDINGS,
    ProtocolEventType,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.registration import (
    ScannerSyncKlipperRegistration,
)
from scanner_firmware.foundation.protocol.events import (
    ProtocolRecord,
    ScheduleZCommand,
)
from scanner_firmware.planning.scanner_sync.interfaces import LoadedScanPlan
from scanner_firmware.planning.scanner_sync.service import DryRunScannerSyncService
from scanner_firmware.planning.trigger_scheduler.types import PositionSample


@dataclass(frozen=True)
class KlipperScannerSyncHarnessStatus:
    loaded_scan_id: str | None
    next_frame_id: int
    registration_oid: int
    mcu_phase: str
    registered_command_count: int
    registered_response_count: int


class DryRunKlipperScannerSyncHarness:
    """Compose fake Klipper registration, protocol codec and dry-run scan service.

    The harness is intentionally local-only. It does not import real Klipper,
    open serial devices, send commands, restart services, toggle GPIO, trigger
    cameras, drive LEDs or command motion.
    """

    def __init__(self, *, first_frame_id: int = 0, protocol_version: int = 1):
        self.mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )
        self.registration = ScannerSyncKlipperRegistration(
            self.mcu,
            protocol_version=protocol_version,
        )
        self.service = DryRunScannerSyncService(
            first_frame_id=first_frame_id,
            protocol_version=protocol_version,
        )
        self.mcu.run_config_callbacks()
        self._pattern_names: tuple[str, ...] = ()

    @property
    def status(self) -> KlipperScannerSyncHarnessStatus:
        return KlipperScannerSyncHarnessStatus(
            loaded_scan_id=self.service.loaded_scan_id,
            next_frame_id=self.service.next_frame_id,
            registration_oid=self.registration.oid,
            mcu_phase=self.mcu.phase,
            registered_command_count=len(self.registration.commands),
            registered_response_count=len(self.mcu.serial_responses),
        )

    def load_scan_recipe(self, scan_recipe: dict[str, Any]) -> LoadedScanPlan:
        self._pattern_names = pattern_names_from_recipe(scan_recipe)
        return self.service.load_scan_recipe(scan_recipe)

    def accept_simulator_preflight(self) -> None:
        self.service.accept_simulator_preflight()

    def start_stripe(
        self,
        stripe_index: int,
        samples: list[PositionSample],
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[ProtocolRecord]:
        return self.service.start_stripe(
            stripe_index,
            samples,
            stop_after_events=stop_after_events,
            fault_after_events=fault_after_events,
            fault_message=fault_message,
        )

    def encode_schedule_z(self, command: ScheduleZCommand) -> EncodedKlipperCommand:
        return encode_schedule_z_command(oid=self.registration.oid, command=command)

    def decode_response(
        self,
        event_type: ProtocolEventType,
        params: dict[str, Any],
    ) -> ProtocolRecord:
        scan_id = self.service.loaded_scan_id
        if scan_id is None:
            raise ValueError("load_scan_recipe must be called before decoding responses")
        return decode_scanner_sync_response(
            event_type,
            params,
            context=ScannerSyncDecodeContext(
                scan_id=scan_id,
                protocol_version=self.registration.protocol_version,
                pattern_names=self._pattern_names,
            ),
        )

    def to_synthetic_callback_json_lines(
        self,
        records: list[ProtocolRecord],
    ) -> list[str]:
        """Encode protocol records as captured Klipper callback JSONL fixtures."""

        return [
            json.dumps(
                synthetic_callback_payload(record, pattern_names=self._pattern_names),
                separators=(",", ":"),
                sort_keys=True,
            )
            for record in records
        ]
