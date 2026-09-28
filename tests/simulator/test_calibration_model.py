import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.calibration.errors import CalibrationError  # noqa: E402
from scanner_firmware.domain.calibration.estimation import (  # noqa: E402
    AxisTravelCalibrationEstimator,
    estimate_axis_steps_per_mm,
    estimate_backlash,
    estimate_repeatability,
)
from scanner_firmware.domain.calibration.lookup import build_led_current_lookup  # noqa: E402
from scanner_firmware.domain.calibration.types import (  # noqa: E402
    AxisTravelObservation,
    BacklashObservation,
    LedCalibrationSample,
)
from scanner_firmware.foundation.firmware_components.interfaces import AxisCalibrationObservation  # noqa: E402


class CalibrationModelTests(unittest.TestCase):
    def test_estimates_axis_steps_per_mm_from_measured_travel(self):
        estimate = estimate_axis_steps_per_mm(
            (
                AxisTravelObservation(axis="X", commanded_steps=1600, measured_mm=1.0),
                AxisTravelObservation(axis="X", commanded_steps=3200, measured_mm=2.0),
            )
        )

        self.assertEqual(estimate.axis, "X")
        self.assertEqual(estimate.steps_per_mm, 1600.0)
        self.assertEqual(estimate.sample_count, 2)
        self.assertEqual(estimate.residual_rms_mm, 0.0)

    def test_axis_estimator_rejects_mixed_axes_and_zero_observations(self):
        with self.assertRaisesRegex(CalibrationError, "at least one"):
            estimate_axis_steps_per_mm(())
        with self.assertRaisesRegex(CalibrationError, "one axis"):
            estimate_axis_steps_per_mm(
                (
                    AxisTravelObservation(axis="X", commanded_steps=1600, measured_mm=1.0),
                    AxisTravelObservation(axis="Y", commanded_steps=1600, measured_mm=1.0),
                )
            )
        with self.assertRaisesRegex(CalibrationError, "commanded_steps"):
            AxisTravelObservation(axis="X", commanded_steps=0, measured_mm=1.0)

    def test_axis_estimator_implements_shared_component_interface(self):
        estimate = AxisTravelCalibrationEstimator().estimate_axis(
            (
                AxisCalibrationObservation(
                    axis="Z",
                    commanded_steps=6400,
                    measured_mm=1.0,
                ),
                AxisCalibrationObservation(
                    axis="Z",
                    commanded_steps=12800,
                    measured_mm=2.0,
                ),
            )
        )

        self.assertEqual(estimate.axis, "Z")
        self.assertEqual(estimate.steps_per_mm, 6400.0)
        self.assertEqual(estimate.sample_count, 2)

    def test_estimates_backlash_from_forward_reverse_observations(self):
        estimate = estimate_backlash(
            (
                BacklashObservation(axis="Y", forward_position_mm=10.00, reverse_position_mm=9.96),
                BacklashObservation(axis="Y", forward_position_mm=12.00, reverse_position_mm=11.94),
            )
        )

        self.assertEqual(estimate.axis, "Y")
        self.assertAlmostEqual(estimate.backlash_mm, 0.05)
        self.assertEqual(estimate.sample_count, 2)

    def test_estimates_repeatability_statistics(self):
        estimate = estimate_repeatability("Z", (0.100, 0.102, 0.098, 0.100))

        self.assertEqual(estimate.axis, "Z")
        self.assertEqual(estimate.sample_count, 4)
        self.assertAlmostEqual(estimate.mean_position_mm, 0.100)
        self.assertAlmostEqual(estimate.peak_to_peak_mm, 0.004)
        self.assertGreater(estimate.standard_deviation_mm, 0.0)

    def test_led_current_lookup_interpolates_brightness_samples(self):
        lookup = build_led_current_lookup(
            "led_white",
            (
                LedCalibrationSample(channel="led_white", brightness=255, current_ma=80.0),
                LedCalibrationSample(channel="led_white", brightness=0, current_ma=0.0),
                LedCalibrationSample(channel="led_white", brightness=127, current_ma=40.0),
            ),
        )

        self.assertEqual(lookup.current_for_brightness(0), 0.0)
        self.assertEqual(lookup.current_for_brightness(255), 80.0)
        self.assertAlmostEqual(lookup.current_for_brightness(64), 20.15748031496063)

    def test_led_lookup_rejects_invalid_or_out_of_range_samples(self):
        with self.assertRaisesRegex(CalibrationError, "between 0 and 255"):
            LedCalibrationSample(channel="led_white", brightness=256, current_ma=1.0)
        lookup = build_led_current_lookup(
            "led_green",
            (
                LedCalibrationSample(channel="led_green", brightness=0, current_ma=0.0),
                LedCalibrationSample(channel="led_green", brightness=127, current_ma=20.0),
            ),
        )
        with self.assertRaisesRegex(CalibrationError, "outside calibrated range"):
            lookup.current_for_brightness(255)


if __name__ == "__main__":
    unittest.main()
