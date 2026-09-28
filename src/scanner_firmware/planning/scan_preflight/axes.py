"""Scan preflight axis constants."""

from typing import Literal


Axis = Literal["X", "Y", "Z"]
REQUIRED_SCAN_AXES: tuple[Axis, ...] = ("X", "Y", "Z")
