import sys
import unittest
from fractions import Fraction
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_core.predictive_z.predictive import (  # noqa: E402
    PredictiveZPlanner,
    ZFocusErrorSample,
    ZPredictivePlannerConfig,
)
from scanner_core.predictive_z.types import StripeContext, ZSchedulerConfig  # noqa: E402
from scanner_firmware.planning.z_scheduler.scheduler import PredictiveZSchedulerSimulator  # noqa: E402
from scanner_firmware.foundation.firmware_components.interfaces import FocusCorrectionSample  # noqa: E402
from scanner_firmware.planning.z_scheduler.predictive import (  # noqa: E402
    ApplyPositionCountBasis,
    PredictiveZMathError,
    PredictiveZMicrometerAdapter,
    ZMicrometerToStepAdapterConfig,
    convert_apply_position_um_to_count,
    predict_apply_position_count,
)


class ZPredictivePlannerTests(unittest.TestCase):
    def _planner(self) -> PredictiveZPlanner:
        return PredictiveZPlanner(
            ZPredictivePlannerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                max_correction_steps=40,
                lead_frames=4,
                lead_position_steps=15,
                deadband_steps=2,
            )
        )

    def test_plans_frame_target_as_future_scheduler_command(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=10,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                command_id="focus-1",
                scan_id="scan-a",
                stripe_id=7,
                frame_id=11,
                focus_error_steps=18,
                reference_z_steps=30,
            ),
            context,
        )

        self.assertTrue(decision.accepted)
        self.assertIsNotNone(decision.command)
        self.assertEqual(decision.target_kind, "frame")
        self.assertEqual(decision.command.apply_at_frame_id, 15)
        self.assertIsNone(decision.command.apply_at_position_count)
        self.assertEqual(decision.z_correction_steps, 18)
        self.assertEqual(decision.command.z_target_steps, 48)

        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_frames=4,
            ),
            context,
        )
        scheduled = scheduler.schedule(decision.command)

        self.assertTrue(scheduled.accepted)
        self.assertEqual(scheduler.queued_count, 1)

    def test_plans_position_target_as_future_scheduler_command(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_position=10,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                command_id="focus-pos",
                scan_id="scan-a",
                stripe_id=7,
                position_count=20,
                focus_error_steps=-12,
                reference_z_steps=50,
            ),
            context,
        )

        self.assertTrue(decision.accepted)
        self.assertIsNotNone(decision.command)
        self.assertEqual(decision.target_kind, "position")
        self.assertIsNone(decision.command.apply_at_frame_id)
        self.assertEqual(decision.command.apply_at_position_count, 35)
        self.assertEqual(decision.z_correction_steps, -12)
        self.assertEqual(decision.command.z_target_steps, 38)

        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_position_steps=15,
            ),
            context,
        )
        scheduled = scheduler.schedule(decision.command)

        self.assertTrue(scheduled.accepted)
        self.assertEqual(scheduler.queued_count, 1)

    def test_plans_position_target_at_forward_stripe_end(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_position=80,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                command_id="focus-end",
                scan_id="scan-a",
                stripe_id=7,
                position_count=85,
                focus_error_steps=10,
                reference_z_steps=50,
            ),
            context,
        )

        self.assertTrue(decision.accepted)
        self.assertIsNotNone(decision.command)
        self.assertEqual(decision.command.apply_at_position_count, 100)

    def test_plans_position_target_at_reverse_stripe_end(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=100,
            end_position=0,
            current_position=20,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                command_id="focus-reverse-end",
                scan_id="scan-a",
                stripe_id=7,
                position_count=15,
                focus_error_steps=10,
                reference_z_steps=50,
            ),
            context,
        )

        self.assertTrue(decision.accepted)
        self.assertIsNotNone(decision.command)
        self.assertEqual(decision.command.apply_at_position_count, 0)

    def test_rejects_deadband_without_command(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=10,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                scan_id="scan-a",
                stripe_id=7,
                frame_id=11,
                focus_error_steps=2,
                reference_z_steps=0,
            ),
            context,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "deadband")
        self.assertIsNone(decision.command)
        self.assertFalse(decision.hardware_outputs_enabled)

    def test_clamps_per_command_correction_and_z_limits(self):
        planner = PredictiveZPlanner(
            ZPredictivePlannerConfig(
                min_z_steps=-20,
                max_z_steps=20,
                max_correction_steps=25,
                lead_frames=4,
                deadband_steps=0,
            )
        )
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=10,
        )

        decision = planner.plan(
            ZFocusErrorSample(
                scan_id="scan-a",
                stripe_id=7,
                frame_id=11,
                focus_error_steps=100,
                reference_z_steps=5,
            ),
            context,
        )

        self.assertTrue(decision.accepted)
        self.assertIsNotNone(decision.command)
        self.assertEqual(decision.z_correction_steps, 25)
        self.assertEqual(decision.command.z_target_steps, 20)

    def test_rejects_insufficient_remaining_frame_lookahead(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=14,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                scan_id="scan-a",
                stripe_id=7,
                frame_id=11,
                focus_error_steps=10,
                reference_z_steps=0,
            ),
            context,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "insufficient_lookahead")
        self.assertIsNone(decision.command)

    def test_rejects_immediate_or_past_target_without_command(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=15,
        )

        decision = self._planner().plan(
            ZFocusErrorSample(
                scan_id="scan-a",
                stripe_id=7,
                frame_id=11,
                focus_error_steps=10,
                reference_z_steps=0,
            ),
            context,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "target_already_passed")
        self.assertIsNone(decision.command)

    def test_micrometer_adapter_converts_reference_and_correction_to_absolute_target(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=10,
        )
        adapter = PredictiveZMicrometerAdapter(
            self._planner(),
            ZMicrometerToStepAdapterConfig(z_steps_per_um=2.0),
        )

        decision = adapter.plan_from_um(
            FocusCorrectionSample(
                scan_id="scan-a",
                stripe_id=7,
                focus_error_um=4.0,
                reference_z_um=20.0,
                frame_id=11,
            ),
            context,
        )

        self.assertTrue(decision.accepted)
        self.assertIsNotNone(decision.command)
        self.assertEqual(decision.z_correction_steps, 8)
        self.assertEqual(decision.command.z_target_steps, 48)

    def test_micrometer_adapter_rounds_half_steps_away_from_zero(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_frame_id=10,
        )
        adapter = PredictiveZMicrometerAdapter(
            PredictiveZPlanner(
                ZPredictivePlannerConfig(
                    min_z_steps=-100,
                    max_z_steps=100,
                    max_correction_steps=40,
                    lead_frames=4,
                    deadband_steps=0,
                )
            ),
            ZMicrometerToStepAdapterConfig(z_steps_per_um=2.5),
        )

        positive = adapter.plan_from_um(
            FocusCorrectionSample(
                scan_id="scan-a",
                stripe_id=7,
                focus_error_um=0.2,
                reference_z_um=0.2,
                frame_id=11,
            ),
            context,
        )
        negative = adapter.plan_from_um(
            FocusCorrectionSample(
                scan_id="scan-a",
                stripe_id=7,
                focus_error_um=-0.2,
                reference_z_um=-0.2,
                frame_id=11,
            ),
            context,
        )

        self.assertTrue(positive.accepted)
        self.assertIsNotNone(positive.command)
        self.assertEqual(positive.z_correction_steps, 1)
        self.assertEqual(positive.command.z_target_steps, 2)
        self.assertTrue(negative.accepted)
        self.assertIsNotNone(negative.command)
        self.assertEqual(negative.z_correction_steps, -1)
        self.assertEqual(negative.command.z_target_steps, -2)

    def test_rejects_focus_sample_without_reference_z_steps(self):
        with self.assertRaises(TypeError):
            ZFocusErrorSample(
                scan_id="scan-a",
                stripe_id=7,
                frame_id=11,
                focus_error_steps=10,
            )

    def test_predicts_apply_position_from_signed_forward_scan_velocity(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_position=10,
        )

        apply_position = predict_apply_position_count(
            measurement_position_count=25,
            signed_scan_velocity_counts_per_second=20,
            total_latency_seconds=Fraction(3, 2),
            context=context,
        )

        self.assertEqual(apply_position, 55)

    def test_predicts_reverse_apply_position_with_negative_signed_velocity(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=100,
            end_position=0,
            current_position=90,
        )

        apply_position = predict_apply_position_count(
            measurement_position_count=80,
            signed_scan_velocity_counts_per_second=-30,
            total_latency_seconds=2,
            context=context,
        )

        self.assertEqual(apply_position, 20)

    def test_predictive_velocity_math_allows_exact_stripe_end_target(self):
        forward = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
            current_position=80,
        )
        reverse = StripeContext(
            scan_id="scan-a",
            stripe_id=8,
            start_position=100,
            end_position=0,
            current_position=20,
        )

        self.assertEqual(
            predict_apply_position_count(
                measurement_position_count=90,
                signed_scan_velocity_counts_per_second=10,
                total_latency_seconds=1,
                context=forward,
            ),
            100,
        )
        self.assertEqual(
            predict_apply_position_count(
                measurement_position_count=10,
                signed_scan_velocity_counts_per_second=-10,
                total_latency_seconds=1,
                context=reverse,
            ),
            0,
        )

    def test_predictive_velocity_math_rejects_zero_or_wrong_signed_direction(self):
        forward = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
        )
        reverse = StripeContext(
            scan_id="scan-a",
            stripe_id=8,
            start_position=100,
            end_position=0,
        )

        for context, velocity in ((forward, 0), (forward, -1), (reverse, 1)):
            with self.subTest(context=context, velocity=velocity):
                with self.assertRaises(PredictiveZMathError):
                    predict_apply_position_count(
                        measurement_position_count=context.position,
                        signed_scan_velocity_counts_per_second=velocity,
                        total_latency_seconds=1,
                        context=context,
                    )

    def test_predictive_velocity_math_rounds_fractional_forward_position_later(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=0,
            end_position=100,
        )

        apply_position = predict_apply_position_count(
            measurement_position_count=10,
            signed_scan_velocity_counts_per_second=3,
            total_latency_seconds=Fraction(1, 2),
            context=context,
        )

        self.assertEqual(apply_position, 12)

    def test_predictive_velocity_math_rounds_fractional_reverse_position_later(self):
        context = StripeContext(
            scan_id="scan-a",
            stripe_id=7,
            start_position=100,
            end_position=0,
        )

        apply_position = predict_apply_position_count(
            measurement_position_count=90,
            signed_scan_velocity_counts_per_second=-3,
            total_latency_seconds=Fraction(1, 2),
            context=context,
        )

        self.assertEqual(apply_position, 88)

    def test_converts_physical_apply_position_with_explicit_rounding_basis(self):
        basis = ApplyPositionCountBasis(
            counts_per_um=Fraction(10, 1),
            position_um_origin=100,
            position_count_origin=200,
        )

        forward = convert_apply_position_um_to_count(
            100.75,
            basis=basis,
            scan_direction_count=1,
        )
        reverse = convert_apply_position_um_to_count(
            100.75,
            basis=basis,
            scan_direction_count=-1,
        )

        self.assertEqual(forward, 208)
        self.assertEqual(reverse, 207)

    def test_apply_position_rounding_rejects_unknown_or_invalid_basis(self):
        with self.assertRaisesRegex(PredictiveZMathError, "counts_per_um"):
            ApplyPositionCountBasis(counts_per_um="unknown")

        with self.assertRaisesRegex(PredictiveZMathError, "scan_direction_count"):
            convert_apply_position_um_to_count(
                10.0,
                basis=ApplyPositionCountBasis(counts_per_um=1),
                scan_direction_count=0,
            )


if __name__ == "__main__":
    unittest.main()
