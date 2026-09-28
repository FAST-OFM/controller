"""Static scanner-sync Klipper patch boundary audit.

The audit reads patch text that has already been captured in this repository.
It does not import Klipper, edit a live checkout, open serial ports, send
commands, toggle outputs, command motion, trigger cameras, drive LEDs or flash
firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from scanner_firmware.adapters.klipper_adapter.readiness.config_parser import (
    ScannerSyncConfigError,
    parse_scanner_sync_config,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    COMMAND_BINDINGS,
    RESPONSE_BINDINGS,
    SCANNER_SYNC_CONFIG_FORMAT,
)


FORBIDDEN_HARDWARE_OUTPUT_SNIPPETS = (
    "gpio_out_setup",
    "gpio_out_write",
    "gpio_out_toggle",
    "queue_digital_out",
    "queue_pwm_out",
    "stepper_stop_on_trigger",
    "command_queue_step",
)


@dataclass(frozen=True)
class KlipperPatchBoundaryAudit:
    """Result of a passive scanner-sync patch boundary audit."""

    disabled_by_default: bool
    metadata_only_mode_enforced: bool
    hardware_outputs_forced_disabled: bool
    patch_config_metadata_only: bool
    patch_config_hardware_outputs_disabled: bool
    patch_config_safety_fields_present: bool
    config_format_present: bool
    missing_command_formats: tuple[str, ...]
    missing_response_formats: tuple[str, ...]
    configured_output_keys: tuple[str, ...]
    forbidden_hardware_snippets: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.blockers


def audit_klipper_patch_boundary(patch_text: str) -> KlipperPatchBoundaryAudit:
    """Audit a Klipper scanner-sync patch for software-only safety boundaries."""

    added_source = _joined_added_source(patch_text)
    config_audit = _config_audit_from_patch(patch_text)
    missing_commands = tuple(
        binding.msgformat
        for binding in COMMAND_BINDINGS
        if binding.msgformat not in added_source
    )
    missing_responses = tuple(
        binding.msgformat
        for binding in RESPONSE_BINDINGS
        if binding.msgformat not in added_source
    )
    forbidden_snippets = tuple(
        snippet for snippet in FORBIDDEN_HARDWARE_OUTPUT_SNIPPETS if snippet in patch_text
    )
    disabled_by_default = _has_disabled_enable_default(added_source)
    metadata_only_mode_enforced = _has_metadata_only_mode_enforcement(added_source)
    hardware_outputs_forced_disabled = _has_hardware_outputs_disabled_enforcement(
        added_source,
    )
    config_format_present = SCANNER_SYNC_CONFIG_FORMAT in added_source

    blockers: list[str] = []
    if not disabled_by_default:
        blockers.append("scanner_sync_enable_default_not_false")
    if not metadata_only_mode_enforced:
        blockers.append("metadata_only_mode_not_enforced")
    if not hardware_outputs_forced_disabled:
        blockers.append("hardware_outputs_not_forced_disabled")
    if not config_audit.metadata_only:
        blockers.append("scanner_sync_config_metadata_only_required")
    if not config_audit.hardware_outputs_disabled:
        blockers.append("scanner_sync_config_hardware_outputs_enabled")
    if not config_audit.safety_fields_present:
        blockers.append("scanner_sync_config_safety_fields_missing")
    if not config_format_present:
        blockers.append("scanner_sync_mcu_config_format_missing")
    if missing_commands:
        blockers.append("scanner_sync_mcu_commands_missing")
    if missing_responses:
        blockers.append("scanner_sync_response_formats_missing")
    if config_audit.error is not None:
        blockers.append("scanner_sync_config_patch_malformed")
    if config_audit.configured_output_keys:
        blockers.append("scanner_sync_output_pins_configured")
    if forbidden_snippets:
        blockers.append("forbidden_hardware_output_api_present")

    return KlipperPatchBoundaryAudit(
        disabled_by_default=disabled_by_default,
        metadata_only_mode_enforced=metadata_only_mode_enforced,
        hardware_outputs_forced_disabled=hardware_outputs_forced_disabled,
        patch_config_metadata_only=config_audit.metadata_only,
        patch_config_hardware_outputs_disabled=config_audit.hardware_outputs_disabled,
        patch_config_safety_fields_present=config_audit.safety_fields_present,
        config_format_present=config_format_present,
        missing_command_formats=missing_commands,
        missing_response_formats=missing_responses,
        configured_output_keys=config_audit.configured_output_keys,
        forbidden_hardware_snippets=forbidden_snippets,
        blockers=tuple(blockers),
    )


def _joined_added_source(patch_text: str) -> str:
    """Join added patch lines so split C/Python strings are searchable."""

    added_lines = [
        line[1:].strip()
        for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "".join(added_lines).replace('"', "").replace("'", "")


@dataclass(frozen=True)
class _PatchConfigAudit:
    metadata_only: bool
    hardware_outputs_disabled: bool
    safety_fields_present: bool
    configured_output_keys: tuple[str, ...]
    error: Optional[ScannerSyncConfigError]


def _config_audit_from_patch(patch_text: str) -> _PatchConfigAudit:
    added_text = _scanner_sync_config_from_patch(patch_text)
    try:
        config = parse_scanner_sync_config(added_text)
    except ScannerSyncConfigError as exc:
        return _PatchConfigAudit(
            metadata_only=False,
            hardware_outputs_disabled=False,
            safety_fields_present=False,
            configured_output_keys=(),
            error=exc,
        )
    if not config.section_present:
        return _PatchConfigAudit(
            metadata_only=True,
            hardware_outputs_disabled=True,
            safety_fields_present=True,
            configured_output_keys=(),
            error=None,
        )
    return _PatchConfigAudit(
        metadata_only=config.metadata_only_mode,
        hardware_outputs_disabled=not config.hardware_outputs_enabled,
        safety_fields_present=config.safety_fields_present,
        configured_output_keys=config.configured_output_keys,
        error=None,
    )


def _scanner_sync_config_from_patch(patch_text: str) -> str:
    lines: list[str] = []
    in_section = False
    for line in patch_text.splitlines():
        if not in_section:
            if line == "+[scanner_sync]":
                in_section = True
                lines.append(line[1:])
            continue
        if not line.startswith("+") or line.startswith("+++"):
            break
        config_line = line[1:]
        stripped = config_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            break
        lines.append(config_line)
    return "\n".join(lines)


def _has_disabled_enable_default(added_source: str) -> bool:
    return "getboolean(enable,False)" in _compact(added_source)


def _has_metadata_only_mode_enforcement(added_source: str) -> bool:
    compact = _compact(added_source)
    return (
        "get(mode,metadata_only)" in compact
        and "self.mode!=metadata_only" in compact
        and "scanner_synconlysupportsmetadata_onlymode" in compact
    )


def _has_hardware_outputs_disabled_enforcement(added_source: str) -> bool:
    compact = _compact(added_source)
    return (
        "getboolean(hardware_outputs_enabled,False)" in compact
        and "ifself.hardware_outputs_enabled:" in compact
        and "hardware_outputs_enabled=0" in compact
    )


def _compact(text: str) -> str:
    return "".join(text.split())
