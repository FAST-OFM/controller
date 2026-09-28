from scanner_core.predictive_z.focus_map import (
    AcceptedFocusObservation,
    FocusMapCalibrationRef,
    FocusMapPredictionTarget,
    FocusMapPriorConfig,
    PredictiveZFocusMap,
)


def test_adjacent_previous_stripe_is_accepted_as_prior():
    focus_map = PredictiveZFocusMap(
        _config(),
        [
            _observation(stripe_id=0, position_index=100, z_focus_steps=1_000),
        ],
    )

    prediction = focus_map.predict_focus(_target(stripe_id=1, position_index=100))

    assert prediction.accepted is True
    assert prediction.reason is None
    assert prediction.z_focus_steps == 1_000
    assert prediction.prior_stripe_id == 0
    assert prediction.stripe_distance == 1
    assert prediction.source_observations == (
        _observation(stripe_id=0, position_index=100, z_focus_steps=1_000),
    )
    assert prediction.confidence < 0.9
    assert _codes(prediction) == (
        "previous_stripe_prior",
        "matched_position_prior",
        "prediction_uncertainty",
        "confidence_downweighted",
    )


def test_calibration_mismatch_rejects_previous_stripe_prior():
    focus_map = PredictiveZFocusMap(
        _config(),
        [
            _observation(
                stripe_id=0,
                position_index=100,
                z_focus_steps=1_000,
                calibration_key="af-cal-a",
            ),
        ],
    )

    prediction = focus_map.predict_focus(
        _target(stripe_id=1, position_index=100, calibration_key="af-cal-b")
    )

    assert prediction.accepted is False
    assert prediction.reason == "calibration_mismatch"
    assert prediction.z_focus_steps is None
    assert prediction.confidence == 0.0


def test_tissue_gap_and_low_tissue_fraction_reject_prior():
    focus_map = PredictiveZFocusMap(
        _config(),
        [
            _observation(
                stripe_id=0,
                position_index=100,
                z_focus_steps=1_000,
                tissue_fraction=0.1,
            ),
        ],
    )

    low_prior_prediction = focus_map.predict_focus(_target(stripe_id=1, position_index=100))
    gap_prediction = focus_map.predict_focus(
        _target(stripe_id=1, position_index=100, tissue_fraction=0.0)
    )

    assert low_prior_prediction.accepted is False
    assert low_prior_prediction.reason == "low_tissue_fraction"
    assert gap_prediction.accepted is False
    assert gap_prediction.reason == "low_tissue_fraction"


def test_stale_and_non_adjacent_previous_stripes_are_rejected():
    stale_focus_map = PredictiveZFocusMap(
        _config(max_sample_age_indices=2),
        [
            _observation(
                stripe_id=0,
                position_index=100,
                z_focus_steps=1_000,
                sample_index=3,
            ),
        ],
    )
    non_adjacent_focus_map = PredictiveZFocusMap(
        _config(max_prior_stripe_distance=1),
        [
            _observation(stripe_id=0, position_index=100, z_focus_steps=1_000),
        ],
    )

    stale_prediction = stale_focus_map.predict_focus(
        _target(stripe_id=1, position_index=100, sample_index=8)
    )
    non_adjacent_prediction = non_adjacent_focus_map.predict_focus(
        _target(stripe_id=2, position_index=100)
    )

    assert stale_prediction.accepted is False
    assert stale_prediction.reason == "stale_prior"
    assert non_adjacent_prediction.accepted is False
    assert non_adjacent_prediction.reason == "non_adjacent_stripe"


def test_slope_clamp_adds_uncertainty_and_diagnostics():
    focus_map = PredictiveZFocusMap(
        _config(
            max_abs_slope_steps_per_position=1.0,
            base_uncertainty_steps=5.0,
            uncertainty_per_position_index=0.1,
            uncertainty_per_sample_age_index=1.0,
            uncertainty_per_stripe_distance=2.0,
            slope_clamp_uncertainty_steps=20.0,
        ),
        [
            _observation(stripe_id=4, position_index=0, z_focus_steps=1_000),
            _observation(stripe_id=4, position_index=100, z_focus_steps=1_400),
        ],
    )

    prediction = focus_map.predict_focus(_target(stripe_id=5, position_index=50))

    assert prediction.accepted is True
    assert prediction.z_focus_steps == 1_050
    assert prediction.uncertainty_steps == 35.0
    assert "slope_clamped" in _codes(prediction)
    assert "confidence_downweighted" in _codes(prediction)
    slope_diagnostic = next(
        diagnostic for diagnostic in prediction.diagnostics if diagnostic.code == "slope_clamped"
    )
    assert slope_diagnostic.details["raw_slope_steps_per_position"] == 4.0
    assert slope_diagnostic.details["applied_slope_steps_per_position"] == 1.0


def _config(**overrides):
    values = {
        "min_observation_confidence": 0.5,
        "min_prediction_confidence": 0.0,
        "min_tissue_fraction": 0.25,
        "min_usable_fraction": 0.5,
        "max_sample_age_indices": 10,
        "max_prior_stripe_distance": 1,
        "max_abs_slope_steps_per_position": 2.0,
        "base_uncertainty_steps": 4.0,
        "uncertainty_per_position_index": 0.0,
        "uncertainty_per_sample_age_index": 0.0,
        "uncertainty_per_stripe_distance": 1.0,
        "slope_clamp_uncertainty_steps": 10.0,
        "uncertainty_full_scale_steps": 100.0,
    }
    values.update(overrides)
    return FocusMapPriorConfig(**values)


def _observation(
    *,
    stripe_id,
    position_index,
    z_focus_steps,
    sample_index=5,
    confidence=0.9,
    tissue_fraction=0.8,
    usable_fraction=0.9,
    calibration_key="af-cal-a",
):
    return AcceptedFocusObservation(
        scan_id="scan-1",
        stripe_id=stripe_id,
        position_index=position_index,
        sample_index=sample_index,
        z_focus_steps=z_focus_steps,
        confidence=confidence,
        tissue_fraction=tissue_fraction,
        usable_fraction=usable_fraction,
        calibration=FocusMapCalibrationRef(calibration_key),
    )


def _target(
    *,
    stripe_id,
    position_index,
    sample_index=8,
    tissue_fraction=0.8,
    usable_fraction=0.9,
    calibration_key="af-cal-a",
):
    return FocusMapPredictionTarget(
        scan_id="scan-1",
        stripe_id=stripe_id,
        position_index=position_index,
        sample_index=sample_index,
        tissue_fraction=tissue_fraction,
        usable_fraction=usable_fraction,
        calibration=FocusMapCalibrationRef(calibration_key),
    )


def _codes(prediction):
    return tuple(diagnostic.code for diagnostic in prediction.diagnostics)
