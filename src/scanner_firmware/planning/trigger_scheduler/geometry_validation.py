"""Recipe geometry validation for trigger schedules."""

from __future__ import annotations

from scanner_core.scan_geometry import ScanGeometryError, StripeGeometry
from scanner_firmware.planning.trigger_scheduler.errors import ScanPlanError


def validate_event_geometry(
    *,
    start_position: int,
    end_position: int,
    first_event_position: int,
    event_pitch: int,
    event_count: int,
    prefix: str,
) -> None:
    if event_pitch == 0:
        raise ScanPlanError(f"{prefix}.event_pitch must be non-zero")
    if event_count < 0:
        raise ScanPlanError(f"{prefix}.event_count must be non-negative")
    if event_count == 0:
        return
    try:
        StripeGeometry(
            axis="X",
            start_position=start_position,
            end_position=end_position,
            first_event_position=first_event_position,
            event_pitch=event_pitch,
            event_count=event_count,
        )
    except ScanGeometryError as exc:
        raise ScanPlanError(f"{prefix}.{exc}") from exc


def position_within_bounds(
    start_position: int, end_position: int, position: int
) -> bool:
    lower = min(start_position, end_position)
    upper = max(start_position, end_position)
    return lower <= position <= upper
