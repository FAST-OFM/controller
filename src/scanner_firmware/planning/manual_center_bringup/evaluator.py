"""Evaluate the V1 manual-centered bounded bring-up gate."""

from __future__ import annotations

import math

from scanner_firmware.planning.manual_center_bringup.types import (
    PlannedPosition,
    V1ManualCenteredBringupDecision,
    V1ManualCenteredBringupError,
    V1ManualCenteredBringupInput,
    XYEnvelope,
    ZFocusEnvelope,
)


def evaluate_v1_manual_centered_bringup(
    bringup: V1ManualCenteredBringupInput,
) -> V1ManualCenteredBringupDecision:
    """Return whether a bounded V1 non-scan hardware test may proceed."""

    validate_v1_manual_centered_bringup(bringup)
    errors = list(_required_review_errors(bringup))
    xy_envelope = bringup.xy_envelope
    z_envelope = bringup.z_focus_envelope

    if xy_envelope is None:
        errors.append("XY manual-center envelope must be configured")
    if z_envelope is None:
        errors.append("numeric Z focus envelope must be configured")
    if not bringup.planned_positions:
        errors.append("at least one planned position must be declared")

    if xy_envelope is not None:
        errors.extend(_xy_position_errors(xy_envelope, bringup.planned_positions))
    if z_envelope is not None:
        errors.extend(_z_position_errors(z_envelope, bringup))

    warnings: list[str] = []
    if not bringup.z_motion_enabled:
        warnings.append("Z motion disabled; Z envelope is checked as a readiness constraint only")
    if not bringup.predictive_z_commands_enabled:
        warnings.append("predictive-Z/autofocus estimates may be observed but must not command Z")

    return V1ManualCenteredBringupDecision(
        accepted=not errors,
        checked_positions=len(bringup.planned_positions),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_v1_manual_centered_bringup(bringup: V1ManualCenteredBringupInput) -> None:
    for name, value in (
        ("procedure_reviewed", bringup.procedure_reviewed),
        ("operator_manual_center_confirmed", bringup.operator_manual_center_confirmed),
        ("emergency_stop_available", bringup.emergency_stop_available),
        ("stop_conditions_reviewed", bringup.stop_conditions_reviewed),
        ("homing_commands_requested", bringup.homing_commands_requested),
        ("scan_workflow_requested", bringup.scan_workflow_requested),
        ("z_motion_enabled", bringup.z_motion_enabled),
        ("predictive_z_commands_enabled", bringup.predictive_z_commands_enabled),
    ):
        if not isinstance(value, bool):
            raise V1ManualCenteredBringupError(f"{name} must be a boolean")
    if bringup.live_test_approval_id is not None and not isinstance(
        bringup.live_test_approval_id,
        str,
    ):
        raise V1ManualCenteredBringupError("live_test_approval_id must be string or null")
    if isinstance(bringup.live_test_approval_id, str) and not bringup.live_test_approval_id:
        raise V1ManualCenteredBringupError("live_test_approval_id must be non-empty when set")
    if bringup.xy_envelope is not None:
        _validate_xy_envelope(bringup.xy_envelope)
    if bringup.z_focus_envelope is not None:
        _validate_z_focus_envelope(bringup.z_focus_envelope)
    if not isinstance(bringup.planned_positions, tuple):
        raise V1ManualCenteredBringupError("planned_positions must be a tuple")
    for position in bringup.planned_positions:
        _validate_position(position)


def _required_review_errors(bringup: V1ManualCenteredBringupInput) -> tuple[str, ...]:
    errors: list[str] = []
    if not bringup.procedure_reviewed:
        errors.append("reviewed live-test procedure is required")
    if not bringup.operator_manual_center_confirmed:
        errors.append("operator manual center confirmation is required")
    if bringup.live_test_approval_id is None:
        errors.append("live-test approval id is required")
    if not bringup.emergency_stop_available:
        errors.append("emergency stop must be available")
    if not bringup.stop_conditions_reviewed:
        errors.append("stop conditions must be reviewed")
    if bringup.homing_commands_requested:
        errors.append("homing commands are forbidden in V1 manual-centered bring-up")
    if bringup.scan_workflow_requested:
        errors.append("scan workflow commands are forbidden in V1 manual-centered bring-up")
    return tuple(errors)


def _xy_position_errors(
    envelope: XYEnvelope,
    positions: tuple[PlannedPosition, ...],
) -> tuple[str, ...]:
    errors: list[str] = []
    min_x = envelope.center_x_mm - envelope.radius_x_mm
    max_x = envelope.center_x_mm + envelope.radius_x_mm
    min_y = envelope.center_y_mm - envelope.radius_y_mm
    max_y = envelope.center_y_mm + envelope.radius_y_mm
    for position in positions:
        if not min_x <= position.x_mm <= max_x:
            errors.append(
                f"planned position {position.label!r} x={position.x_mm:g}mm is outside "
                f"manual-center envelope [{min_x:g}, {max_x:g}]mm"
            )
        if not min_y <= position.y_mm <= max_y:
            errors.append(
                f"planned position {position.label!r} y={position.y_mm:g}mm is outside "
                f"manual-center envelope [{min_y:g}, {max_y:g}]mm"
            )
    return tuple(errors)


def _z_position_errors(
    envelope: ZFocusEnvelope,
    bringup: V1ManualCenteredBringupInput,
) -> tuple[str, ...]:
    errors: list[str] = []
    min_z = envelope.manual_focus_z_um + envelope.min_delta_um
    max_z = envelope.manual_focus_z_um + envelope.max_delta_um
    positions_with_z = tuple(
        position for position in bringup.planned_positions if position.z_um is not None
    )
    if bringup.z_motion_enabled and not positions_with_z:
        errors.append("Z motion enabled requires at least one planned Z position")
    for position in positions_with_z:
        assert position.z_um is not None
        if not bringup.z_motion_enabled:
            errors.append(f"planned position {position.label!r} contains Z while Z motion is disabled")
        if not min_z <= position.z_um <= max_z:
            errors.append(
                f"planned position {position.label!r} z={position.z_um:g}um is outside "
                f"manual-focus envelope [{min_z:g}, {max_z:g}]um"
            )
    if bringup.predictive_z_commands_enabled:
        errors.append("predictive-Z command output is forbidden in V1 manual-centered bring-up")
    return tuple(errors)


def _validate_xy_envelope(envelope: XYEnvelope) -> None:
    for name, value in (
        ("center_x_mm", envelope.center_x_mm),
        ("center_y_mm", envelope.center_y_mm),
        ("radius_x_mm", envelope.radius_x_mm),
        ("radius_y_mm", envelope.radius_y_mm),
    ):
        if not _finite_number(value):
            raise V1ManualCenteredBringupError(f"xy_envelope.{name} must be finite")
    if envelope.radius_x_mm <= 0 or envelope.radius_y_mm <= 0:
        raise V1ManualCenteredBringupError("XY envelope radii must be positive")


def _validate_z_focus_envelope(envelope: ZFocusEnvelope) -> None:
    for name, value in (
        ("manual_focus_z_um", envelope.manual_focus_z_um),
        ("min_delta_um", envelope.min_delta_um),
        ("max_delta_um", envelope.max_delta_um),
    ):
        if not _finite_number(value):
            raise V1ManualCenteredBringupError(f"z_focus_envelope.{name} must be finite")
    if not envelope.min_delta_um < 0 < envelope.max_delta_um:
        raise V1ManualCenteredBringupError(
            "Z focus envelope must straddle manual focus with negative and positive deltas"
        )


def _validate_position(position: PlannedPosition) -> None:
    if not isinstance(position, PlannedPosition):
        raise V1ManualCenteredBringupError("planned_positions must contain PlannedPosition")
    if not isinstance(position.label, str) or not position.label:
        raise V1ManualCenteredBringupError("planned position label must be a non-empty string")
    if not _finite_number(position.x_mm):
        raise V1ManualCenteredBringupError("planned position x_mm must be finite")
    if not _finite_number(position.y_mm):
        raise V1ManualCenteredBringupError("planned position y_mm must be finite")
    if position.z_um is not None and not _finite_number(position.z_um):
        raise V1ManualCenteredBringupError("planned position z_um must be finite or null")


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))
