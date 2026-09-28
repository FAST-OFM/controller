"""Field parsing helpers for dry-run scan recipes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scanner_firmware.planning.trigger_scheduler.errors import ScanPlanError
from scanner_firmware.planning.trigger_scheduler.types import CoordinateSource


def require_non_empty_string(
    mapping: Mapping[str, Any], key: str, display_name: str
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ScanPlanError(f"{display_name} must be a non-empty string")
    return value


def require_int(mapping: Mapping[str, Any], key: str, display_name: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScanPlanError(f"{display_name} must be an integer")
    return value


def require_aliased_int(
    mapping: Mapping[str, Any], aliases: tuple[str, ...], display_name: str
) -> int:
    present = [alias for alias in aliases if alias in mapping]
    if len(present) > 1:
        raise ScanPlanError(f"{display_name} has multiple aliases: {', '.join(present)}")
    if not present:
        raise ScanPlanError(f"{display_name} must be an integer")
    return require_int(mapping, present[0], display_name)


def optional_bool(mapping: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise ScanPlanError(f"{key} must be a boolean")
    return value


def require_pattern_sequence(
    mapping: Mapping[str, Any], key: str, display_name: str
) -> tuple[str, ...]:
    value = mapping.get(key)
    if not is_sequence(value) or not value:
        raise ScanPlanError(f"{display_name} must be a non-empty sequence")
    patterns = tuple(value)
    if any(not isinstance(pattern, str) or not pattern for pattern in patterns):
        raise ScanPlanError(f"{display_name} entries must be non-empty strings")
    return patterns


def optional_coordinate_source(
    mapping: Mapping[str, Any], display_name: str
) -> CoordinateSource:
    value = mapping.get("coordinate_source", "step_indexed")
    if value not in ("step_indexed", "encoder_indexed", "hybrid"):
        raise ScanPlanError(
            f"{display_name} must be step_indexed, encoder_indexed, or hybrid"
        )
    return value


def is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
