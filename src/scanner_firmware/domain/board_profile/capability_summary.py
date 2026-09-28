"""Software-only board-profile capability summary.

The summary reads already documented board-profile metadata. It does not probe
hardware, infer unknown electrical facts, toggle outputs, open controller
connections, command motion or flash firmware.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

import yaml

from scanner_firmware.domain.board_profile.kinematics import (
    UNKNOWN,
    MotionKinematics,
    derive_motion_kinematics,
)
from scanner_firmware.domain.board_profile.state_machine import (
    BoardProfileState,
    profile_state,
)
from scanner_firmware.domain.board_profile.validator import validate_board_profile


BOARD_PROFILE_CAPABILITY_SUMMARY_SCHEMA_ID = "board_profile_capability_summary_v1"
BOARD_PROFILE_CAPABILITY_SUMMARY_SCHEMA_VERSION = "1.0.0"
PINMAP_VERIFIED_STATES = frozenset(("pinmap_verified", "hardware_tested"))


BoardProfileCapability = Literal[
    "motion_kinematics",
    "camera_or_sync_trigger_candidate",
    "led_gate_candidates",
    "homing_config_disabled",
    "controller_discovery_static_only",
]
ControllerDiscoveryStatus = Literal["unknown", "not_run", "static_only", "ready"]


class BoardProfileCapabilitySummaryError(ValueError):
    """Raised when a board-profile capability summary cannot be built."""


@dataclass(frozen=True)
class ControllerDiscoverySummary:
    controller_kind: str = UNKNOWN
    status: ControllerDiscoveryStatus = "unknown"
    printer_config_present: bool | str = UNKNOWN
    hardware_outputs_enabled: bool = False
    live_access_performed: bool = False

    def __post_init__(self) -> None:
        _required_string(self.controller_kind, "controller_kind")
        if self.status not in ("unknown", "not_run", "static_only", "ready"):
            raise BoardProfileCapabilitySummaryError(
                "controller discovery status must be unknown, not_run, static_only or ready"
            )
        if not isinstance(self.hardware_outputs_enabled, bool):
            raise BoardProfileCapabilitySummaryError(
                "controller discovery hardware_outputs_enabled must be a bool"
            )
        if not isinstance(self.live_access_performed, bool):
            raise BoardProfileCapabilitySummaryError(
                "controller discovery live_access_performed must be a bool"
            )
        if self.hardware_outputs_enabled:
            raise BoardProfileCapabilitySummaryError(
                "board-profile capability summaries cannot enable hardware outputs"
            )
        if self.live_access_performed:
            raise BoardProfileCapabilitySummaryError(
                "board-profile capability summaries cannot consume live hardware access"
            )
        if not isinstance(self.printer_config_present, bool | str):
            raise BoardProfileCapabilitySummaryError(
                "printer_config_present must be a bool or 'unknown'"
            )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "controller_kind": self.controller_kind,
            "status": self.status,
            "printer_config_present": self.printer_config_present,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_access_performed": self.live_access_performed,
        }


@dataclass(frozen=True)
class PinCapability:
    alias: str
    pin: str
    status: str
    capability: str
    source_signal: str | None = None
    output_type: str | None = None
    measured_high_v: float | str | None = None
    load_tested: bool | None = None
    boot_default_state: str = UNKNOWN

    @property
    def is_unknown(self) -> bool:
        return self.pin == UNKNOWN

    @property
    def is_blocked(self) -> bool:
        if self.pin == UNKNOWN:
            return True
        if self.load_tested is False:
            return True
        if self.boot_default_state == UNKNOWN:
            return True
        return False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "pin": self.pin,
            "status": self.status,
            "capability": self.capability,
            "source_signal": self.source_signal,
            "output_type": self.output_type,
            "measured_high_v": self.measured_high_v,
            "load_tested": self.load_tested,
            "boot_default_state": self.boot_default_state,
            "blocked": self.is_blocked,
        }


@dataclass(frozen=True)
class BoardProfileCapabilitySummary:
    board: str
    profile_state: BoardProfileState
    profile_valid: bool
    capabilities: tuple[BoardProfileCapability, ...]
    motion_kinematics: MotionKinematics
    camera_or_sync_trigger: PinCapability
    led_outputs: tuple[PinCapability, ...]
    controller_discovery: ControllerDiscoverySummary
    homing_status: str
    homing_config_enabled: bool | str
    open_unknowns: tuple[str, ...]
    blockers: tuple[str, ...]
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False

    @property
    def ready_for_output_simulation(self) -> bool:
        return not any(output.pin == UNKNOWN for output in self.led_outputs)

    @property
    def ready_for_live_hardware(self) -> bool:
        return False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_id": BOARD_PROFILE_CAPABILITY_SUMMARY_SCHEMA_ID,
            "schema_version": BOARD_PROFILE_CAPABILITY_SUMMARY_SCHEMA_VERSION,
            "board": self.board,
            "profile_state": self.profile_state,
            "profile_valid": self.profile_valid,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "ready_for_output_simulation": self.ready_for_output_simulation,
            "ready_for_live_hardware": self.ready_for_live_hardware,
            "capabilities": list(self.capabilities),
            "motion_kinematics": _motion_kinematics_dict(self.motion_kinematics),
            "camera_or_sync_trigger": self.camera_or_sync_trigger.to_json_dict(),
            "led_outputs": [output.to_json_dict() for output in self.led_outputs],
            "controller_discovery": self.controller_discovery.to_json_dict(),
            "homing": {
                "status": self.homing_status,
                "config_enabled": self.homing_config_enabled,
            },
            "open_unknowns": list(self.open_unknowns),
            "blockers": list(self.blockers),
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_json_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def load_board_profile_capability_summary(
    path: str | Path,
) -> BoardProfileCapabilitySummary:
    """Load a YAML board profile and build a software-only capability summary."""

    profile = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(profile, Mapping):
        raise BoardProfileCapabilitySummaryError("board profile must be a mapping")
    return build_board_profile_capability_summary(profile)


def build_board_profile_capability_summary(
    profile: Mapping[str, object],
    *,
    controller_discovery: ControllerDiscoverySummary | None = None,
) -> BoardProfileCapabilitySummary:
    """Build a summary from documented profile metadata only."""

    validate_board_profile(profile)

    state = profile_state(profile)
    pins = _mapping(profile.get("pins"), "pins")
    safety_status = _optional_mapping(profile.get("safety_status"), "safety_status")
    homing_status = _optional_mapping(safety_status.get("homing"), "safety_status.homing")
    led_status = _optional_mapping(
        safety_status.get("led_outputs"),
        "safety_status.led_outputs",
    )

    trigger = _trigger_capability(pins, safety_status)
    led_outputs = tuple(
        _led_capability(alias, pins, led_status)
        for alias in ("led_green", "led_red", "led_white")
    )
    discovery = controller_discovery or ControllerDiscoverySummary()
    homing_config_enabled = _value_or_unknown(homing_status.get("config_enabled"))
    capabilities = _capabilities(
        trigger,
        led_outputs,
        homing_config_enabled,
        discovery,
    )
    blockers = _blockers(
        state=state,
        trigger=trigger,
        led_outputs=led_outputs,
        controller_discovery=discovery,
        homing_status=homing_status,
        homing_config_enabled=homing_config_enabled,
    )

    return BoardProfileCapabilitySummary(
        board=_required_string(profile.get("board"), "board"),
        profile_state=state,
        profile_valid=True,
        capabilities=capabilities,
        motion_kinematics=derive_motion_kinematics(profile),
        camera_or_sync_trigger=trigger,
        led_outputs=led_outputs,
        controller_discovery=discovery,
        homing_status=_string_value(homing_status.get("status"), default=UNKNOWN),
        homing_config_enabled=homing_config_enabled,
        open_unknowns=_string_tuple(profile.get("open_unknowns"), "open_unknowns"),
        blockers=blockers,
    )


def _trigger_capability(
    pins: Mapping[str, object],
    safety_status: Mapping[str, object],
) -> PinCapability:
    trigger_status = _optional_mapping(
        safety_status.get("camera_or_sync_trigger"),
        "safety_status.camera_or_sync_trigger",
    )
    return PinCapability(
        alias="camera_or_sync_trigger",
        pin=_string_value(pins.get("camera_or_sync_trigger"), default=UNKNOWN),
        status=_string_value(trigger_status.get("status"), default=UNKNOWN),
        capability="camera_or_sync_trigger_candidate",
        source_signal=_optional_string(trigger_status.get("source_signal")),
        output_type=_optional_string(trigger_status.get("output_type")),
        measured_high_v=_optional_number_or_string(trigger_status.get("measured_high_v")),
        load_tested=_optional_bool(trigger_status.get("load_tested")),
        boot_default_state=_string_value(trigger_status.get("boot_default_state"), default=UNKNOWN),
    )


def _led_capability(
    alias: str,
    pins: Mapping[str, object],
    led_status: Mapping[str, object],
) -> PinCapability:
    status = _optional_mapping(led_status.get(alias), f"safety_status.led_outputs.{alias}")
    return PinCapability(
        alias=alias,
        pin=_string_value(pins.get(alias), default=UNKNOWN),
        status=_string_value(status.get("status"), default=led_status.get("status", UNKNOWN)),
        capability="led_gate_candidate",
        source_signal=_optional_string(status.get("source_signal")),
        output_type=_optional_string(status.get("output_type")),
        measured_high_v=_optional_number_or_string(status.get("measured_high_v")),
        load_tested=_optional_bool(status.get("load_tested")),
        boot_default_state=_string_value(status.get("boot_default_state"), default=UNKNOWN),
    )


def _capabilities(
    trigger: PinCapability,
    led_outputs: tuple[PinCapability, ...],
    homing_config_enabled: bool | str,
    controller_discovery: ControllerDiscoverySummary,
) -> tuple[BoardProfileCapability, ...]:
    values: list[BoardProfileCapability] = ["motion_kinematics"]
    if not trigger.is_unknown:
        values.append("camera_or_sync_trigger_candidate")
    if any(not output.is_unknown for output in led_outputs):
        values.append("led_gate_candidates")
    if homing_config_enabled is False:
        values.append("homing_config_disabled")
    if controller_discovery.status == "static_only":
        values.append("controller_discovery_static_only")
    return tuple(values)


def _blockers(
    *,
    state: BoardProfileState,
    trigger: PinCapability,
    led_outputs: tuple[PinCapability, ...],
    controller_discovery: ControllerDiscoverySummary,
    homing_status: Mapping[str, object],
    homing_config_enabled: bool | str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if state not in PINMAP_VERIFIED_STATES:
        blockers.append("pinmap_not_verified")
    if trigger.pin == UNKNOWN:
        blockers.append("camera_or_sync_trigger_unknown")
    if trigger.boot_default_state == UNKNOWN:
        blockers.append("camera_or_sync_trigger_boot_default_unknown")
    for output in led_outputs:
        if output.pin == UNKNOWN:
            blockers.append(f"{output.alias}_pin_unknown")
        if output.load_tested is False:
            blockers.append(f"{output.alias}_load_not_tested")
        if output.boot_default_state == UNKNOWN:
            blockers.append(f"{output.alias}_boot_default_unknown")
    if homing_config_enabled is not True:
        blockers.append("homing_not_enabled")
    if _string_value(homing_status.get("status"), default=UNKNOWN) != "verified":
        blockers.append("homing_not_verified")
    if controller_discovery.status in ("unknown", "not_run"):
        blockers.append("controller_discovery_unknown")
    if controller_discovery.status == "static_only":
        blockers.append("controller_discovery_static_only")
    if controller_discovery.printer_config_present is not True:
        blockers.append("printer_config_not_confirmed")
    return tuple(blockers)


def _motion_kinematics_dict(kinematics: MotionKinematics) -> dict[str, dict[str, Any]]:
    return {
        axis: {
            "motor_full_steps_per_rev": value.motor_full_steps_per_rev,
            "microsteps": value.microsteps,
            "travel_per_rev_mm": _json_number(value.travel_per_rev_mm),
            "steps_per_mm": _json_number(value.steps_per_mm),
            "steps_per_um": _json_number(value.steps_per_um),
        }
        for axis, value in (
            ("x", kinematics.x),
            ("y", kinematics.y),
            ("z", kinematics.z),
        )
    }


def _json_number(value: Fraction | str) -> int | float | str:
    if value == UNKNOWN:
        return UNKNOWN
    if value.denominator == 1:
        return value.numerator
    return float(value)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BoardProfileCapabilitySummaryError(f"{name} must be a mapping")
    return value


def _optional_mapping(value: object, name: str) -> Mapping[str, object]:
    if value is None:
        return {}
    return _mapping(value, name)


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise BoardProfileCapabilitySummaryError(f"{name} must be a non-empty string")
    return value


def _string_value(value: object, *, default: object) -> str:
    if value is None:
        value = default
    if not isinstance(value, str):
        return str(value)
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BoardProfileCapabilitySummaryError("expected string or null")
    return value


def _optional_number_or_string(value: object) -> float | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise BoardProfileCapabilitySummaryError("expected number, string or null")
    if isinstance(value, int | float | str):
        return value
    raise BoardProfileCapabilitySummaryError("expected number, string or null")


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise BoardProfileCapabilitySummaryError("expected bool or null")
    return value


def _value_or_unknown(value: object) -> bool | str:
    if isinstance(value, bool):
        return value
    if value is None:
        return UNKNOWN
    if isinstance(value, str):
        return value
    raise BoardProfileCapabilitySummaryError("expected bool, string or null")


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise BoardProfileCapabilitySummaryError(f"{name} must be a sequence")
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise BoardProfileCapabilitySummaryError(f"{name} entries must be strings")
        output.append(item)
    return tuple(output)
