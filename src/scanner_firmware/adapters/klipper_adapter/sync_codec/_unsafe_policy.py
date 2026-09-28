"""Policy-backed unsafe-field checks for scanner-sync command records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from scanner_firmware.adapters.klipper_adapter.sync_codec._errors import (
    ScannerSyncCommandBoundaryError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._scalar_validation import (
    require_bool,
)


POLICY_ARTIFACT_ID = "scanner_sync_command_boundary_policy_v1"
POLICY = json.loads(
    (Path(__file__).with_name("scanner_sync_command_boundary_policy.v1.json")).read_text(
        encoding="utf-8"
    )
)
if POLICY.get("artifact_id") != POLICY_ARTIFACT_ID:
    raise RuntimeError("scanner-sync command boundary policy artifact mismatch")

CANONICAL_COMMANDS = frozenset(POLICY["canonical_commands"])
COMMAND_ALIASES = {
    alias: str(details["canonical"])
    for alias, details in POLICY.get("legacy_aliases", {}).items()
    if isinstance(details, Mapping)
}
ALIAS_CONTEXT_FIELDS = {
    alias: str(details["allowed_only_when_context_field"])
    for alias, details in POLICY.get("legacy_aliases", {}).items()
    if isinstance(details, Mapping)
}
FORBIDDEN_COMMANDS = frozenset(POLICY.get("forbidden_commands", ()))
FORBIDDEN_RECORD_KEYS = frozenset(POLICY.get("forbidden_record_keys", ()))
BOOLEAN_SAFETY_FIELDS = frozenset(POLICY.get("boolean_safety_fields", ()))
STOP_REASONS = frozenset(POLICY.get("stop_reasons", ()))
PROTOCOL_VERSION = str(POLICY.get("protocol_version", "1.0.0"))


def validate_hardware_outputs(
    record: Mapping[str, Any],
    record_index: int,
    *,
    dry_run: bool,
    replay: bool,
    allow_hardware_outputs: bool,
) -> None:
    if "hardware_outputs_enabled" not in record:
        return
    value = record["hardware_outputs_enabled"]
    require_bool("hardware_outputs_enabled", value, record_index=record_index)
    if value and (dry_run or replay or not allow_hardware_outputs):
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: hardware_outputs_enabled must be false "
            "for replay/dry-run command validation"
        )


def reject_unsafe_fields(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_str = str(key)
            child_path = f"{path}.{key_str}"
            if key_str in FORBIDDEN_RECORD_KEYS:
                raise ScannerSyncCommandBoundaryError(
                    f"{child_path}: forbidden hardware/runtime field"
                )
            if key_str in BOOLEAN_SAFETY_FIELDS and child is True:
                raise ScannerSyncCommandBoundaryError(
                    f"{child_path}: unsafe hardware output enabled"
                )
            reject_unsafe_fields(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_unsafe_fields(child, f"{path}[{index}]")
