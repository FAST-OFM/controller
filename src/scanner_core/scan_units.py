"""Pure unit conversion helpers for scan math boundaries."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
from math import isfinite
from numbers import Real


NANOMETERS_PER_MICROMETER = 1000
MICROMETERS_PER_MILLIMETER = 1000


class UnitConversionError(ValueError):
    """Raised when a physical-unit value cannot be converted safely."""


def round_half_away_from_zero(value: object, *, name: str = "value") -> int:
    """Round a finite numeric value to an integer, with half steps away from zero."""

    decimal_value = _finite_decimal(value, name)
    try:
        return int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise UnitConversionError(f"{name} cannot be rounded to an integer") from exc


def micrometers_to_nanometers(value_um: object, *, name: str = "value_um") -> int:
    """Convert micrometers to integer nanometers using explicit tie-breaking."""

    return round_half_away_from_zero(
        _finite_decimal(value_um, name) * Decimal(NANOMETERS_PER_MICROMETER),
        name=f"{name}_as_nm",
    )


def micrometers_to_steps(
    value_um: object,
    *,
    steps_per_um: object,
    name: str = "value_um",
    scale_name: str = "steps_per_um",
) -> int:
    """Convert micrometers to integer scheduler steps using explicit tie-breaking."""

    return round_half_away_from_zero(
        _finite_decimal(value_um, name) * _positive_decimal(steps_per_um, scale_name),
        name=f"{name}_as_steps",
    )


def _positive_decimal(value: object, name: str) -> Decimal:
    decimal_value = _finite_decimal(value, name)
    if decimal_value <= 0:
        raise UnitConversionError(f"{name} must be a positive finite number")
    return decimal_value


def _finite_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise UnitConversionError(f"{name} must be a finite number")
    if isinstance(value, Fraction):
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
    elif isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, Real):
        if not isfinite(value):
            raise UnitConversionError(f"{name} must be a finite number")
        decimal_value = Decimal(str(value))
    else:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise UnitConversionError(f"{name} must be a finite number") from exc
    if not decimal_value.is_finite():
        raise UnitConversionError(f"{name} must be a finite number")
    return decimal_value


__all__ = [
    "MICROMETERS_PER_MILLIMETER",
    "NANOMETERS_PER_MICROMETER",
    "UnitConversionError",
    "micrometers_to_nanometers",
    "micrometers_to_steps",
    "round_half_away_from_zero",
]
