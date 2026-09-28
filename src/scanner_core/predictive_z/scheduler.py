"""No-hardware predictive-Z scheduler simulator."""

from __future__ import annotations

from .types import (
    QueuedZCommand,
    RejectReason,
    StripeContext,
    TargetKind,
    ZAppliedEvent,
    ZCommand,
    ZScheduleDecision,
    ZSchedulerConfig,
)


class PredictiveZSchedulerSimulator:
    """Queue future Z corrections and apply them against synthetic progress."""

    def __init__(self, config: ZSchedulerConfig, context: StripeContext):
        self._config = config
        self._scan_id = context.scan_id
        self._stripe_id = context.stripe_id
        self._start_position = context.start_position
        self._end_position = context.end_position
        self._current_position = context.position
        self._current_frame_id = context.current_frame_id
        self._queue: list[QueuedZCommand] = []
        self._next_sequence = 0

    @property
    def queued_count(self) -> int:
        return len(self._queue)

    @property
    def current_frame_id(self) -> int:
        return self._current_frame_id

    @property
    def current_position(self) -> int:
        return self._current_position

    def schedule(self, command: ZCommand) -> ZScheduleDecision:
        reason = self._reject_reason(command)
        if reason is not None:
            return ZScheduleDecision(
                accepted=False,
                status="rejected",
                reason=reason,
                command=command,
                hardware_outputs_enabled=False,
            )

        target_kind, sort_key = self._target(command)
        self._queue.append(
            QueuedZCommand(
                command=command,
                target_kind=target_kind,
                sort_key=sort_key,
                sequence=self._next_sequence,
            )
        )
        self._next_sequence += 1
        self._queue.sort(key=lambda queued: (queued.target_kind, queued.sort_key, queued.sequence))
        return ZScheduleDecision(
            accepted=True,
            status="accepted",
            reason=None,
            command=command,
            hardware_outputs_enabled=False,
        )

    def advance_to(
        self, *, frame_id: int | None = None, position: int | None = None
    ) -> list[ZAppliedEvent]:
        if frame_id is None and position is None:
            raise ValueError("frame_id or position is required")
        if frame_id is not None:
            if frame_id < self._current_frame_id:
                raise ValueError("frame_id cannot move backwards")
            self._current_frame_id = frame_id
        if position is not None:
            if self._position_distance(position) < 0:
                raise ValueError("position cannot move backwards along the stripe")
            if not self._position_within_stripe(position):
                raise ValueError("position must remain within stripe bounds")
            self._current_position = position

        applied: list[ZAppliedEvent] = []
        remaining: list[QueuedZCommand] = []
        for queued in self._queue:
            if self._queued_target_reached(queued):
                applied.append(self._applied_event(queued))
            else:
                remaining.append(queued)
        self._queue = remaining
        return applied

    def _reject_reason(self, command: ZCommand) -> RejectReason | None:
        if (command.apply_at_frame_id is None) == (command.apply_at_position_count is None):
            return "invalid_target"
        if command.scan_id != self._scan_id or command.stripe_id != self._stripe_id:
            return "scan_or_stripe_mismatch"
        if not self._config.min_z_steps <= command.z_target_steps <= self._config.max_z_steps:
            return "z_limit_exceeded"

        if command.apply_at_frame_id is not None:
            lookahead = command.apply_at_frame_id - self._current_frame_id
            if lookahead <= 0:
                return "target_already_passed"
            if lookahead < self._config.lead_frames + self._config.settle_frames:
                return "insufficient_lookahead"
            if self._target_in_no_correction_window("frame", command.apply_at_frame_id):
                return "no_correction_window"
            return None

        assert command.apply_at_position_count is not None
        if not self._position_within_stripe(command.apply_at_position_count):
            return "target_outside_stripe"
        lookahead = self._position_distance(command.apply_at_position_count)
        if lookahead <= 0:
            return "target_already_passed"
        if lookahead < self._config.lead_position_steps + self._config.settle_position_steps:
            return "insufficient_lookahead"
        if self._target_in_no_correction_window("position", command.apply_at_position_count):
            return "no_correction_window"
        return None

    def _target(self, command: ZCommand) -> tuple[TargetKind, int]:
        if command.apply_at_frame_id is not None:
            return "frame", command.apply_at_frame_id
        assert command.apply_at_position_count is not None
        return "position", self._position_progress(command.apply_at_position_count)

    def _queued_target_reached(self, queued: QueuedZCommand) -> bool:
        command = queued.command
        if queued.target_kind == "frame":
            assert command.apply_at_frame_id is not None
            return self._current_frame_id >= command.apply_at_frame_id
        assert command.apply_at_position_count is not None
        return self._position_distance(command.apply_at_position_count) <= 0

    def _applied_event(self, queued: QueuedZCommand) -> ZAppliedEvent:
        command = queued.command
        return ZAppliedEvent(
            type="Z_APPLIED",
            scan_id=command.scan_id,
            stripe_id=command.stripe_id,
            command_id=command.command_id,
            apply_target_kind=queued.target_kind,
            apply_at_frame_id=command.apply_at_frame_id,
            apply_at_position_count=command.apply_at_position_count,
            frame_id=self._current_frame_id,
            position=self._current_position,
            z_target_steps=command.z_target_steps,
            hardware_outputs_enabled=False,
            status="ok",
        )

    def _position_distance(self, position: int) -> int:
        return (position - self._current_position) * self._direction()

    def _position_progress(self, position: int) -> int:
        return (position - self._start_position) * self._direction()

    def _position_within_stripe(self, position: int) -> bool:
        lower = min(self._start_position, self._end_position)
        upper = max(self._start_position, self._end_position)
        return lower <= position <= upper

    def _direction(self) -> int:
        if self._end_position > self._start_position:
            return 1
        return -1

    def _target_in_no_correction_window(self, target_kind: TargetKind, target: int) -> bool:
        return any(
            window.target_kind == target_kind and window.contains(target)
            for window in self._config.no_correction_windows
        )
