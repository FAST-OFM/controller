"""Klipper protocol dictionary scanner for scanner-sync capabilities.

This module is passive. It parses already-captured Klipper dictionary or log
text and never opens serial ports, sends commands, toggles outputs, commands
motion, triggers cameras, drives LEDs or flashes firmware.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (
    EXPECTED_COMMAND_FORMATS,
    EXPECTED_RESPONSE_FORMATS,
    LiveKlipperScannerSyncObservation,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    SCANNER_SYNC_CONFIG_FORMAT,
)


@dataclass(frozen=True)
class ScannerSyncDictionaryCapabilities:
    """Scanner-sync command and response formats found in Klipper dictionary text."""

    config_format_present: bool
    command_formats: frozenset[str]
    response_formats: frozenset[str]
    missing_command_formats: tuple[str, ...]
    missing_response_formats: tuple[str, ...]

    @property
    def has_all_required_commands(self) -> bool:
        return not self.missing_command_formats

    @property
    def has_all_required_responses(self) -> bool:
        return not self.missing_response_formats


def scan_scanner_sync_dictionary(text: str) -> ScannerSyncDictionaryCapabilities:
    """Find scanner-sync message formats in Klipper dictionary-like text."""

    message_formats = _json_message_formats(text) | _message_format_lines(text)
    config_format_present = SCANNER_SYNC_CONFIG_FORMAT in message_formats
    command_formats = frozenset(
        msgformat for msgformat in EXPECTED_COMMAND_FORMATS if msgformat in message_formats
    )
    response_formats = frozenset(
        msgformat for msgformat in EXPECTED_RESPONSE_FORMATS if msgformat in message_formats
    )
    return ScannerSyncDictionaryCapabilities(
        config_format_present=config_format_present,
        command_formats=command_formats,
        response_formats=response_formats,
        missing_command_formats=tuple(
            msgformat
            for msgformat in EXPECTED_COMMAND_FORMATS
            if msgformat not in command_formats
        ),
        missing_response_formats=tuple(
            msgformat
            for msgformat in EXPECTED_RESPONSE_FORMATS
            if msgformat not in response_formats
        ),
    )


def observation_from_dictionary(
    text: str,
    *,
    host_extra_present: bool,
    config_section_present: bool,
    config_enable: bool,
    mcu_connected: bool,
    response_dispatch_available: bool,
    metadata_only_mode: bool = True,
    hardware_outputs_enabled: bool = False,
    config_safety_fields_present: bool = True,
    configured_output_keys: tuple[str, ...] = (),
    protocol_version: int = 1,
) -> LiveKlipperScannerSyncObservation:
    """Build a live-readiness observation from captured dictionary text."""

    capabilities = scan_scanner_sync_dictionary(text)
    return LiveKlipperScannerSyncObservation(
        host_extra_present=host_extra_present,
        config_section_present=config_section_present,
        config_enable=config_enable,
        mcu_connected=mcu_connected,
        mcu_config_format_present=capabilities.config_format_present,
        mcu_command_formats=capabilities.command_formats,
        registered_response_formats=capabilities.response_formats,
        protocol_version=protocol_version,
        metadata_only_mode=metadata_only_mode,
        hardware_outputs_enabled=hardware_outputs_enabled,
        config_safety_fields_present=config_safety_fields_present,
        configured_output_keys=configured_output_keys,
        response_dispatch_available=response_dispatch_available,
    )


def _message_format_lines(text: str) -> frozenset[str]:
    return frozenset(
        normalized
        for line in text.splitlines()
        if (normalized := _normalize_message_format_line(line))
    )


def _json_message_formats(text: str) -> frozenset[str]:
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(payload, dict):
        return frozenset()

    formats: set[str] = set()
    for section_name in ("commands", "responses"):
        section = payload.get(section_name)
        if isinstance(section, dict):
            formats.update(key for key in section if isinstance(key, str))
    return frozenset(formats)


def _normalize_message_format_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    if stripped.endswith(","):
        stripped = stripped[:-1].rstrip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ("'", '"'):
        stripped = stripped[1:-1]
    return stripped
