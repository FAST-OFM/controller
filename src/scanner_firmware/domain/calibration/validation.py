"""Calibration validation helpers."""

from __future__ import annotations

from math import isfinite
from numbers import Real

from scanner_firmware.domain.calibration.errors import CalibrationError


def require_axis(axis: object) -> None:
    if axis not in ("X", "Y", "Z"):
        raise CalibrationError("axis must be X, Y or Z")


def require_channel(channel: object) -> None:
    if not isinstance(channel, str) or not channel:
        raise CalibrationError("channel must be a non-empty string")


def require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CalibrationError(f"{name} must be an integer")


def require_finite(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise CalibrationError(f"{name} must be a finite number")


def require_positive(name: str, value: object) -> None:
    require_finite(name, value)
    if value <= 0.0:
        raise CalibrationError(f"{name} must be positive")
