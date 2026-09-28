"""Pure count-space helpers for predictive-Z apply-position math."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import ceil, floor, isfinite
from numbers import Real

from .types import StripeContext


class PredictiveZMathError(ValueError):
    """Raised when predictive-Z target math cannot produce a safe integer target."""


@dataclass(frozen=True)
class ApplyPositionCountBasis:
    """Linear physical-position to scheduler-count basis for schedule-Z targets."""

    counts_per_um: object
    position_um_origin: object = 0
    position_count_origin: int = 0

    def __post_init__(self) -> None:
        counts_per_um = _finite_fraction(self.counts_per_um, "counts_per_um")
        if counts_per_um == 0:
            raise PredictiveZMathError("counts_per_um must be non-zero")
        _finite_fraction(self.position_um_origin, "position_um_origin")
        _require_int("position_count_origin", self.position_count_origin)

    def count_coordinate_for_um(self, position_um: object) -> Fraction:
        return Fraction(self.position_count_origin, 1) + (
            _finite_fraction(position_um, "apply_at_position_um")
            - _finite_fraction(self.position_um_origin, "position_um_origin")
        ) * _finite_fraction(self.counts_per_um, "counts_per_um")


def predict_apply_position_count(
    *,
    measurement_position_count: int,
    signed_scan_velocity_counts_per_second: object,
    total_latency_seconds: object,
    context: StripeContext,
) -> int:
    """Return the integer apply position from signed count velocity and latency."""

    _require_int("measurement_position_count", measurement_position_count)
    velocity = _finite_fraction(
        signed_scan_velocity_counts_per_second,
        "signed_scan_velocity_counts_per_second",
    )
    latency = _finite_fraction(total_latency_seconds, "total_latency_seconds")

    if velocity == 0:
        raise PredictiveZMathError("signed_scan_velocity_counts_per_second must be non-zero")
    if velocity * context.direction < 0:
        raise PredictiveZMathError(
            "signed_scan_velocity_counts_per_second must agree with stripe direction"
        )
    if latency < 0:
        raise PredictiveZMathError("total_latency_seconds must be non-negative")
    if not _position_within_stripe_bounds(context, measurement_position_count):
        raise PredictiveZMathError("measurement_position_count must be within stripe bounds")

    predicted = Fraction(measurement_position_count, 1) + velocity * latency
    apply_position = round_apply_position_count_coordinate(
        predicted,
        scan_direction_count=context.direction,
    )
    if not _position_within_stripe_bounds(context, apply_position):
        raise PredictiveZMathError("predicted apply position is outside stripe bounds")
    return apply_position


def round_apply_position_count_coordinate(
    raw_count_coordinate: object,
    *,
    scan_direction_count: int,
) -> int:
    """Round a raw scheduler count coordinate without moving the target earlier."""

    if scan_direction_count not in (-1, 1):
        raise PredictiveZMathError("scan_direction_count must be -1 or 1")
    raw = _finite_fraction(raw_count_coordinate, "raw_count_coordinate")
    if scan_direction_count > 0:
        return ceil(raw)
    return floor(raw)


def convert_apply_position_um_to_count(
    apply_at_position_um: object,
    *,
    basis: ApplyPositionCountBasis,
    scan_direction_count: int,
) -> int:
    """Convert a physical apply position to a rounded scheduler count target."""

    return round_apply_position_count_coordinate(
        basis.count_coordinate_for_um(apply_at_position_um),
        scan_direction_count=scan_direction_count,
    )


def _require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")


def _position_within_stripe_bounds(context: StripeContext, position: int) -> bool:
    lower = min(context.start_position, context.end_position)
    upper = max(context.start_position, context.end_position)
    return lower <= position <= upper


def _finite_fraction(value: object, name: str) -> Fraction:
    if isinstance(value, bool):
        raise PredictiveZMathError(f"{name} must be a finite number")
    if isinstance(value, Fraction):
        fraction = value
    elif isinstance(value, int):
        fraction = Fraction(value, 1)
    elif isinstance(value, Decimal):
        fraction = _decimal_to_fraction(value, name)
    elif isinstance(value, Real):
        if not isfinite(value):
            raise PredictiveZMathError(f"{name} must be a finite number")
        fraction = _decimal_to_fraction(Decimal(str(value)), name)
    else:
        try:
            fraction = _decimal_to_fraction(Decimal(str(value)), name)
        except (InvalidOperation, ValueError) as exc:
            raise PredictiveZMathError(f"{name} must be a finite number") from exc
    if fraction.denominator == 0:
        raise PredictiveZMathError(f"{name} must be a finite number")
    return fraction


def _decimal_to_fraction(value: Decimal, name: str) -> Fraction:
    if not value.is_finite():
        raise PredictiveZMathError(f"{name} must be a finite number")
    return Fraction(value)


__all__ = [
    "ApplyPositionCountBasis",
    "PredictiveZMathError",
    "convert_apply_position_um_to_count",
    "predict_apply_position_count",
    "round_apply_position_count_coordinate",
]
