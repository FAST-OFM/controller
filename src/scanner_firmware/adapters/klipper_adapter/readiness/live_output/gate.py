"""Passive stationary AF/timed-output live-output gate validator.

This module validates already-captured review data only. It does not import
Klipper, open serial ports, restart services, send commands, toggle GPIO,
command motion, trigger cameras, drive LEDs or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class LiveOutputGatePackageError(ValueError):
    """Raised when live-output gate YAML cannot be parsed."""


@dataclass(frozen=True)
class LiveOutputGateValidation:
    """Static validation result for a no-motion live-output gate package."""

    review_ready: bool
    blockers: tuple[str, ...]
    software_only: bool = True
    live_hardware_access_used: bool = False
    can_execute_live_output: bool = False
    can_flash_firmware: bool = False


_MISSING = object()

_STRING_FIELDS: tuple[tuple[str, ...], ...] = (
    ("gate_id",),
    ("review_issue_or_pr",),
    ("live_pi_hostname",),
    ("mks_flash_gate_ref",),
    ("firmware_artifact", "commit"),
    ("firmware_artifact", "binary_path"),
    ("firmware_artifact", "dictionary_path"),
    ("firmware_artifact", "patch_artifact_path"),
    ("printer_cfg", "active_printer_cfg_path"),
    ("printer_cfg", "baseline_backup_path"),
    ("rollback", "plan_path"),
    ("rollback", "previous_firmware_artifact"),
    ("rollback", "previous_printer_cfg_backup"),
    ("timed_output_sequence", "command_fixture"),
    ("timed_output_sequence", "all_outputs_off_fixture"),
    ("expected_observation",),
)

_BOOL_FIELDS: tuple[tuple[str, ...], ...] = (
    ("current_state", "klipper_service_active"),
    ("current_state", "mks_serial_path_present"),
    ("current_state", "mcu_handshake_restored"),
    ("current_state", "identify_response_timeout_observed"),
    ("current_scanner_sync_config", "enable"),
    ("current_scanner_sync_config", "hardware_outputs_enabled"),
    ("current_scanner_sync_config", "output_pins_configured"),
    ("proposed_scanner_sync_config", "enable"),
    ("proposed_scanner_sync_config", "hardware_outputs_enabled"),
    ("proposed_scanner_sync_config", "output_pins_configured"),
    ("no_motion_constraints", "motors_commanded"),
    ("no_motion_constraints", "homing_commanded"),
    ("no_motion_constraints", "z_motion_commanded"),
    ("no_motion_constraints", "manual_center_required"),
    ("timed_output_sequence", "status_lifecycle_matches_validators"),
    ("timed_output_sequence", "scanner_sync_stop_guarded_by_active_sequence"),
    ("timed_output_sequence", "all_outputs_off_is_finite_one_shot"),
    ("safe_state", "all_outputs_off_command_available"),
    ("safe_state", "post_stop_safe_state_required"),
    ("live_test_gate", "required"),
    ("live_test_gate", "approved"),
    ("live_test_gate", "executed"),
    ("stop_conditions_reviewed",),
)

_REQUIRED_FIELDS = _STRING_FIELDS + _BOOL_FIELDS + (
    ("proposed_scanner_sync_config", "mode"),
    ("outputs",),
    ("stop_conditions",),
)

_REQUIRED_OUTPUTS = (
    "hq_xvs_sync",
    "led_white_gate",
    "led_red_gate",
    "led_green_gate",
)

_REQUIRED_OUTPUT_STRING_FIELDS = ("pin", "connector", "polarity", "load_path", "default_state")
_LED_OUTPUTS = frozenset({"led_white_gate", "led_red_gate", "led_green_gate"})
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


def validate_live_output_gate_yaml(text: str) -> LiveOutputGateValidation:
    """Parse and validate a live-output gate package from YAML text."""

    return validate_live_output_gate_package(_load_live_output_gate_yaml(text))


def validate_live_output_gate_package(payload: Any) -> LiveOutputGateValidation:
    """Validate static live-output review data without approving execution."""

    if not isinstance(payload, Mapping):
        return LiveOutputGateValidation(
            review_ready=False,
            blockers=("live_output_gate_package_must_be_mapping",),
        )

    gate = payload.get("live_output_gate")
    if not isinstance(gate, Mapping):
        return LiveOutputGateValidation(
            review_ready=False,
            blockers=("live_output_gate_missing",),
        )

    blockers: list[str] = []
    blockers.extend(_validate_required_fields(gate))
    blockers.extend(_validate_current_state(gate))
    blockers.extend(_validate_current_scanner_sync_config(gate))
    blockers.extend(_validate_proposed_scanner_sync_config(gate))
    blockers.extend(_validate_no_motion_constraints(gate))
    blockers.extend(_validate_timed_output_sequence(gate))
    blockers.extend(_validate_safe_state(gate))
    blockers.extend(_validate_live_test_gate(gate))
    blockers.extend(_validate_outputs(gate))
    blockers.extend(_validate_stop_conditions(gate))
    blockers.extend(_validate_no_approval_claims(payload))
    return LiveOutputGateValidation(
        review_ready=not blockers,
        blockers=tuple(_dedupe(blockers)),
    )


def _load_live_output_gate_yaml(text: str) -> Any:
    """Load live-output gate YAML without performing hardware or network actions."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional dev dependency
        raise LiveOutputGatePackageError(
            "PyYAML is required to parse live-output gate YAML"
        ) from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise LiveOutputGatePackageError("invalid live-output gate YAML") from exc


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

    return blockers


