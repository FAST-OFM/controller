"""LED calibration workflow modes."""

from __future__ import annotations

from typing import Literal

from scanner_firmware.domain.calibration.errors import CalibrationError


LedWorkflowMode = Literal["calibration", "runtime"]
CALIBRATION_MODE: LedWorkflowMode = "calibration"
RUNTIME_MODE: LedWorkflowMode = "runtime"


def require_led_workflow_mode(mode: object) -> None:
    if mode not in (CALIBRATION_MODE, RUNTIME_MODE):
        raise CalibrationError("LED workflow mode must be calibration or runtime")


__all__ = [
    "CALIBRATION_MODE",
    "RUNTIME_MODE",
    "LedWorkflowMode",
    "require_led_workflow_mode",
]
