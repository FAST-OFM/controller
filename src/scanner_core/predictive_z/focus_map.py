"""Pure predictive-Z focus-map priors from accepted autofocus observations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Literal, Protocol, runtime_checkable


FocusMapRejectReason = Literal[
    "no_previous_stripe_prior",
    "calibration_mismatch",
    "low_tissue_fraction",
    "low_usable_fraction",
    "low_confidence",
    "stale_prior",
    "future_prior",
    "non_adjacent_stripe",
    "low_prediction_confidence",
    "insufficient_prior_samples",
]


@dataclass(frozen=True)
class FocusMapCalibrationRef:
    """Calibration identity used to decide whether a prior is compatible."""

    calibration_key: str

    def __post_init__(self) -> None:
        if not self.calibration_key:
            raise ValueError("calibration_key must be non-empty")

    def compatible_with(self, other: "FocusMapCalibrationRef") -> bool:
        return self.calibration_key == other.calibration_key


@dataclass(frozen=True)
class AcceptedFocusObservation:
    """Accepted autofocus result indexed by scan, stripe and sample position."""

    scan_id: str
    stripe_id: int
    position_index: int
    sample_index: int
    z_focus_steps: int
    confidence: float
    tissue_fraction: float
    usable_fraction: float
    calibration: FocusMapCalibrationRef

    def __post_init__(self) -> None:
        _require_non_empty_string("scan_id", self.scan_id)
        for name, value in (
            ("stripe_id", self.stripe_id),
            ("position_index", self.position_index),
            ("sample_index", self.sample_index),
            ("z_focus_steps", self.z_focus_steps),
        ):
            _require_int(name, value)
        if self.stripe_id < 0:
            raise ValueError("stripe_id must be non-negative")
        if self.sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        _require_unit_interval("confidence", self.confidence)
        _require_unit_interval("tissue_fraction", self.tissue_fraction)
        _require_unit_interval("usable_fraction", self.usable_fraction)


@dataclass(frozen=True)
class FocusMapPredictionTarget:
    """Position-indexed prediction target for a stripe not yet autofocus-sampled."""

    scan_id: str
    stripe_id: int
    position_index: int
    sample_index: int
    tissue_fraction: float
    usable_fraction: float
    calibration: FocusMapCalibrationRef

    def __post_init__(self) -> None:
        _require_non_empty_string("scan_id", self.scan_id)
        for name, value in (
            ("stripe_id", self.stripe_id),
            ("position_index", self.position_index),
            ("sample_index", self.sample_index),
        ):
            _require_int(name, value)
        if self.stripe_id < 0:
            raise ValueError("stripe_id must be non-negative")
        if self.sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        _require_unit_interval("tissue_fraction", self.tissue_fraction)
        _require_unit_interval("usable_fraction", self.usable_fraction)


@dataclass(frozen=True)
class FocusMapPriorConfig:
    """Configurable heuristics for accepting previous-stripe focus priors."""

    min_observation_confidence: float
    min_prediction_confidence: float
    min_tissue_fraction: float
    min_usable_fraction: float
    max_sample_age_indices: int
    max_prior_stripe_distance: int
    max_abs_slope_steps_per_position: float
    base_uncertainty_steps: float
    uncertainty_per_position_index: float
    uncertainty_per_sample_age_index: float
    uncertainty_per_stripe_distance: float
    slope_clamp_uncertainty_steps: float
    uncertainty_full_scale_steps: float
    require_calibration_match: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("min_observation_confidence", self.min_observation_confidence),
            ("min_prediction_confidence", self.min_prediction_confidence),
            ("min_tissue_fraction", self.min_tissue_fraction),
            ("min_usable_fraction", self.min_usable_fraction),
        ):
            _require_unit_interval(name, value)
        for name, value in (
            ("max_sample_age_indices", self.max_sample_age_indices),
            ("max_prior_stripe_distance", self.max_prior_stripe_distance),
        ):
            _require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name, value in (
            ("max_abs_slope_steps_per_position", self.max_abs_slope_steps_per_position),
            ("base_uncertainty_steps", self.base_uncertainty_steps),
            ("uncertainty_per_position_index", self.uncertainty_per_position_index),
            ("uncertainty_per_sample_age_index", self.uncertainty_per_sample_age_index),
            ("uncertainty_per_stripe_distance", self.uncertainty_per_stripe_distance),
            ("slope_clamp_uncertainty_steps", self.slope_clamp_uncertainty_steps),
            ("uncertainty_full_scale_steps", self.uncertainty_full_scale_steps),
        ):
            _require_finite_number(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.uncertainty_full_scale_steps <= 0:
            raise ValueError("uncertainty_full_scale_steps must be positive")
        if not isinstance(self.require_calibration_match, bool):
            raise ValueError("require_calibration_match must be a boolean")


@dataclass(frozen=True)
class FocusMapDiagnostic:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string("code", self.code)
        _require_non_empty_string("message", self.message)


@dataclass(frozen=True)
class FocusMapPrediction:
    """Accepted or rejected focus-map prediction with auditable prior details."""

    accepted: bool
    status: Literal["accepted", "rejected"]
    reason: FocusMapRejectReason | None
    target: FocusMapPredictionTarget
    z_focus_steps: int | None
    confidence: float
    uncertainty_steps: float
    diagnostics: tuple[FocusMapDiagnostic, ...]
    source_observations: tuple[AcceptedFocusObservation, ...] = ()
    prior_stripe_id: int | None = None
    stripe_distance: int | None = None

    def __post_init__(self) -> None:
        if self.status not in ("accepted", "rejected"):
            raise ValueError("status must be accepted or rejected")
        if self.accepted != (self.status == "accepted"):
            raise ValueError("accepted must match status")
        if self.accepted and self.reason is not None:
            raise ValueError("accepted predictions cannot have a rejection reason")
        if not self.accepted and self.reason is None:
            raise ValueError("rejected predictions require a reason")
        if self.accepted and self.z_focus_steps is None:
            raise ValueError("accepted predictions require z_focus_steps")
        if self.z_focus_steps is not None:
            _require_int("z_focus_steps", self.z_focus_steps)
        _require_unit_interval("confidence", self.confidence)
        _require_finite_number("uncertainty_steps", self.uncertainty_steps)
        if self.uncertainty_steps < 0:
            raise ValueError("uncertainty_steps must be non-negative")
        if self.stripe_distance is not None:
            _require_int("stripe_distance", self.stripe_distance)
            if self.stripe_distance < 0:
                raise ValueError("stripe_distance must be non-negative")


@runtime_checkable
class FocusObservationSource(Protocol):
    def focus_observations(self, scan_id: str) -> Iterable[AcceptedFocusObservation]: ...


@runtime_checkable
class FocusMapPredictor(Protocol):
    def predict_focus(self, target: FocusMapPredictionTarget) -> FocusMapPrediction: ...


class PredictiveZFocusMap:
    """Build position-indexed focus predictions from previous-stripe AF priors."""

    def __init__(
        self,
        config: FocusMapPriorConfig,
        observations: Iterable[AcceptedFocusObservation] = (),
    ) -> None:
        self._config = config
        self._observations = list(observations)

    def add_observation(self, observation: AcceptedFocusObservation) -> None:
        self._observations.append(observation)

    def focus_observations(self, scan_id: str) -> tuple[AcceptedFocusObservation, ...]:
        return tuple(observation for observation in self._observations if observation.scan_id == scan_id)

    def predict_focus(self, target: FocusMapPredictionTarget) -> FocusMapPrediction:
        target_rejection = self._target_rejection(target)
        if target_rejection is not None:
            return self._rejected(target, target_rejection)

        scan_observations = self.focus_observations(target.scan_id)
        prior_stripe_id = self._nearest_previous_stripe_id(target, scan_observations)
        if prior_stripe_id is None:
            return self._rejected(target, "no_previous_stripe_prior")

        stripe_distance = target.stripe_id - prior_stripe_id
        if stripe_distance > self._config.max_prior_stripe_distance:
            return self._rejected(
                target,
                "non_adjacent_stripe",
                prior_stripe_id=prior_stripe_id,
                stripe_distance=stripe_distance,
                diagnostics=(
                    _diagnostic(
                        "non_adjacent_stripe",
                        "previous stripe prior exceeds configured stripe distance",
                        {
                            "stripe_distance": stripe_distance,
                            "max_prior_stripe_distance": self._config.max_prior_stripe_distance,
                        },
                    ),
                ),
            )

        candidates = tuple(
            observation
            for observation in scan_observations
            if observation.stripe_id == prior_stripe_id
        )
        filtered = self._compatible_candidates(target, candidates)
        if not filtered:
            return self._rejected(target, "calibration_mismatch", prior_stripe_id, stripe_distance)

        filtered = tuple(
            observation for observation in filtered if target.sample_index >= observation.sample_index
        )
        if not filtered:
            return self._rejected(target, "future_prior", prior_stripe_id, stripe_distance)

        filtered = tuple(
            observation
            for observation in filtered
            if target.sample_index - observation.sample_index <= self._config.max_sample_age_indices
        )
        if not filtered:
            return self._rejected(target, "stale_prior", prior_stripe_id, stripe_distance)

        filtered = tuple(
            observation
            for observation in filtered
            if observation.confidence >= self._config.min_observation_confidence
        )
        if not filtered:
            return self._rejected(target, "low_confidence", prior_stripe_id, stripe_distance)

        filtered = tuple(
            observation
            for observation in filtered
            if observation.tissue_fraction >= self._config.min_tissue_fraction
        )
        if not filtered:
            return self._rejected(target, "low_tissue_fraction", prior_stripe_id, stripe_distance)

        filtered = tuple(
            observation
            for observation in filtered
            if observation.usable_fraction >= self._config.min_usable_fraction
        )
        if not filtered:
            return self._rejected(target, "low_usable_fraction", prior_stripe_id, stripe_distance)

        return self._prediction_from_candidates(target, prior_stripe_id, stripe_distance, filtered)

    def _target_rejection(self, target: FocusMapPredictionTarget) -> FocusMapRejectReason | None:
        if target.tissue_fraction < self._config.min_tissue_fraction:
            return "low_tissue_fraction"
        if target.usable_fraction < self._config.min_usable_fraction:
            return "low_usable_fraction"
        return None

    def _compatible_candidates(
        self,
        target: FocusMapPredictionTarget,
        candidates: tuple[AcceptedFocusObservation, ...],
    ) -> tuple[AcceptedFocusObservation, ...]:
        if not self._config.require_calibration_match:
            return candidates
        return tuple(
            observation
            for observation in candidates
            if observation.calibration.compatible_with(target.calibration)
        )

    def _nearest_previous_stripe_id(
        self,
        target: FocusMapPredictionTarget,
        observations: tuple[AcceptedFocusObservation, ...],
    ) -> int | None:
        previous_stripe_ids = {
            observation.stripe_id
            for observation in observations
            if observation.stripe_id < target.stripe_id
        }
        if not previous_stripe_ids:
            return None
        return max(previous_stripe_ids)

    def _prediction_from_candidates(
        self,
        target: FocusMapPredictionTarget,
        prior_stripe_id: int,
        stripe_distance: int,
        candidates: tuple[AcceptedFocusObservation, ...],
    ) -> FocusMapPrediction:
        unique_candidates = _unique_by_position(candidates)
        source, z_focus_steps, slope_diagnostics, position_distance = self._interpolate(
            target,
            unique_candidates,
        )
        sample_age = max(target.sample_index - observation.sample_index for observation in source)
        uncertainty_steps = self._uncertainty(
            position_distance=position_distance,
            sample_age=sample_age,
            stripe_distance=stripe_distance,
            slope_clamped=any(diagnostic.code == "slope_clamped" for diagnostic in slope_diagnostics),
        )
        source_confidence = min(observation.confidence for observation in source)
        confidence = _prediction_confidence(
            source_confidence,
            uncertainty_steps,
            self._config.uncertainty_full_scale_steps,
        )
        diagnostics = (
            _diagnostic(
                "previous_stripe_prior",
                "prediction uses compatible previous-stripe autofocus observations",
                {
                    "prior_stripe_id": prior_stripe_id,
                    "stripe_distance": stripe_distance,
                    "source_count": len(source),
                },
            ),
            *slope_diagnostics,
            _diagnostic(
                "prediction_uncertainty",
                "prediction uncertainty was computed from configured prior heuristics",
                {
                    "uncertainty_steps": uncertainty_steps,
                    "position_distance": position_distance,
                    "sample_age": sample_age,
                    "stripe_distance": stripe_distance,
                },
            ),
        )
        if confidence < source_confidence:
            diagnostics = (
                *diagnostics,
                _diagnostic(
                    "confidence_downweighted",
                    "prediction confidence was downweighted by uncertainty",
                    {
                        "source_confidence": source_confidence,
                        "prediction_confidence": confidence,
                    },
                ),
            )
        if confidence < self._config.min_prediction_confidence:
            return self._rejected(
                target,
                "low_prediction_confidence",
                prior_stripe_id,
                stripe_distance,
                diagnostics,
            )
        return FocusMapPrediction(
            accepted=True,
            status="accepted",
            reason=None,
            target=target,
            z_focus_steps=z_focus_steps,
            confidence=confidence,
            uncertainty_steps=uncertainty_steps,
            diagnostics=diagnostics,
            source_observations=source,
            prior_stripe_id=prior_stripe_id,
            stripe_distance=stripe_distance,
        )

    def _interpolate(
        self,
        target: FocusMapPredictionTarget,
        observations: tuple[AcceptedFocusObservation, ...],
    ) -> tuple[tuple[AcceptedFocusObservation, ...], int, tuple[FocusMapDiagnostic, ...], int]:
        if not observations:
            raise ValueError("at least one observation is required")
        exact = tuple(
            observation for observation in observations if observation.position_index == target.position_index
        )
        if exact:
            source = (max(exact, key=lambda observation: observation.confidence),)
            return (
                source,
                source[0].z_focus_steps,
                (
                    _diagnostic(
                        "matched_position_prior",
                        "prediction uses a previous-stripe prior at the same position index",
                        {"position_index": target.position_index},
                    ),
                ),
                0,
            )
        if len(observations) == 1:
            source = (observations[0],)
            return (
                source,
                source[0].z_focus_steps,
                (
                    _diagnostic(
                        "single_point_prior",
                        "prediction uses one previous-stripe prior with uncertainty",
                        {"position_index": source[0].position_index},
                    ),
                ),
                abs(target.position_index - source[0].position_index),
            )

        lower, upper = _bracketing_observations(target.position_index, observations)
        raw_slope = (upper.z_focus_steps - lower.z_focus_steps) / (
            upper.position_index - lower.position_index
        )
        applied_slope = _clamp_float(
            raw_slope,
            -self._config.max_abs_slope_steps_per_position,
            self._config.max_abs_slope_steps_per_position,
        )
        anchor = lower if target.position_index >= lower.position_index else upper
        position_offset = target.position_index - anchor.position_index
        z_focus_steps = round(anchor.z_focus_steps + applied_slope * position_offset)
        source = (lower, upper)
        mode = "interpolated_prior" if lower.position_index < target.position_index < upper.position_index else "extrapolated_prior"
        diagnostics = (
            _diagnostic(
                mode,
                "prediction applies the previous-stripe focus trend by position index",
                {
                    "lower_position_index": lower.position_index,
                    "upper_position_index": upper.position_index,
                    "raw_slope_steps_per_position": raw_slope,
                    "applied_slope_steps_per_position": applied_slope,
                },
            ),
        )
        if applied_slope != raw_slope:
            diagnostics = (
                *diagnostics,
                _diagnostic(
                    "slope_clamped",
                    "previous-stripe focus trend exceeded configured slope clamp",
                    {
                        "raw_slope_steps_per_position": raw_slope,
                        "applied_slope_steps_per_position": applied_slope,
                        "max_abs_slope_steps_per_position": self._config.max_abs_slope_steps_per_position,
                    },
                ),
            )
        return source, z_focus_steps, diagnostics, abs(position_offset)

    def _uncertainty(
        self,
        *,
        position_distance: int,
        sample_age: int,
        stripe_distance: int,
        slope_clamped: bool,
    ) -> float:
        uncertainty = (
            self._config.base_uncertainty_steps
            + position_distance * self._config.uncertainty_per_position_index
            + sample_age * self._config.uncertainty_per_sample_age_index
            + stripe_distance * self._config.uncertainty_per_stripe_distance
        )
        if slope_clamped:
            uncertainty += self._config.slope_clamp_uncertainty_steps
        return uncertainty

    def _rejected(
        self,
        target: FocusMapPredictionTarget,
        reason: FocusMapRejectReason,
        prior_stripe_id: int | None = None,
        stripe_distance: int | None = None,
        diagnostics: tuple[FocusMapDiagnostic, ...] = (),
    ) -> FocusMapPrediction:
        if not diagnostics:
            diagnostics = (
                _diagnostic(
                    reason,
                    "focus-map prior was rejected by configured heuristics",
                    {
                        "prior_stripe_id": prior_stripe_id,
                        "stripe_distance": stripe_distance,
                    },
                ),
            )
        return FocusMapPrediction(
            accepted=False,
            status="rejected",
            reason=reason,
            target=target,
            z_focus_steps=None,
            confidence=0.0,
            uncertainty_steps=0.0,
            diagnostics=diagnostics,
            prior_stripe_id=prior_stripe_id,
            stripe_distance=stripe_distance,
        )


def _unique_by_position(
    observations: tuple[AcceptedFocusObservation, ...],
) -> tuple[AcceptedFocusObservation, ...]:
    selected: dict[int, AcceptedFocusObservation] = {}
    for observation in sorted(
        observations,
        key=lambda item: (item.position_index, -item.confidence, -item.sample_index),
    ):
        selected.setdefault(observation.position_index, observation)
    return tuple(selected[position] for position in sorted(selected))


def _bracketing_observations(
    position_index: int,
    observations: tuple[AcceptedFocusObservation, ...],
) -> tuple[AcceptedFocusObservation, AcceptedFocusObservation]:
    before = tuple(observation for observation in observations if observation.position_index < position_index)
    after = tuple(observation for observation in observations if observation.position_index > position_index)
    if before and after:
        return before[-1], after[0]
    if before:
        return before[-2], before[-1]
    if after:
        return after[0], after[1]
    raise ValueError("at least two distinct observation positions are required")


def _prediction_confidence(
    source_confidence: float,
    uncertainty_steps: float,
    uncertainty_full_scale_steps: float,
) -> float:
    uncertainty_fraction = min(1.0, uncertainty_steps / uncertainty_full_scale_steps)
    return max(0.0, min(1.0, source_confidence * (1.0 - uncertainty_fraction)))


def _diagnostic(code: str, message: str, details: dict[str, Any]) -> FocusMapDiagnostic:
    return FocusMapDiagnostic(code=code, message=message, details=details)


def _clamp_float(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _require_non_empty_string(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")


def _require_finite_number(name: str, value: object) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def _require_unit_interval(name: str, value: object) -> None:
    _require_finite_number(name, value)
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