def _validate_current_state(gate: Mapping[str, Any]) -> list[str]:
    current = gate.get("current_state")
    if not isinstance(current, Mapping):
        return []

    blockers: list[str] = []
    if current.get("klipper_service_active") is not True:
        blockers.append("current_state.klipper_service_must_be_active")
    if current.get("mks_serial_path_present") is not True:
        blockers.append("current_state.mks_serial_path_must_be_present")
    if current.get("mcu_handshake_restored") is not True:
        blockers.append("current_state.mcu_handshake_must_be_restored")
    if current.get("identify_response_timeout_observed") is not False:
        blockers.append("current_state.identify_response_timeout_unresolved")
    return blockers


def _validate_current_scanner_sync_config(gate: Mapping[str, Any]) -> list[str]:
    config = gate.get("current_scanner_sync_config")
    if not isinstance(config, Mapping):
        return []

    blockers: list[str] = []
    if config.get("enable") is not False:
        blockers.append("current_scanner_sync_config.enable_must_be_false_before_gate")
    if config.get("hardware_outputs_enabled") is not False:
        blockers.append(
            "current_scanner_sync_config.hardware_outputs_enabled_must_be_false"
        )
    if config.get("output_pins_configured") is not False:
        blockers.append("current_scanner_sync_config.output_pins_configured_must_be_false")
    return blockers


def _validate_proposed_scanner_sync_config(gate: Mapping[str, Any]) -> list[str]:
    config = gate.get("proposed_scanner_sync_config")
    if not isinstance(config, Mapping):
        return []

    blockers: list[str] = []
    if config.get("mode") != "timed_output_sequence_bench":
        blockers.append("proposed_scanner_sync_config.mode_must_be_timed_output_sequence_bench")
    if config.get("enable") is not True:
        blockers.append("proposed_scanner_sync_config.enable_must_be_true_for_review")
    if config.get("hardware_outputs_enabled") is not True:
        blockers.append(
            "proposed_scanner_sync_config.hardware_outputs_enabled_must_be_true_for_review"
        )
    if config.get("output_pins_configured") is not True:
        blockers.append(
            "proposed_scanner_sync_config.output_pins_configured_must_be_true_for_review"
        )
    return blockers


def _validate_no_motion_constraints(gate: Mapping[str, Any]) -> list[str]:
    constraints = gate.get("no_motion_constraints")
    if not isinstance(constraints, Mapping):
        return []

    blockers: list[str] = []
    for field in ("motors_commanded", "homing_commanded", "z_motion_commanded"):
        if constraints.get(field) is not False:
            blockers.append(f"no_motion_constraints.{field}_must_be_false")
    if constraints.get("manual_center_required") is not False:
        blockers.append("no_motion_constraints.manual_center_required_must_be_false")
    return blockers


