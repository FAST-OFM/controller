"""Software-only LED calibration workflow.

This module consumes already-measured sense-resistor samples. It does not read
ADCs, toggle LED outputs, open serial ports, drive GPIO or perform live
measurement.
"""

from __future__ import annotations

from scanner_firmware.domain.calibration.errors import CalibrationError
from scanner_firmware.domain.calibration.led_modes import (
    CALIBRATION_MODE,
    RUNTIME_MODE,
    LedWorkflowMode,
    require_led_workflow_mode,
)
from scanner_firmware.domain.calibration.led_resistor import LedChannelResistorMetadata
from scanner_firmware.domain.calibration.led_runtime import (
    LedRuntimeCurrentModel,
    LedRuntimeSetpoint,
)
from scanner_firmware.domain.calibration.led_samples import SenseResistorSample
from scanner_firmware.domain.calibration.led_tables import (
    LedCalibrationTable,
    NormalizedLedCurrentPoint,
    normalized_led_current_points,
)
from scanner_firmware.domain.calibration.lookup import build_led_current_lookup
from scanner_firmware.domain.calibration.types import LedCalibrationSample


class LedCalibrationWorkflow:
    """Build calibrated LED current lookup tables from recorded samples."""

    def __init__(self, metadata: LedChannelResistorMetadata, mode: LedWorkflowMode):
        require_led_workflow_mode(mode)
        self._metadata = metadata
        self._mode = mode

    def build_table(self, samples: tuple[SenseResistorSample, ...]) -> LedCalibrationTable:
        if self._mode != CALIBRATION_MODE:
            raise CalibrationError(
                "LED calibration samples may only be consumed in calibration mode"
            )
        if len(samples) < 2:
            raise CalibrationError("LED calibration requires at least two on-time samples")

        calibration_samples: list[LedCalibrationSample] = []
        for sample in samples:
            self._validate_sample(sample)
            current_ma = self._metadata.current_ma_from_sense_mv(sample.sense_resistor_mv)
            self._metadata.validate_target_current(current_ma)
            calibration_samples.append(
                LedCalibrationSample(
                    channel=sample.channel,
                    brightness=sample.brightness,
                    current_ma=current_ma,
                )
            )

        lookup = build_led_current_lookup(self._metadata.channel, tuple(calibration_samples))
        return LedCalibrationTable(
            channel=self._metadata.channel,
            mode=CALIBRATION_MODE,
            metadata=self._metadata,
            lookup=lookup,
            points=normalized_led_current_points(lookup),
        )

    def _validate_sample(self, sample: SenseResistorSample) -> None:
        if sample.channel != self._metadata.channel:
            raise CalibrationError("sample channel must match resistor metadata channel")
        if not sample.led_on:
            raise CalibrationError("sense-resistor sample is only valid while LED is on")


__all__ = [
    "CALIBRATION_MODE",
    "RUNTIME_MODE",
    "LedCalibrationTable",
    "LedCalibrationWorkflow",
    "LedChannelResistorMetadata",
    "LedRuntimeCurrentModel",
    "LedRuntimeSetpoint",
    "LedWorkflowMode",
    "NormalizedLedCurrentPoint",
    "SenseResistorSample",
]
