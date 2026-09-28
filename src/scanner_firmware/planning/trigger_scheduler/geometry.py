"""Geometry helpers for dry-run trigger scheduling."""

from __future__ import annotations

from scanner_core.scan_geometry import (
    PositionSample as AxisPositionSample,
)
from scanner_core.scan_geometry import (
    ScanGeometryError,
    StripeGeometry,
)
from scanner_firmware.planning.trigger_scheduler.types import (
    FrameEvent,
    PositionSample,
    ScheduleError,
    SchedulerEvent,
    StripeSchedule,
)


def validate_schedule(schedule: StripeSchedule) -> None:
    if not schedule.dry_run:
        raise ScheduleError("dry_run must be true for Phase 0 dry-run scheduler")
    if schedule.hardware_outputs_enabled:
        raise ScheduleError(
            "hardware_outputs_enabled requires an approved backend; none exists in Phase 0"
        )
    if schedule.event_pitch == 0:
        raise ScheduleError("event_pitch must be non-zero")
    if schedule.event_count < 0:
        raise ScheduleError("event_count must be non-negative")
    if not schedule.pattern_sequence:
        raise ScheduleError("pattern_sequence must not be empty")
    if schedule.event_count == 0:
        return

    stripe_geometry(schedule)


def frame_events(events: list[SchedulerEvent]) -> list[FrameEvent]:
    return [event for event in events if isinstance(event, FrameEvent)]


def frame_event_count(events: list[SchedulerEvent]) -> int:
    return len(frame_events(events))


def stripe_direction(schedule: StripeSchedule) -> int:
    return stripe_geometry(schedule).direction


def position_within_stripe(schedule: StripeSchedule, position: int) -> bool:
    return stripe_geometry(schedule).contains_position(position)


def sample_reached(
    schedule: StripeSchedule, sample: PositionSample, target_position: int
) -> bool:
    current = sample_position(schedule, sample)
    if stripe_direction(schedule) > 0:
        return current >= target_position
    return current <= target_position


def sample_position(schedule: StripeSchedule, sample: PositionSample) -> int:
    return sample.x_step_commanded if schedule.axis == "X" else sample.y_step_commanded


def sample_overshoot(
    schedule: StripeSchedule,
    sample: PositionSample,
    event_position: int,
) -> int:
    try:
        return stripe_geometry(schedule).overshoot_for_sample(
            event_position=event_position,
            sample=AxisPositionSample(
                axis=schedule.axis,
                position=sample_position(schedule, sample),
            ),
        )
    except ScanGeometryError as exc:
        raise ScheduleError(str(exc)) from exc


def stripe_geometry(schedule: StripeSchedule) -> StripeGeometry:
    try:
        return StripeGeometry(
            axis=schedule.axis,
            start_position=schedule.start_position,
            end_position=schedule.end_position,
            first_event_position=schedule.first_event_position,
            event_pitch=schedule.event_pitch,
            event_count=schedule.event_count,
        )
    except ScanGeometryError as exc:
        raise ScheduleError(str(exc)) from exc
