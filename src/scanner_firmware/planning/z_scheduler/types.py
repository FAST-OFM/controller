"""Firmware-local predictive-Z scheduler queue and outcome records.

Shared predictive-Z command, stripe and scheduler configuration objects are
owned by ``scanner_core.predictive_z`` and must be imported from scanner-core
directly. This module defines only firmware-local outcome ledger shapes for
simulator and protocol fixtures. These dataclasses do not open devices, talk to
Klipper, move motors or expose an immediate ``move_z_now`` path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from scanner_core.predictive_z.types import RejectReason, TargetKind, ZCommand

ZOutcomeKind = Literal["accepted", "rejected", "applied"]


@dataclass(frozen=True)
class QueuedZCommand:
    command: ZCommand
    seq: int
    schedule_order: int


@dataclass(frozen=True)
class ZScheduleDecision:
    command: ZCommand
    seq: int
    accepted: bool
    reason: RejectReason | None = None
    hardware_outputs_enabled: bool = False

    @property
    def status(self) -> Literal["accepted", "rejected"]:
        return "accepted" if self.accepted else "rejected"


@dataclass(frozen=True)
class ZAppliedEvent:
    scan_id: str
    stripe_id: int
    command_id: str | None
    seq: int
    apply_target_kind: TargetKind
    apply_at_frame_id: int | None
    apply_at_position_count: int | None
    frame_id: int
    position: int | None
    z_target_steps: int
    hardware_outputs_enabled: bool = False
    status: Literal["ok"] = "ok"
    type: Literal["Z_APPLIED"] = field(default="Z_APPLIED", init=False)


@dataclass(frozen=True)
class ZSchedulerOutcome:
    seq: int
    outcome: ZOutcomeKind
    scan_id: str
    stripe_id: int
    command_id: str | None
    apply_target_kind: TargetKind | None = None
    apply_at_frame_id: int | None = None
    apply_at_position_count: int | None = None
    applied_frame_id: int | None = None
    applied_position: int | None = None
    z_target_steps: int | None = None
    reason: RejectReason | None = None
    hardware_outputs_enabled: bool = False

    @property
    def terminal(self) -> bool:
        return self.outcome in ("rejected", "applied")


__all__ = [
    "QueuedZCommand",
    "ZAppliedEvent",
    "ZScheduleDecision",
    "ZSchedulerOutcome",
]
