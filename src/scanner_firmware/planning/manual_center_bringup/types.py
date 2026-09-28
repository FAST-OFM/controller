"""Manual-centered V1 bring-up gate value objects.

This gate is intentionally separate from scan preflight. Normal scan workflows
still require homing. The V1 bring-up path exists only for an explicitly
reviewed, operator-centered, bounded non-scan hardware test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XYEnvelope:
    center_x_mm: float
    center_y_mm: float
    radius_x_mm: float
    radius_y_mm: float


@dataclass(frozen=True)
class ZFocusEnvelope:
    manual_focus_z_um: float
    min_delta_um: float
    max_delta_um: float


@dataclass(frozen=True)
class PlannedPosition:
    label: str
    x_mm: float
    y_mm: float
    z_um: float | None = None


@dataclass(frozen=True)
class V1ManualCenteredBringupInput:
    procedure_reviewed: bool
    operator_manual_center_confirmed: bool
    live_test_approval_id: str | None
    emergency_stop_available: bool
    stop_conditions_reviewed: bool
    homing_commands_requested: bool
    scan_workflow_requested: bool
    xy_envelope: XYEnvelope | None
    z_focus_envelope: ZFocusEnvelope | None
    planned_positions: tuple[PlannedPosition, ...]
    z_motion_enabled: bool = False
    predictive_z_commands_enabled: bool = False


@dataclass(frozen=True)
class V1ManualCenteredBringupDecision:
    accepted: bool
    checked_positions: int
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class V1ManualCenteredBringupError(ValueError):
    """Raised when V1 manual-centered bring-up input is malformed."""
