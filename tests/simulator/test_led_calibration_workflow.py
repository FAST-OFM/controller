import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.calibration.led_modes import (  # noqa: E402
    CALIBRATION_MODE,
    RUNTIME_MODE,
)
from scanner_firmware.domain.calibration.led_resistor import (  # noqa: E402
    LedChannelResistorMetadata,
)
from scanner_firmware.domain.calibration.led_runtime import (  # noqa: E402
    LedRuntimeCurrentModel,
)
from scanner_firmware.domain.calibration.led_samples import (  # noqa: E402
    SenseResistorSample,
)
from scanner_firmware.domain.calibration.led_workflow import (  # noqa: E402
    LedCalibrationWorkflow,
)
from scanner_firmware.domain.calibration.errors import CalibrationError  # noqa: E402


class LedCalibrationWorkflowTests(unittest.TestCase):
    def test_builds_lookup_from_accepted_on_time_samples(self):
        table = LedCalibrationWorkflow(_metadata(), CALIBRATION_MODE).build_table(
            (
                SenseResistorSample(
                    channel="led_white",
                    brightness=0,
                    sense_resistor_mv=0.0,
                    led_on=True,
                ),
                SenseResistorSample(
                    channel="led_white",
                    brightness=127,
                    sense_resistor_mv=100.0,
                    led_on=True,
                ),
                SenseResistorSample(
                    channel="led_white",
                    brightness=255,
                    sense_resistor_mv=200.0,
                    led_on=True,
                ),
            )
        )

        self.assertEqual(table.channel, "led_white")
        self.assertEqual(table.mode, CALIBRATION_MODE)
        self.assertEqual(table.lookup.current_for_brightness(255), 100.0)
        self.assertEqual(
            [
                (point.brightness, point.current_ma, point.normalized_current)
                for point in table.points
            ],
            [(0, 0.0, 0.0), (127, 50.0, 0.5), (255, 100.0, 1.0)],
        )
        self.assertAlmostEqual(table.points[1].normalized_brightness, 127 / 255.0)

    def test_rejects_off_time_sense_resistor_samples(self):
        with self.assertRaisesRegex(CalibrationError, "only valid while LED is on"):
            LedCalibrationWorkflow(_metadata(), CALIBRATION_MODE).build_table(
                (
                    SenseResistorSample(
                        channel="led_white",
                        brightness=0,
                        sense_resistor_mv=0.0,
                        led_on=True,
                    ),
                    SenseResistorSample(
                        channel="led_white",
                        brightness=127,
                        sense_resistor_mv=100.0,
                        led_on=False,
                    ),
                )
            )

    def test_rejects_out_of_range_target_current(self):
        table = _table()
        runtime = LedRuntimeCurrentModel(table, RUNTIME_MODE)

        with self.assertRaisesRegex(CalibrationError, "exceeds channel maximum"):
            runtime.setpoint_for_target_current(125.0)

    def test_runtime_interpolates_brightness_via_existing_lookup(self):
        runtime = LedRuntimeCurrentModel(_table(), RUNTIME_MODE)

        setpoint = runtime.setpoint_for_target_current(25.0)

        self.assertEqual(setpoint.channel, "led_white")
        self.assertEqual(setpoint.brightness, 64)
        self.assertAlmostEqual(setpoint.normalized_brightness, 64 / 255.0)
        self.assertAlmostEqual(setpoint.predicted_current_ma, 25.19685039370079)

    def test_calibration_and_runtime_modes_are_explicit(self):
        with self.assertRaisesRegex(CalibrationError, "calibration mode"):
            LedCalibrationWorkflow(_metadata(), RUNTIME_MODE).build_table(
                (
                    SenseResistorSample(
                        channel="led_white",
                        brightness=0,
                        sense_resistor_mv=0.0,
                        led_on=True,
                    ),
                    SenseResistorSample(
                        channel="led_white",
                        brightness=255,
                        sense_resistor_mv=200.0,
                        led_on=True,
                    ),
                )
            )
        with self.assertRaisesRegex(CalibrationError, "runtime mode"):
            LedRuntimeCurrentModel(_table(), CALIBRATION_MODE)


def _metadata() -> LedChannelResistorMetadata:
    return LedChannelResistorMetadata(
        channel="led_white",
        sense_resistor_ohms=2.0,
        sense_resistor_power_watts=0.25,
        target_current_max_ma=100.0,
    )


def _table():
    return LedCalibrationWorkflow(_metadata(), CALIBRATION_MODE).build_table(
        (
            SenseResistorSample(
                channel="led_white",
                brightness=0,
                sense_resistor_mv=0.0,
                led_on=True,
            ),
            SenseResistorSample(
                channel="led_white",
                brightness=127,
                sense_resistor_mv=100.0,
                led_on=True,
            ),
            SenseResistorSample(
                channel="led_white",
                brightness=255,
                sense_resistor_mv=200.0,
                led_on=True,
            ),
        )
    )


if __name__ == "__main__":
    unittest.main()
