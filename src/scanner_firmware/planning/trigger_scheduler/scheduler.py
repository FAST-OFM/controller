"""Dry-run position-event scheduler."""

from __future__ import annotations

from typing import Iterable

from scanner_firmware.domain.coordinate_source.errors import CoordinateSourceError
from scanner_firmware.domain.coordinate_source.fusion import resolve_coordinate
from scanner_firmware.domain.coordinate_source.types import (
    CoordinateSample,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError
from scanner_firmware.planning.led_scheduler.patterns import LogicalLedPatternResolver
from scanner_firmware.planning.led_scheduler.timing import (
    LogicalLedTimingModel,
    build_disabled_output_led_timing_contract,
)
from scanner_firmware.planning.led_scheduler.types import (
    LedPatternTimingProfile,
    LedPatternTimingSet,
)
from scanner_firmware.planning.trigger_scheduler.geometry import (
    frame_event_count,
    frame_events,
    sample_overshoot,
    sample_position,
    sample_reached,
    validate_schedule,
)
from scanner_firmware.planning.trigger_scheduler.types import (
    FrameEvent,
    PositionSample,
    ScheduleError,
    SchedulerEvent,
    SchedulerTerminalEvent,
    StripeSchedule,
    TerminalReasonCode,
    TerminalStatus,
)


class DryRunPositionEventScheduler:
    """Emit FRAME_EVENT records from commanded position samples."""

    def __init__(self, *, first_frame_id: int = 0, protocol_version: int = 1):
        if first_frame_id < 0:
            raise ValueError("first_frame_id must be non-negative")
        self._next_frame_id = first_frame_id
        self._protocol_version = protocol_version
        self._led_patterns = LogicalLedPatternResolver()
        self._led_timing = LogicalLedTimingModel()

    @property
    def next_frame_id(self) -> int:
        return self._next_frame_id

    def run(
        self,
        schedule: StripeSchedule,
        samples: Iterable[PositionSample],
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[SchedulerEvent]:
        validate_schedule(schedule)
        try:
            _validate_led_timing_profiles(
                schedule.pattern_led_timing,
                schedule.pattern_sequence,
            )
        except LedTimingError as exc:
            raise ScheduleError(str(exc), reason_code="scheduler_fault") from exc
        if stop_after_events is not None and stop_after_events < 0:
            raise ValueError("stop_after_events must be non-negative")
        if fault_after_events is not None and fault_after_events < 0:
            raise ValueError("fault_after_events must be non-negative")
        if stop_after_events is not None and fault_after_events is not None:
            raise ValueError("stop_after_events and fault_after_events are mutually exclusive")

        events: list[SchedulerEvent] = []
        next_position = schedule.first_event_position
        last_sample_time_us = 0
        if stop_after_events == 0:
            events.append(
                self._build_terminal_event(
                    schedule,
                    events,
                    status="stopped",
                    reason_code="host_stop",
                    mcu_time_us=0,
                    message="stop requested before frame emission",
                )
            )
            return events
        if fault_after_events == 0:
            events.append(
                self._build_terminal_event(
                    schedule,
                    events,
                    status="fault",
                    reason_code="scheduler_fault",
                    mcu_time_us=0,
                    message=fault_message,
                )
            )
            return events

        for sample in samples:
            last_sample_time_us = sample.mcu_time_us
            while frame_event_count(events) < schedule.event_count and sample_reached(
                schedule, sample, next_position
            ):
                frame_count = frame_event_count(events)
                try:
                    events.append(
                        self._build_event(
                            schedule,
                            sample,
                            frame_count,
                            event_position=next_position,
                        )
                    )
                except ScheduleError as exc:
                    events.append(
                        self._build_terminal_event(
                            schedule,
                            events,
                            status="fault",
                            reason_code=exc.reason_code,
                            mcu_time_us=sample.mcu_time_us,
                            message=str(exc),
                        )
                    )
                    self._next_frame_id += frame_count
                    return events
                frame_count += 1
                if (
                    stop_after_events is not None
                    and frame_count >= stop_after_events
                    and frame_count < schedule.event_count
                ):
                    events.append(
                        self._build_terminal_event(
                            schedule,
                            events,
                            status="stopped",
                            reason_code="host_stop",
                            mcu_time_us=sample.mcu_time_us,
                            message="stop requested during stripe execution",
                        )
                    )
                    self._next_frame_id += frame_count
                    return events
                if (
                    fault_after_events is not None
                    and frame_count >= fault_after_events
                    and frame_count < schedule.event_count
                ):
                    events.append(
                        self._build_terminal_event(
                            schedule,
                            events,
                            status="fault",
                            reason_code="scheduler_fault",
                            mcu_time_us=sample.mcu_time_us,
                            message=fault_message,
                        )
                    )
                    self._next_frame_id += frame_count
                    return events
                next_position += schedule.event_pitch

            if frame_event_count(events) >= schedule.event_count:
                break

        emitted_frame_count = frame_event_count(events)
        if emitted_frame_count < schedule.event_count:
            events.append(
                self._build_terminal_event(
                    schedule,
                    events,
                    status="fault",
                    reason_code="position_stream_exhausted",
                    mcu_time_us=last_sample_time_us,
                    message=(
                        "position sample stream ended before all planned "
                        "FRAME_EVENT records were emitted"
                    ),
                )
            )
        self._next_frame_id += emitted_frame_count
        return events

    def _build_event(
        self,
        schedule: StripeSchedule,
        sample: PositionSample,
        stripe_frame_index: int,
        *,
        event_position: int,
    ) -> FrameEvent:
        pattern = schedule.pattern_sequence[
            stripe_frame_index % len(schedule.pattern_sequence)
        ]
        led_pattern = self._led_patterns.resolve(pattern)
        led_timing = self._build_led_timing(schedule, sample, pattern)
        try:
            coordinate = resolve_coordinate(
                CoordinateSample(
                    x_step_commanded=sample.x_step_commanded,
                    y_step_commanded=sample.y_step_commanded,
                    z_step_commanded=sample.z_step_commanded,
                    x_encoder_count=sample.x_encoder_count,
                    y_encoder_count=sample.y_encoder_count,
                ),
                schedule.coordinate_source,
            )
        except CoordinateSourceError as exc:
            raise ScheduleError(str(exc), reason_code="coordinate_source_error") from exc
        current_position = sample_position(schedule, sample)
        position_overshoot_count = sample_overshoot(
            schedule,
            sample,
            event_position,
        )
        coordinate_flags = coordinate.flags
        if position_overshoot_count != 0:
            coordinate_flags = coordinate_flags + ("sample_overshot_event_position",)
        x_count = coordinate.x_count
        y_count = coordinate.y_count
        if coordinate.source in ("step_indexed", "hybrid"):
            if schedule.axis == "X":
                x_count = event_position
            else:
                y_count = event_position
        return FrameEvent(
            type="FRAME_EVENT",
            protocol_version=self._protocol_version,
            scan_id=schedule.scan_id,
            stripe_id=schedule.stripe_id,
            frame_id=self._next_frame_id + stripe_frame_index,
            stripe_frame_index=stripe_frame_index,
            pattern=pattern,
            led_gate_names=led_pattern.gate_names,
            led_timing=led_timing,
            trigger_output_name="camera_or_sync_trigger",
            coordinate_source_used=coordinate.source,
            position_axis=schedule.axis,
            event_position=event_position,
            sample_position=current_position,
            position_overshoot_count=position_overshoot_count,
            x_count=x_count,
            y_count=y_count,
            z_count=coordinate.z_count,
            x_step_commanded=coordinate.x_step_commanded,
            y_step_commanded=coordinate.y_step_commanded,
            z_step_commanded=coordinate.z_step_commanded,
            x_encoder_count=coordinate.x_encoder_count,
            y_encoder_count=coordinate.y_encoder_count,
            coordinate_flags=coordinate_flags,
            mcu_time_us=sample.mcu_time_us,
            hardware_outputs_enabled=False,
            status="ok",
        )

    def _build_led_timing(
        self,
        schedule: StripeSchedule,
        sample: PositionSample,
        pattern: str,
    ) -> dict[str, object] | None:
        if schedule.pattern_led_timing is None:
            return None
        timing_profile = schedule.pattern_led_timing.profile_for(pattern)
        led_pattern = self._led_patterns.resolve(pattern)
        baseline_gate_names = _baseline_gate_names_for_pattern(
            timing_profile,
            led_pattern.frame_use,
        )
        try:
            plan = self._led_timing.plan_frame(
                pattern=pattern,
                frame_start_us=sample.mcu_time_us,
                exposure_start_us=sample.mcu_time_us
                + timing_profile.exposure_start_offset_us,
                exposure_us=timing_profile.exposure_us,
                gate_pulse_us=timing_profile.gate_pulse_us,
                settle_us=timing_profile.settle_us,
                frame_period_us=timing_profile.frame_period_us,
                trigger_pulse_us=timing_profile.trigger_pulse_us,
                gate_pre_trigger_us=timing_profile.gate_pre_trigger_us,
                gate_post_exposure_us=timing_profile.gate_post_exposure_us,
                baseline_gate_names=baseline_gate_names,
                baseline_suppress_pre_gate_us=timing_profile.baseline_suppress_pre_gate_us,
                baseline_restore_post_gate_us=timing_profile.baseline_restore_post_gate_us,
                polarity=timing_profile.polarity,
                brightness_by_gate=_brightness_for_active_gates(
                    timing_profile.brightness_by_gate,
                    led_pattern.gate_names,
                    led_pattern.gate_names + baseline_gate_names,
                ),
            )
        except LedTimingError as exc:
            raise ScheduleError(str(exc), reason_code="scheduler_fault") from exc
        return build_disabled_output_led_timing_contract(plan).to_json_dict()

    def _build_terminal_event(
        self,
        schedule: StripeSchedule,
        events: list[SchedulerEvent],
        *,
        status: TerminalStatus,
        reason_code: TerminalReasonCode,
        mcu_time_us: int,
        message: str,
    ) -> SchedulerTerminalEvent:
        emitted_events = frame_events(events)
        return SchedulerTerminalEvent(
            type="SCHEDULER_TERMINAL",
            protocol_version=self._protocol_version,
            scan_id=schedule.scan_id,
            stripe_id=schedule.stripe_id,
            status=status,
            reason_code=reason_code,
            emitted_frame_count=len(emitted_events),
            expected_frame_count=schedule.event_count,
            last_frame_id=emitted_events[-1].frame_id if emitted_events else None,
            next_frame_id=self._next_frame_id + len(emitted_events),
            next_stripe_frame_index=len(emitted_events),
            mcu_time_us=mcu_time_us,
            hardware_outputs_enabled=False,
            message=message,
        )


def _brightness_for_active_gates(
    brightness_by_gate: dict[str, float] | None,
    gate_names: tuple[str, ...],
    allowed_gate_names: tuple[str, ...],
) -> dict[str, float] | None:
    if brightness_by_gate is None:
        return None
    invalid_gate_names = sorted(set(brightness_by_gate) - set(allowed_gate_names))
    if invalid_gate_names:
        raise LedTimingError(
            "brightness setpoint for gate not used by schedule: "
            + ", ".join(invalid_gate_names)
        )
    return {
        gate_name: brightness_by_gate[gate_name]
        for gate_name in gate_names
        if gate_name in brightness_by_gate
    }


def _validate_led_timing_profiles(
    timing_set: LedPatternTimingSet | None,
    pattern_sequence: tuple[str, ...],
) -> None:
    if timing_set is None:
        return
    for pattern in tuple(dict.fromkeys(pattern_sequence)):
        timing_set.profile_for(pattern)


def _baseline_gate_names_for_pattern(
    config: LedPatternTimingProfile,
    frame_use: str,
) -> tuple[str, ...]:
    if frame_use != "autofocus":
        return ()
    return config.baseline_gate_names
