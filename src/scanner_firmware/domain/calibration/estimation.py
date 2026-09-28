"""Axis calibration estimators."""

from __future__ import annotations

from math import sqrt

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.types import (
    Axis,
    AxisCalibrationEstimate,
    AxisTravelObservation,
    BacklashEstimate,
    BacklashObservation,
    RepeatabilityEstimate,
)
from scanner_firmware.domain.calibration.validation import require_axis, require_finite
from scanner_firmware.foundation.firmware_components.interfaces import (
    AxisCalibrationEstimate as ComponentAxisCalibrationEstimate,
)
from scanner_firmware.foundation.firmware_components.interfaces import (
    AxisCalibrationObservation,
    ComponentSafety,
)


def estimate_axis_steps_per_mm(
    observations: tuple[AxisTravelObservation, ...],
) -> AxisCalibrationEstimate:
    if not observations:
        raise CalibrationError("at least one axis travel observation is required")
    axis = observations[0].axis
    if any(observation.axis != axis for observation in observations):
        raise CalibrationError("all axis travel observations must use one axis")

    observed = tuple(
        abs(observation.commanded_steps / observation.measured_mm)
        for observation in observations
    )
    estimate = sum(observed) / len(observed)
    residuals = tuple(
        abs(observation.measured_mm) - (abs(observation.commanded_steps) / estimate)
        for observation in observations
    )
    return AxisCalibrationEstimate(
        axis=axis,
        steps_per_mm=estimate,
        sample_count=len(observations),
        residual_rms_mm=_rms(residuals),
        min_observed_steps_per_mm=min(observed),
        max_observed_steps_per_mm=max(observed),
    )


class AxisTravelCalibrationEstimator:
    """Shared-interface adapter for axis travel calibration."""

    safety = ComponentSafety()

    def estimate_axis(
        self,
        observations: tuple[AxisCalibrationObservation, ...],
    ) -> ComponentAxisCalibrationEstimate:
        estimate = estimate_axis_steps_per_mm(
            tuple(
                AxisTravelObservation(
                    axis=observation.axis,
                    commanded_steps=observation.commanded_steps,
                    measured_mm=observation.measured_mm,
                )
                for observation in observations
            )
        )
        return ComponentAxisCalibrationEstimate(
            axis=estimate.axis,
            steps_per_mm=estimate.steps_per_mm,
            sample_count=estimate.sample_count,
            residual_rms_mm=estimate.residual_rms_mm,
        )


def estimate_backlash(
    observations: tuple[BacklashObservation, ...],
) -> BacklashEstimate:
    if not observations:
        raise CalibrationError("at least one backlash observation is required")
    axis = observations[0].axis
    if any(observation.axis != axis for observation in observations):
        raise CalibrationError("all backlash observations must use one axis")
    backlash_values = tuple(
        abs(observation.forward_position_mm - observation.reverse_position_mm)
        for observation in observations
    )
    return BacklashEstimate(
        axis=axis,
        backlash_mm=sum(backlash_values) / len(backlash_values),
        sample_count=len(backlash_values),
    )


def estimate_repeatability(
    axis: Axis,
    positions_mm: tuple[float, ...],
) -> RepeatabilityEstimate:
    require_axis(axis)
    if len(positions_mm) < 2:
        raise CalibrationError("repeatability requires at least two samples")
    for position in positions_mm:
        require_finite("position_mm", position)
    mean = sum(positions_mm) / len(positions_mm)
    variance = sum((position - mean) ** 2 for position in positions_mm) / len(
        positions_mm
    )
    min_position = min(positions_mm)
    max_position = max(positions_mm)
    return RepeatabilityEstimate(
        axis=axis,
        sample_count=len(positions_mm),
        mean_position_mm=mean,
        min_position_mm=min_position,
        max_position_mm=max_position,
        peak_to_peak_mm=max_position - min_position,
        standard_deviation_mm=sqrt(variance),
    )


def _rms(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    return sqrt(sum(value * value for value in values) / len(values))
