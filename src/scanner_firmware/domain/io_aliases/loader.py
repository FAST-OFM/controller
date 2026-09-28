"""Strict loader for already-parsed logical IO alias registry mappings.

The loader reads YAML/JSON-like data supplied by an outer adapter. It does not
open files, bind controller pins, toggle GPIO, command motion, trigger cameras
or drive LED outputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scanner_firmware.domain.io_aliases.errors import IoAliasRegistryError
from scanner_firmware.domain.io_aliases.pin_ref import parse_pin_reference
from scanner_firmware.domain.io_aliases.registry import IoAliasRegistry
from scanner_firmware.domain.io_aliases.types import (
    IoAliasEntry,
    OutputState,
    RejectedActivePin,
)


ROOT_FIELDS = frozenset(
    (
        "board_id",
        "hardware_outputs_armed",
        "aliases",
        "rejected_active_pins",
    )
)
ALIAS_FIELDS = frozenset(
    (
        "name",
        "pin",
        "status",
        "output_state",
        "evidence",
        "load_status",
        "active_alias_reviewed",
        "notes",
    )
)
OUTPUT_STATE_FIELDS = frozenset(("active_value", "inactive_value"))
REJECTED_PIN_FIELDS = frozenset(("pin", "reason"))


def load_io_alias_registry_from_mapping(data: Mapping[str, Any]) -> IoAliasRegistry:
    """Build a validated IO alias registry from an already-read mapping."""

    root = _require_mapping("io_alias_registry", data)
    _reject_unknown_fields("io_alias_registry", root, ROOT_FIELDS)
    _require_fields("io_alias_registry", root, ROOT_FIELDS)

    return IoAliasRegistry(
        board_id=_require_string("board_id", root["board_id"]),
        hardware_outputs_armed=_require_bool(
            "hardware_outputs_armed",
            root["hardware_outputs_armed"],
        ),
        aliases=_load_aliases(root["aliases"]),
        rejected_active_pins=_load_rejected_active_pins(root["rejected_active_pins"]),
    )


def _load_aliases(value: object) -> tuple[IoAliasEntry, ...]:
    sequence = _require_sequence("aliases", value)
    return tuple(_load_alias(item, index=index) for index, item in enumerate(sequence))


def _load_alias(value: object, *, index: int) -> IoAliasEntry:
    name = f"aliases[{index}]"
    data = _require_mapping(name, value)
    _reject_unknown_fields(name, data, ALIAS_FIELDS)
    required = frozenset(("name", "pin", "status", "output_state", "evidence"))
    _require_fields(name, data, required)
    return IoAliasEntry(
        name=_require_string(f"{name}.name", data["name"]),
        pin=parse_pin_reference(data["pin"], field_name=f"{name}.pin"),
        status=data["status"],
        output_state=_load_output_state(data["output_state"], field_name=f"{name}.output_state"),
        evidence=_require_string(f"{name}.evidence", data["evidence"]),
        load_status=data.get("load_status", "unknown"),
        active_alias_reviewed=_optional_bool(
            f"{name}.active_alias_reviewed",
            data.get("active_alias_reviewed", False),
        ),
        notes=_optional_string_tuple(f"{name}.notes", data.get("notes", ())),
    )


def _load_output_state(value: object, *, field_name: str) -> OutputState:
    data = _require_mapping(field_name, value)
    _reject_unknown_fields(field_name, data, OUTPUT_STATE_FIELDS)
    _require_fields(field_name, data, OUTPUT_STATE_FIELDS)
    return OutputState(
        active_value=data["active_value"],
        inactive_value=data["inactive_value"],
    )


def _load_rejected_active_pins(value: object) -> tuple[RejectedActivePin, ...]:
    sequence = _require_sequence("rejected_active_pins", value)
    return tuple(
        _load_rejected_active_pin(item, index=index) for index, item in enumerate(sequence)
    )


def _load_rejected_active_pin(value: object, *, index: int) -> RejectedActivePin:
    name = f"rejected_active_pins[{index}]"
    data = _require_mapping(name, value)
    _reject_unknown_fields(name, data, REJECTED_PIN_FIELDS)
    _require_fields(name, data, REJECTED_PIN_FIELDS)
    return RejectedActivePin(
        pin=parse_pin_reference(data["pin"], field_name=f"{name}.pin"),
        reason=_require_string(f"{name}.reason", data["reason"]),
    )


def _require_mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IoAliasRegistryError(f"{name} must be a mapping")
    return value


def _require_sequence(name: str, value: object) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise IoAliasRegistryError(f"{name} must be a sequence")
    return value


def _require_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise IoAliasRegistryError(f"{name} must be a non-empty string")
    return value


def _require_bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise IoAliasRegistryError(f"{name} must be a boolean")
    return value


def _optional_bool(name: str, value: object) -> bool:
    return _require_bool(name, value)


def _optional_string_tuple(name: str, value: object) -> tuple[str, ...]:
    sequence = _require_sequence(name, value)
    output = []
    for index, item in enumerate(sequence):
        output.append(_require_string(f"{name}[{index}]", item))
    return tuple(output)


def _require_fields(name: str, data: Mapping[str, Any], required: frozenset[str]) -> None:
    missing = sorted(required.difference(data))
    if missing:
        raise IoAliasRegistryError(f"{name} missing required field(s): {', '.join(missing)}")


def _reject_unknown_fields(name: str, data: Mapping[str, Any], allowed: frozenset[str]) -> None:
    field_names = set()
    for key in data:
        if not isinstance(key, str):
            raise IoAliasRegistryError(f"{name} field names must be strings")
        field_names.add(key)
    unknown = sorted(field_names.difference(allowed))
    if unknown:
        raise IoAliasRegistryError(f"{name} unknown field(s): {', '.join(unknown)}")
