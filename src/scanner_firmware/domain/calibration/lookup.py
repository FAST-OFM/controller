"""Calibration lookup tables."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.types import LedCalibrationSample
from scanner_firmware.domain.calibration.validation import require_channel, require_int


@dataclass(frozen=True)
class LedCurrentLookup:
    channel: str
    samples: tuple[LedCalibrationSample, ...]

    def __post_init__(self) -> None:
        require_channel(self.channel)
        if len(self.samples) < 2:
            raise CalibrationError("LED lookup requires at least two samples")
        seen: set[int] = set()
        last_brightness = -1
        for sample in self.samples:
            if sample.channel != self.channel:
                raise CalibrationError("all LED samples must use lookup channel")
            if sample.brightness in seen:
                raise CalibrationError("duplicate brightness sample")
            if sample.brightness < last_brightness:
                raise CalibrationError("LED samples must be sorted by brightness")
            seen.add(sample.brightness)
            last_brightness = sample.brightness

    def current_for_brightness(self, brightness: int) -> float:
        require_int("brightness", brightness)
        if (
            brightness < self.samples[0].brightness
            or brightness > self.samples[-1].brightness
        ):
            raise CalibrationError("brightness is outside calibrated range")

        for sample in self.samples:
            if sample.brightness == brightness:
                return sample.current_ma

        lower = self.samples[0]
        upper = self.samples[-1]
        for left, right in zip(self.samples, self.samples[1:]):
            if left.brightness <= brightness <= right.brightness:
                lower = left
                upper = right
                break

        span = upper.brightness - lower.brightness
        if span == 0:
            raise CalibrationError("invalid zero-width brightness interval")
        fraction = (brightness - lower.brightness) / span
        return lower.current_ma + fraction * (upper.current_ma - lower.current_ma)


def build_led_current_lookup(
    channel: str,
    samples: tuple[LedCalibrationSample, ...],
) -> LedCurrentLookup:
    return LedCurrentLookup(
        channel=channel,
        samples=tuple(sorted(samples, key=lambda sample: sample.brightness)),
    )
