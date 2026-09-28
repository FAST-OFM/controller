"""Stationary AF timing-test protocol planning."""

from __future__ import annotations

from scanner_firmware.foundation.protocol.events import (
    FrameEventRecord,
    RunStationaryAfTestCommand,
)
from scanner_firmware.planning.led_scheduler.atomic_window import (
    MKS_V1_AF_PATTERN,
    MksV1AtomicIlluminationWindowConfig,
    build_mks_v1_no_motion_af_window,
)
from scanner_firmware.planning.led_scheduler.constants import (
    LED_GREEN_GATE,
    LED_RED_GATE,
)


def build_stationary_af_test_frame_events(
    command: RunStationaryAfTestCommand,
    *,
    protocol_version: int = 1,
    first_mcu_time_us: int | None = None,
    trigger_output_name: str = "hq_xvs_sync",
) -> tuple[FrameEventRecord, ...]:
    """Build no-motion FRAME_EVENT records for a stationary AF timing test.

    The returned records are protocol metadata for simulator and host-side
    validation. They do not open a controller, toggle outputs or move axes.
    """

    records: list[FrameEventRecord] = []
    base_mcu_time_us = command.settle_us if first_mcu_time_us is None else first_mcu_time_us
    for frame_index in range(command.frame_count):
        mcu_time_us = base_mcu_time_us + frame_index * command.frame_period_us
        window = build_mks_v1_no_motion_af_window(
            MksV1AtomicIlluminationWindowConfig(
                frame_start_us=mcu_time_us,
                settle_us=command.settle_us,
                exposure_hold_us=command.exposure_hold_us,
                xvs_trigger_pulse_us=command.xvs_trigger_pulse_us,
                trigger_position_count=command.event_position_count,
                frame_period_us=command.frame_period_us,
            )
        )
        x_count = command.event_position_count if command.position_axis == "X" else 0
        y_count = command.event_position_count if command.position_axis == "Y" else 0
        records.append(
            FrameEventRecord(
                protocol_version=protocol_version,
                scan_id=command.scan_id,
                stripe_id=command.stripe_id,
                frame_id=command.first_frame_id + frame_index,
                stripe_frame_index=frame_index,
                pattern=MKS_V1_AF_PATTERN,
                coordinate_source_used="step_indexed",
                position_axis=command.position_axis,
                event_position=command.event_position_count,
                sample_position=command.event_position_count,
                position_overshoot_count=0,
                x_count=x_count,
                y_count=y_count,
                z_count=0,
                x_step_commanded=x_count,
                y_step_commanded=y_count,
                z_step_commanded=0,
                mcu_time_us=mcu_time_us,
                led_gate_names=(LED_RED_GATE, LED_GREEN_GATE),
                led_timing=window.contract.to_json_dict(),
                trigger_output_name=trigger_output_name,
                hardware_outputs_enabled=False,
                status="ok",
            )
        )
    return tuple(records)
