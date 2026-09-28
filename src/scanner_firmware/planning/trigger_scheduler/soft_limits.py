"""Soft-limit parsing and validation for dry-run scan recipes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scanner_firmware.planning.trigger_scheduler.errors import ScanPlanError
from scanner_firmware.planning.trigger_scheduler.recipe_fields import require_int

SoftLimits = Mapping[str, tuple[int, int]]


def optional_soft_limits(scan_recipe: Mapping[str, Any]) -> SoftLimits:
    value = scan_recipe.get("soft_limits")
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ScanPlanError("soft_limits must be a mapping")

    limits: dict[str, tuple[int, int]] = {}
    for axis in ("X", "Y"):
        axis_limits = value.get(axis)
        if axis_limits is None:
            continue
        if not isinstance(axis_limits, Mapping):
            raise ScanPlanError(f"soft_limits.{axis} must be a mapping")
        lower = require_int(axis_limits, "min", f"soft_limits.{axis}.min")
        upper = require_int(axis_limits, "max", f"soft_limits.{axis}.max")
        if lower > upper:
            raise ScanPlanError(f"soft_limits.{axis}.min must be <= max")
        limits[axis] = (lower, upper)
    return limits


def validate_axis_soft_limits(
    *,
    axis: str,
    soft_limits: SoftLimits,
    start_position: int,
    end_position: int,
    first_event_position: int,
    event_pitch: int,
    event_count: int,
    prefix: str,
) -> None:
    if axis not in soft_limits:
        return
    lower, upper = soft_limits[axis]
    last_event_position = first_event_position + event_pitch * max(event_count - 1, 0)
    for field_name, position in (
        ("start_position", start_position),
        ("end_position", end_position),
        ("first_event_position", first_event_position),
        ("last_event_position", last_event_position),
    ):
        if not lower <= position <= upper:
            raise ScanPlanError(
                f"{prefix}.{field_name} is outside configured {axis} soft limits"
            )
