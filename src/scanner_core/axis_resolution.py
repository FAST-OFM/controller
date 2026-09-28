"""Pure axis resolution helpers derived from mechanics configuration."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .scan_geometry import ScanGeometryError


@dataclass(frozen=True)
class AxisResolution:
    """Exact step resolution derived from motor and screw mechanics."""

    screw_pitch_mm: Fraction
    microsteps: int
    motor_steps_per_rev: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "screw_pitch_mm",
            _positive_fraction(self.screw_pitch_mm, "screw_pitch_mm"),
        )
        _validate_positive_int(self.microsteps, "microsteps")
        _validate_positive_int(self.motor_steps_per_rev, "motor_steps_per_rev")

    @property
    def steps_per_rev(self) -> Fraction:
        return Fraction(self.motor_steps_per_rev * self.microsteps, 1)

    @property
    def steps_per_mm(self) -> Fraction:
        return self.steps_per_rev / self.screw_pitch_mm


def steps_per_mm_from_screw_pitch(
    *,
    screw_pitch_mm: object,
    microsteps: int,
    motor_steps_per_rev: int,
) -> Fraction:
    """Convert screw pitch, microsteps and motor steps into exact steps/mm."""

    return AxisResolution(
        screw_pitch_mm=_positive_fraction(screw_pitch_mm, "screw_pitch_mm"),
        microsteps=microsteps,
        motor_steps_per_rev=motor_steps_per_rev,
    ).steps_per_mm


def _validate_int(value: object, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScanGeometryError(f"{name} must be an integer")


def _validate_positive_int(value: object, name: str) -> None:
    _validate_int(value, name)
    if value <= 0:
        raise ScanGeometryError(f"{name} must be a positive integer")


def _positive_fraction(value: object, name: str) -> Fraction:
    try:
        fraction = Fraction(str(value))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ScanGeometryError(f"{name} must be a positive number") from exc
    if fraction <= 0:
        raise ScanGeometryError(f"{name} must be a positive number")
    return fraction


__all__ = [
    "AxisResolution",
    "steps_per_mm_from_screw_pitch",
]
