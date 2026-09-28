"""Software-only aggregate platform configuration model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ControllerKind = Literal["klipper_mks", "grblhal", "rp2040_sync", "unknown"]
HomingFeasibilityStatus = Literal["implemented", "not_implemented", "unknown"]
REQUIRED_PLATFORM_AXES: tuple[Literal["X", "Y", "Z"], ...] = ("X", "Y", "Z")
HOMING_FEASIBILITY_STATUSES: tuple[HomingFeasibilityStatus, ...] = (
    "implemented",
    "not_implemented",
    "unknown",
)


class PlatformConfigError(ValueError):
    """Raised when aggregate platform configuration is invalid."""


@dataclass(frozen=True)
class PlatformProfile:
    board_id: str
    controller_kind: ControllerKind
    printer_config_present: bool
    safe_defaults_declared: bool

    def __post_init__(self) -> None:
        _require_non_empty("board_id", self.board_id)
        if self.controller_kind not in ("klipper_mks", "grblhal", "rp2040_sync", "unknown"):
            raise PlatformConfigError(f"unsupported controller_kind: {self.controller_kind}")
        _require_bool("printer_config_present", self.printer_config_present)
        _require_bool("safe_defaults_declared", self.safe_defaults_declared)


@dataclass(frozen=True)
class MotionConfig:
    homed_axes: tuple[str, ...]
    soft_limits_configured: bool
    scan_roi_within_limits: bool
    coordinate_source_valid: bool
    homing_feasibility_status: HomingFeasibilityStatus
    homing_enabled: bool = True

    def __post_init__(self) -> None:
        for axis in self.homed_axes:
            if axis not in REQUIRED_PLATFORM_AXES:
                raise PlatformConfigError(f"unsupported homed axis: {axis}")
        if len(set(self.homed_axes)) != len(self.homed_axes):
            raise PlatformConfigError("homed_axes must not contain duplicates")
        _require_bool("homing_enabled", self.homing_enabled)
        _require_bool("soft_limits_configured", self.soft_limits_configured)
        _require_bool("scan_roi_within_limits", self.scan_roi_within_limits)
        _require_bool("coordinate_source_valid", self.coordinate_source_valid)
        if self.homing_feasibility_status not in HOMING_FEASIBILITY_STATUSES:
            raise PlatformConfigError(
                "homing_feasibility_status must be one of: "
                f"{', '.join(HOMING_FEASIBILITY_STATUSES)}"
            )


@dataclass(frozen=True)
class IoConfig:
    camera_trigger_config_valid: bool
    led_pattern_valid: bool
    inactive_output_states_declared: bool
    output_ownership_unambiguous: bool
    hardware_outputs_armed: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("camera_trigger_config_valid", self.camera_trigger_config_valid),
            ("led_pattern_valid", self.led_pattern_valid),
            ("inactive_output_states_declared", self.inactive_output_states_declared),
            ("output_ownership_unambiguous", self.output_ownership_unambiguous),
            ("hardware_outputs_armed", self.hardware_outputs_armed),
        ):
            _require_bool(name, value)

    @property
    def valid_for_preflight(self) -> bool:
        return (
            self.camera_trigger_config_valid
            and self.led_pattern_valid
            and self.inactive_output_states_declared
            and self.output_ownership_unambiguous
        )


@dataclass(frozen=True)
class ScanRecipeConfig:
    dry_run: bool
    requested_scan_mode: str
    z_policy_valid: bool

    def __post_init__(self) -> None:
        _require_bool("dry_run", self.dry_run)
        _require_non_empty("requested_scan_mode", self.requested_scan_mode)
        _require_bool("z_policy_valid", self.z_policy_valid)


@dataclass(frozen=True)
class ScannerPlatformConfig:
    profile: PlatformProfile
    motion: MotionConfig
    io: IoConfig
    scan_recipe: ScanRecipeConfig

    def to_scan_preflight_input(self):
        """Compatibility wrapper for the planning-layer preflight adapter."""

        from scanner_firmware.planning.scan_preflight.platform_config_adapter import (
            scan_preflight_input_from_platform_config,
        )

        return scan_preflight_input_from_platform_config(self)


def _require_non_empty(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise PlatformConfigError(f"{name} must be a non-empty string")


def _require_bool(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise PlatformConfigError(f"{name} must be a boolean")
