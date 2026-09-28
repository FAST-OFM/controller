"""Passive MKS scanner-sync flash/connectivity gate.

This module validates already-captured review data only. It does not import
Klipper, open serial ports, restart services, send commands, toggle GPIO,
command motion, trigger cameras, drive LEDs or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class MksFlashGatePackageError(ValueError):
    """Raised when flash-gate YAML cannot be parsed."""


@dataclass(frozen=True)
class MksFlashGateValidation:
    """Static validation result for an MKS flash/connectivity gate package."""

    review_ready: bool
    blockers: tuple[str, ...]
    software_only: bool = True
    live_hardware_access_used: bool = False
    can_execute_flash: bool = False


_MISSING = object()

_STRING_FIELDS: tuple[tuple[str, ...], ...] = (
    ("live_pi_hostname",),
    ("klipper_commit",),
    ("captured_artifacts", "klipper_config_path"),
    ("captured_artifacts", "klipper_dictionary_path"),
    ("captured_artifacts", "klipper_binary_path"),
    ("captured_artifacts", "active_printer_cfg_path"),
    ("serial_paths", "mks_by_path"),
    ("firmware_flash", "bootloader_or_flash_method"),
    ("firmware_flash", "exact_command_or_ui_steps"),
    ("rollback", "plan_path"),
    ("rollback", "previous_klipper_ref"),
    ("rollback", "previous_firmware_artifact"),
    ("rollback", "printer_cfg_backup_path"),
)

_BOOL_FIELDS: tuple[tuple[str, ...], ...] = (
    ("connectivity", "klipper_service_active"),
    ("connectivity", "mks_serial_path_present"),
    ("connectivity", "mcu_handshake_restored"),
    ("connectivity", "identify_response_timeout_observed"),
    ("scanner_sync_config", "enable"),
    ("scanner_sync_config", "metadata_only_mode"),
    ("scanner_sync_config", "hardware_outputs_enabled"),
    ("scanner_sync_config", "output_pins_configured"),
)

_REQUIRED_FIELDS = _STRING_FIELDS + _BOOL_FIELDS
_FALSEY_APPROVAL_VALUES = {"", "false", "no", "none", "null", "not approved", "unapproved"}
_APPROVAL_VALUES = {
    "approved",
    "approved_for_live_execution",
    "authorized",
    "true",
    "yes",
    "on",
    "1",
}


def validate_mks_flash_gate_yaml(text: str) -> MksFlashGateValidation:
    """Parse and validate an MKS flash-gate package from YAML text."""

    return validate_mks_flash_gate_package(_load_mks_flash_gate_yaml(text))


def validate_mks_flash_gate_package(payload: Any) -> MksFlashGateValidation:
    """Validate static MKS flash/connectivity gate data."""

    if not isinstance(payload, Mapping):
        return MksFlashGateValidation(
            review_ready=False,
            blockers=("mks_flash_gate_package_must_be_mapping",),
        )

    gate = payload.get("mks_flash_gate")
    if not isinstance(gate, Mapping):
        return MksFlashGateValidation(
            review_ready=False,
            blockers=("mks_flash_gate_missing",),
        )

    blockers: list[str] = []
    blockers.extend(_validate_required_fields(gate))
    blockers.extend(_validate_connectivity_gate(gate))
    blockers.extend(_validate_scanner_sync_safety(gate))
    blockers.extend(_validate_no_approval_claims(payload))
    return MksFlashGateValidation(
        review_ready=not blockers,
        blockers=tuple(_dedupe(blockers)),
    )


def _load_mks_flash_gate_yaml(text: str) -> Any:
    """Load MKS flash-gate YAML without performing hardware or network actions."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional dev dependency
        raise MksFlashGatePackageError("PyYAML is required to parse flash-gate YAML") from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MksFlashGatePackageError("invalid MKS flash-gate YAML") from exc


