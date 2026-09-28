"""Software-only frame id allocation and planned FRAME_EVENT publishing."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from scanner_firmware.planning.frame_counter.publishing.allocator import FrameIdAllocator
from scanner_firmware.planning.frame_counter.publishing.errors import (
    DuplicatePlannedFrameError,
    FrameEventPublishError,
    FramePublishScopeError,
    FramePublishTerminalError,
)
from scanner_firmware.planning.frame_counter.publishing.records import (
    CoordinateSource,
    FramePublisherTerminal,
    FramePublishKey,
    PlannedFrameTrigger,
    PositionAxis,
    PublishedFrameEvent,
    TerminalReasonCode,
    TerminalStatus,
)
from scanner_firmware.planning.frame_counter.common.validation import (
    require_non_empty,
    require_non_negative,
)


class FrameEventPublisher:
    """Publish one metadata-only FRAME_EVENT per planned trigger."""

    def __init__(
        self,
        allocator: Optional[FrameIdAllocator] = None,
        *,
        protocol_version: int = 1,
    ) -> None:
        require_non_negative("protocol_version", protocol_version)
        self._allocator = allocator if allocator is not None else FrameIdAllocator()
        self._protocol_version = protocol_version
        self._published: Dict[FramePublishKey, PublishedFrameEvent] = {}
        self._terminal_streams: set[Tuple[str, int]] = set()

    @property
    def next_frame_id(self) -> int:
        return self._allocator.next_frame_id

    def publish_planned(self, trigger: PlannedFrameTrigger) -> PublishedFrameEvent:
        stream_key = (trigger.scan_id, trigger.stripe_id)
        if stream_key in self._terminal_streams:
            raise FramePublishScopeError(
                "cannot publish planned FRAME_EVENT after terminal summary"
            )
        if trigger.key in self._published:
            raise DuplicatePlannedFrameError(
                "duplicate planned FRAME_EVENT for "
                f"scan_id={trigger.scan_id!r} stripe_id={trigger.stripe_id} "
                f"stripe_frame_index={trigger.stripe_frame_index}"
            )

        event = PublishedFrameEvent(
            protocol_version=self._protocol_version,
            scan_id=trigger.scan_id,
            stripe_id=trigger.stripe_id,
            frame_id=self._allocator.allocate(),
            stripe_frame_index=trigger.stripe_frame_index,
            pattern=trigger.pattern,
            led_gate_names=trigger.led_gate_names,
            led_timing=trigger.led_timing,
            trigger_output_name=trigger.trigger_output_name,
            coordinate_source_used=trigger.coordinate_source_used,
            position_axis=trigger.position_axis,
            event_position=trigger.event_position,
            sample_position=trigger.sample_position,
            position_overshoot_count=trigger.position_overshoot_count,
            x_count=trigger.x_count,
            y_count=trigger.y_count,
            z_count=trigger.z_count,
            x_step_commanded=trigger.x_step_commanded,
            y_step_commanded=trigger.y_step_commanded,
            z_step_commanded=trigger.z_step_commanded,
            x_encoder_count=trigger.x_encoder_count,
            y_encoder_count=trigger.y_encoder_count,
            coordinate_flags=trigger.coordinate_flags,
            mcu_time_us=trigger.mcu_time_us,
            hardware_outputs_enabled=False,
            status="ok",
        )
        self._published[trigger.key] = event
        return event

    def terminal_summary(
        self,
        *,
        scan_id: str,
        stripe_id: int,
        expected_frame_count: int,
        mcu_time_us: int,
        status: TerminalStatus = "stopped",
        reason_code: TerminalReasonCode = "host_stop",
        message: str = "",
    ) -> FramePublisherTerminal:
        require_non_empty("scan_id", scan_id)
        require_non_negative("stripe_id", stripe_id)
        require_non_negative("expected_frame_count", expected_frame_count)
        require_non_negative("mcu_time_us", mcu_time_us)
        stream_key = (scan_id, stripe_id)
        if stream_key in self._terminal_streams:
            raise FramePublishTerminalError("terminal summary already published")

        frame_events = self._stream_events(scan_id, stripe_id)
        emitted_frame_count = len(frame_events)
        if emitted_frame_count > expected_frame_count:
            raise FramePublishTerminalError(
                "expected_frame_count is less than emitted planned FRAME_EVENT count"
            )
        terminal = FramePublisherTerminal(
            protocol_version=self._protocol_version,
            scan_id=scan_id,
            stripe_id=stripe_id,
            status=status,
            reason_code=reason_code,
            emitted_frame_count=emitted_frame_count,
            expected_frame_count=expected_frame_count,
            last_frame_id=frame_events[-1].frame_id if frame_events else None,
            next_frame_id=self._allocator.next_frame_id,
            next_stripe_frame_index=_next_stripe_frame_index(frame_events),
            mcu_time_us=mcu_time_us,
            hardware_outputs_enabled=False,
            message=message,
        )
        self._terminal_streams.add(stream_key)
        return terminal

    def _stream_events(
        self, scan_id: str, stripe_id: int
    ) -> Tuple[PublishedFrameEvent, ...]:
        return tuple(
            sorted(
                (
                    event
                    for key, event in self._published.items()
                    if key[0] == scan_id and key[1] == stripe_id
                ),
                key=lambda event: event.stripe_frame_index,
            )
        )


def _next_stripe_frame_index(events: Tuple[PublishedFrameEvent, ...]) -> int:
    if not events:
        return 0
    return max(event.stripe_frame_index for event in events) + 1


__all__ = [
    "CoordinateSource",
    "DuplicatePlannedFrameError",
    "FrameEventPublishError",
    "FrameEventPublisher",
    "FrameIdAllocator",
    "FramePublishScopeError",
    "FramePublishTerminalError",
    "FramePublisherTerminal",
    "FramePublishKey",
    "PlannedFrameTrigger",
    "PositionAxis",
    "PublishedFrameEvent",
    "TerminalReasonCode",
    "TerminalStatus",
]
