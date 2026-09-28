"""Scan preflight validation helpers."""

from __future__ import annotations

from scanner_firmware.planning.scan_preflight.axes import Axis, REQUIRED_SCAN_AXES
from scanner_firmware.planning.scan_preflight.decisions import (
    HOMING_FEASIBILITY_STATUSES,
    ScanPreflightError,
    ScanPreflightInput,
)


def validate_preflight(preflight: ScanPreflightInput) -> None:
    if not isinstance(preflight.dry_run, bool):
        raise ScanPreflightError("dry_run must be a boolean")
    if not isinstance(preflight.hardware_outputs_enabled, bool):
        raise ScanPreflightError("hardware_outputs_enabled must be a boolean")
    for name, value in (
        ("soft_limits_configured", preflight.soft_limits_configured),
        ("scan_roi_within_limits", preflight.scan_roi_within_limits),
        ("led_pattern_valid", preflight.led_pattern_valid),
        ("camera_trigger_config_valid", preflight.camera_trigger_config_valid),
        ("coordinate_source_valid", preflight.coordinate_source_valid),
        ("homing_enabled", preflight.homing_enabled),
        ("z_policy_configured", preflight.z_policy_configured),
    ):
        if not isinstance(value, bool):
            raise ScanPreflightError(f"{name} must be a boolean")
    validate_axes("required_axes", preflight.required_axes)
    validate_axes("homed_axes", preflight.homed_axes)
    if set(preflight.required_axes) != set(REQUIRED_SCAN_AXES):
        raise ScanPreflightError("scan preflight requires X, Y and Z axes")
    if len(preflight.required_axes) != len(REQUIRED_SCAN_AXES):
        raise ScanPreflightError("required_axes must not contain duplicates")
    if preflight.homing_feasibility_status not in HOMING_FEASIBILITY_STATUSES:
        raise ScanPreflightError(
            "homing_feasibility_status must be implemented, not_implemented or unknown"
        )


def validate_axes(name: str, axes: tuple[Axis, ...]) -> None:
    if not isinstance(axes, tuple):
        raise ScanPreflightError(f"{name} must be a tuple")
    for axis in axes:
        if axis not in REQUIRED_SCAN_AXES:
            raise ScanPreflightError(f"{name} contains unsupported axis: {axis}")


def blocking_precondition_errors(preflight: ScanPreflightInput) -> tuple[str, ...]:
    errors: list[str] = []
    if not preflight.soft_limits_configured:
        errors.append("soft limits must be configured before scan start")
    if not preflight.scan_roi_within_limits:
        errors.append("scan ROI must be within configured soft limits")
    if not preflight.led_pattern_valid:
        errors.append("LED pattern must be valid before scan start")
    if not preflight.camera_trigger_config_valid:
        errors.append("camera trigger config must be valid before scan start")
    if not preflight.coordinate_source_valid:
        errors.append("coordinate source must be valid before scan start")
    if not preflight.z_policy_configured:
        errors.append("Z policy must be configured before scan start")
    return tuple(errors)
