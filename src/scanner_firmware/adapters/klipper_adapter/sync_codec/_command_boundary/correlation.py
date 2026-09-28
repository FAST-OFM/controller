"""Common command identity and sequence correlation validation."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from scanner_firmware.adapters.klipper_adapter.sync_codec._errors import (
    ScannerSyncCommandBoundaryError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec._scalar_validation import (
    require_int_field,
    require_non_empty_str,
    require_non_negative_int_field,
)


class CommandCorrelationContext(Protocol):
    expected_scan_id: str | None
    expected_stripe_id: int | None
    expected_first_seq: int | None
    require_contiguous_seq: bool


def validate_common_command_record(
    record: Mapping[str, Any],
    record_index: int,
    context: CommandCorrelationContext,
) -> int:
    seq = require_int_field(record, "seq", record_index)
    if seq < 0:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: seq must be non-negative"
        )
    scan_id = require_non_empty_str(record, "scan_id", record_index)
    if context.expected_scan_id is not None and scan_id != context.expected_scan_id:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: scan_id mismatch, "
            f"expected {context.expected_scan_id}, got {scan_id}"
        )
    stripe_id = require_non_negative_int_field(record, "stripe_id", record_index)
    if context.expected_stripe_id is not None and stripe_id != context.expected_stripe_id:
        raise ScannerSyncCommandBoundaryError(
            f"record {record_index}: stripe_id mismatch, "
            f"expected {context.expected_stripe_id}, got {stripe_id}"
        )
    return seq


class CommandSeqCorrelation:
    def __init__(self, context: CommandCorrelationContext) -> None:
        self._expected_seq = context.expected_first_seq
        self._require_contiguous_seq = context.require_contiguous_seq
        self._seen_seqs: set[int] = set()

    def accept(self, seq: int, record_index: int) -> None:
        if seq in self._seen_seqs:
            raise ScannerSyncCommandBoundaryError(
                f"record {record_index}: duplicate seq {seq}"
            )
        if self._require_contiguous_seq:
            if self._expected_seq is None:
                self._expected_seq = seq
            if seq != self._expected_seq:
                raise ScannerSyncCommandBoundaryError(
                    f"record {record_index}: seq correlation failed, "
                    f"expected {self._expected_seq}, got {seq}"
                )
            self._expected_seq += 1
        self._seen_seqs.add(seq)
