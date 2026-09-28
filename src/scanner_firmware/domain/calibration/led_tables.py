"""LED calibration table records and normalization."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.led_modes import LedWorkflowMode
from scanner_firmware.domain.calibration.led_resistor import LedChannelResistorMetadata
from scanner_firmware.domain.calibration.lookup import LedCurrentLookup


@dataclass(frozen=True)
class NormalizedLedCurrentPoint:
    channel: str
    brightness: int
    normalized_brightness: float
    current_ma: float
    normalized_current: float


@dataclass(frozen=True)
class LedCalibrationTable:
    channel: str
    mode: LedWorkflowMode
    metadata: LedChannelResistorMetadata
    lookup: LedCurrentLookup
    points: tuple[NormalizedLedCurrentPoint, ...]


def normalized_led_current_points(
    lookup: LedCurrentLookup,
) -> tuple[NormalizedLedCurrentPoint, ...]:
    max_current_ma = lookup.samples[-1].current_ma
    if max_current_ma <= 0.0:
        raise CalibrationError("LED calibration requires a positive maximum current")
    return tuple(
        NormalizedLedCurrentPoint(
            channel=sample.channel,
            brightness=sample.brightness,
            normalized_brightness=sample.brightness / 255.0,
            current_ma=sample.current_ma,
            normalized_current=sample.current_ma / max_current_ma,
        )
        for sample in lookup.samples
    )


__all__ = [
    "LedCalibrationTable",
    "NormalizedLedCurrentPoint",
    "normalized_led_current_points",
]
