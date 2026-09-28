"""Software-only timed output sequence interpreter.

The interpreter models the logical side effects of
``RunTimedOutputSequenceCommand`` without GPIO, Klipper, MCU timers or hardware
adapters. It is intended for planning/simulator tests that need to reason about
latched output state, repeat bounds and event-marker metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.foundation.protocol.events import (
    RunTimedOutputSequenceCommand,
    TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG,
    TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK,
    TimedOutputSequenceStep,
    timed_output_sequence_event_flag_names,
)

TimedOutputSequenceStatus = Literal["completed", "stopped", "fault"]
TimedOutputSequenceReason = Literal[
    "finite_completion",
    "host_stop",
    "simulator_repeat_bound",
    "simulator_fault",
]
TimedOutputSequenceFinalStateSource = Literal["idle", "safe"]

DEFAULT_MAX_INFINITE_REPEATS = 1024

class TimedOutputSequenceSimulatorError(ValueError):
    """Raised when simulator controls are internally inconsistent."""


@dataclass(frozen=True)
class TimedOutputSequenceEventFlagTrace:
    """Decoded event flags observed at one simulated step."""

    trace_index: int
    repeat_index: int
    step_index: int
    mcu_time_us: int
    event_flags: int
    event_flag_names: tuple[str, ...]
    frame_event_marker: bool


@dataclass(frozen=True)
class TimedOutputSequenceStepTrace:
    """Logical output state transition for one simulated sequence step."""

    trace_index: int
    repeat_index: int
    step_index: int
    start_time_us: int
    end_time_us: int
    delay_us: int
    output_mask: int
    output_values: int
    latched_outputs_before: int
    latched_outputs_after: int
    event_flags: int
    event_flag_names: tuple[str, ...]
    frame_event_marker: bool
    hardware_outputs_enabled: bool = False


@dataclass(frozen=True)
class TimedOutputSequenceRunResult:
    """Complete software-only result for one timed-output command."""

    scan_id: str
    stripe_id: int
    command_seq: int
    seq_id: int
    status: TimedOutputSequenceStatus
    reason_code: TimedOutputSequenceReason
    repeat_count_requested: int
    repeat_count_executed: int
    max_infinite_repeats: int
    bounded_by_simulator_max: bool
    elapsed_us: int
    step_trace: tuple[TimedOutputSequenceStepTrace, ...]
    event_flag_trace: tuple[TimedOutputSequenceEventFlagTrace, ...]
    frame_event_marker_count: int
    final_state_source: TimedOutputSequenceFinalStateSource
    final_latched_outputs_before_terminal_state: int
    final_latched_outputs_after_terminal_state: int
    final_output_mask: int
    final_output_values: int
    hardware_outputs_enabled: bool = False


class TimedOutputSequenceSimulator:
    """Interpret timed-output commands as deterministic metadata traces."""

    def __init__(
        self,
        *,
        max_infinite_repeats: int = DEFAULT_MAX_INFINITE_REPEATS,
        initial_latched_outputs: int = 0,
    ) -> None:
        _require_positive_int("max_infinite_repeats", max_infinite_repeats)
        _require_known_output_byte("initial_latched_outputs", initial_latched_outputs)
        self._max_infinite_repeats = max_infinite_repeats
        self._initial_latched_outputs = initial_latched_outputs

    @property
    def max_infinite_repeats(self) -> int:
        return self._max_infinite_repeats

    @property
    def initial_latched_outputs(self) -> int:
        return self._initial_latched_outputs

    def run(
        self,
        command: RunTimedOutputSequenceCommand,
        *,
        stop_after_steps: int | None = None,
        fault_after_steps: int | None = None,
        fault_message: str = "simulated timed-output sequence fault",
    ) -> TimedOutputSequenceRunResult:
        """Run a command until finite completion, stop, fault or repeat bound.

        ``stop_after_steps`` and ``fault_after_steps`` count emitted step traces.
        A value of ``0`` terminates before the first step. If both controls are
        provided, the earliest threshold wins; equal thresholds prefer fault.
        """

        _validate_control("stop_after_steps", stop_after_steps)
        _validate_control("fault_after_steps", fault_after_steps)
        if not fault_message:
            raise TimedOutputSequenceSimulatorError("fault_message must be non-empty")
        if not command.diagnostic_only:
            raise TimedOutputSequenceSimulatorError(
                "timed output sequence simulator accepts diagnostic-only commands"
            )

        trace: list[TimedOutputSequenceStepTrace] = []
        event_flag_trace: list[TimedOutputSequenceEventFlagTrace] = []
        repeat_limit = _repeat_limit(command, self._max_infinite_repeats)
        latched_outputs = self._initial_latched_outputs
        elapsed_us = 0
        status: TimedOutputSequenceStatus = "completed"
        reason_code: TimedOutputSequenceReason = "finite_completion"
        repeat_count_executed = 0

        for repeat_index in range(repeat_limit):
            for step_index, step in enumerate(command.steps):
                terminal = _terminal_for_controls(
                    step_count=len(trace),
                    stop_after_steps=stop_after_steps,
                    fault_after_steps=fault_after_steps,
                )
                if terminal is not None:
                    status, reason_code = terminal
                    return _build_result(
                        command=command,
                        status=status,
                        reason_code=reason_code,
                        max_infinite_repeats=self._max_infinite_repeats,
                        bounded_by_simulator_max=False,
                        repeat_count_executed=repeat_count_executed,
                        elapsed_us=elapsed_us,
                        latched_outputs=latched_outputs,
                        step_trace=tuple(trace),
                        event_flag_trace=tuple(event_flag_trace),
                    )

                before = latched_outputs
                latched_outputs = _apply_step(before, step)
                flag_names = _event_flag_names(step.event_flags)
                frame_marker = bool(
                    step.event_flags & TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG
                )
                step_trace = TimedOutputSequenceStepTrace(
                    trace_index=len(trace),
                    repeat_index=repeat_index,
                    step_index=step_index,
                    start_time_us=elapsed_us,
                    end_time_us=elapsed_us + step.delay_us,
                    delay_us=step.delay_us,
                    output_mask=step.output_mask,
                    output_values=step.output_values,
                    latched_outputs_before=before,
                    latched_outputs_after=latched_outputs,
                    event_flags=step.event_flags,
                    event_flag_names=flag_names,
                    frame_event_marker=frame_marker,
                )
                trace.append(step_trace)
                event_flag_trace.append(
                    TimedOutputSequenceEventFlagTrace(
                        trace_index=step_trace.trace_index,
                        repeat_index=repeat_index,
                        step_index=step_index,
                        mcu_time_us=step_trace.start_time_us,
                        event_flags=step.event_flags,
                        event_flag_names=flag_names,
                        frame_event_marker=frame_marker,
                    )
                )
                elapsed_us += step.delay_us
                if step_index == len(command.steps) - 1:
                    repeat_count_executed += 1

                terminal = _terminal_for_controls(
                    step_count=len(trace),
                    stop_after_steps=stop_after_steps,
                    fault_after_steps=fault_after_steps,
                )
                if terminal is not None:
                    status, reason_code = terminal
                    return _build_result(
                        command=command,
                        status=status,
                        reason_code=reason_code,
                        max_infinite_repeats=self._max_infinite_repeats,
                        bounded_by_simulator_max=False,
                        repeat_count_executed=repeat_count_executed,
                        elapsed_us=elapsed_us,
                        latched_outputs=latched_outputs,
                        step_trace=tuple(trace),
                        event_flag_trace=tuple(event_flag_trace),
                    )

        bounded = command.repeat_count == 0
        if bounded:
            status = "stopped"
            reason_code = "simulator_repeat_bound"
        return _build_result(
            command=command,
            status=status,
            reason_code=reason_code,
            max_infinite_repeats=self._max_infinite_repeats,
            bounded_by_simulator_max=bounded,
            repeat_count_executed=repeat_count_executed,
            elapsed_us=elapsed_us,
            latched_outputs=latched_outputs,
            step_trace=tuple(trace),
            event_flag_trace=tuple(event_flag_trace),
        )


def simulate_timed_output_sequence(
    command: RunTimedOutputSequenceCommand,
    *,
    max_infinite_repeats: int = DEFAULT_MAX_INFINITE_REPEATS,
    initial_latched_outputs: int = 0,
    stop_after_steps: int | None = None,
    fault_after_steps: int | None = None,
    fault_message: str = "simulated timed-output sequence fault",
) -> TimedOutputSequenceRunResult:
    """Convenience wrapper for a one-shot timed-output sequence simulation."""

    return TimedOutputSequenceSimulator(
        max_infinite_repeats=max_infinite_repeats,
        initial_latched_outputs=initial_latched_outputs,
    ).run(
        command,
        stop_after_steps=stop_after_steps,
        fault_after_steps=fault_after_steps,
        fault_message=fault_message,
    )


def _apply_step(latched_outputs: int, step: TimedOutputSequenceStep) -> int:
    if step.output_mask == 0:
        return latched_outputs
    return _apply_output_state(
        latched_outputs,
        output_mask=step.output_mask,
        output_values=step.output_values,
    )


def _apply_output_state(
    latched_outputs: int,
    *,
    output_mask: int,
    output_values: int,
) -> int:
    return (latched_outputs & ~output_mask) | (output_values & output_mask)


def _build_result(
    *,
    command: RunTimedOutputSequenceCommand,
    status: TimedOutputSequenceStatus,
    reason_code: TimedOutputSequenceReason,
    max_infinite_repeats: int,
    bounded_by_simulator_max: bool,
    repeat_count_executed: int,
    elapsed_us: int,
    latched_outputs: int,
    step_trace: tuple[TimedOutputSequenceStepTrace, ...],
    event_flag_trace: tuple[TimedOutputSequenceEventFlagTrace, ...],
) -> TimedOutputSequenceRunResult:
    if status == "completed":
        final_state_source: TimedOutputSequenceFinalStateSource = "idle"
        final_output_mask = command.idle_output_mask
        final_output_values = command.idle_output_values
    else:
        final_state_source = "safe"
        final_output_mask = command.safe_output_mask
        final_output_values = command.safe_output_values
    final_latched_outputs = _apply_output_state(
        latched_outputs,
        output_mask=final_output_mask,
        output_values=final_output_values,
    )
    return TimedOutputSequenceRunResult(
        scan_id=command.scan_id,
        stripe_id=command.stripe_id,
        command_seq=command.seq,
        seq_id=command.seq_id,
        status=status,
        reason_code=reason_code,
        repeat_count_requested=command.repeat_count,
        repeat_count_executed=repeat_count_executed,
        max_infinite_repeats=max_infinite_repeats,
        bounded_by_simulator_max=bounded_by_simulator_max,
        elapsed_us=elapsed_us,
        step_trace=step_trace,
        event_flag_trace=event_flag_trace,
        frame_event_marker_count=sum(1 for event in event_flag_trace if event.frame_event_marker),
        final_state_source=final_state_source,
        final_latched_outputs_before_terminal_state=latched_outputs,
        final_latched_outputs_after_terminal_state=final_latched_outputs,
        final_output_mask=final_output_mask,
        final_output_values=final_output_values,
    )


def _terminal_for_controls(
    *,
    step_count: int,
    stop_after_steps: int | None,
    fault_after_steps: int | None,
) -> tuple[TimedOutputSequenceStatus, TimedOutputSequenceReason] | None:
    fault_due = fault_after_steps is not None and step_count >= fault_after_steps
    stop_due = stop_after_steps is not None and step_count >= stop_after_steps
    if fault_due:
        return "fault", "simulator_fault"
    if stop_due:
        return "stopped", "host_stop"
    return None


def _event_flag_names(event_flags: int) -> tuple[str, ...]:
    return timed_output_sequence_event_flag_names(event_flags)


def _validate_control(name: str, value: int | None) -> None:
    if value is None:
        return
    _require_non_negative_int(name, value)


def _require_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TimedOutputSequenceSimulatorError(f"{name} must be an integer")
    if value <= 0:
        raise TimedOutputSequenceSimulatorError(f"{name} must be positive")


def _require_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TimedOutputSequenceSimulatorError(f"{name} must be an integer")
    if value < 0:
        raise TimedOutputSequenceSimulatorError(f"{name} must be non-negative")


def _require_known_output_byte(name: str, value: int) -> None:
    _require_non_negative_int(name, value)
    if value & ~TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK:
        raise TimedOutputSequenceSimulatorError(
            f"{name} contains bits outside the known logical output mask"
        )


def _repeat_limit(command: RunTimedOutputSequenceCommand, max_infinite_repeats: int) -> int:
    return max_infinite_repeats if command.repeat_count == 0 else command.repeat_count
