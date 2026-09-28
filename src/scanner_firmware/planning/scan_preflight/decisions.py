"""Scan preflight value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.planning.scan_preflight.axes import Axis


HomingFeasibilityStatus = Literal["implemented", "not_implemented", "unknown"]
HOMING_FEASIBILITY_STATUSES: tuple[HomingFeasibilityStatus, ...] = (
    "implemented",
    "not_implemented",
    "unknown",
)


@dataclass(frozen=True)
class ScanPreflightInput:
    """Parsed scan preflight state supplied by simulator orchestration."""

    required_axes: tuple[Axis, ...]
    homed_axes: tuple[Axis, ...]
    dry_run: bool
    hardware_outputs_enabled: bool
    soft_limits_configured: bool = True
    scan_roi_within_limits: bool = True
    led_pattern_valid: bool = True
    camera_trigger_config_valid: bool = True
    coordinate_source_valid: bool = True
    homing_feasibility_status: HomingFeasibilityStatus = "implemented"
    homing_enabled: bool = True
    z_policy_configured: bool = True


@dataclass(frozen=True)
class ScanPreflightDecision:
    accepted: bool
    missing_axes: tuple[Axis, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class ScanPreflightError(ValueError):
    """Raised when scan preflight input is malformed."""
