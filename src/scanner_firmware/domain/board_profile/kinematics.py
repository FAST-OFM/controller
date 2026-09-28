"""Config-derived motion kinematics for board profiles.

This module works on parsed profile metadata only. It does not import Klipper,
open serial ports, toggle GPIO, flash firmware or access hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping


UNKNOWN = "unknown"
DERIVED_VALUES_PATH = ("mechanics", "derived_values")
FORBIDDEN_KINEMATICS_FIELDS = frozenset(
    (
        "kinematics",
        "motion_kinematics",
        "steps_per_mm",
        "steps_per_um",
        "x_steps_per_mm",
        "y_steps_per_mm",
        "z_steps_per_mm",
        "x_steps_per_um",
        "y_steps_per_um",
        "z_steps_per_um",
    )
)


class MotionKinematicsError(ValueError):
    """Raised when motion kinematics inputs or derived values are invalid."""


@dataclass(frozen=True)
class AxisKinematics:
    axis: str
    motor_full_steps_per_rev: int | str
    microsteps: int | str
    travel_per_rev_mm: Fraction | str

    @property
    def steps_per_rev(self) -> Fraction | str:
        if UNKNOWN in (
            self.motor_full_steps_per_rev,
            self.microsteps,
        ):
            return UNKNOWN
        return Fraction(self.motor_full_steps_per_rev * self.microsteps, 1)

    @property
    def steps_per_mm(self) -> Fraction | str:
        steps_per_rev = self.steps_per_rev
        if UNKNOWN in (steps_per_rev, self.travel_per_rev_mm):
            return UNKNOWN
        return self.steps_per_rev / self.travel_per_rev_mm

    @property
    def steps_per_um(self) -> Fraction | str:
        steps_per_mm = self.steps_per_mm
        if steps_per_mm == UNKNOWN:
            return UNKNOWN
        return self.steps_per_mm / 1000


@dataclass(frozen=True)
class MotionKinematics:
    x: AxisKinematics
    y: AxisKinematics
    z: AxisKinematics

    def axis(self, name: str) -> AxisKinematics:
        normalized = name.lower()
        if normalized == "x":
            return self.x
        if normalized == "y":
            return self.y
        if normalized == "z":
            return self.z
        raise MotionKinematicsError(f"unknown motion axis: {name!r}")


def derive_motion_kinematics(profile: Mapping[str, object]) -> MotionKinematics:
    """Derive X/Y/Z motion resolution from a parsed board profile."""

    mechanics = _mapping(profile.get("mechanics"), "mechanics")
    full_steps = _positive_int_or_unknown(
        mechanics.get("motor_full_steps_per_rev"),
        "mechanics.motor_full_steps_per_rev",
    )
    microsteps = _positive_int_or_unknown(
        mechanics.get("configured_microsteps"),
        "mechanics.configured_microsteps",
    )
    return MotionKinematics(
        x=_derive_axis(mechanics, "x", full_steps, microsteps),
        y=_derive_axis(mechanics, "y", full_steps, microsteps),
        z=_derive_axis(mechanics, "z", full_steps, microsteps),
    )


def validate_profile_derived_kinematics(profile: Mapping[str, object]) -> None:
    """Validate that documented derived motion values match config inputs."""

    _reject_independent_kinematics_constants(profile, path=())
    mechanics = _mapping(profile.get("mechanics"), "mechanics")
    kinematics = derive_motion_kinematics(profile)
    expected = {
        "x_steps_per_mm": kinematics.x.steps_per_mm,
        "y_steps_per_mm": kinematics.y.steps_per_mm,
        "z_steps_per_mm": kinematics.z.steps_per_mm,
        "z_steps_per_um": kinematics.z.steps_per_um,
    }
    if "derived_values" not in mechanics:
        return
    derived_values = _mapping(
        mechanics.get("derived_values"),
        "mechanics.derived_values",
    )
    for field, value in expected.items():
        if field not in derived_values:
            raise MotionKinematicsError(f"missing derived motion value: {field}")
        actual = _positive_fraction_or_unknown(
            derived_values[field],
            f"mechanics.derived_values.{field}",
        )
        if actual != value:
            if value == UNKNOWN:
                raise MotionKinematicsError(
                    f"{field} must stay unknown because source motion fields are unknown"
                )
            raise MotionKinematicsError(
                f"{field}={float(actual):g} does not match config-derived "
                f"value {float(value):g}"
            )


def _derive_axis(
    mechanics: Mapping[str, object],
    axis: str,
    full_steps: int | str,
    microsteps: int | str,
) -> AxisKinematics:
    travel_per_rev_mm = _positive_fraction_or_unknown(
        mechanics.get(f"{axis}_travel_per_rev_mm"),
        f"mechanics.{axis}_travel_per_rev_mm",
    )
    return AxisKinematics(
        axis=axis.upper(),
        motor_full_steps_per_rev=full_steps,
        microsteps=microsteps,
        travel_per_rev_mm=travel_per_rev_mm,
    )


def _reject_independent_kinematics_constants(
    value: object,
    *,
    path: tuple[str, ...],
) -> None:
    if not isinstance(value, Mapping):
        return
    for key, child in value.items():
        if not isinstance(key, str):
            continue
        child_path = (*path, key)
        if _is_independent_kinematics_field(key, child_path):
            raise MotionKinematicsError(
                f"{_format_path(child_path)} must not define independent motion kinematics"
            )
        _reject_independent_kinematics_constants(child, path=child_path)


def _is_independent_kinematics_field(key: str, path: tuple[str, ...]) -> bool:
    if path[: len(DERIVED_VALUES_PATH)] == DERIVED_VALUES_PATH:
        return False
    return _normalize_field_name(key) in FORBIDDEN_KINEMATICS_FIELDS


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MotionKinematicsError(f"{name} must be a mapping")
    return value


def _positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MotionKinematicsError(f"{name} must be a positive integer")
    return value


def _positive_int_or_unknown(value: object, name: str) -> int | str:
    if value == UNKNOWN:
        return UNKNOWN
    return _positive_int(value, name)


def _positive_fraction(value: object, name: str) -> Fraction:
    try:
        fraction = Fraction(str(value))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise MotionKinematicsError(f"{name} must be a positive number") from exc
    if fraction <= 0:
        raise MotionKinematicsError(f"{name} must be a positive number")
    return fraction


def _positive_fraction_or_unknown(value: object, name: str) -> Fraction | str:
    if value == UNKNOWN:
        return UNKNOWN
    return _positive_fraction(value, name)


def _normalize_field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _format_path(path: tuple[str, ...]) -> str:
    return ".".join(path) if path else "<root>"
