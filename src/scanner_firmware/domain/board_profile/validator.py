"""Board profile validation for simulator and documentation checks.

The validator works on parsed board metadata only. It does not import Klipper,
open serial ports, toggle GPIO, flash firmware or access hardware.
"""

from __future__ import annotations

from collections.abc import Mapping

from scanner_firmware.domain.board_profile.kinematics import (
    validate_profile_derived_kinematics,
)
from scanner_firmware.domain.board_profile.state_machine import (
    validate_board_profile_state,
)


REQUIRED_ACTIVE_ALIASES = (
    "camera_or_sync_trigger",
    "led_green",
    "led_red",
    "led_white",
)
UNKNOWN = "unknown"
UNKNOWN_HARDWARE_PLACEHOLDER_VALUES = frozenset(
    (
        "fixme",
        "placeholder",
        "tbd",
        "todo",
        "to_be_determined",
    )
)
UNKNOWN_HARDWARE_PATH_NAMES = frozenset(
    (
        "current",
        "diag",
        "driver",
        "enable",
        "endstop",
        "gpio",
        "home",
        "homing",
        "mechanics",
        "microsteps",
        "motor",
        "pin",
        "pins",
        "rail",
        "step",
        "travel_per_rev",
        "trigger",
        "voltage",
    )
)


class BoardProfileError(ValueError):
    """Raised when board metadata is internally inconsistent."""


def validate_required_aliases(profile: Mapping[str, object]) -> None:
    pins = _mapping(profile.get("pins"), "pins")
    missing = [alias for alias in REQUIRED_ACTIVE_ALIASES if alias not in pins]
    if missing:
        raise BoardProfileError(f"missing required active aliases: {', '.join(missing)}")


def validate_superseded_outputs_not_active(profile: Mapping[str, object]) -> None:
    pins = _mapping(profile.get("pins"), "pins")
    superseded = _superseded_led_candidates(profile)
    active = {alias: pins[alias] for alias in ("led_green", "led_red", "led_white")}

    conflicts = [
        f"{alias}={pin}"
        for alias, pin in active.items()
        if pin != UNKNOWN and pin in superseded
    ]
    if conflicts:
        raise BoardProfileError(
            "active LED aliases use superseded pins: " + ", ".join(conflicts)
        )

    legacy_position_event = pins.get("legacy_position_event_gpio")
    camera_trigger = pins.get("camera_or_sync_trigger")
    if (
        legacy_position_event
        and legacy_position_event != UNKNOWN
        and camera_trigger != UNKNOWN
        and camera_trigger == legacy_position_event
    ):
        raise BoardProfileError(
            "camera_or_sync_trigger must not use legacy_position_event_gpio"
        )


def validate_board_profile(profile: Mapping[str, object]) -> None:
    validate_board_profile_state(profile)
    validate_no_unknown_hardware_placeholders(profile)
    validate_required_aliases(profile)
    validate_superseded_outputs_not_active(profile)
    validate_profile_derived_kinematics(profile)


def validate_no_unknown_hardware_placeholders(profile: Mapping[str, object]) -> None:
    placeholders = tuple(_iter_unknown_hardware_placeholders(profile, path=()))
    if placeholders:
        raise BoardProfileError(
            "unknown hardware values must use explicit 'unknown': "
            + ", ".join(placeholders)
        )


def _superseded_led_candidates(profile: Mapping[str, object]) -> set[str]:
    safety_status = profile.get("safety_status")
    if safety_status is None:
        return set()
    led_outputs = _mapping(
        _mapping(safety_status, "safety_status").get("led_outputs"),
        "safety_status.led_outputs",
    )
    candidates = led_outputs.get("superseded_e0_led_candidates")
    if candidates is None:
        return set()
    candidate_map = _mapping(
        candidates,
        "safety_status.led_outputs.superseded_e0_led_candidates",
    )

    pins: set[str] = set()
    for value in candidate_map.values():
        if isinstance(value, Mapping) and "pin" in value:
            pin = str(value["pin"])
            if pin != UNKNOWN:
                pins.add(pin)
    return pins


def _iter_unknown_hardware_placeholders(
    value: object,
    *,
    path: tuple[str, ...],
) -> tuple[str, ...]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            child_path = (*path, key)
            if _is_unknown_hardware_placeholder(child, child_path):
                paths.append(_format_path(child_path))
            paths.extend(_iter_unknown_hardware_placeholders(child, path=child_path))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            paths.extend(_iter_unknown_hardware_placeholders(child, path=(*path, f"[{index}]")))
    return tuple(paths)


def _is_unknown_hardware_placeholder(value: object, path: tuple[str, ...]) -> bool:
    if not isinstance(value, str):
        return False
    if _normalize_field_name(value) not in UNKNOWN_HARDWARE_PLACEHOLDER_VALUES:
        return False
    return _is_unknown_hardware_path(path)


def _is_unknown_hardware_path(path: tuple[str, ...]) -> bool:
    normalized_parts = tuple(
        _normalize_field_name(part)
        for part in path
        if not part.startswith("[")
    )
    for part in normalized_parts:
        if part in UNKNOWN_HARDWARE_PATH_NAMES:
            return True
        if any(name in part for name in UNKNOWN_HARDWARE_PATH_NAMES):
            return True
    return False


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BoardProfileError(f"{name} must be a mapping")
    return value


def _normalize_field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _format_path(path: tuple[str, ...]) -> str:
    if not path:
        return "<root>"
    output = ""
    for part in path:
        if part.startswith("["):
            output += part
        elif output:
            output += f".{part}"
        else:
            output = part
    return output
