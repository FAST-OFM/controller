"""Validation rules for decoded scanner-sync event streams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    ScannerSyncEventStreamError,
    ScannerSyncStreamValidation,
    ZOutcomeValidation,
)
from scanner_firmware.foundation.protocol.events import (
    FrameEventRecord,
    ProtocolRecord,
    SchedulerTerminalRecord,
    TimedOutputSequenceStatusRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
)


def validate_scanner_sync_event_sequence(
    records: Iterable[ProtocolRecord],
    *,
    require_z_terminal_outcomes: bool = True,
    require_timed_output_sequence_terminal_outcomes: bool = True,
) -> ScannerSyncStreamValidation:
    """Validate ordering and terminal consistency for decoded protocol records."""

    frames: list[FrameEventRecord] = []
    terminals: list[SchedulerTerminalRecord] = []
    expected_stripe_index_by_stripe: dict[int, int] = {}
    terminal_stripes: set[int] = set()
    previous_frame_id: int | None = None
    stream_scan_id: str | None = None
    z_seq_state: dict[int, _ZSeqState] = {}
    timed_output_sequence_state: dict[int, _TimedOutputSequenceState] = {}
    z_scheduled_count = 0
    z_applied_count = 0
    z_rejected_count = 0
    timed_output_sequence_status_count = 0
    last_position_by_stripe: dict[int, int] = {}
    position_direction_by_stripe: dict[int, int] = {}

    for record_index, record in enumerate(records):
        if record.hardware_outputs_enabled:
            raise ScannerSyncEventStreamError(
                f"record {record_index}: hardware outputs must be disabled"
            )
        stream_scan_id = _validate_scan_identity(record_index, record, stream_scan_id)
        if isinstance(record, FrameEventRecord):
            if record.stripe_id in terminal_stripes:
                raise ScannerSyncEventStreamError(
                    f"FRAME_EVENT for stripe {record.stripe_id} follows SCHEDULER_TERMINAL"
                )
            if previous_frame_id is not None and record.frame_id != previous_frame_id + 1:
                raise ScannerSyncEventStreamError(
                    "FRAME_EVENT frame_id must be contiguous: "
                    f"expected {previous_frame_id + 1}, got {record.frame_id}"
                )
            previous_frame_id = record.frame_id

            expected_stripe_index = expected_stripe_index_by_stripe.get(record.stripe_id, 0)
            if record.stripe_frame_index != expected_stripe_index:
                raise ScannerSyncEventStreamError(
                    "FRAME_EVENT stripe_frame_index must be contiguous for stripe "
                    f"{record.stripe_id}: expected {expected_stripe_index}, "
                    f"got {record.stripe_frame_index}"
                )
            expected_stripe_index_by_stripe[record.stripe_id] = record.stripe_frame_index + 1
            _track_position_progress(
                record,
                last_position_by_stripe=last_position_by_stripe,
                position_direction_by_stripe=position_direction_by_stripe,
            )
            frames.append(record)
        elif isinstance(record, SchedulerTerminalRecord):
            if record.stripe_id in terminal_stripes:
                raise ScannerSyncEventStreamError(
                    f"duplicate SCHEDULER_TERMINAL for stripe {record.stripe_id}"
                )
            _validate_terminal_record(record, frames)
            terminal_stripes.add(record.stripe_id)
            terminals.append(record)
        elif isinstance(record, ZScheduledRecord):
            _validate_z_scheduled(
                record,
                z_seq_state,
                record_index=record_index,
                frames=frames,
                last_position_by_stripe=last_position_by_stripe,
                position_direction_by_stripe=position_direction_by_stripe,
            )
            z_scheduled_count += 1
        elif isinstance(record, ZAppliedRecord):
            _validate_z_applied(record, z_seq_state)
            z_applied_count += 1
        elif isinstance(record, ZRejectedRecord):
            _validate_z_rejected(record, z_seq_state)
            z_rejected_count += 1
        elif isinstance(record, TimedOutputSequenceStatusRecord):
            _validate_timed_output_sequence_status(
                record,
                timed_output_sequence_state,
                record_index=record_index,
            )
            timed_output_sequence_status_count += 1

    if require_z_terminal_outcomes:
        _validate_z_terminal_outcomes(z_seq_state)
    if require_timed_output_sequence_terminal_outcomes:
        _validate_timed_output_sequence_terminal_outcomes(timed_output_sequence_state)

    first_frame_id = frames[0].frame_id if frames else None
    last_frame_id = frames[-1].frame_id if frames else None
    return ScannerSyncStreamValidation(
        frame_count=len(frames),
        terminal_count=len(terminals),
        first_frame_id=first_frame_id,
        last_frame_id=last_frame_id,
        next_frame_id=(last_frame_id + 1 if last_frame_id is not None else None),
        stripes_seen=tuple(sorted({frame.stripe_id for frame in frames})),
        z_scheduled_count=z_scheduled_count,
        z_applied_count=z_applied_count,
        z_rejected_count=z_rejected_count,
        timed_output_sequence_status_count=timed_output_sequence_status_count,
        z_outcomes=tuple(
            state.to_outcome() for _, state in sorted(z_seq_state.items())
        ),
    )


@dataclass
class _TimedOutputSequenceState:
    seq_id: int
    first_record_index: int
    seq: int | None = None
    scan_id: str | None = None
    stripe_id: int | None = None
    accepted: bool = False
    started: bool = False
    terminal_status: str | None = None
    terminal_record_index: int | None = None


def _validate_terminal_record(
    terminal: SchedulerTerminalRecord,
    frames: list[FrameEventRecord],
) -> None:
    if terminal.status not in ("stopped", "fault"):
        raise ScannerSyncEventStreamError(
            "SCHEDULER_TERMINAL status must be stopped or fault; "
            "clean completion emits no terminal record"
        )
    stripe_frames = [frame for frame in frames if frame.stripe_id == terminal.stripe_id]
    if terminal.emitted_frame_count != len(stripe_frames):
        raise ScannerSyncEventStreamError(
            "SCHEDULER_TERMINAL emitted_frame_count does not match decoded "
            f"stripe frame count: expected {len(stripe_frames)}, "
            f"got {terminal.emitted_frame_count}"
        )
    if terminal.expected_frame_count < terminal.emitted_frame_count:
        raise ScannerSyncEventStreamError(
            "SCHEDULER_TERMINAL expected_frame_count must be >= emitted_frame_count"
        )
    if terminal.expected_frame_count == terminal.emitted_frame_count:
        raise ScannerSyncEventStreamError(
            "SCHEDULER_TERMINAL expected_frame_count must be greater than "
            "emitted_frame_count for stopped/fault records; clean completion "
            "emits no terminal record"
        )
    if stripe_frames:
        last_frame = stripe_frames[-1]
        if terminal.last_frame_id is not None and terminal.last_frame_id != last_frame.frame_id:
            raise ScannerSyncEventStreamError(
                "SCHEDULER_TERMINAL last_frame_id does not match last decoded "
                f"FRAME_EVENT: expected {last_frame.frame_id}, got {terminal.last_frame_id}"
            )
        if terminal.next_frame_id != last_frame.frame_id + 1:
            raise ScannerSyncEventStreamError(
                "SCHEDULER_TERMINAL next_frame_id does not follow last decoded "
                f"FRAME_EVENT: expected {last_frame.frame_id + 1}, "
                f"got {terminal.next_frame_id}"
            )
        if terminal.next_stripe_frame_index != last_frame.stripe_frame_index + 1:
            raise ScannerSyncEventStreamError(
                "SCHEDULER_TERMINAL next_stripe_frame_index does not follow last "
                f"decoded FRAME_EVENT: expected {last_frame.stripe_frame_index + 1}, "
                f"got {terminal.next_stripe_frame_index}"
            )
    elif terminal.last_frame_id is not None:
        raise ScannerSyncEventStreamError(
            "SCHEDULER_TERMINAL last_frame_id must be null when no frames emitted"
        )


def _validate_timed_output_sequence_status(
    record: TimedOutputSequenceStatusRecord,
    state_by_seq_id: dict[int, _TimedOutputSequenceState],
    *,
    record_index: int,
) -> None:
    state = state_by_seq_id.setdefault(
        record.seq_id,
        _TimedOutputSequenceState(
            seq_id=record.seq_id,
            first_record_index=record_index,
        ),
    )
    _validate_timed_output_sequence_identity(record, state, record_index=record_index)
    if state.terminal_status is not None:
        raise ScannerSyncEventStreamError(
            f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={record.seq_id} status "
            f"{record.status!r} appears after terminal status "
            f"{state.terminal_status!r} at record {state.terminal_record_index}"
        )

    if record.status == "accepted":
        if state.accepted:
            raise ScannerSyncEventStreamError(
                f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={record.seq_id} "
                "duplicates accepted status"
            )
        state.accepted = True
        return
    if record.status == "started":
        if not state.accepted:
            raise ScannerSyncEventStreamError(
                f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={record.seq_id} "
                "started before accepted"
            )
        if state.started:
            raise ScannerSyncEventStreamError(
                f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={record.seq_id} "
                "duplicates started status"
            )
        state.started = True
        return
    if record.status in {"completed", "stopped", "fault"}:
        if not state.accepted:
            raise ScannerSyncEventStreamError(
                f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={record.seq_id} "
                f"{record.status} before accepted"
            )
        if not state.started:
            raise ScannerSyncEventStreamError(
                f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={record.seq_id} "
                f"{record.status} before started"
            )
        state.terminal_status = record.status
        state.terminal_record_index = record_index
        return
    if record.status == "rejected":
        state.terminal_status = record.status
        state.terminal_record_index = record_index


def _validate_timed_output_sequence_identity(
    record: TimedOutputSequenceStatusRecord,
    state: _TimedOutputSequenceState,
    *,
    record_index: int,
) -> None:
    _validate_or_set_timed_output_identity(
        state,
        "seq",
        record.seq,
        record_index=record_index,
    )
    _validate_or_set_timed_output_identity(
        state,
        "scan_id",
        record.scan_id,
        record_index=record_index,
    )
    _validate_or_set_timed_output_identity(
        state,
        "stripe_id",
        record.stripe_id,
        record_index=record_index,
    )


def _validate_or_set_timed_output_identity(
    state: _TimedOutputSequenceState,
    field_name: str,
    value: int | str | None,
    *,
    record_index: int,
) -> None:
    if value is None:
        return
    existing = getattr(state, field_name)
    if existing is None:
        setattr(state, field_name, value)
        return
    if existing != value:
        raise ScannerSyncEventStreamError(
            f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={state.seq_id} {field_name} "
            f"changed from {existing!r} to {value!r} at record {record_index}"
        )


def _validate_timed_output_sequence_terminal_outcomes(
    state_by_seq_id: dict[int, _TimedOutputSequenceState],
) -> None:
    for seq_id, state in state_by_seq_id.items():
        if state.terminal_status is None:
            raise ScannerSyncEventStreamError(
                f"TIMED_OUTPUT_SEQUENCE_STATUS seq_id={seq_id} is missing terminal status"
            )


def _validate_z_scheduled(
    record: ZScheduledRecord,
    z_seq_state: dict[int, "_ZSeqState"],
    *,
    record_index: int,
    frames: list[FrameEventRecord],
    last_position_by_stripe: dict[int, int],
    position_direction_by_stripe: dict[int, int],
) -> None:
    prior = z_seq_state.get(record.seq)
    if prior is not None:
        raise ScannerSyncEventStreamError(
            f"Z_SCHEDULED seq={record.seq} duplicates existing Z state {prior.outcome}"
        )
    if record.status != "accepted":
        raise ScannerSyncEventStreamError(
            f"Z_SCHEDULED seq={record.seq} must have accepted status"
        )
    scheduled_after_frame_id = frames[-1].frame_id if frames else None
    scheduled_after_position = (
        last_position_by_stripe.get(record.stripe_id)
        if record.stripe_id is not None
        else None
    )
    scheduled_position_direction = (
        position_direction_by_stripe.get(record.stripe_id)
        if record.stripe_id is not None
        else None
    )
    z_seq_state[record.seq] = _ZSeqState(
        seq=record.seq,
        outcome="scheduled",
        scan_id=record.scan_id,
        stripe_id=record.stripe_id,
        command_id=record.command_id,
        scheduled_record_index=record_index,
        scheduled_after_frame_id=scheduled_after_frame_id,
        scheduled_after_position=scheduled_after_position,
        scheduled_position_direction=scheduled_position_direction,
    )


def _validate_z_applied(
    record: ZAppliedRecord,
    z_seq_state: dict[int, "_ZSeqState"],
) -> None:
    prior = z_seq_state.get(record.seq)
    if prior is None or prior.outcome != "scheduled":
        prior_outcome = prior.outcome if prior is not None else None
        raise ScannerSyncEventStreamError(
            f"Z_APPLIED seq={record.seq} requires prior Z_SCHEDULED, got {prior_outcome}"
        )
    if record.status != "ok":
        raise ScannerSyncEventStreamError(
            f"Z_APPLIED seq={record.seq} must have ok status"
        )
    _validate_z_identity(record, prior)
    _validate_z_apply_target(record, prior)
    z_seq_state[record.seq] = prior.applied(record)


def _validate_z_rejected(
    record: ZRejectedRecord,
    z_seq_state: dict[int, "_ZSeqState"],
) -> None:
    prior = z_seq_state.get(record.seq)
    if prior is not None:
        raise ScannerSyncEventStreamError(
            f"Z_REJECTED seq={record.seq} conflicts with existing Z state {prior.outcome}"
        )
    if record.status != "rejected":
        raise ScannerSyncEventStreamError(
            f"Z_REJECTED seq={record.seq} must have rejected status"
        )
    z_seq_state[record.seq] = _ZSeqState(
        seq=record.seq,
        outcome="rejected",
        scan_id=record.scan_id,
        stripe_id=record.stripe_id,
        command_id=record.command_id,
    )


def _validate_z_terminal_outcomes(z_seq_state: dict[int, "_ZSeqState"]) -> None:
    dangling = sorted(seq for seq, state in z_seq_state.items() if state.outcome == "scheduled")
    if dangling:
        formatted = ", ".join(str(seq) for seq in dangling)
        raise ScannerSyncEventStreamError(
            "Z_SCHEDULED records require one terminal outcome per seq; "
            f"missing Z_APPLIED for seq {formatted}"
        )


def _validate_scan_identity(
    record_index: int,
    record: ProtocolRecord,
    stream_scan_id: str | None,
) -> str | None:
    scan_id = getattr(record, "scan_id", None)
    if scan_id is None:
        return stream_scan_id
    if stream_scan_id is None:
        return scan_id
    if scan_id != stream_scan_id:
        raise ScannerSyncEventStreamError(
            f"record {record_index}: scan_id mismatch: expected {stream_scan_id}, got {scan_id}"
        )
    return stream_scan_id


def _track_position_progress(
    record: FrameEventRecord,
    *,
    last_position_by_stripe: dict[int, int],
    position_direction_by_stripe: dict[int, int],
) -> None:
    previous_position = last_position_by_stripe.get(record.stripe_id)
    if previous_position is not None and record.event_position != previous_position:
        direction = 1 if record.event_position > previous_position else -1
        previous_direction = position_direction_by_stripe.get(record.stripe_id)
        if previous_direction is not None and previous_direction != direction:
            raise ScannerSyncEventStreamError(
                f"FRAME_EVENT position direction changed for stripe {record.stripe_id}"
            )
        position_direction_by_stripe[record.stripe_id] = direction
    last_position_by_stripe[record.stripe_id] = record.event_position


def _validate_z_identity(record: ZAppliedRecord, prior: "_ZSeqState") -> None:
    _validate_optional_identity("scan_id", record.seq, prior.scan_id, record.scan_id)
    _validate_optional_identity("stripe_id", record.seq, prior.stripe_id, record.stripe_id)
    _validate_optional_identity("command_id", record.seq, prior.command_id, record.command_id)


def _validate_optional_identity(
    name: str,
    seq: int,
    expected: object | None,
    actual: object | None,
) -> None:
    if expected is not None and actual is not None and expected != actual:
        raise ScannerSyncEventStreamError(
            f"Z_APPLIED seq={seq} {name} mismatch: expected {expected}, got {actual}"
        )


def _validate_z_apply_target(record: ZAppliedRecord, prior: "_ZSeqState") -> None:
    if record.apply_target_kind is None:
        return
    if record.apply_target_kind == "frame":
        if record.apply_at_frame_id is None:
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} frame target requires apply_at_frame_id"
            )
        if record.apply_at_position_count is not None:
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} frame target cannot carry position target"
            )
        if record.frame_id != record.apply_at_frame_id:
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} frame_id must match apply_at_frame_id"
            )
        if (
            prior.scheduled_after_frame_id is not None
            and record.apply_at_frame_id <= prior.scheduled_after_frame_id
        ):
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} target frame is not after Z_SCHEDULED"
            )
        return

    if record.apply_target_kind == "position":
        if record.apply_at_position_count is None:
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} position target requires apply_at_position_count"
            )
        if record.apply_at_frame_id is not None:
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} position target cannot carry frame target"
            )
        if record.position is not None and record.position != record.apply_at_position_count:
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} position must match apply_at_position_count"
            )
        if (
            prior.scheduled_after_position is not None
            and prior.scheduled_position_direction is not None
            and (
                record.apply_at_position_count - prior.scheduled_after_position
            )
            * prior.scheduled_position_direction
            <= 0
        ):
            raise ScannerSyncEventStreamError(
                f"Z_APPLIED seq={record.seq} target position is not after Z_SCHEDULED"
            )
        return

    raise ScannerSyncEventStreamError(
        f"Z_APPLIED seq={record.seq} has unsupported apply_target_kind"
    )


class _ZSeqState:
    def __init__(
        self,
        *,
        seq: int,
        outcome: str,
        scan_id: str | None,
        stripe_id: int | None,
        command_id: str | None,
        scheduled_record_index: int | None = None,
        scheduled_after_frame_id: int | None = None,
        scheduled_after_position: int | None = None,
        scheduled_position_direction: int | None = None,
        apply_target_kind: str | None = None,
        apply_at_frame_id: int | None = None,
        apply_at_position_count: int | None = None,
        applied_frame_id: int | None = None,
        applied_position: int | None = None,
        z_target_steps: int | None = None,
    ) -> None:
        self.seq = seq
        self.outcome = outcome
        self.scan_id = scan_id
        self.stripe_id = stripe_id
        self.command_id = command_id
        self.scheduled_record_index = scheduled_record_index
        self.scheduled_after_frame_id = scheduled_after_frame_id
        self.scheduled_after_position = scheduled_after_position
        self.scheduled_position_direction = scheduled_position_direction
        self.apply_target_kind = apply_target_kind
        self.apply_at_frame_id = apply_at_frame_id
        self.apply_at_position_count = apply_at_position_count
        self.applied_frame_id = applied_frame_id
        self.applied_position = applied_position
        self.z_target_steps = z_target_steps

    def applied(self, record: ZAppliedRecord) -> "_ZSeqState":
        return _ZSeqState(
            seq=self.seq,
            outcome="applied",
            scan_id=record.scan_id or self.scan_id,
            stripe_id=record.stripe_id if record.stripe_id is not None else self.stripe_id,
            command_id=record.command_id or self.command_id,
            scheduled_record_index=self.scheduled_record_index,
            scheduled_after_frame_id=self.scheduled_after_frame_id,
            scheduled_after_position=self.scheduled_after_position,
            scheduled_position_direction=self.scheduled_position_direction,
            apply_target_kind=record.apply_target_kind,
            apply_at_frame_id=record.apply_at_frame_id,
            apply_at_position_count=record.apply_at_position_count,
            applied_frame_id=record.frame_id,
            applied_position=record.position,
            z_target_steps=record.z_target_steps,
        )

    def to_outcome(self) -> ZOutcomeValidation:
        return ZOutcomeValidation(
            seq=self.seq,
            outcome=self.outcome,
            scan_id=self.scan_id,
            stripe_id=self.stripe_id,
            command_id=self.command_id,
            apply_target_kind=self.apply_target_kind,
            apply_at_frame_id=self.apply_at_frame_id,
            apply_at_position_count=self.apply_at_position_count,
            applied_frame_id=self.applied_frame_id,
            applied_position=self.applied_position,
            z_target_steps=self.z_target_steps,
        )
