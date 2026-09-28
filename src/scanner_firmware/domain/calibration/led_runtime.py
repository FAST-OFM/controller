"""Runtime LED current setpoint lookup."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.led_modes import (
    RUNTIME_MODE,
    LedWorkflowMode,
    require_led_workflow_mode,
)
from scanner_firmware.domain.calibration.led_tables import LedCalibrationTable


@dataclass(frozen=True)
class LedRuntimeSetpoint:
    channel: str
    target_current_ma: float
    brightness: int
    normalized_brightness: float
    predicted_current_ma: float


class LedRuntimeCurrentModel:
    """Use an existing LED lookup table to resolve runtime current setpoints."""

    def __init__(self, table: LedCalibrationTable, mode: LedWorkflowMode = RUNTIME_MODE):
        require_led_workflow_mode(mode)
        if mode != RUNTIME_MODE:
            raise CalibrationError("runtime current model requires runtime mode")
        self._table = table
        self._metadata = table.metadata

    def setpoint_for_target_current(self, target_current_ma: float) -> LedRuntimeSetpoint:
        self._metadata.validate_target_current(target_current_ma)
        samples = self._table.lookup.samples
        if target_current_ma < samples[0].current_ma or target_current_ma > samples[-1].current_ma:
            raise CalibrationError("target_current_ma is outside calibrated current range")

        if target_current_ma == samples[0].current_ma:
            brightness = samples[0].brightness
        elif target_current_ma == samples[-1].current_ma:
            brightness = samples[-1].brightness
        else:
            brightness = self._interpolated_brightness(target_current_ma)

        predicted_current_ma = self._table.lookup.current_for_brightness(brightness)
        return LedRuntimeSetpoint(
            channel=self._table.channel,
            target_current_ma=target_current_ma,
            brightness=brightness,
            normalized_brightness=brightness / 255.0,
            predicted_current_ma=predicted_current_ma,
        )

    def _interpolated_brightness(self, target_current_ma: float) -> int:
        samples = self._table.lookup.samples
        for lower, upper in zip(samples, samples[1:]):
            if lower.current_ma <= target_current_ma <= upper.current_ma:
                current_span = upper.current_ma - lower.current_ma
                if current_span <= 0.0:
                    raise CalibrationError("LED current lookup must increase with brightness")
                fraction = (target_current_ma - lower.current_ma) / current_span
                interpolated = lower.brightness + fraction * (upper.brightness - lower.brightness)
                return round(interpolated)
        raise CalibrationError("target_current_ma is outside calibrated current range")


__all__ = ["LedRuntimeCurrentModel", "LedRuntimeSetpoint"]
