"""Shared scanner-sync codec types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    SUPPORTED_PROTOCOL_VERSIONS,
)


class ScannerSyncCodecError(ValueError):
    """Raised when local scanner-sync payload conversion fails."""


@dataclass(frozen=True)
class EncodedKlipperCommand:
    name: str
    msgformat: str
    args: tuple[Union[int, str, bytes], ...]


@dataclass(frozen=True)
class ScannerSyncDecodeContext:
    scan_id: str
    protocol_version: int = 1
    coordinate_source_used: str = "step_indexed"
    trigger_output_name: str = "camera_or_sync_trigger"
    pattern_names: tuple[str, ...] = ()
    pattern_led_gate_names: tuple[tuple[str, ...], ...] = ()
    led_gate_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ScannerSyncCodecError(f"unsupported protocol_version: {self.protocol_version}")
        _require_str_tuple("pattern_names", self.pattern_names)
        _require_nested_str_tuple(
            "pattern_led_gate_names", self.pattern_led_gate_names
        )
        _require_str_tuple("led_gate_names", self.led_gate_names)


def _require_str_tuple(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or not all(
        isinstance(value, str) for value in values
    ):
        raise ScannerSyncCodecError(f"{name} must be a tuple of strings")


def _require_nested_str_tuple(
    name: str, values: tuple[tuple[str, ...], ...]
) -> None:
    if not isinstance(values, tuple):
        raise ScannerSyncCodecError(f"{name} must be a tuple of string tuples")
    for item in values:
        _require_str_tuple(name, item)
