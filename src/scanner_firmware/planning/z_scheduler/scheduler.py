"""Software-only predictive-Z scheduler queue fixture."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scanner_core.predictive_z.types import (
    RejectReason,
    StripeContext,
    TargetKind,
    ZCommand,
    ZSchedulerConfig,
)
from scanner_firmware.planning.z_scheduler.types import (
    QueuedZCommand,
    ZAppliedEvent,
    ZScheduleDecision,
    ZSchedulerOutcome,
)


class PredictiveZSchedulerSimulator:
    """In-memory future-only Z queue used by tests and replay fixtures.

    The simulator records every accepted, rejected and applied outcome. It is
    intentionally metadata-only: ``hardware_outputs_enabled`` is always false
    and there is no immediate ``move_z_now`` command surface.
    """

    def __init__(self, config: ZSchedulerConfig, context: StripeContext):
        self.config = config
        self.context = context
        self.current_frame_id = context.current_frame_id
        self.current_position = context.position
        self._queue: list[QueuedZCommand] = []
        self._next_schedule_order = 0
        self._outcomes: list[ZSchedulerOutcome] = []
        self._terminal_outcome_by_seq: dict[int, ZSchedulerOutcome] = {}

    @property
    def queued_count(self) -> int:
        return len(self._queue)

    @property
    def queued(self) -> tuple[QueuedZCommand, ...]:
        return tuple(self._queue)

    @property
    def outcomes(self) -> tuple[ZSchedulerOutcome, ...]:
        return tuple(self._outcomes)

    @property
    def terminal_outcomes(self) -> tuple[ZSchedulerOutcome, ...]:
        return tuple(outcome for outcome in self._outcomes if outcome.terminal)

    @property
    def terminal_outcome_by_seq(self) -> Mapping[int, ZSchedulerOutcome]:
        return dict(self._terminal_outcome_by_seq)

    def schedule(self, command: ZCommand, *, seq: int | None = None) -> ZScheduleDecision:
        seq = self._seq_for(command, explicit_seq=seq)
        reason = self._rejection_reason(command)
        if reason is not None:
            decision = ZScheduleDecision(
                command=command,
                seq=seq,
                accepted=False,
                reason=reason,
                hardware_outputs_enabled=False,
            )
            self._record_rejected(decision)
            return decision

        queued = QueuedZCommand(
            command=command,
            seq=seq,
            schedule_order=self._next_schedule_order,
        )
        self._next_schedule_order += 1
        self._queue.append(queued)
        decision = ZScheduleDecision(
            command=command,
            seq=seq,
            accepted=True,
            hardware_outputs_enabled=False,
        )
        self._record_accepted(decision)
        return decision

    def advance_to(
        self,
        *,
        frame_id: int | None = None,
        position: int | None = None,
    ) -> list[ZAppliedEvent]:
        if frame_id is not None:
            self.current_frame_id = frame_id
        if position is not None:
            self.current_position = position

        ready = [queued for queued in self._queue if self._ready(queued, frame_id, position)]
        ready.sort(key=self._apply_order_key)
        if not ready:
            return []

        ready_ids = {id(queued) for queued in ready}
        self._queue = [queued for queued in self._queue if id(queued) not in ready_ids]
        events = [self._applied_event(queued) for queued in ready]
        for event in events:
            self._record_applied(event)
        return events

    def validate_terminal_outcomes(self) -> None:
        missing = [
            outcome.seq
            for outcome in self._outcomes
            if outcome.outcome == "accepted"
            and outcome.seq not in self._terminal_outcome_by_seq
        ]
        if missing:
            formatted = ", ".join(str(seq) for seq in sorted(missing))
            raise ValueError(
                "Z_SCHEDULED decisions require one terminal outcome per seq; "
                f"missing applied/rejected outcome for seq {formatted}"
            )

    def _seq_for(self, command: ZCommand, *, explicit_seq: int | None) -> int:
        if explicit_seq is not None:
            return explicit_seq
        command_seq = getattr(command, "seq", None)
        if command_seq is not None:
            return command_seq
        return self._next_schedule_order

    def _rejection_reason(self, command: ZCommand) -> RejectReason | None:
        if command.scan_id != self.context.scan_id or command.stripe_id != self.context.stripe_id:
            return "scan_or_stripe_mismatch"
        target_kind = _target_kind(command)
        target_value = _target_value(command)
        if target_kind is None or target_value is None:
            return "invalid_target"
        if not self.config.min_z_steps <= command.z_target_steps <= self.config.max_z_steps:
            return "z_limit_exceeded"
        if target_kind == "frame":
            return self._frame_target_rejection(target_value)
        return self._position_target_rejection(target_value)

    def _frame_target_rejection(self, target_frame_id: int) -> RejectReason | None:
        if target_frame_id <= self.current_frame_id:
            return "target_already_passed"
        if target_frame_id - self.current_frame_id < _required_frame_lookahead(self.config):
            return "insufficient_lookahead"
        if self._in_no_correction_window("frame", target_frame_id):
            return "no_correction_window"
        return None

    def _position_target_rejection(self, target_position: int) -> RejectReason | None:
        if not self._position_within_stripe(target_position):
            return "target_outside_stripe"
        distance = self._progress_delta(self.current_position, target_position)
        if distance <= 0:
            return "target_already_passed"
        if distance < _required_position_lookahead(self.config):
            return "insufficient_lookahead"
        if self._in_no_correction_window("position", target_position):
            return "no_correction_window"
        return None

    def _ready(
        self,
        queued: QueuedZCommand,
        frame_id: int | None,
        position: int | None,
    ) -> bool:
        command = queued.command
        if command.apply_at_frame_id is not None:
            return frame_id is not None and command.apply_at_frame_id <= frame_id
        if command.apply_at_position_count is not None:
            return (
                position is not None
                and self._progress_from_start(command.apply_at_position_count)
                <= self._progress_from_start(position)
            )
        return False

    def _apply_order_key(self, queued: QueuedZCommand) -> tuple[int, int]:
        command = queued.command
        if command.apply_at_frame_id is not None:
            return (command.apply_at_frame_id, queued.schedule_order)
        if command.apply_at_position_count is not None:
            return (
                self._progress_from_start(command.apply_at_position_count),
                queued.schedule_order,
            )
        return (0, queued.schedule_order)

    def _applied_event(self, queued: QueuedZCommand) -> ZAppliedEvent:
        command = queued.command
        target_kind = _target_kind(command)
        if target_kind is None:
            raise AssertionError("queued Z command lost target kind")
        frame_id = (
            command.apply_at_frame_id
            if command.apply_at_frame_id is not None
            else self.current_frame_id
        )
        position = (
            command.apply_at_position_count
            if command.apply_at_position_count is not None
            else self.current_position
        )
        return ZAppliedEvent(
            scan_id=command.scan_id,
            stripe_id=command.stripe_id,
            command_id=command.command_id,
            seq=queued.seq,
            apply_target_kind=target_kind,
            apply_at_frame_id=command.apply_at_frame_id,
            apply_at_position_count=command.apply_at_position_count,
            frame_id=frame_id,
            position=position,
            z_target_steps=command.z_target_steps,
            hardware_outputs_enabled=False,
        )

    def _record_accepted(self, decision: ZScheduleDecision) -> None:
        self._outcomes.append(
            ZSchedulerOutcome(
                seq=decision.seq,
                outcome="accepted",
                scan_id=decision.command.scan_id,
                stripe_id=decision.command.stripe_id,
                command_id=decision.command.command_id,
                apply_target_kind=_target_kind(decision.command),
                apply_at_frame_id=decision.command.apply_at_frame_id,
                apply_at_position_count=decision.command.apply_at_position_count,
                z_target_steps=decision.command.z_target_steps,
                hardware_outputs_enabled=False,
            )
        )

    def _record_rejected(self, decision: ZScheduleDecision) -> None:
        if decision.reason is None:
            raise AssertionError("rejected decision requires a reason")
        outcome = ZSchedulerOutcome(
            seq=decision.seq,
            outcome="rejected",
            scan_id=decision.command.scan_id,
            stripe_id=decision.command.stripe_id,
            command_id=decision.command.command_id,
            apply_target_kind=_target_kind(decision.command),
            apply_at_frame_id=decision.command.apply_at_frame_id,
            apply_at_position_count=decision.command.apply_at_position_count,
            z_target_steps=decision.command.z_target_steps,
            reason=decision.reason,
            hardware_outputs_enabled=False,
        )
        self._outcomes.append(outcome)
        self._terminal_outcome_by_seq[decision.seq] = outcome

    def _record_applied(self, event: ZAppliedEvent) -> None:
        outcome = ZSchedulerOutcome(
            seq=event.seq,
            outcome="applied",
            scan_id=event.scan_id,
            stripe_id=event.stripe_id,
            command_id=event.command_id,
            apply_target_kind=event.apply_target_kind,
            apply_at_frame_id=event.apply_at_frame_id,
            apply_at_position_count=event.apply_at_position_count,
            applied_frame_id=event.frame_id,
            applied_position=event.position,
            z_target_steps=event.z_target_steps,
            hardware_outputs_enabled=False,
        )
        self._outcomes.append(outcome)
        self._terminal_outcome_by_seq[event.seq] = outcome

    def _in_no_correction_window(self, target_kind: TargetKind, target: int) -> bool:
        return any(
            _window_contains(window, target_kind=target_kind, target=target)
            for window in self.config.no_correction_windows
        )

    def _position_within_stripe(self, position: int) -> bool:
        lower = min(self.context.start_position, self.context.end_position)
        upper = max(self.context.start_position, self.context.end_position)
        return lower <= position <= upper

    def _progress_delta(self, start: int, end: int) -> int:
        return (end - start) * self.context.direction

    def _progress_from_start(self, position: int) -> int:
        return self._progress_delta(self.context.start_position, position)


def _target_kind(command: Any) -> TargetKind | None:
    target_kind = getattr(command, "target_kind", None)
    if target_kind is not None:
        return target_kind
    has_frame = getattr(command, "apply_at_frame_id", None) is not None
    has_position = getattr(command, "apply_at_position_count", None) is not None
    if has_frame == has_position:
        return None
    if has_frame:
        return "frame"
    return "position"


def _target_value(command: Any) -> int | None:
    target_value = getattr(command, "target_value", None)
    if target_value is not None:
        return target_value
    if getattr(command, "apply_at_frame_id", None) is not None:
        return command.apply_at_frame_id
    return getattr(command, "apply_at_position_count", None)


def _window_contains(window: Any, *, target_kind: TargetKind, target: int) -> bool:
    try:
        return bool(window.contains(target_kind=target_kind, target=target))
    except TypeError:
        return bool(window.target_kind == target_kind and window.contains(target))


def _required_frame_lookahead(config: Any) -> int:
    explicit = getattr(config, "required_frame_lookahead", None)
    if explicit is not None:
        return explicit
    return int(getattr(config, "lead_frames", 0) + getattr(config, "settle_frames", 0))


def _required_position_lookahead(config: Any) -> float:
    explicit = getattr(config, "required_position_lookahead", None)
    if explicit is not None:
        return explicit
    return float(
        getattr(config, "lead_position_steps", 0)
        + getattr(config, "settle_position_steps", 0)
    )


__all__ = ["PredictiveZSchedulerSimulator"]
