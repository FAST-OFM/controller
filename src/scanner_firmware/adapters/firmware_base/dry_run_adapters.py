"""Dry-run adapters for firmware-base spike candidates.

These adapters convert synthetic candidate-specific position streams into the
common dry-run scheduler input. They do not call Klipper, grblHAL, controller
firmware, GPIO, camera, LED or motor APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_core.scan_units import round_half_away_from_zero
from scanner_firmware.planning.trigger_scheduler.types import PositionSample


Axis = Literal["X", "Y"]


@dataclass(frozen=True)
class KlipperCommandedPositionSample:
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int = 0
    event_time_s: float = 0.0


@dataclass(frozen=True)
class GrblHalPlannerSnapshot:
    x_machine_count: int
    y_machine_count: int
    z_machine_count: int = 0
    tick_us: int = 0


@dataclass(frozen=True)
class StepDirPulse:
    axis: Axis
    direction: Literal[-1, 1]
    timestamp_us: int
    pulse_count: int = 1


class DryRunAdapterError(ValueError):
    """Raised when a synthetic candidate stream is invalid."""


def klipper_commanded_positions_to_samples(
    positions: list[KlipperCommandedPositionSample],
) -> list[PositionSample]:
    """Map synthetic Klipper commanded positions to scheduler samples."""

    return [
        PositionSample(
            x_step_commanded=position.x_step_commanded,
            y_step_commanded=position.y_step_commanded,
            z_step_commanded=position.z_step_commanded,
            mcu_time_us=_seconds_to_microseconds(position.event_time_s),
        )
        for position in positions
    ]


def grblhal_planner_snapshots_to_samples(
    snapshots: list[GrblHalPlannerSnapshot],
) -> list[PositionSample]:
    """Map synthetic grblHAL planner snapshots to scheduler samples."""

    return [
        PositionSample(
            x_step_commanded=snapshot.x_machine_count,
            y_step_commanded=snapshot.y_machine_count,
            z_step_commanded=snapshot.z_machine_count,
            mcu_time_us=snapshot.tick_us,
        )
        for snapshot in snapshots
    ]


def step_dir_pulses_to_samples(
    pulses: list[StepDirPulse],
    *,
    x_start_count: int = 0,
    y_start_count: int = 0,
    z_step_commanded: int = 0,
) -> list[PositionSample]:
    """Convert synthetic STEP/DIR pulses into commanded-position samples."""

    x_count = x_start_count
    y_count = y_start_count
    samples: list[PositionSample] = []

    for pulse in pulses:
        _validate_pulse(pulse)
        if pulse.axis == "X":
            x_count += pulse.direction * pulse.pulse_count
        elif pulse.axis == "Y":
            y_count += pulse.direction * pulse.pulse_count
        else:
            raise DryRunAdapterError(f"unsupported axis: {pulse.axis}")

        samples.append(
            PositionSample(
                x_step_commanded=x_count,
                y_step_commanded=y_count,
                z_step_commanded=z_step_commanded,
                mcu_time_us=pulse.timestamp_us,
            )
        )

    return samples


def _seconds_to_microseconds(value: float) -> int:
    if value < 0:
        raise DryRunAdapterError("event_time_s must be non-negative")
    return round_half_away_from_zero(value * 1_000_000, name="event_time_us")


def _validate_pulse(pulse: StepDirPulse) -> None:
    if pulse.direction not in (-1, 1):
        raise DryRunAdapterError("direction must be -1 or 1")
    if pulse.pulse_count <= 0:
        raise DryRunAdapterError("pulse_count must be positive")
    if pulse.timestamp_us < 0:
        raise DryRunAdapterError("timestamp_us must be non-negative")
