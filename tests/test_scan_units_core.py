from decimal import Decimal
from fractions import Fraction

import pytest

from scanner_core.axis_resolution import AxisResolution, steps_per_mm_from_screw_pitch
from scanner_core.scan_geometry import ScanGeometryError
from scanner_core.scan_units import (
    MICROMETERS_PER_MILLIMETER,
    NANOMETERS_PER_MICROMETER,
    UnitConversionError,
    micrometers_to_nanometers,
    micrometers_to_steps,
    round_half_away_from_zero,
)


def test_scan_unit_constants_are_canonical():
    assert NANOMETERS_PER_MICROMETER == 1000
    assert MICROMETERS_PER_MILLIMETER == 1000


def test_round_half_away_from_zero():
    assert round_half_away_from_zero(0.5) == 1
    assert round_half_away_from_zero(-0.5) == -1
    assert round_half_away_from_zero(Decimal("1.5")) == 2
    assert round_half_away_from_zero(Decimal("-1.5")) == -2
    assert round_half_away_from_zero(Fraction(3, 2)) == 2
    assert round_half_away_from_zero(Fraction(-3, 2)) == -2


def test_micrometer_conversions_use_half_away_from_zero():
    assert micrometers_to_nanometers(0.0005) == 1
    assert micrometers_to_nanometers(-0.0005) == -1
    assert micrometers_to_steps(0.2, steps_per_um=2.5) == 1
    assert micrometers_to_steps(-0.2, steps_per_um=2.5) == -1
    assert micrometers_to_steps(Fraction(1, 4), steps_per_um=Fraction(10, 1)) == 3
    assert micrometers_to_steps(Fraction(-1, 4), steps_per_um=Fraction(10, 1)) == -3


def test_unit_conversions_reject_invalid_numbers_and_scales():
    for value in (True, float("nan"), float("inf"), "not-a-number"):
        with pytest.raises(UnitConversionError):
            round_half_away_from_zero(value)

    for steps_per_um in (0, -1, False, float("nan"), "not-a-number"):
        with pytest.raises(UnitConversionError):
            micrometers_to_steps(1, steps_per_um=steps_per_um)


def test_derives_steps_per_mm_from_screw_pitch_and_microsteps():
    resolution = AxisResolution(
        screw_pitch_mm=Fraction(1, 4),
        microsteps=8,
        motor_steps_per_rev=200,
    )

    assert resolution.steps_per_rev == Fraction(1600, 1)
    assert resolution.steps_per_mm == Fraction(6400, 1)
    assert (
        steps_per_mm_from_screw_pitch(
            screw_pitch_mm="0.25",
            microsteps=8,
            motor_steps_per_rev=200,
        )
        == Fraction(6400, 1)
    )


def test_rejects_invalid_resolution_inputs():
    invalid_cases = (
        {"screw_pitch_mm": 0, "microsteps": 16, "motor_steps_per_rev": 200},
        {"screw_pitch_mm": 2, "microsteps": 0, "motor_steps_per_rev": 200},
        {"screw_pitch_mm": 2, "microsteps": 16, "motor_steps_per_rev": False},
    )

    for kwargs in invalid_cases:
        with pytest.raises(ScanGeometryError):
            steps_per_mm_from_screw_pitch(**kwargs)
