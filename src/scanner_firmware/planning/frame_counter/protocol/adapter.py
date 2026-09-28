"""Frame counter to protocol.events conversion helpers.

This adapter is software-only. It copies already-published metadata into the
protocol record dataclasses and never touches hardware, transports, clocks or
process APIs.
"""

from __future__ import annotations

from typing import Union

from scanner_firmware.foundation.protocol.events import (
    FrameEventRecord,
    ProtocolSerializationError,
    SchedulerTerminalRecord,
)
from scanner_firmware.planning.frame_counter.publishing.records import (
    FramePublisherTerminal,
    PublishedFrameEvent,
)


FrameCounterProtocolRecord = Union[FrameEventRecord, SchedulerTerminalRecord]


class FrameCounterProtocolAdapterError(ProtocolSerializationError):
    """Raised when frame_counter metadata cannot be represented by protocol.events."""


def published_frame_event_to_protocol_record(
    event: PublishedFrameEvent,
) -> FrameEventRecord:
    """Convert a published frame event into a protocol ``FRAME_EVENT`` record."""

    _require_type(event, "FRAME_EVENT")
    try:
        return FrameEventRecord.from_published_frame_event(event)
    except ProtocolSerializationError as exc:
        raise FrameCounterProtocolAdapterError(str(exc)) from exc


def frame_publisher_terminal_to_protocol_record(
    terminal: FramePublisherTerminal,
) -> SchedulerTerminalRecord:
    """Convert a supported publisher terminal into a protocol terminal record."""

    _require_type(terminal, "SCHEDULER_TERMINAL")
    _require_hardware_outputs_disabled(terminal)
    if terminal.status not in ("stopped", "fault"):
        raise FrameCounterProtocolAdapterError(
            "protocol SchedulerTerminalRecord does not support terminal "
            f"status {terminal.status!r}"
        )
    if terminal.reason_code not in (
        "host_stop",
        "scheduler_fault",
        "coordinate_source_error",
        "position_stream_exhausted",
    ):
        raise FrameCounterProtocolAdapterError(
            "protocol SchedulerTerminalRecord does not support terminal "
            f"reason_code {terminal.reason_code!r}"
        )

    return SchedulerTerminalRecord(
        protocol_version=terminal.protocol_version,
        scan_id=terminal.scan_id,
        stripe_id=terminal.stripe_id,
        status=terminal.status,
        reason_code=terminal.reason_code,
        emitted_frame_count=terminal.emitted_frame_count,
        expected_frame_count=terminal.expected_frame_count,
        last_frame_id=terminal.last_frame_id,
        next_frame_id=terminal.next_frame_id,
        next_stripe_frame_index=terminal.next_stripe_frame_index,
        mcu_time_us=terminal.mcu_time_us,
        message=terminal.message,
        hardware_outputs_enabled=False,
    )


def frame_counter_event_to_protocol_record(
    event: Union[PublishedFrameEvent, FramePublisherTerminal],
) -> FrameCounterProtocolRecord:
    """Dispatch a frame_counter event or terminal to its protocol record shape."""

    event_type = getattr(event, "type", None)
    if event_type == "FRAME_EVENT":
        return published_frame_event_to_protocol_record(event)
    if event_type == "SCHEDULER_TERMINAL":
        return frame_publisher_terminal_to_protocol_record(event)
    raise FrameCounterProtocolAdapterError(
        "unsupported frame_counter event type: %r" % event_type
    )


def _require_type(event: object, expected_type: str) -> None:
    if getattr(event, "type", None) != expected_type:
        raise FrameCounterProtocolAdapterError(f"expected {expected_type} frame_counter event")


def _require_hardware_outputs_disabled(event: object) -> None:
    if getattr(event, "hardware_outputs_enabled", None) is not False:
        raise FrameCounterProtocolAdapterError("hardware_outputs_enabled must be false")
