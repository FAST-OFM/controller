"""Calibration data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.validation import (
    require_axis,
    require_channel,
    require_finite,
    require_int,
)


Axis = Literal["X", "Y", "Z"]


@dataclass(frozen=True)
class AxisTravelObservation:
    axis: Axis
    commanded_steps: int
    measured_mm: float

    def __post_init__(self) -> None:
        require_axis(self.axis)
        require_int("commanded_steps", self.commanded_steps)
        require_finite("measured_mm", self.measured_mm)
        if self.commanded_steps == 0:
            raise CalibrationError("commanded_steps must be non-zero")
        if self.measured_mm == 0.0:
            raise CalibrationError("measured_mm must be non-zero")


@dataclass(frozen=True)
class AxisCalibrationEstimate:
    axis: Axis
    steps_per_mm: float
    sample_count: int
    residual_rms_mm: float
    min_observed_steps_per_mm: float
    max_observed_steps_per_mm: float


@dataclass(frozen=True)
class BacklashObservation:
    axis: Axis
    forward_position_mm: float
    reverse_position_mm: float

    def __post_init__(self) -> None:
        require_axis(self.axis)
        require_finite("forward_position_mm", self.forward_position_mm)
        require_finite("reverse_position_mm", self.reverse_position_mm)


@dataclass(frozen=True)
class BacklashEstimate:
    axis: Axis
    backlash_mm: float
    sample_count: int


@dataclass(frozen=True)
class RepeatabilityEstimate:
    axis: Axis
    sample_count: int
    mean_position_mm: float
    min_position_mm: float
    max_position_mm: float
    peak_to_peak_mm: float
    standard_deviation_mm: float


@dataclass(frozen=True)
class LedCalibrationSample:
    channel: str
    brightness: int
    current_ma: float

    def __post_init__(self) -> None:
        require_channel(self.channel)
        require_int("brightness", self.brightness)
        if not 0 <= self.brightness <= 255:
            raise CalibrationError("brightness must be between 0 and 255")
        require_finite("current_ma", self.current_ma)
        if self.current_ma < 0.0:
            raise CalibrationError("current_ma must be non-negative")
