"""Start/stop command validation at the host boundary."""

from __future__ import annotations

from typing import Any, Mapping

from scanner_firmware.adapters.klipper_adapter.sync_codec import (
    _unsafe_policy as _command_boundary_policy,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._errors import (
    ScannerSyncCommandBoundaryError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._scalar_validation import (
    require_non_empty_str,
    require_non_negative_int_field,
)


STOP_REASONS = _command_boundary_policy.STOP_REASONS


def validate_start_record(record: Mapping[str, Any], record_index: int) -> None:
    require_non_negative_int_field(record, "next_frame_id", record_index)


def validate_stop_record(record: Mapping[str, Any], record_index: int) -> None:
    reason = require_non_empty_str(record, "reason", record_index)
    if reason not in STOP_REASONS:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: unsupported scanner_sync_stop reason {reason!r}"
        )
