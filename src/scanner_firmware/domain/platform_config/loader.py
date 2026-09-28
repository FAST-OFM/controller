"""Strict software-only loader for already-parsed platform config mappings.

This module consumes YAML/JSON-like mappings that were already read by an
outer adapter. It does not open files, access hardware, configure cameras,
toggle outputs, command motion or contact a controller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scanner_firmware.domain.platform_config.model import (
    IoConfig,
    MotionConfig,
    PlatformConfigError,
    PlatformProfile,
    ScanRecipeConfig,
    ScannerPlatformConfig,
)


TOP_LEVEL_FIELDS = frozenset(("profile", "motion", "io", "scan_recipe"))
PROFILE_FIELDS = frozenset(
    ("board_id", "controller_kind", "printer_config_present", "safe_defaults_declared")
)
MOTION_FIELDS = frozenset(
    (
        "homed_axes",
        "soft_limits_configured",
        "scan_roi_within_limits",
        "coordinate_source_valid",
        "homing_feasibility_status",
        "homing_enabled",
    )
)
IO_FIELDS = frozenset(
    (
        "camera_trigger_config_valid",
        "led_pattern_valid",
        "inactive_output_states_declared",
        "output_ownership_unambiguous",
        "hardware_outputs_armed",
    )
)
SCAN_RECIPE_FIELDS = frozenset(("dry_run", "requested_scan_mode", "z_policy_valid"))


def load_platform_config_from_mapping(data: Mapping[str, Any]) -> ScannerPlatformConfig:
    """Build a validated scanner platform config from an already-read mapping."""

    root = _require_mapping("platform_config", data)
    _reject_unknown_fields("platform_config", root, TOP_LEVEL_FIELDS)
    _require_fields("platform_config", root, TOP_LEVEL_FIELDS)

    return ScannerPlatformConfig(
        profile=_load_profile(_section(root, "profile")),
        motion=_load_motion(_section(root, "motion")),
        io=_load_io(_section(root, "io")),
        scan_recipe=_load_scan_recipe(_section(root, "scan_recipe")),
    )


def _load_profile(data: Mapping[str, Any]) -> PlatformProfile:
    _reject_unknown_fields("profile", data, PROFILE_FIELDS)
    _require_fields("profile", data, PROFILE_FIELDS)
    return PlatformProfile(
        board_id=data["board_id"],
        controller_kind=data["controller_kind"],
        printer_config_present=data["printer_config_present"],
        safe_defaults_declared=data["safe_defaults_declared"],
    )


def _load_motion(data: Mapping[str, Any]) -> MotionConfig:
    _reject_unknown_fields("motion", data, MOTION_FIELDS)
    _require_fields("motion", data, MOTION_FIELDS)
    return MotionConfig(
        homed_axes=_load_homed_axes(data["homed_axes"]),
        soft_limits_configured=data["soft_limits_configured"],
        scan_roi_within_limits=data["scan_roi_within_limits"],
        coordinate_source_valid=data["coordinate_source_valid"],
        homing_feasibility_status=data["homing_feasibility_status"],
        homing_enabled=data["homing_enabled"],
    )


def _load_io(data: Mapping[str, Any]) -> IoConfig:
    _reject_unknown_fields("io", data, IO_FIELDS)
    _require_fields("io", data, IO_FIELDS)
    return IoConfig(
        camera_trigger_config_valid=data["camera_trigger_config_valid"],
        led_pattern_valid=data["led_pattern_valid"],
        inactive_output_states_declared=data["inactive_output_states_declared"],
        output_ownership_unambiguous=data["output_ownership_unambiguous"],
        hardware_outputs_armed=data["hardware_outputs_armed"],
    )


def _load_scan_recipe(data: Mapping[str, Any]) -> ScanRecipeConfig:
    _reject_unknown_fields("scan_recipe", data, SCAN_RECIPE_FIELDS)
    _require_fields("scan_recipe", data, SCAN_RECIPE_FIELDS)
    return ScanRecipeConfig(
        dry_run=data["dry_run"],
        requested_scan_mode=data["requested_scan_mode"],
        z_policy_valid=data["z_policy_valid"],
    )


def _load_homed_axes(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PlatformConfigError("motion.homed_axes must be a sequence of axis names")
    return tuple(value)


def _section(root: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return _require_mapping(name, root[name])


def _require_mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PlatformConfigError(f"{name} must be a mapping")
    return value


def _require_fields(name: str, data: Mapping[str, Any], required: frozenset[str]) -> None:
    missing = sorted(required.difference(data))
    if missing:
        raise PlatformConfigError(f"{name} missing required field(s): {', '.join(missing)}")


def _reject_unknown_fields(name: str, data: Mapping[str, Any], allowed: frozenset[str]) -> None:
    field_names = set()
    for key in data:
        if not isinstance(key, str):
            raise PlatformConfigError(f"{name} field names must be strings")
        field_names.add(key)
    unknown = sorted(field_names.difference(allowed))
    if unknown:
        raise PlatformConfigError(f"{name} unknown field(s): {', '.join(unknown)}")
