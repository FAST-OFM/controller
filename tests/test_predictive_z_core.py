from decimal import Decimal
from fractions import Fraction

import pytest

from scanner_core.predictive_z import (
    ApplyPositionCountBasis,
    PredictiveZBudget,
    PredictiveZMathError,
    PredictiveZPlanner,
    PredictiveZSchedulerSimulator,
    StripeContext,
    ZCommand,
    ZFocusErrorSample,
    ZNoCorrectionWindow,
    ZPredictivePlannerConfig,
    ZSchedulerConfig,
    compute_apply_frame_id,
    compute_apply_position_um,
    convert_apply_position_um_to_count,
    predict_apply_position_count,
    round_apply_position_count,
    round_apply_position_count_coordinate,
)


def test_predictive_planner_accepts_future_frame_target():
    planner = PredictiveZPlanner(
        ZPredictivePlannerConfig(
            min_z_steps=0,
            max_z_steps=1000,
            max_correction_steps=50,
            lead_frames=3,
            deadband_steps=1,
        )
    )
    sample = ZFocusErrorSample(
        scan_id="scan-1",
        stripe_id=2,
        frame_id=10,
        focus_error_steps=20,
        reference_z_steps=500,
        command_id="af-10",
    )
    context = StripeContext(
        scan_id="scan-1",
        stripe_id=2,
        start_position=0,
        end_position=1000,
        current_frame_id=10,
    )

    decision = planner.plan(sample, context)

    assert decision.accepted
    assert decision.command is not None
    assert decision.command.apply_at_frame_id == 13
    assert decision.command.z_target_steps == 520
    assert decision.z_correction_steps == 20
    assert not decision.hardware_outputs_enabled


def test_predictive_planner_rounds_fractional_position_by_direction():
    planner = PredictiveZPlanner(
        ZPredictivePlannerConfig(
            min_z_steps=0,
            max_z_steps=1000,
            max_correction_steps=50,
            lead_position_steps=2.5,
        )
    )
    sample = ZFocusErrorSample(
        scan_id="scan-1",
        stripe_id=0,
        position_count=100,
        focus_error_steps=-10,
        reference_z_steps=500,
    )
    context = StripeContext(
        scan_id="scan-1",
        stripe_id=0,
        start_position=0,
        end_position=200,
        current_position=100,
    )

    decision = planner.plan(sample, context)

    assert decision.accepted
    assert decision.command is not None
    assert decision.command.apply_at_position_count == 103
    assert decision.command.z_target_steps == 490


def test_predictive_planner_rounds_reverse_position_without_early_target():
    planner = PredictiveZPlanner(
        ZPredictivePlannerConfig(
            min_z_steps=0,
            max_z_steps=1000,
            max_correction_steps=50,
            lead_position_steps=2.5,
        )
    )
    sample = ZFocusErrorSample(
        scan_id="scan-1",
        stripe_id=0,
        position_count=100,
        focus_error_steps=10,
        reference_z_steps=500,
    )
    context = StripeContext(
        scan_id="scan-1",
        stripe_id=0,
        start_position=200,
        end_position=0,
        current_position=100,
    )

    decision = planner.plan(sample, context)

    assert decision.accepted
    assert decision.command is not None
    assert decision.command.apply_at_position_count == 97


def test_predictive_planner_rejects_deadband_and_stale_targets():
    planner = PredictiveZPlanner(
        ZPredictivePlannerConfig(
            min_z_steps=0,
            max_z_steps=1000,
            max_correction_steps=50,
            lead_frames=2,
            deadband_steps=3,
        )
    )
    context = StripeContext(
        scan_id="scan-1",
        stripe_id=0,
        start_position=0,
        end_position=1000,
        current_frame_id=10,
    )

    assert (
        planner.plan(
            ZFocusErrorSample(
                scan_id="scan-1",
                stripe_id=0,
                frame_id=11,
                focus_error_steps=2,
                reference_z_steps=500,
            ),
            context,
        ).reason
        == "deadband"
    )
    assert (
        planner.plan(
            ZFocusErrorSample(
                scan_id="scan-1",
                stripe_id=0,
                frame_id=7,
                focus_error_steps=10,
                reference_z_steps=500,
            ),
            context,
        ).reason
        == "target_already_passed"
    )


def test_scheduler_applies_frame_and_position_commands_without_hardware_outputs():
    scheduler = PredictiveZSchedulerSimulator(
        ZSchedulerConfig(min_z_steps=0, max_z_steps=1000, lead_frames=1),
        StripeContext(scan_id="scan-1", stripe_id=0, start_position=0, end_position=100),
    )

    frame_decision = scheduler.schedule(
        ZCommand(scan_id="scan-1", stripe_id=0, z_target_steps=510, apply_at_frame_id=2)
    )
    position_decision = scheduler.schedule(
        ZCommand(scan_id="scan-1", stripe_id=0, z_target_steps=520, apply_at_position_count=20)
    )

    assert frame_decision.accepted
    assert position_decision.accepted
    assert scheduler.queued_count == 2
    assert [event.z_target_steps for event in scheduler.advance_to(frame_id=2)] == [510]
    assert [event.z_target_steps for event in scheduler.advance_to(position=20)] == [520]


