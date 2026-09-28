import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_core.axis_resolution import (  # noqa: E402
    AxisResolution,
    steps_per_mm_from_screw_pitch,
)
from scanner_core.scan_geometry import (  # noqa: E402
    PositionSample,
    ScanGeometryError,
    StripeGeometry,
    validate_axis,
)
from scanner_core.scan_units import (  # noqa: E402
    UnitConversionError,
    micrometers_to_nanometers,
    micrometers_to_steps,
    round_half_away_from_zero,
)
from scanner_firmware.domain.scan_math.contracts import (  # noqa: E402
    FIRMWARE_MATH_CONTRACT_ID,
    FUTURE_COORDINATE_SOURCE,
    GEOMETRY_SOURCE_MODULE,
    INITIAL_COORDINATE_SOURCE,
    MICROMETERS_PER_MILLIMETER,
    NANOMETERS_PER_MICROMETER,
    OVERSHOOT_SIGN_CONVENTION,
    PHYSICAL_DISTANCE_UNIT,
    POSITION_COUNT_UNIT,
    ROUNDING_MODE,
    SCHEDULED_EVENT_POSITION_RULE,
)


class ScanMathGeometryTests(unittest.TestCase):
    def test_firmware_math_contract_v1_names_source_units_rounding_and_sign(self):
        self.assertEqual(FIRMWARE_MATH_CONTRACT_ID, "firmware_math_units_sign_rounding_v1")
        self.assertEqual(GEOMETRY_SOURCE_MODULE, "scanner_core.scan_geometry")
        self.assertEqual(ROUNDING_MODE, "round_half_away_from_zero")
        self.assertEqual(POSITION_COUNT_UNIT, "controller_count")
        self.assertEqual(PHYSICAL_DISTANCE_UNIT, "micrometer")
        self.assertEqual(NANOMETERS_PER_MICROMETER, 1000)
        self.assertEqual(MICROMETERS_PER_MILLIMETER, 1000)
        self.assertEqual(INITIAL_COORDINATE_SOURCE, "commanded_step_count")
        self.assertEqual(FUTURE_COORDINATE_SOURCE, "encoder_count")
        self.assertEqual(OVERSHOOT_SIGN_CONVENTION, "sample_position_minus_event_position")
        self.assertEqual(SCHEDULED_EVENT_POSITION_RULE, "event_position_remains_scheduled_count")

    def test_firmware_scan_math_tests_use_scanner_core_primitives_directly(self):
        self.assertEqual(StripeGeometry.__module__, "scanner_core.scan_geometry")
        self.assertEqual(PositionSample.__module__, "scanner_core.scan_geometry")
        self.assertEqual(validate_axis.__module__, "scanner_core.scan_geometry")
        self.assertEqual(round_half_away_from_zero.__module__, "scanner_core.scan_units")

    def test_builds_forward_x_geometry_positions_and_direction(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=0,
            event_pitch=25,
            event_count=5,
        )

        self.assertEqual(geometry.direction, 1)
        self.assertEqual(geometry.positions, (0, 25, 50, 75, 100))
        self.assertEqual(geometry.pitch, 25)
        self.assertEqual(geometry.last_position, 100)
        self.assertEqual(geometry.lower_bound, 0)
        self.assertEqual(geometry.upper_bound, 100)
        self.assertTrue(geometry.contains_position(75))
        self.assertTrue(geometry.is_event_position(50))
        self.assertFalse(geometry.is_event_position(60))
        self.assertEqual(
            geometry.position_samples,
            (
                PositionSample(axis="X", event_index=0, position_count=0),
                PositionSample(axis="X", event_index=1, position_count=25),
                PositionSample(axis="X", event_index=2, position_count=50),
                PositionSample(axis="X", event_index=3, position_count=75),
                PositionSample(axis="X", event_index=4, position_count=100),
            ),
        )

    def test_core_axis_normalization_and_pitch_alias_semantics_are_available(self):
        geometry = StripeGeometry(
            axis="x",
            start_position=100,
            end_position=160,
            pitch=20,
            event_count=3,
        )

        self.assertEqual(validate_axis("x"), "X")
        self.assertEqual(validate_axis("y"), "Y")
        self.assertEqual(geometry.axis, "X")
        self.assertEqual(geometry.positions, (120, 140, 160))
        self.assertEqual(
            geometry.position_for_event(0),
            PositionSample(axis="X", event_index=0, position_count=120),
        )

    def test_builds_reverse_y_geometry_positions_and_direction(self):
        geometry = StripeGeometry(
            axis="Y",
            start_position=100,
            end_position=0,
            first_event_position=100,
            event_pitch=-30,
            event_count=4,
        )

        self.assertEqual(geometry.direction, -1)
        self.assertEqual(geometry.positions, (100, 70, 40, 10))
        self.assertEqual(geometry.last_position, 10)
        self.assertTrue(geometry.contains_position(0))
        self.assertTrue(geometry.contains_position(100))

    def test_allows_zero_event_count_with_empty_positions(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=10,
            event_pitch=10,
            event_count=0,
        )

        self.assertEqual(geometry.positions, ())
        self.assertIsNone(geometry.last_position)
        self.assertFalse(geometry.is_event_position(0))

    def test_rejects_invalid_axis_direction_pitch_and_counts(self):
        invalid_cases = (
            {"axis": "Z", "start_position": 0, "end_position": 10, "pitch": 1, "event_count": 1},
            {
                "axis": "X",
                "start_position": 0,
                "end_position": 0,
                "first_event_position": 0,
                "event_pitch": 1,
                "event_count": 1,
            },
            {
                "axis": "X",
                "start_position": 0,
                "end_position": 10,
                "first_event_position": 0,
                "event_pitch": 0,
                "event_count": 1,
            },
            {
                "axis": "X",
                "start_position": 0,
                "end_position": 10,
                "first_event_position": 0,
                "event_pitch": -1,
                "event_count": 1,
            },
            {
                "axis": "Y",
                "start_position": 10,
                "end_position": 0,
                "first_event_position": 10,
                "event_pitch": 1,
                "event_count": 1,
            },
            {
                "axis": "Y",
                "start_position": 10,
                "end_position": 0,
                "first_event_position": 10,
                "event_pitch": -1,
                "event_count": -1,
            },
            {
                "axis": "X",
                "start_position": 0,
                "end_position": 10,
                "first_event_position": 0,
                "event_pitch": 1,
                "event_count": True,
            },
            {
                "axis": "X",
                "start_position": 0,
                "end_position": 10,
                "first_event_position": True,
                "event_pitch": 1,
                "event_count": 1,
            },
        )

        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ScanGeometryError):
                    if "pitch" in kwargs:
                        pitch = kwargs["pitch"]
                        kwargs = {
                            **kwargs,
                            "first_event_position": kwargs["start_position"],
                            "event_pitch": pitch,
                        }
                        kwargs.pop("pitch")
                    StripeGeometry(**kwargs)

    def test_allows_first_event_inside_stripe_after_start(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=10,
            event_pitch=20,
            event_count=4,
        )

        self.assertEqual(geometry.positions, (10, 30, 50, 70))
        self.assertFalse(geometry.is_event_position(0))
        self.assertTrue(geometry.is_event_position(30))

    def test_rejects_last_position_outside_bounds(self):
        with self.assertRaisesRegex(ScanGeometryError, "last event position"):
            StripeGeometry(
                axis="X",
                start_position=0,
                end_position=10,
                first_event_position=0,
                event_pitch=4,
                event_count=4,
            )

    def test_checks_bounds_and_planned_event_positions(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=10,
            end_position=30,
            first_event_position=10,
            event_pitch=10,
            event_count=2,
        )

        self.assertEqual(geometry.require_within_bounds(20), 20)
        self.assertEqual(geometry.require_event_position(10), 10)
        with self.assertRaisesRegex(ScanGeometryError, "outside stripe bounds"):
            geometry.require_within_bounds(31, "sample.position")
        with self.assertRaisesRegex(ScanGeometryError, "planned stripe event"):
            geometry.require_event_position(30)

    def test_calculates_forward_sample_overshoot(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=0,
            event_pitch=20,
            event_count=5,
        )

        overshoot = geometry.overshoot_for_sample(
            event_position=40,
            sample=PositionSample(axis="X", position=47),
        )

        self.assertEqual(overshoot, 7)

    def test_calculates_reverse_sample_overshoot_as_signed_position_delta(self):
        geometry = StripeGeometry(
            axis="Y",
            start_position=100,
            end_position=0,
            first_event_position=100,
            event_pitch=-20,
            event_count=5,
        )

        overshoot = geometry.overshoot_for_sample(
            event_position=60,
            sample=PositionSample(axis="Y", position=52),
        )

        self.assertEqual(overshoot, -8)

    def test_rejects_sample_axis_mismatch_before_overshoot(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=0,
            event_pitch=20,
            event_count=5,
        )

        with self.assertRaisesRegex(ScanGeometryError, "sample axis"):
            geometry.overshoot_for_sample(
                event_position=40,
                sample=PositionSample(axis="Y", position=45),
            )

    def test_rejects_sample_that_has_not_reached_event(self):
        geometry = StripeGeometry(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=0,
            event_pitch=20,
            event_count=5,
        )

        with self.assertRaisesRegex(ScanGeometryError, "not reached"):
            geometry.overshoot_for_sample(
                event_position=40,
                sample=PositionSample(axis="X", position=39),
            )

    def test_derives_steps_per_mm_from_screw_pitch_and_microsteps(self):
        resolution = AxisResolution(
            screw_pitch_mm=Fraction(1, 4),
            microsteps=8,
            motor_steps_per_rev=200,
        )

        self.assertEqual(resolution.steps_per_rev, Fraction(1600, 1))
        self.assertEqual(resolution.steps_per_mm, Fraction(6400, 1))
        self.assertEqual(
            steps_per_mm_from_screw_pitch(
                screw_pitch_mm="0.25",
                microsteps=8,
                motor_steps_per_rev=200,
            ),
            Fraction(6400, 1),
        )

    def test_unit_conversions_round_half_away_from_zero(self):
        self.assertEqual(round_half_away_from_zero(0.5), 1)
        self.assertEqual(round_half_away_from_zero(-0.5), -1)
        self.assertEqual(round_half_away_from_zero(Decimal("1.5")), 2)
        self.assertEqual(round_half_away_from_zero(Decimal("-1.5")), -2)
        self.assertEqual(round_half_away_from_zero(Fraction(3, 2)), 2)
        self.assertEqual(round_half_away_from_zero(Fraction(-3, 2)), -2)
        self.assertEqual(micrometers_to_nanometers(0.0005), 1)
        self.assertEqual(micrometers_to_nanometers(-0.0005), -1)
        self.assertEqual(
            micrometers_to_steps(0.2, steps_per_um=2.5),
            1,
        )
        self.assertEqual(
            micrometers_to_steps(-0.2, steps_per_um=2.5),
            -1,
        )
        self.assertEqual(
            micrometers_to_steps(Fraction(1, 4), steps_per_um=Fraction(10, 1)),
            3,
        )
        self.assertEqual(
            micrometers_to_steps(Fraction(-1, 4), steps_per_um=Fraction(10, 1)),
            -3,
        )

    def test_unit_conversions_reject_invalid_numbers_and_scales(self):
        invalid_rounding_values = (True, float("nan"), float("inf"), "not-a-number")
        for value in invalid_rounding_values:
            with self.subTest(value=value):
                with self.assertRaises(UnitConversionError):
                    round_half_away_from_zero(value)

        invalid_step_scales = (0, -1, False, float("nan"), "not-a-number")
        for steps_per_um in invalid_step_scales:
            with self.subTest(steps_per_um=steps_per_um):
                with self.assertRaises(UnitConversionError):
                    micrometers_to_steps(1, steps_per_um=steps_per_um)

    def test_rejects_invalid_resolution_inputs(self):
        invalid_cases = (
            {"screw_pitch_mm": 0, "microsteps": 16, "motor_steps_per_rev": 200},
            {"screw_pitch_mm": 2, "microsteps": 0, "motor_steps_per_rev": 200},
            {"screw_pitch_mm": 2, "microsteps": 16, "motor_steps_per_rev": False},
        )

        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ScanGeometryError):
                    steps_per_mm_from_screw_pitch(**kwargs)


if __name__ == "__main__":
    unittest.main()
