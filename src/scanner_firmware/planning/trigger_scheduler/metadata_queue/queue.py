"""Metadata-only queue for dry-run trigger scheduler events."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from scanner_firmware.foundation.protocol.events import (
    ProtocolRecord,
    scheduler_event_to_protocol_record,
)
from scanner_firmware.planning.trigger_scheduler.types import SchedulerEvent


class MetadataQueueError(ValueError):
    """Raised when scheduler metadata cannot be queued safely."""


class MetadataQueueOverflow(MetadataQueueError):
    """Raised when the metadata queue capacity would be exceeded."""


@dataclass(frozen=True)
class QueuedMetadataRecord:
    sequence_id: int
    scheduler_event: SchedulerEvent
    protocol_record: ProtocolRecord
    metadata_only: bool = True
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        if self.sequence_id < 0:
            raise MetadataQueueError("sequence_id must be non-negative")
        if self.metadata_only is not True:
            raise MetadataQueueError("queued scheduler metadata must be metadata-only")
        if self.hardware_outputs_enabled is not False:
            raise MetadataQueueError("metadata queue cannot enable hardware outputs")
        if getattr(self.scheduler_event, "hardware_outputs_enabled", None) is not False:
            raise MetadataQueueError("scheduler event hardware_outputs_enabled must be false")
        if getattr(self.protocol_record, "hardware_outputs_enabled", None) is not False:
            raise MetadataQueueError("protocol record hardware_outputs_enabled must be false")


class TriggerMetadataQueue:
    """Bounded FIFO for scheduler metadata records.

    The queue stores metadata records only. It does not command motion, toggle
    pins, trigger cameras, drive LEDs, open transports or attach Linux wall-clock
    identity to frame records.
    """

    def __init__(self, *, max_depth: int):
        if max_depth <= 0:
            raise MetadataQueueError("max_depth must be positive")
        self._max_depth = max_depth
        self._records: list[QueuedMetadataRecord] = []

    @property
    def max_depth(self) -> int:
        return self._max_depth

    @property
    def queued_count(self) -> int:
        return len(self._records)

    @property
    def remaining_capacity(self) -> int:
        return self._max_depth - len(self._records)

    def enqueue_event(self, event: SchedulerEvent) -> QueuedMetadataRecord:
        if len(self._records) >= self._max_depth:
            raise MetadataQueueOverflow("metadata queue capacity exceeded")
        record = QueuedMetadataRecord(
            sequence_id=len(self._records),
            scheduler_event=event,
            protocol_record=scheduler_event_to_protocol_record(event),
        )
        self._records.append(record)
        return record

    def enqueue_events(self, events: Iterable[SchedulerEvent]) -> tuple[QueuedMetadataRecord, ...]:
        queued: list[QueuedMetadataRecord] = []
        for event in events:
            queued.append(self.enqueue_event(event))
        return tuple(queued)

    def snapshot(self) -> tuple[QueuedMetadataRecord, ...]:
        return tuple(self._records)

    def snapshot_protocol_records(self) -> tuple[ProtocolRecord, ...]:
        return tuple(record.protocol_record for record in self._records)

    def drain(self) -> tuple[QueuedMetadataRecord, ...]:
        records = self.snapshot()
        self._records.clear()
        return records

    def drain_protocol_records(self) -> tuple[ProtocolRecord, ...]:
        return tuple(record.protocol_record for record in self.drain())


def queue_scheduler_metadata_events(
    events: Iterable[SchedulerEvent],
    *,
    max_depth: int,
) -> TriggerMetadataQueue:
    queue = TriggerMetadataQueue(max_depth=max_depth)
    queue.enqueue_events(events)
    return queue
