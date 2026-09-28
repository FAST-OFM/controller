"""Dry-run scan execution trace plan DTOs.

These records are intentionally local to ``planning.scan_execution``. They are
not a host-side scan planner and must not grow camera, autofocus, tiling or
recipe ownership.
"""

from __future__ import annotations

from dataclasses import dataclass

from scanner_core.scan_geometry import Axis
from scanner_firmware.planning.scan_execution.modes import ScanMode


@dataclass(frozen=True)
class ExecutionFramePlan:
    scan_id: str
    stripe_id: int
    frame_id: int
    stripe_frame_index: int
    scan_axis: Axis
    scan_axis_position: int
    scan_mode: ScanMode | str
    dry_run: bool = True
    hardware_outputs_enabled: bool = False


@dataclass(frozen=True)
class ExecutionStripePlan:
    stripe_id: int
    scan_axis: Axis
    frames: tuple[ExecutionFramePlan, ...]


@dataclass(frozen=True)
class ExecutionScanPlan:
    scan_id: str
    stripes: tuple[ExecutionStripePlan, ...]
    dry_run: bool = True
    hardware_outputs_enabled: bool = False

    @property
    def frames(self) -> tuple[ExecutionFramePlan, ...]:
        return tuple(frame for stripe in self.stripes for frame in stripe.frames)
