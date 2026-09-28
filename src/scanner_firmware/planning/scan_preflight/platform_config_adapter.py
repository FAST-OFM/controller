"""Build scan preflight inputs from platform configuration objects."""

from __future__ import annotations

from scanner_firmware.planning.scan_preflight.axes import REQUIRED_SCAN_AXES
from scanner_firmware.planning.scan_preflight.decisions import ScanPreflightInput


def scan_preflight_input_from_platform_config(config: object) -> ScanPreflightInput:
    """Build preflight input from a validated platform config object.

    This planning-layer adapter intentionally uses the config object's public
    attributes instead of importing the domain type. That keeps
    ``platform_config`` from depending on this planning package at module
    import time while preserving the existing aggregate workflow.
    """

    return ScanPreflightInput(
        required_axes=REQUIRED_SCAN_AXES,
        homed_axes=config.motion.homed_axes,
        dry_run=config.scan_recipe.dry_run,
        hardware_outputs_enabled=config.io.hardware_outputs_armed,
        soft_limits_configured=config.motion.soft_limits_configured,
        scan_roi_within_limits=config.motion.scan_roi_within_limits,
        led_pattern_valid=config.io.led_pattern_valid,
        camera_trigger_config_valid=config.io.camera_trigger_config_valid,
        coordinate_source_valid=(
            config.motion.coordinate_source_valid
            and config.io.valid_for_preflight
        ),
        homing_feasibility_status=config.motion.homing_feasibility_status,
        homing_enabled=config.motion.homing_enabled,
        z_policy_configured=config.scan_recipe.z_policy_valid,
    )
