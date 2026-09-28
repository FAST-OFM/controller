"""Models for passive scanner-sync event stream decoding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    ProtocolEventType,
)


class ScannerSyncEventStreamError(ValueError):
    """Raised when a scanner-sync event stream payload is malformed."""


@dataclass(frozen=True)
class RawScannerSyncEvent:
    event_type: ProtocolEventType
    params: dict[str, Any]


@dataclass(frozen=True)
class ZOutcomeValidation:
    seq: int
    outcome: str
    scan_id: str | None
    stripe_id: int | None
    command_id: str | None
    apply_target_kind: str | None = None
    apply_at_frame_id: int | None = None
    apply_at_position_count: int | None = None
    applied_frame_id: int | None = None
    applied_position: int | None = None
    z_target_steps: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "outcome": self.outcome,
            "scan_id": self.scan_id,
            "stripe_id": self.stripe_id,
            "command_id": self.command_id,
            "apply_target_kind": self.apply_target_kind,
            "apply_at_frame_id": self.apply_at_frame_id,
            "apply_at_position_count": self.apply_at_position_count,
            "applied_frame_id": self.applied_frame_id,
            "applied_position": self.applied_position,
            "z_target_steps": self.z_target_steps,
        }


@dataclass(frozen=True)
class ScannerSyncStreamValidation:
    frame_count: int
    terminal_count: int
    first_frame_id: int | None
    last_frame_id: int | None
    next_frame_id: int | None
    stripes_seen: tuple[int, ...]
    z_scheduled_count: int = 0
    z_applied_count: int = 0
    z_rejected_count: int = 0
    timed_output_sequence_status_count: int = 0
    z_outcomes: tuple[ZOutcomeValidation, ...] = ()


@dataclass(frozen=True)
class ScannerSyncCaptureReport:
    accepted: bool
    record_count: int
    event_types: tuple[str, ...]
    validation: ScannerSyncStreamValidation

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "record_count": self.record_count,
            "event_types": list(self.event_types),
            "frame_count": self.validation.frame_count,
            "terminal_count": self.validation.terminal_count,
            "first_frame_id": self.validation.first_frame_id,
            "last_frame_id": self.validation.last_frame_id,
            "next_frame_id": self.validation.next_frame_id,
            "stripes_seen": list(self.validation.stripes_seen),
            "z_scheduled_count": self.validation.z_scheduled_count,
            "z_applied_count": self.validation.z_applied_count,
            "z_rejected_count": self.validation.z_rejected_count,
            "timed_output_sequence_status_count": (
                self.validation.timed_output_sequence_status_count
            ),
            "z_outcomes": [
                outcome.to_json_dict() for outcome in self.validation.z_outcomes
            ],
        }


PROTOCOL_EVENT_TYPES: frozenset[str] = frozenset(
    (
        "FRAME_EVENT",
        "SCHEDULER_TERMINAL",
        "Z_SCHEDULED",
        "Z_APPLIED",
        "Z_REJECTED",
        "TIMED_OUTPUT_SEQUENCE_STATUS",
    )
)
