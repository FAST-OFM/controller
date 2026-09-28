"""Pure predictive-Z command planning from focus error samples."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from .latency import round_apply_position_count
from .types import RejectReason, StripeContext, TargetKind, ZCommand


PredictiveRejectReason = RejectReason | Literal["deadband"]


@dataclass(frozen=True)
class ZFocusErrorSample:
    scan_id: str
    stripe_id: int
    focus_error_steps: int
    reference_z_steps: int
    frame_id: int | None = None
    position_count: int | None = None
    command_id: str | None = None

    def __post_init__(self) -> None:
        if not self.scan_id:
            raise ValueError("scan_id must be non-empty")
        if (self.frame_id is None) == (self.position_count is None):
            raise ValueError("focus sample requires exactly one frame_id or position_count")
        for name, value in (
            ("stripe_id", self.stripe_id),
            ("focus_error_steps", self.focus_error_steps),
            ("reference_z_steps", self.reference_z_steps),
        ):
            _require_int(name, value)
        if self.stripe_id < 0:
            raise ValueError("stripe_id must be non-negative")
        if self.frame_id is not None and self.frame_id < 0:
            raise ValueError("frame_id must be non-negative")


@dataclass(frozen=True)
class ZPredictivePlannerConfig:
    min_z_steps: int
    max_z_steps: int
    max_correction_steps: int
    lead_frames: int = 0
    lead_position_steps: float = 0
    deadband_steps: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("min_z_steps", self.min_z_steps),
            ("max_z_steps", self.max_z_steps),
            ("max_correction_steps", self.max_correction_steps),
            ("lead_frames", self.lead_frames),
            ("deadband_steps", self.deadband_steps),
        ):
            _require_int(name, value)
        _require_finite_number("lead_position_steps", self.lead_position_steps)
        if self.min_z_steps > self.max_z_steps:
            raise ValueError("min_z_steps must be <= max_z_steps")
        if self.max_correction_steps <= 0:
            raise ValueError("max_correction_steps must be positive")
        if self.lead_frames < 0:
            raise ValueError("lead_frames must be non-negative")
        if self.lead_position_steps < 0:
            raise ValueError("lead_position_steps must be non-negative")
        if self.deadband_steps < 0:
            raise ValueError("deadband_steps must be non-negative")


@dataclass(frozen=True)
class ZPredictivePlanDecision:
    accepted: bool
    status: Literal["accepted", "rejected"]
    reason: PredictiveRejectReason | None
    sample: ZFocusErrorSample
    command: ZCommand | None
    target_kind: TargetKind | None
    z_correction_steps: int | None
    hardware_outputs_enabled: bool = False


class PredictiveZPlanner:
    """Plan future scheduled Z corrections from focus error samples."""

    def __init__(self, config: ZPredictivePlannerConfig):
        self._config = config

    def plan(self, sample: ZFocusErrorSample, context: StripeContext) -> ZPredictivePlanDecision:
        if sample.scan_id != context.scan_id or sample.stripe_id != context.stripe_id:
            return self._rejected(sample, "scan_or_stripe_mismatch")

        if abs(sample.focus_error_steps) <= self._config.deadband_steps:
            return self._rejected(sample, "deadband")

        z_correction_steps = self._clamped_correction(sample.focus_error_steps)
        z_target_steps = self._clamped_target(sample.reference_z_steps + z_correction_steps)

        if sample.frame_id is not None:
            target_frame_id = sample.frame_id + self._config.lead_frames
            lookahead = target_frame_id - context.current_frame_id
            if lookahead <= 0:
                return self._rejected(
                    sample, "target_already_passed", "frame", z_correction_steps
                )
            if lookahead < self._config.lead_frames:
                return self._rejected(
                    sample, "insufficient_lookahead", "frame", z_correction_steps
                )
            return self._accepted(
                sample,
                ZCommand(
                    command_id=sample.command_id,
                    scan_id=sample.scan_id,
                    stripe_id=sample.stripe_id,
                    apply_at_frame_id=target_frame_id,
                    z_target_steps=z_target_steps,
                ),
                "frame",
                z_correction_steps,
            )

        assert sample.position_count is not None
        target_position = round_apply_position_count(
            sample.position_count + context.direction * float(self._config.lead_position_steps),
            context.direction,
        )
        if not self._position_within_stripe(context, target_position):
            return self._rejected(
                sample, "target_outside_stripe", "position", z_correction_steps
            )
        lookahead = (target_position - context.position) * context.direction
        if lookahead <= 0:
            return self._rejected(
                sample, "target_already_passed", "position", z_correction_steps
            )
        if lookahead < self._config.lead_position_steps:
            return self._rejected(
                sample, "insufficient_lookahead", "position", z_correction_steps
            )
        return self._accepted(
            sample,
            ZCommand(
                command_id=sample.command_id,
                scan_id=sample.scan_id,
                stripe_id=sample.stripe_id,
                apply_at_position_count=target_position,
                z_target_steps=z_target_steps,
            ),
            "position",
            z_correction_steps,
        )

    def plan_many(
        self, samples: list[ZFocusErrorSample], context: StripeContext
    ) -> tuple[ZPredictivePlanDecision, ...]:
        return tuple(self.plan(sample, context) for sample in samples)

    def _clamped_correction(self, focus_error_steps: int) -> int:
        return _clamp(
            focus_error_steps,
            -self._config.max_correction_steps,
            self._config.max_correction_steps,
        )

    def _clamped_target(self, z_target_steps: int) -> int:
        return _clamp(z_target_steps, self._config.min_z_steps, self._config.max_z_steps)

    def _accepted(
        self,
        sample: ZFocusErrorSample,
        command: ZCommand,
        target_kind: TargetKind,
        z_correction_steps: int,
    ) -> ZPredictivePlanDecision:
        return ZPredictivePlanDecision(
            accepted=True,
            status="accepted",
            reason=None,
            sample=sample,
            command=command,
            target_kind=target_kind,
            z_correction_steps=z_correction_steps,
        )

    def _rejected(
        self,
        sample: ZFocusErrorSample,
        reason: PredictiveRejectReason,
        target_kind: TargetKind | None = None,
        z_correction_steps: int | None = None,
    ) -> ZPredictivePlanDecision:
        return ZPredictivePlanDecision(
            accepted=False,
            status="rejected",
            reason=reason,
            sample=sample,
            command=None,
            target_kind=target_kind,
            z_correction_steps=z_correction_steps,
        )

    def _position_within_stripe(self, context: StripeContext, position: int) -> bool:
        lower = min(context.start_position, context.end_position)
        upper = max(context.start_position, context.end_position)
        return lower <= position <= upper


def _clamp(value: int, lower: int, upper: int) -> int:
    return min(max(value, lower), upper)


def _require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")


def _require_finite_number(name: str, value: object) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
