"""Hardware-free scanner sync service boundary.

This module composes scan-plan parsing, dry-run scheduling and protocol
serialization. It does not import Klipper, open serial ports, command motion,
toggle GPIO, trigger cameras or drive LEDs.
"""

from __future__ import annotations

from typing import Any, Mapping

from scanner_firmware.foundation.protocol.events import (
    ProtocolRecord,
)
from scanner_firmware.planning.scan_preflight.axes import REQUIRED_SCAN_AXES
from scanner_firmware.planning.scan_preflight.decisions import (
    ScanPreflightDecision,
    ScanPreflightInput,
)
from scanner_firmware.planning.scan_preflight.evaluator import evaluate_scan_preflight
from scanner_firmware.planning.scanner_sync.interfaces import LoadedScanPlan, PositionSampleSource
from scanner_firmware.planning.trigger_scheduler.errors import ScanPlanError
from scanner_firmware.planning.trigger_scheduler.metadata_queue.queue import (
    MetadataQueueOverflow,
    TriggerMetadataQueue,
    queue_scheduler_metadata_events,
)
from scanner_firmware.planning.trigger_scheduler.recipe_builder import (
    build_stripe_schedules,
)
from scanner_firmware.planning.trigger_scheduler.scheduler import (
    DryRunPositionEventScheduler,
)
from scanner_firmware.planning.trigger_scheduler.types import (
    PositionSample,
)


class ScannerSyncServiceError(ValueError):
    """Raised when the dry-run sync service is used out of sequence."""


DEFAULT_METADATA_QUEUE_DEPTH = 4096


class DryRunScannerSyncService:
    """Protocol-facing dry-run scanner sync service.

    The service mirrors the future command flow (`load_scan_recipe`,
    `start_scan`) without touching hardware. Future Klipper integration can
    keep this boundary and replace the synthetic position-sample source with a
    reviewed Klipper commanded-position adapter.
    """

    def __init__(
        self,
        *,
        first_frame_id: int = 0,
        protocol_version: int = 1,
        metadata_queue_depth: int = DEFAULT_METADATA_QUEUE_DEPTH,
    ):
        self._scheduler = DryRunPositionEventScheduler(
            first_frame_id=first_frame_id,
            protocol_version=protocol_version,
        )
        if metadata_queue_depth <= 0:
            raise ScannerSyncServiceError("metadata_queue_depth must be positive")
        self._metadata_queue_depth = metadata_queue_depth
        self._schedules = ()
        self._scan_id: str | None = None
        self._preflight_decision: ScanPreflightDecision | None = None

    @property
    def loaded_scan_id(self) -> str | None:
        return self._scan_id

    @property
    def next_frame_id(self) -> int:
        return self._scheduler.next_frame_id

    @property
    def preflight_decision(self) -> ScanPreflightDecision | None:
        return self._preflight_decision

    @property
    def metadata_queue_depth(self) -> int:
        return self._metadata_queue_depth

    def load_scan_recipe(self, scan_recipe: Mapping[str, Any]) -> LoadedScanPlan:
        schedules = build_stripe_schedules(scan_recipe)
        if not schedules:
            raise ScanPlanError("scan recipe produced no schedules")
        self._schedules = schedules
        self._scan_id = schedules[0].scan_id
        self._preflight_decision = None
        return LoadedScanPlan(scan_id=self._scan_id, stripe_count=len(schedules))

    def run_preflight(self, preflight: ScanPreflightInput) -> ScanPreflightDecision:
        decision = evaluate_scan_preflight(preflight)
        if decision.accepted:
            self._preflight_decision = decision
        return decision

    def accept_simulator_preflight(
        self,
        *,
        homed_axes: tuple[str, ...] = (),
    ) -> ScanPreflightDecision:
        return self.run_preflight(
            ScanPreflightInput(
                required_axes=REQUIRED_SCAN_AXES,
                homed_axes=homed_axes,  # type: ignore[arg-type]
                dry_run=True,
                hardware_outputs_enabled=False,
            )
        )

    def start_stripe(
        self,
        stripe_index: int,
        samples: list[PositionSample],
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[ProtocolRecord]:
        queue = self.start_stripe_metadata_queue(
            stripe_index,
            samples,
            stop_after_events=stop_after_events,
            fault_after_events=fault_after_events,
            fault_message=fault_message,
        )
        return list(queue.drain_protocol_records())

    def start_stripe_metadata_queue(
        self,
        stripe_index: int,
        samples: list[PositionSample],
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> TriggerMetadataQueue:
        self._require_startable_stripe(stripe_index)
        schedule = self._schedules[stripe_index]
        if self._metadata_queue_depth < schedule.event_count:
            raise MetadataQueueOverflow(
                "metadata queue capacity is smaller than planned scheduler output"
            )

        events = self._scheduler.run(
            schedule,
            samples,
            stop_after_events=stop_after_events,
            fault_after_events=fault_after_events,
            fault_message=fault_message,
        )
        return queue_scheduler_metadata_events(
            events,
            max_depth=self._metadata_queue_depth,
        )

    def start_stripe_json_lines(
        self,
        stripe_index: int,
        samples: list[PositionSample],
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[str]:
        return [
            record.to_json(separators=(",", ":"), sort_keys=True)
            for record in self.start_stripe(
                stripe_index,
                samples,
                stop_after_events=stop_after_events,
                fault_after_events=fault_after_events,
                fault_message=fault_message,
            )
        ]

    def start_stripe_from_source(
        self,
        stripe_index: int,
        source: PositionSampleSource,
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[ProtocolRecord]:
        return self.start_stripe(
            stripe_index,
            list(source.samples_for_stripe(stripe_index)),
            stop_after_events=stop_after_events,
            fault_after_events=fault_after_events,
            fault_message=fault_message,
        )

    def _require_startable_stripe(self, stripe_index: int) -> None:
        if self._scan_id is None:
            raise ScannerSyncServiceError("load_scan_recipe must be called before start_stripe")
        if stripe_index < 0 or stripe_index >= len(self._schedules):
            raise ScannerSyncServiceError("stripe_index is outside the loaded scan plan")
        if self._preflight_decision is None:
            raise ScannerSyncServiceError("accepted scan preflight is required before start_stripe")
        if not self._preflight_decision.accepted:
            raise ScannerSyncServiceError("scan preflight must be accepted before start_stripe")
