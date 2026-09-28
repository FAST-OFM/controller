"""Pure scan stripe geometry contracts.

This module is shared domain math only. It never commands motion, reads
hardware state, toggles GPIO, triggers cameras, emits light or opens devices.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast


Axis = Literal["X", "Y"]
VALID_AXES = frozenset(("X", "Y"))


class ScanGeometryError(ValueError):
    """Raised when scan geometry inputs or position samples are invalid."""


@dataclass(frozen=True, init=False)
class PositionSample:
    """One position sample on a scan axis."""

    axis: Axis
    position_count: int
    event_index: int | None

    def __init__(
        self,
        *,
        axis: str,
        position: int | None = None,
        position_count: int | None = None,
        event_index: int | None = None,
    ) -> None:
        if position is not None and position_count is not None and position != position_count:
            raise ScanGeometryError("position and position_count must match when both are supplied")
        resolved_position = position_count if position_count is not None else position
        if resolved_position is None:
            raise ScanGeometryError("position or position_count is required")

        normalized_axis = validate_axis(axis)
        _validate_int(resolved_position, "position_count")
        if event_index is not None:
            _validate_int(event_index, "event_index")
            if event_index < 0:
                raise ScanGeometryError("event_index must be non-negative")

        object.__setattr__(self, "axis", normalized_axis)
        object.__setattr__(self, "position_count", resolved_position)
        object.__setattr__(self, "event_index", event_index)

    @property
    def position(self) -> int:
        """Backward-compatible alias for ``position_count``."""

        return self.position_count


@dataclass(frozen=True, init=False)
class StripeGeometry:
    """Position-indexed event geometry for one scan stripe."""

    axis: Axis
    start_position: int
    end_position: int
    first_event_position: int
    event_pitch: int
    event_count: int

    def __init__(
        self,
        *,
        axis: str,
        start_position: int,
        end_position: int,
        event_count: int,
        first_event_position: int | None = None,
        event_pitch: int | None = None,
        pitch: int | None = None,
    ) -> None:
        if event_pitch is not None and pitch is not None and event_pitch != pitch:
            raise ScanGeometryError("event_pitch and pitch must match when both are supplied")
        resolved_pitch = event_pitch if event_pitch is not None else pitch
        if resolved_pitch is None:
            raise ScanGeometryError("event_pitch or pitch is required")

        normalized_axis = validate_axis(axis)
        _validate_int(start_position, "start_position")
        _validate_int(end_position, "end_position")
        _validate_int(resolved_pitch, "event_pitch")
        _validate_int(event_count, "event_count")
        if first_event_position is not None:
            _validate_int(first_event_position, "first_event_position")

        if start_position == end_position:
            raise ScanGeometryError("start_position and end_position must differ")
        if resolved_pitch == 0:
            raise ScanGeometryError("event_pitch must be non-zero")
        if event_count < 0:
            raise ScanGeometryError("event_count must be non-negative")

        resolved_first_event = (
            start_position + resolved_pitch
            if first_event_position is None
            else first_event_position
        )

        object.__setattr__(self, "axis", normalized_axis)
        object.__setattr__(self, "start_position", start_position)
        object.__setattr__(self, "end_position", end_position)
        object.__setattr__(self, "first_event_position", resolved_first_event)
        object.__setattr__(self, "event_pitch", resolved_pitch)
        object.__setattr__(self, "event_count", event_count)

        if self.pitch_direction != self.direction:
            raise ScanGeometryError("event_pitch sign must agree with stripe direction")
        for name, position_value in (
            ("first event position", self.first_event_position),
            ("last event position", self.last_position),
        ):
            if position_value is not None and not self.contains_position(position_value):
                raise ScanGeometryError(f"{name} is outside stripe bounds")

    @property
    def direction(self) -> int:
        """Return ``1`` for increasing stripes and ``-1`` for decreasing stripes."""

        return 1 if self.end_position > self.start_position else -1

    @property
    def pitch_direction(self) -> int:
        """Return the direction implied by the signed event pitch."""

        return 1 if self.event_pitch > 0 else -1

    @property
    def pitch(self) -> int:
        """Backward-compatible alias for ``event_pitch``."""

        return self.event_pitch

    @property
    def positions(self) -> tuple[int, ...]:
        """Scheduled event positions from first event at event-pitch intervals."""

        return tuple(
            self.first_event_position + self.event_pitch * index
            for index in range(self.event_count)
        )

    @property
    def position_samples(self) -> tuple[PositionSample, ...]:
        """Scheduled event positions as indexed ``PositionSample`` values."""

        return tuple(
            PositionSample(
                axis=self.axis,
                event_index=event_index,
                position_count=position,
            )
            for event_index, position in enumerate(self.positions)
        )

    @property
    def last_position(self) -> int | None:
        """Last scheduled event position, or ``None`` when there are no events."""

        if self.event_count == 0:
            return None
        return self.first_event_position + self.event_pitch * (self.event_count - 1)

    @property
    def lower_bound(self) -> int:
        return min(self.start_position, self.end_position)

    @property
    def upper_bound(self) -> int:
        return max(self.start_position, self.end_position)

    def position_for_event(self, event_index: int) -> PositionSample:
        """Return the indexed scheduled position sample for one event."""

        _validate_int(event_index, "event_index")
        if event_index < 0:
            raise ScanGeometryError("event_index must be non-negative")
        if event_index >= self.event_count:
            raise ScanGeometryError("event_index must be less than event_count")
        return PositionSample(
            axis=self.axis,
            event_index=event_index,
            position_count=self.positions[event_index],
        )

    def contains_position(self, position: int) -> bool:
        """Return whether ``position`` is inside the inclusive stripe bounds."""

        _validate_int(position, "position")
        return self.lower_bound <= position <= self.upper_bound

    def require_within_bounds(self, position: int, name: str = "position") -> int:
        """Return ``position`` when it is inside bounds, otherwise raise."""

        _validate_int(position, name)
        if not self.contains_position(position):
            raise ScanGeometryError(f"{name} is outside stripe bounds")
        return position

    def is_event_position(self, position: int) -> bool:
        """Return whether ``position`` is one of this stripe's planned events."""

        _validate_int(position, "position")
        if self.event_count == 0 or not self.contains_position(position):
            return False
        offset = position - self.first_event_position
        return (
            offset % self.event_pitch == 0
            and 0 <= offset // self.event_pitch < self.event_count
        )

    def require_event_position(self, position: int) -> int:
        """Return a planned event position, otherwise raise."""

        _validate_int(position, "event_position")
        if not self.is_event_position(position):
            raise ScanGeometryError("event_position is not a planned stripe event")
        return position

    def overshoot_for_sample(
        self,
        *,
        event_position: int,
        sample: PositionSample,
    ) -> int:
        """Return sample overshoot past a planned event in position counts."""

        self.require_event_position(event_position)
        if sample.axis != self.axis:
            raise ScanGeometryError("sample axis must match stripe axis")
        self.require_within_bounds(sample.position_count, "sample.position")

        signed_delta = sample.position_count - event_position
        if signed_delta * self.direction < 0:
            raise ScanGeometryError("sample.position has not reached event_position")
        return signed_delta


def validate_axis(axis: object) -> Axis:
    """Validate and normalize a scan axis name."""

    if not isinstance(axis, str):
        raise ScanGeometryError("axis must be X or Y")
    normalized = axis.upper()
    if normalized not in VALID_AXES:
        raise ScanGeometryError("axis must be X or Y")
    return cast(Axis, normalized)


def _validate_int(value: object, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScanGeometryError(f"{name} must be an integer")


__all__ = [
    "Axis",
    "PositionSample",
    "ScanGeometryError",
    "StripeGeometry",
    "validate_axis",
]
