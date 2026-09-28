"""Sense-resistor metadata and current conversion for LED calibration."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.validation import (
    require_channel,
    require_finite,
    require_positive,
)


@dataclass(frozen=True)
class LedChannelResistorMetadata:
    channel: str
    sense_resistor_ohms: float
    sense_resistor_power_watts: float
    target_current_min_ma: float = 0.0
    target_current_max_ma: float | None = None

    def __post_init__(self) -> None:
        require_channel(self.channel)
        require_positive("sense_resistor_ohms", self.sense_resistor_ohms)
        require_positive("sense_resistor_power_watts", self.sense_resistor_power_watts)
        require_finite("target_current_min_ma", self.target_current_min_ma)
        if self.target_current_min_ma < 0.0:
            raise CalibrationError("target_current_min_ma must be non-negative")
        if self.target_current_max_ma is not None:
            require_positive("target_current_max_ma", self.target_current_max_ma)
            if self.target_current_max_ma < self.target_current_min_ma:
                raise CalibrationError(
                    "target_current_max_ma must be greater than or equal to target_current_min_ma"
                )

    def current_ma_from_sense_mv(self, sense_resistor_mv: float) -> float:
        require_finite("sense_resistor_mv", sense_resistor_mv)
        if sense_resistor_mv < 0.0:
            raise CalibrationError("sense_resistor_mv must be non-negative")
        return sense_resistor_mv / self.sense_resistor_ohms

    def resistor_power_watts_for_current(self, current_ma: float) -> float:
        require_finite("current_ma", current_ma)
        if current_ma < 0.0:
            raise CalibrationError("current_ma must be non-negative")
        current_amps = current_ma / 1000.0
        return current_amps * current_amps * self.sense_resistor_ohms

    def validate_target_current(self, current_ma: float) -> None:
        require_finite("target_current_ma", current_ma)
        if current_ma < self.target_current_min_ma:
            raise CalibrationError("target_current_ma is below channel minimum")
        if self.target_current_max_ma is not None and current_ma > self.target_current_max_ma:
            raise CalibrationError("target_current_ma exceeds channel maximum")
        if self.resistor_power_watts_for_current(current_ma) > self.sense_resistor_power_watts:
            raise CalibrationError("target_current_ma exceeds sense resistor power rating")


__all__ = ["LedChannelResistorMetadata"]
