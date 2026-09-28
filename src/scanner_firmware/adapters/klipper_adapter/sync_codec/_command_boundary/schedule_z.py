"""Schedule-Z command validation and canonicalization at the host boundary."""

from __future__ import annotations

from typing import Any, Mapping

from scanner_firmware.adapters.klipper_adapter.sync_codec._errors import (
    ScannerSyncCommandBoundaryError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._scalar_validation import (
    has_present_value,
    require_non_negative_int_field,
    require_number_field,
)
from scanner_firmware.foundation.protocol.events import SCHEDULE_Z_COMMAND
from scanner_firmware.planning.z_scheduler.predictive import (
    PredictiveZMathError,
    convert_apply_position_um_to_count,
)


def validate_schedule_z_record(
    record: Mapping[str, Any],
    record_index: int,
    context: Any,
) -> None:
    require_number_field(record, "z_target_um", record_index)

    has_frame_target = has_present_value(record, "apply_at_frame_id")
    has_position_target = has_present_value(record, "apply_at_position_count")
    has_physical_position_target = has_present_value(record, "apply_at_position_um")
    if not (has_frame_target or has_position_target or has_physical_position_target):
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: schedule_z requires at least one future target"
        )
    if has_frame_target and (has_position_target or has_physical_position_target):
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: schedule_z requires exactly one target kind"
        )
    if has_frame_target:
        apply_at_frame_id = require_non_negative_int_field(
            record, "apply_at_frame_id", record_index
        )
        if (
            context.current_frame_id is not None
            and apply_at_frame_id <= context.current_frame_id
        ):
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: apply_at_frame_id must be in the future"
            )
    if has_position_target:
        apply_at_position_count = require_non_negative_int_field(
            record, "apply_at_position_count", record_index
        )
    elif has_physical_position_target:
        require_number_field(record, "apply_at_position_um", record_index)
        apply_at_position_count = _rounded_apply_position_um_target(
            record["apply_at_position_um"],
            record_index=record_index,
            context=context,
        )
    else:
        apply_at_position_count = None
    if apply_at_position_count is not None:
        _validate_future_position_target(
            apply_at_position_count,
            record_index=record_index,
            context=context,
        )


def canonicalized_schedule_z_record(
    record: Mapping[str, Any],
    context: Any,
) -> dict[str, Any]:
    payload = dict(record)
    payload["cmd"] = SCHEDULE_Z_COMMAND
    if (
        has_present_value(payload, "apply_at_position_um")
        and not has_present_value(payload, "apply_at_position_count")
    ):
        payload["apply_at_position_count"] = _rounded_apply_position_um_target(
            payload["apply_at_position_um"],
            record_index=0,
            context=context,
        )
    return payload


def _rounded_apply_position_um_target(
    apply_at_position_um: Any,
    *,
    record_index: int,
    context: Any,
) -> int:
    if context.apply_position_count_basis is None:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: apply_at_position_um requires "
            "apply_position_count_basis"
        )
    if context.position_direction is None:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: apply_at_position_um requires position_direction"
        )
    try:
        return convert_apply_position_um_to_count(
            apply_at_position_um,
            basis=context.apply_position_count_basis,
            scan_direction_count=context.position_direction,
        )
    except PredictiveZMathError as exc:
        raise ScannerSyncCommandBoundaryError(f"record {record_index}: {exc}") from exc


def _validate_future_position_target(
    apply_at_position_count: int,
    *,
    record_index: int,
    context: Any,
) -> None:
    if context.current_position_count is None:
        return
    if context.position_direction is None:
        if apply_at_position_count == context.current_position_count:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: apply_at_position_count must be in the future"
            )
        return
    if (
        apply_at_position_count - context.current_position_count
    ) * context.position_direction <= 0:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: apply_at_position_count must be in the future"
        )
