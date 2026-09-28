"""Scalar validation helpers for scanner-sync command records."""

from __future__ import annotations

from typing import Any, Mapping

from scanner_firmware.adapters.klipper_adapter.sync_codec._errors import (
    ScannerSyncCommandBoundaryError,
)


def require_non_empty_str(
    record: Mapping[str, Any],
    key: str,
    record_index: int,
) -> str:
    value = require_field(record, key, record_index)
    if not isinstance(value, str) or not value:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {key} must be a non-empty string"
        )
    return value


def require_int_field(record: Mapping[str, Any], key: str, record_index: int) -> int:
    value = require_field(record, key, record_index)
    require_int(key, value, record_index=record_index)
    return value


def require_non_negative_int_field(
    record: Mapping[str, Any],
    key: str,
    record_index: int,
) -> int:
    value = require_int_field(record, key, record_index)
    if value < 0:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {key} must be non-negative"
        )
    return value


def require_number_field(record: Mapping[str, Any], key: str, record_index: int) -> None:
    value = require_field(record, key, record_index)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: {key} must be numeric"
        )


def require_field(record: Mapping[str, Any], key: str, record_index: int) -> Any:
    if key not in record:
        raise ScannerSyncCommandBoundaryError(f"record {record_index}: missing {key}")
    return record[key]


def require_int(
    key: str,
    value: Any,
    *,
    record_index: int | None = None,
) -> None:
    prefix = f"record {record_index}: " if record_index is not None else ""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScannerSyncCommandBoundaryError(f"{prefix}{key} must be an integer")


def require_bool(
    key: str,
    value: Any,
    *,
    record_index: int | None = None,
) -> None:
    prefix = f"record {record_index}: " if record_index is not None else ""
    if not isinstance(value, bool):
        raise ScannerSyncCommandBoundaryError(f"{prefix}{key} must be a boolean")


def has_present_value(record: Mapping[str, Any], key: str) -> bool:
    return key in record and record[key] is not None
