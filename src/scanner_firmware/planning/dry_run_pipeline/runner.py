"""Software-only dry-run FRAME_EVENT replay runner."""

from __future__ import annotations

from collections.abc import Iterable

from scanner_firmware.planning.dry_run_pipeline.types import (
    DryRunFrameResult,
    DryRunPipelineConfig,
    DryRunPipelineResult,
)
from scanner_firmware.planning.frame_counter.publishing.allocator import FrameIdAllocator
from scanner_firmware.planning.frame_counter.publishing.publisher import FrameEventPublisher
from scanner_firmware.planning.frame_counter.publishing.records import (
    PlannedFrameTrigger,
)


def run_dry_run_pipeline(
    planned_triggers: Iterable[PlannedFrameTrigger],
    *,
    config: DryRunPipelineConfig | None = None,
    first_frame_id: int = 0,
) -> DryRunPipelineResult:
    """Replay planned metadata triggers into FRAME_EVENT protocol records.

    This fixture boundary deliberately starts from already-planned frame triggers.
    Higher-level Pi planning and image-analysis responsibilities stay outside
    firmware.
    """

    resolved_config = config if config is not None else DryRunPipelineConfig()
    publisher = FrameEventPublisher(
        FrameIdAllocator(first_frame_id=first_frame_id),
        protocol_version=resolved_config.protocol_version,
    )
    frame_results: list[DryRunFrameResult] = []
    for trigger in planned_triggers:
        event = publisher.publish_planned(trigger)
        frame_results.append(
            DryRunFrameResult(
                planned_trigger=trigger,
                published_event=event,
                protocol_record=event.to_protocol_record(),
            )
        )

    return DryRunPipelineResult(frame_results=tuple(frame_results))
