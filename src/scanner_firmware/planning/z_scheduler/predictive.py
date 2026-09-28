"""Firmware predictive-Z adapters around the shared pure core.

This module keeps firmware-owned conversion boundaries. Shared count-space
apply-position helpers, planner value objects and no-hardware scheduler
planning model live in `scanner_core.predictive_z`.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import TYPE_CHECKING

from scanner_core.predictive_z import (
    ApplyPositionCountBasis,
    PredictiveZMathError,
    convert_apply_position_um_to_count,
    predict_apply_position_count,
    round_apply_position_count_coordinate,
)
from scanner_core.predictive_z import predictive as _predictive_core
from scanner_core.scan_units import micrometers_to_steps
from scanner_firmware.foundation.firmware_components.interfaces import FocusCorrectionSample

if TYPE_CHECKING:
    from scanner_core.predictive_z.predictive import (
        PredictiveZPlanner,
        ZFocusErrorSample,
        ZPredictivePlanDecision,
    )
    from scanner_core.predictive_z.types import StripeContext


@dataclass(frozen=True)
class ZMicrometerToStepAdapterConfig:
    """Conversion boundary from public focus units to scheduler steps."""

    z_steps_per_um: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.z_steps_per_um, bool)
            or not isinstance(self.z_steps_per_um, Real)
            or not isfinite(self.z_steps_per_um)
            or self.z_steps_per_um <= 0.0
        ):
            raise ValueError("z_steps_per_um must be a positive finite number")


class PredictiveZMicrometerAdapter:
    """Plan future Z commands from public micrometer focus samples.

    Public focus/autofocus boundaries use micrometers. The scheduler queue uses
    controller steps. This adapter is the single firmware-side owner for that
    conversion.
    """

    def __init__(
        self,
        planner: PredictiveZPlanner,
        config: ZMicrometerToStepAdapterConfig,
    ):
        self._planner = planner
        self._config = config

    def plan_from_um(
        self,
        sample: FocusCorrectionSample,
        context: StripeContext,
    ) -> ZPredictivePlanDecision:
        return self._planner.plan(self._to_step_sample(sample), context)

    def _to_step_sample(self, sample: FocusCorrectionSample) -> ZFocusErrorSample:
        return _predictive_core.ZFocusErrorSample(
            scan_id=sample.scan_id,
            stripe_id=sample.stripe_id,
            focus_error_steps=micrometers_to_steps(
                sample.focus_error_um,
                steps_per_um=self._config.z_steps_per_um,
                name="focus_error_um",
            ),
            reference_z_steps=micrometers_to_steps(
                sample.reference_z_um,
                steps_per_um=self._config.z_steps_per_um,
                name="reference_z_um",
            ),
            frame_id=sample.frame_id,
            position_count=sample.position_count,
        )


__all__ = [
    "ApplyPositionCountBasis",
    "PredictiveZMathError",
    "PredictiveZMicrometerAdapter",
    "ZMicrometerToStepAdapterConfig",
    "convert_apply_position_um_to_count",
    "predict_apply_position_count",
    "round_apply_position_count_coordinate",
]
