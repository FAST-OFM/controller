"""Passive parser for captured Klipper scanner-sync config text.

The parser reads already-captured `printer.cfg` text. It does not import
Klipper, open serial ports, restart services, toggle outputs, command motion,
trigger cameras, drive LEDs or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass


class ScannerSyncConfigError(ValueError):
    """Raised when scanner-sync config text is malformed."""


@dataclass(frozen=True)
class ScannerSyncConfigObservation:
    section_present: bool
    enable: bool = False
    protocol_version: int = 1
    metadata_only_mode: bool = True
    mode_present: bool = False
    hardware_outputs_enabled: bool = False
    hardware_outputs_enabled_present: bool = False
    configured_output_keys: tuple[str, ...] = ()

    @property
    def safety_fields_present(self) -> bool:
        return self.mode_present and self.hardware_outputs_enabled_present

    @property
    def output_pins_configured(self) -> bool:
        return bool(self.configured_output_keys)


def parse_scanner_sync_config(text: str) -> ScannerSyncConfigObservation:
    """Parse the `[scanner_sync]` section from captured Klipper config text."""

    section = _scanner_sync_section(text)
    if section is None:
        return ScannerSyncConfigObservation(section_present=False)

    values = _parse_key_values(section)
    return ScannerSyncConfigObservation(
        section_present=True,
        enable=_parse_bool(values.get("enable", "false"), "scanner_sync.enable"),
        protocol_version=_parse_positive_int(
            values.get("protocol_version", "1"),
            "scanner_sync.protocol_version",
        ),
        metadata_only_mode=_parse_metadata_only_mode(values),
        mode_present="mode" in values or "metadata_only_mode" in values,
        hardware_outputs_enabled=_parse_bool(
            values.get("hardware_outputs_enabled", "false"),
            "scanner_sync.hardware_outputs_enabled",
        ),
        hardware_outputs_enabled_present="hardware_outputs_enabled" in values,
        configured_output_keys=_configured_output_keys(values),
    )


def _scanner_sync_section(text: str) -> list[str] | None:
    in_section = False
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                break
            in_section = stripped == "[scanner_sync]"
            continue
        if in_section:
            lines.append(raw_line)
    if not in_section and not lines:
        return None
    return lines


def _parse_key_values(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "#" in stripped:
            stripped = stripped.split("#", 1)[0].rstrip()
        if ":" not in stripped:
            raise ScannerSyncConfigError(f"invalid scanner_sync config line: {line!r}")
        key, value = stripped.split(":", 1)
        normalized_key = key.strip().lower()
        if not normalized_key:
            raise ScannerSyncConfigError(f"empty scanner_sync config key: {line!r}")
        values[normalized_key] = value.strip()
    return values


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "yes", "on", "1"):
        return True
    if normalized in ("false", "no", "off", "0"):
        return False
    raise ScannerSyncConfigError(f"{name} must be boolean")


def _parse_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ScannerSyncConfigError(f"{name} must be a positive integer") from exc
    if parsed < 1:
        raise ScannerSyncConfigError(f"{name} must be a positive integer")
    return parsed


def _parse_metadata_only_mode(values: dict[str, str]) -> bool:
    if "metadata_only_mode" in values:
        return _parse_bool(values["metadata_only_mode"], "scanner_sync.metadata_only_mode")
    if "mode" in values:
        return values["mode"].strip().lower() == "metadata_only"
    return True


def _configured_output_keys(values: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        key
        for key, value in sorted(values.items())
        if _looks_like_output_mapping(key) and not _is_unset_output_value(value)
    )


def _looks_like_output_mapping(key: str) -> bool:
    if key == "hardware_outputs_enabled":
        return False
    return any(
        token in key
        for token in (
            "pin",
            "output",
            "trigger",
            "strobe",
            "led",
        )
    )


def _is_unset_output_value(value: str) -> bool:
    return value.strip().lower() in ("", "none", "null", "unset", "disabled", "false", "0")
