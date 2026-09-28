"""Dry-run pipeline replay data contracts."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.foundation.protocol.events import FrameEventRecord
from scanner_firmware.planning.dry_run_pipeline.errors import DryRunPipelineError
from scanner_firmware.planning.frame_counter.publishing.records import (
    PlannedFrameTrigger,
    PublishedFrameEvent,
)


@dataclass(frozen=True)
class DryRunPipelineConfig:
    protocol_version: int = 1

    def __post_init__(self) -> None:
        if self.protocol_version < 0:
            raise DryRunPipelineError("protocol_version must be non-negative")


@dataclass(frozen=True)
class DryRunFrameResult:
    planned_trigger: PlannedFrameTrigger
    published_event: PublishedFrameEvent
    protocol_record: FrameEventRecord


@dataclass(frozen=True)
class DryRunPipelineResult:
    frame_results: tuple[DryRunFrameResult, ...]

    @property
    def protocol_records(self) -> tuple[FrameEventRecord, ...]:
        return tuple(frame.protocol_record for frame in self.frame_results)

    @property
    def published_events(self) -> tuple[PublishedFrameEvent, ...]:
        return tuple(frame.published_event for frame in self.frame_results)
