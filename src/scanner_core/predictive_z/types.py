"""Pure value objects for predictive-Z planning and scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal


TargetKind = Literal["frame", "position"]
RejectReason = Literal[
    "invalid_target",
    "scan_or_stripe_mismatch",
    "target_already_passed",
    "insufficient_lookahead",
    "z_limit_exceeded",
    "target_outside_stripe",
    "no_correction_window",
]


@dataclass(frozen=True)
class ZNoCorrectionWindow:
    target_kind: TargetKind
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.target_kind not in ("frame", "position"):
            raise ValueError("target_kind must be frame or position")
        if self.start > self.end:
            raise ValueError("no-correction window start must be <= end")

    def contains(self, target: int) -> bool:
        return self.start <= target <= self.end


@dataclass(frozen=True)
class ZSchedulerConfig:
    min_z_steps: int
    max_z_steps: int
    lead_frames: int = 0
    settle_frames: int = 0
    lead_position_steps: float = 0
    settle_position_steps: float = 0
    no_correction_windows: tuple[ZNoCorrectionWindow, ...] = ()
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("min_z_steps", self.min_z_steps),
            ("max_z_steps", self.max_z_steps),
            ("lead_frames", self.lead_frames),
            ("settle_frames", self.settle_frames),
        ):
            _require_int(name, value)
        _require_finite_number("lead_position_steps", self.lead_position_steps)
        _require_finite_number("settle_position_steps", self.settle_position_steps)
        if self.min_z_steps > self.max_z_steps:
            raise ValueError("min_z_steps must be <= max_z_steps")
        if self.lead_frames < 0:
            raise ValueError("lead_frames must be non-negative")
        if self.settle_frames < 0:
            raise ValueError("settle_frames must be non-negative")
        if self.lead_position_steps < 0:
            raise ValueError("lead_position_steps must be non-negative")
        if self.settle_position_steps < 0:
            raise ValueError("settle_position_steps must be non-negative")
        if self.hardware_outputs_enabled:
            raise ValueError("Z scheduler simulator cannot enable hardware outputs")


@dataclass(frozen=True)
class StripeContext:
    scan_id: str
    stripe_id: int
    start_position: int
    end_position: int
    current_position: int | None = None
    current_frame_id: int = 0

    def __post_init__(self) -> None:
        if not self.scan_id:
            raise ValueError("scan_id must be non-empty")
        _require_int("stripe_id", self.stripe_id)
        _require_int("start_position", self.start_position)
        _require_int("end_position", self.end_position)
        _require_int("current_frame_id", self.current_frame_id)
        if self.stripe_id < 0:
            raise ValueError("stripe_id must be non-negative")
        if self.start_position == self.end_position:
            raise ValueError("start_position and end_position must differ")
        if self.current_frame_id < 0:
            raise ValueError("current_frame_id must be non-negative")
        position = self.position
        lower = min(self.start_position, self.end_position)
        upper = max(self.start_position, self.end_position)
        if not lower <= position <= upper:
            raise ValueError("current_position must be within stripe bounds")

    @property
    def position(self) -> int:
        if self.current_position is None:
            return self.start_position
        return self.current_position

    @property
    def direction(self) -> int:
        if self.end_position > self.start_position:
            return 1
        return -1


@dataclass(frozen=True)
class ZCommand:
    scan_id: str
    stripe_id: int
    z_target_steps: int
    apply_at_frame_id: int | None = None
    apply_at_position_count: int | None = None
    command_id: str | None = None


@dataclass(frozen=True)
class ZScheduleDecision:
    accepted: bool
    status: Literal["accepted", "rejected"]
    reason: RejectReason | None
    command: ZCommand
    hardware_outputs_enabled: bool


@dataclass(frozen=True)
class ZAppliedEvent:
    type: Literal["Z_APPLIED"]
    scan_id: str
    stripe_id: int
    command_id: str | None
    apply_target_kind: TargetKind
    apply_at_frame_id: int | None
    apply_at_position_count: int | None
    frame_id: int
    position: int
    z_target_steps: int
    hardware_outputs_enabled: bool
    status: Literal["ok"]


@dataclass(frozen=True)
class QueuedZCommand:
    command: ZCommand
    target_kind: TargetKind
    sort_key: int
    sequence: int


def _require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")


def _require_finite_number(name: str, value: object) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
