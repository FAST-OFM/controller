"""Measured LED sense-resistor samples."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.validation import require_channel, require_finite


@dataclass(frozen=True)
class SenseResistorSample:
    channel: str
    brightness: int
    sense_resistor_mv: float
    led_on: bool

    def __post_init__(self) -> None:
        require_channel(self.channel)
        if not isinstance(self.brightness, int) or isinstance(self.brightness, bool):
            raise CalibrationError("brightness must be an integer")
        if not 0 <= self.brightness <= 255:
            raise CalibrationError("brightness must be between 0 and 255")
        require_finite("sense_resistor_mv", self.sense_resistor_mv)
        if self.sense_resistor_mv < 0.0:
            raise CalibrationError("sense_resistor_mv must be non-negative")
        if not isinstance(self.led_on, bool):
            raise CalibrationError("led_on must be a boolean")


__all__ = ["SenseResistorSample"]