def _validate_timed_output_sequence(gate: Mapping[str, Any]) -> list[str]:
    sequence = gate.get("timed_output_sequence")
    if not isinstance(sequence, Mapping):
        return []

    blockers: list[str] = []
    if sequence.get("status_lifecycle_matches_validators") is not True:
        blockers.append("timed_output_sequence.status_lifecycle_must_match_validators")
    if sequence.get("scanner_sync_stop_guarded_by_active_sequence") is not True:
        blockers.append("timed_output_sequence.stop_must_be_guarded_by_active_sequence")
    if sequence.get("all_outputs_off_is_finite_one_shot") is not True:
        blockers.append("timed_output_sequence.all_outputs_off_must_be_finite_one_shot")
    return blockers


def _validate_safe_state(gate: Mapping[str, Any]) -> list[str]:
    safe_state = gate.get("safe_state")
    if not isinstance(safe_state, Mapping):
        return []

    blockers: list[str] = []
    if safe_state.get("all_outputs_off_command_available") is not True:
        blockers.append("safe_state.all_outputs_off_command_must_be_available")
    if safe_state.get("post_stop_safe_state_required") is not True:
        blockers.append("safe_state.post_stop_safe_state_must_be_required")
    return blockers


def _validate_live_test_gate(gate: Mapping[str, Any]) -> list[str]:
    live_gate = gate.get("live_test_gate")
    if not isinstance(live_gate, Mapping):
        return []

    blockers: list[str] = []
    if live_gate.get("required") is not True:
        blockers.append("live_test_gate.required_must_be_true")
    if live_gate.get("approved") is not False:
        blockers.append("live_test_gate.approved_must_be_false_in_static_package")
    if live_gate.get("executed") is not False:
        blockers.append("live_test_gate.executed_must_be_false_in_static_package")
    return blockers


def _validate_outputs(gate: Mapping[str, Any]) -> list[str]:
    outputs = gate.get("outputs")
    if not isinstance(outputs, Mapping):
        return []

    blockers: list[str] = []
    for output_name in _REQUIRED_OUTPUTS:
        output = outputs.get(output_name)
        if not isinstance(output, Mapping):
            blockers.append(f"outputs.{output_name}_missing")
            continue
        blockers.extend(_validate_output(output_name, output))
    return blockers


def _validate_output(output_name: str, output: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field in _REQUIRED_OUTPUT_STRING_FIELDS:
        value = output.get(field)
        if value is None:
            blockers.append(f"outputs.{output_name}.{field}_missing")
        elif _contains_unknown(value):
            blockers.append(f"outputs.{output_name}.{field}_unknown")
        elif not isinstance(value, str) or not value.strip():
            blockers.append(f"outputs.{output_name}.{field}_must_be_nonempty_string")

    if output.get("verified_loaded_behavior") is not False:
        blockers.append(f"outputs.{output_name}.verified_loaded_behavior_must_be_false")
    if output_name in _LED_OUTPUTS:
        if output.get("external_current_limit_reviewed") is not True:
            blockers.append(
                f"outputs.{output_name}.external_current_limit_reviewed_must_be_true"
            )
    elif output_name == "hq_xvs_sync":
        if output.get("level_shift_reviewed") is not True:
            blockers.append("outputs.hq_xvs_sync.level_shift_reviewed_must_be_true")
    return blockers


def _validate_stop_conditions(gate: Mapping[str, Any]) -> list[str]:
    stop_conditions = gate.get("stop_conditions")
    if not isinstance(stop_conditions, list):
        return []

    blockers: list[str] = []
    observed = {item for item in stop_conditions if isinstance(item, str)}
    for required in (
        "unexpected_output_state",
        "unexpected_current_or_heating",
        "camera_trigger_mismatch",
        "communication_fault",
        "operator_uncertainty",
    ):
        if required not in observed:
            blockers.append(f"stop_conditions.must_include_{required}")
    if gate.get("stop_conditions_reviewed") is not True:
        blockers.append("stop_conditions_reviewed_must_be_true")
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