def _validate_required_fields(gate: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path in _REQUIRED_FIELDS:
        value = _lookup(gate, path)
        field = _field_name(path)
        if value is _MISSING:
            blockers.append(f"{field}_missing")
        elif _contains_unknown(value):
            blockers.append(f"{field}_unknown")

    for path in _STRING_FIELDS:
        value = _lookup(gate, path)
        if value is _MISSING or _contains_unknown(value):
            continue
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"{_field_name(path)}_must_be_nonempty_string")

    for path in _BOOL_FIELDS:
        value = _lookup(gate, path)
        if value is _MISSING or _contains_unknown(value):
            continue
        if not isinstance(value, bool):
            blockers.append(f"{_field_name(path)}_must_be_boolean")

    serial_paths = gate.get("serial_paths")
    if isinstance(serial_paths, Mapping):
        by_id = serial_paths.get("mks_by_id")
        if _contains_unknown(by_id):
            blockers.append("serial_paths.mks_by_id_unknown")
        elif by_id is not None and not isinstance(by_id, str):
            blockers.append("serial_paths.mks_by_id_must_be_string")

    return blockers


def _validate_connectivity_gate(gate: Mapping[str, Any]) -> list[str]:
    connectivity = gate.get("connectivity")
    if not isinstance(connectivity, Mapping):
        return []

    blockers: list[str] = []
    if connectivity.get("klipper_service_active") is not True:
        blockers.append("connectivity.klipper_service_must_be_active")
    if connectivity.get("mks_serial_path_present") is not True:
        blockers.append("connectivity.mks_serial_path_must_be_present")
    if connectivity.get("mcu_handshake_restored") is not True:
        blockers.append("connectivity.mcu_handshake_must_be_restored")
    if connectivity.get("identify_response_timeout_observed") is not False:
        blockers.append("connectivity.identify_response_timeout_unresolved")
    return blockers


def _validate_scanner_sync_safety(gate: Mapping[str, Any]) -> list[str]:
    config = gate.get("scanner_sync_config")
    if not isinstance(config, Mapping):
        return []

    blockers: list[str] = []
    if config.get("enable") is not False:
        blockers.append("scanner_sync_config.enable_must_remain_false_before_flash")
    if config.get("metadata_only_mode") is not True:
        blockers.append("scanner_sync_config.metadata_only_mode_must_be_true")
    if config.get("hardware_outputs_enabled") is not False:
        blockers.append("scanner_sync_config.hardware_outputs_enabled_must_be_false")
    if config.get("output_pins_configured") is not False:
        blockers.append("scanner_sync_config.output_pins_configured_must_be_false")
    return blockers


def _validate_no_approval_claims(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(payload):
        key = path[-1].lower() if path else ""
        if "approved" in key and not _is_effectively_false(value):
            blockers.append(f"{'.'.join(path)}_must_not_claim_approval")
        elif "approval" in key and _value_claims_approval(value):
            blockers.append(f"{'.'.join(path)}_must_not_claim_approval")
        elif key in ("status", "state", "claim") and _value_claims_approval(value):
            blockers.append(f"{'.'.join(path)}_must_not_claim_approval")
    return blockers


def _lookup(root: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = root
    for segment in path:
        if not isinstance(node, Mapping) or segment not in node:
            return _MISSING
        node = node[segment]
    return node


def _contains_unknown(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().upper() == "UNKNOWN"
    if isinstance(value, Mapping):
        return any(_contains_unknown(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unknown(item) for item in value)
    return False


def _field_name(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _walk(node: Any, path: tuple[str, ...] = ()) -> tuple[tuple[tuple[str, ...], Any], ...]:
    items: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            child_path = (*path, str(key))
            items.append((child_path, value))
            items.extend(_walk(value, child_path))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            items.extend(_walk(value, (*path, str(index))))
    return tuple(items)


def _value_claims_approval(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        return normalized in _APPROVAL_VALUES or "approved_for" in normalized
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _is_effectively_false(value: Any) -> bool:
    if value is False or value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _FALSEY_APPROVAL_VALUES
    return False


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)