def test_scheduler_rejects_no_correction_window_and_unsafe_hardware_flag():
    with pytest.raises(ValueError, match="cannot enable hardware"):
        ZSchedulerConfig(min_z_steps=0, max_z_steps=1000, hardware_outputs_enabled=True)

    scheduler = PredictiveZSchedulerSimulator(
        ZSchedulerConfig(
            min_z_steps=0,
            max_z_steps=1000,
            no_correction_windows=(ZNoCorrectionWindow("position", 40, 60),),
        ),
        StripeContext(scan_id="scan-1", stripe_id=0, start_position=0, end_position=100),
    )

    decision = scheduler.schedule(
        ZCommand(scan_id="scan-1", stripe_id=0, z_target_steps=500, apply_at_position_count=50)
    )

    assert not decision.accepted
    assert decision.reason == "no_correction_window"


def test_latency_helpers_are_direction_aware():
    budget = PredictiveZBudget(
        exposure_to_frame_ready_ms=10,
        frame_matching_ms=5,
        af_compute_ms=10,
        pi_to_mcu_ms=5,
        mcu_queue_ms=5,
        z_response_or_settle_ms=15,
    )

    assert compute_apply_position_um(1000.0, -200.0, budget) == 990.0
    assert compute_apply_frame_id(10, 20.0, budget, safety_frames=1) == 12
    assert round_apply_position_count(100.25, 1) == 101
    assert round_apply_position_count(100.25, -1) == 100


def test_count_space_rounding_uses_exact_direction_policy():
    assert round_apply_position_count_coordinate(Fraction(401, 4), scan_direction_count=1) == 101
    assert round_apply_position_count_coordinate(Decimal("100.25"), scan_direction_count=-1) == 100
    assert round_apply_position_count_coordinate("100.0", scan_direction_count=1) == 100

    with pytest.raises(PredictiveZMathError, match="scan_direction_count must be -1 or 1"):
        round_apply_position_count_coordinate(100.25, scan_direction_count=2)
    with pytest.raises(PredictiveZMathError, match="raw_count_coordinate must be a finite number"):
        round_apply_position_count_coordinate(float("nan"), scan_direction_count=1)


def test_count_basis_converts_physical_apply_position_to_scheduler_count():
    basis = ApplyPositionCountBasis(
        counts_per_um=Decimal("2.5"),
        position_um_origin=Decimal("10.0"),
        position_count_origin=100,
    )

    assert basis.count_coordinate_for_um(Decimal("11.3")) == Fraction(413, 4)
    assert convert_apply_position_um_to_count(
        Decimal("11.3"),
        basis=basis,
        scan_direction_count=1,
    ) == 104
    assert convert_apply_position_um_to_count(
        Decimal("11.3"),
        basis=basis,
        scan_direction_count=-1,
    ) == 103

    with pytest.raises(PredictiveZMathError, match="counts_per_um must be non-zero"):
        ApplyPositionCountBasis(counts_per_um=0)


def test_predict_apply_position_count_projects_latency_in_count_space():
    forward_context = StripeContext(
        scan_id="scan-1",
        stripe_id=0,
        start_position=0,
        end_position=200,
        current_position=25,
    )
    reverse_context = StripeContext(
        scan_id="scan-1",
        stripe_id=1,
        start_position=200,
        end_position=0,
        current_position=175,
    )

    assert (
        predict_apply_position_count(
            measurement_position_count=100,
            signed_scan_velocity_counts_per_second=Decimal("25.5"),
            total_latency_seconds=Decimal("0.2"),
            context=forward_context,
        )
        == 106
    )
    assert (
        predict_apply_position_count(
            measurement_position_count=100,
            signed_scan_velocity_counts_per_second=Decimal("-25.5"),
            total_latency_seconds=Decimal("0.2"),
            context=reverse_context,
        )
        == 94
    )

    with pytest.raises(PredictiveZMathError, match="must agree with stripe direction"):
        predict_apply_position_count(
            measurement_position_count=100,
            signed_scan_velocity_counts_per_second=-10,
            total_latency_seconds=1,
            context=forward_context,
        )
    with pytest.raises(PredictiveZMathError, match="measurement_position_count"):
        predict_apply_position_count(
            measurement_position_count=250,
            signed_scan_velocity_counts_per_second=10,
            total_latency_seconds=1,
            context=forward_context,
        )
    with pytest.raises(PredictiveZMathError, match="outside stripe bounds"):
        predict_apply_position_count(
            measurement_position_count=195,
            signed_scan_velocity_counts_per_second=10,
            total_latency_seconds=1,
            context=forward_context,
        )
