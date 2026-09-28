"""Deterministic simulator-only scan execution traces."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_core.scan_geometry import Axis
from scanner_firmware.planning.scan_execution.modes import ALL_SCAN_MODES, ScanMode
from scanner_firmware.planning.scan_execution.plan import (
    ExecutionFramePlan,
    ExecutionScanPlan,
    ExecutionStripePlan,
)
from scanner_firmware.planning.scan_execution.states import (
    ScanExecutionError,
    TerminalReason,
)


EXECUTE_ILLUMINATION_AND_TRIGGER = "EXECUTE_ILLUMINATION_AND_TRIGGER"

STOP_AND_CAPTURE_STEPS = (
    "MOVE_TO_TARGET",
    "SETTLE_XY",
    "OPTIONAL_Z",
    "SETTLE_Z",
    EXECUTE_ILLUMINATION_AND_TRIGGER,
    "FRAME_EVENT",
    "NEXT_FRAME",
)
MICRO_STOP_STEPS = (
    "MOVE_INCREMENT",
    "HOLD",
    EXECUTE_ILLUMINATION_AND_TRIGGER,
    "FRAME_EVENT",
    "OPTIONAL_Z_WINDOW",
    "NEXT_INCREMENT",
)
SEGMENTED_FLY_SCAN_FRAME_STEPS = (
    "SCAN_SEGMENT_WITH_POSITION_TRIGGER",
    EXECUTE_ILLUMINATION_AND_TRIGGER,
    "FRAME_EVENT",
)
FLY_SCAN_OPEN_LOOP_FRAME_STEPS = (
    "CONSTANT_VELOCITY_POSITION_TRIGGER",
    EXECUTE_ILLUMINATION_AND_TRIGGER,
    "FRAME_EVENT",
)
FLY_SCAN_PREDICTIVE_Z_FRAME_STEPS = (
    "CONSTANT_VELOCITY_POSITION_TRIGGER",
    EXECUTE_ILLUMINATION_AND_TRIGGER,
    "FRAME_EVENT",
    "PREDICTIVE_Z_QUEUE_CHECK",
    "APPLY_SCHEDULED_Z",
)


@dataclass(frozen=True)
class ScanExecutionTraceEvent:
    """One software-only execution trace event."""

    sequence: int
    scan_id: str
    mode: ScanMode
    step: str
    stripe_id: int | None = None
    frame_id: int | None = None
    stripe_frame_index: int | None = None
    position_axis: Axis | None = None
    event_position: int | None = None
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise ScanExecutionError("trace event sequence must be an integer")
        if self.sequence < 0:
            raise ScanExecutionError("trace event sequence must be non-negative")
        if not isinstance(self.scan_id, str) or not self.scan_id:
            raise ScanExecutionError("trace event scan_id must be a non-empty string")
        if self.mode not in ALL_SCAN_MODES:
            raise ScanExecutionError(f"trace event mode is not canonical: {self.mode}")
        if not isinstance(self.step, str) or not self.step:
            raise ScanExecutionError("trace event step must be a non-empty string")
        if self.position_axis is not None and self.position_axis not in ("X", "Y"):
            raise ScanExecutionError("trace event position_axis must be X or Y")
        if self.hardware_outputs_enabled is not False:
            raise ScanExecutionError(
                "simulator scan execution traces require hardware_outputs_enabled=false"
            )


@dataclass(frozen=True)
class ScanExecutionTrace:
    """Complete deterministic trace for one compiled dry-run scan plan."""

    scan_id: str
    mode: ScanMode
    events: tuple[ScanExecutionTraceEvent, ...]
    terminal_reason: TerminalReason = "DRY_RUN_COMPLETE"
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.scan_id, str) or not self.scan_id:
            raise ScanExecutionError("trace scan_id must be a non-empty string")
        if self.mode not in ALL_SCAN_MODES:
            raise ScanExecutionError(f"trace mode is not canonical: {self.mode}")
        if not self.events:
            raise ScanExecutionError("trace events must be non-empty")
        if self.hardware_outputs_enabled is not False:
            raise ScanExecutionError(
                "simulator scan execution traces require hardware_outputs_enabled=false"
            )
        for expected_sequence, event in enumerate(self.events):
            if event.sequence != expected_sequence:
                raise ScanExecutionError("trace event sequences must be contiguous")
            if event.scan_id != self.scan_id:
                raise ScanExecutionError("trace event scan_id must match trace")
            if event.mode != self.mode:
                raise ScanExecutionError("trace event mode must match trace")

    @property
    def frame_event_count(self) -> int:
        return sum(1 for event in self.events if event.step == "FRAME_EVENT")

    @property
    def steps(self) -> tuple[str, ...]:
        return tuple(event.step for event in self.events)


def build_simulator_scan_execution_trace(plan: ExecutionScanPlan) -> ScanExecutionTrace:
    """Build a deterministic dry-run execution trace for a compiled scan plan."""

    _validate_plan(plan)
    mode = _single_canonical_mode(plan)
    builder = _TraceBuilder(scan_id=plan.scan_id, mode=mode)
    builder.add_plan_step("SCAN_PREPARE")

    if mode == "stop_and_capture":
        _trace_frames(builder, plan.frames, STOP_AND_CAPTURE_STEPS)
    elif mode == "micro_stop":
        _trace_frames(builder, plan.frames, MICRO_STOP_STEPS)
    elif mode == "segmented_fly_scan":
        _trace_segmented_fly_scan(builder, plan.stripes)
    elif mode == "fly_scan_open_loop":
        _trace_fly_scan(builder, plan.stripes, FLY_SCAN_OPEN_LOOP_FRAME_STEPS)
    elif mode == "fly_scan_predictive_z":
        _trace_fly_scan(builder, plan.stripes, FLY_SCAN_PREDICTIVE_Z_FRAME_STEPS)
    else:
        raise ScanExecutionError(f"unsupported scan execution mode: {mode}")

    builder.add_plan_step("DRY_RUN_COMPLETE")
    return ScanExecutionTrace(
        scan_id=plan.scan_id,
        mode=mode,
        events=builder.events,
    )


class _TraceBuilder:
    def __init__(self, *, scan_id: str, mode: ScanMode) -> None:
        self._scan_id = scan_id
        self._mode = mode
        self._events: list[ScanExecutionTraceEvent] = []

    @property
    def events(self) -> tuple[ScanExecutionTraceEvent, ...]:
        return tuple(self._events)

    def add_plan_step(self, step: str) -> None:
        self._add(step=step)

    def add_stripe_step(self, step: str, stripe: ExecutionStripePlan) -> None:
        self._add(
            step=step,
            stripe_id=stripe.stripe_id,
            position_axis=stripe.scan_axis,
        )

    def add_frame_step(self, step: str, frame: ExecutionFramePlan) -> None:
        self._add(
            step=step,
            stripe_id=frame.stripe_id,
            frame_id=frame.frame_id,
            stripe_frame_index=frame.stripe_frame_index,
            position_axis=frame.scan_axis,
            event_position=frame.scan_axis_position,
        )

    def _add(
        self,
        *,
        step: str,
        stripe_id: int | None = None,
        frame_id: int | None = None,
        stripe_frame_index: int | None = None,
        position_axis: Axis | None = None,
        event_position: int | None = None,
    ) -> None:
        self._events.append(
            ScanExecutionTraceEvent(
                sequence=len(self._events),
                scan_id=self._scan_id,
                mode=self._mode,
                step=step,
                stripe_id=stripe_id,
                frame_id=frame_id,
                stripe_frame_index=stripe_frame_index,
                position_axis=position_axis,
                event_position=event_position,
                hardware_outputs_enabled=False,
            )
        )


def _trace_frames(
    builder: _TraceBuilder,
    frames: tuple[ExecutionFramePlan, ...],
    steps: tuple[str, ...],
) -> None:
    for frame in frames:
        for step in steps:
            builder.add_frame_step(step, frame)


def _trace_segmented_fly_scan(
    builder: _TraceBuilder,
    stripes: tuple[ExecutionStripePlan, ...],
) -> None:
    for stripe in stripes:
        builder.add_stripe_step("ACCELERATE", stripe)
        _trace_frames(builder, stripe.frames, SEGMENTED_FLY_SCAN_FRAME_STEPS)
        builder.add_stripe_step("BOUNDARY_WINDOW", stripe)
        builder.add_stripe_step("OPTIONAL_Z", stripe)
        builder.add_stripe_step("NEXT_SEGMENT", stripe)


def _trace_fly_scan(
    builder: _TraceBuilder,
    stripes: tuple[ExecutionStripePlan, ...],
    frame_steps: tuple[str, ...],
) -> None:
    for stripe in stripes:
        builder.add_stripe_step("ACCELERATE", stripe)
        _trace_frames(builder, stripe.frames, frame_steps)
        builder.add_stripe_step("DECELERATE", stripe)


def _validate_plan(plan: ExecutionScanPlan) -> None:
    if not isinstance(plan, ExecutionScanPlan):
        raise ScanExecutionError("plan must be an ExecutionScanPlan")
    if plan.dry_run is not True:
        raise ScanExecutionError("simulator scan execution traces require dry_run=true")
    if plan.hardware_outputs_enabled is not False:
        raise ScanExecutionError(
            "simulator scan execution traces require hardware_outputs_enabled=false"
        )
    if not plan.frames:
        raise ScanExecutionError("plan must contain at least one frame")

    for stripe_index, stripe in enumerate(plan.stripes):
        if not isinstance(stripe, ExecutionStripePlan):
            raise ScanExecutionError(
                f"plan.stripes[{stripe_index}] must be an ExecutionStripePlan"
            )
        for frame_index, frame in enumerate(stripe.frames):
            _validate_frame(plan, stripe, stripe_index, frame, frame_index)


def _validate_frame(
    plan: ExecutionScanPlan,
    stripe: ExecutionStripePlan,
    stripe_index: int,
    frame: ExecutionFramePlan,
    frame_index: int,
) -> None:
    if not isinstance(frame, ExecutionFramePlan):
        raise ScanExecutionError(
            f"plan.stripes[{stripe_index}].frames[{frame_index}] "
            "must be an ExecutionFramePlan"
        )
    if frame.scan_id != plan.scan_id:
        raise ScanExecutionError("frame scan_id must match plan scan_id")
    if frame.stripe_id != stripe.stripe_id:
        raise ScanExecutionError("frame stripe_id must match stripe")
    if frame.dry_run is not True:
        raise ScanExecutionError("frame dry_run must be true")
    if frame.hardware_outputs_enabled is not False:
        raise ScanExecutionError(
            "simulator scan execution traces require hardware_outputs_enabled=false"
        )


def _single_canonical_mode(plan: ExecutionScanPlan) -> ScanMode:
    modes = {frame.scan_mode for frame in plan.frames}
    noncanonical = sorted(mode for mode in modes if mode not in ALL_SCAN_MODES)
    if noncanonical:
        raise ScanExecutionError(
            f"scan execution mode is not canonical: {', '.join(noncanonical)}"
        )
    if len(modes) != 1:
        raise ScanExecutionError("scan execution trace requires exactly one scan mode")
    return modes.pop()
