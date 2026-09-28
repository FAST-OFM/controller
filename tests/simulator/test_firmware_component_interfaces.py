import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.foundation.firmware_components.interfaces import (  # noqa: E402
    AxisCalibrationObservation,
    ComponentSafety,
    FocusCorrectionSample,
    LedBrightnessState,
    RawBayerFocusFrameInput,
    StripeGeometryInput,
)


class FirmwareComponentInterfaceTests(unittest.TestCase):
    def test_component_safety_rejects_hardware_output_boundaries(self):
        self.assertTrue(ComponentSafety().software_only)

        with self.assertRaisesRegex(ValueError, "software-only"):
            ComponentSafety(software_only=False)
        with self.assertRaisesRegex(ValueError, "hardware outputs"):
            ComponentSafety(hardware_outputs_enabled=True)

    def test_interface_value_objects_are_plain_software_inputs(self):
        geometry = StripeGeometryInput(
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=10,
            event_pitch=5,
            event_count=3,
        )
        frame = RawBayerFocusFrameInput(
            encoding="raw_bayer_linear",
            width=2,
            height=2,
            bayer_pattern="RGGB",
            rows=((10.0, 11.0), (19.0, 20.0)),
        )
        calibration = AxisCalibrationObservation(
            axis="Z",
            commanded_steps=400,
            measured_mm=0.25,
        )
        correction = FocusCorrectionSample(
            scan_id="scan-a",
            stripe_id=1,
            focus_error_um=2.5,
            reference_z_um=10.0,
            frame_id=42,
        )

        self.assertEqual(geometry.event_pitch, 5)
        self.assertEqual(frame.encoding, "raw_bayer_linear")
        self.assertEqual(frame.bayer_pattern, "RGGB")
        self.assertEqual(calibration.axis, "Z")
        self.assertEqual(correction.frame_id, 42)

    def test_led_brightness_state_is_logical_and_channel_preserving(self):
        state = LedBrightnessState(red=12, green=34, white=56)

        updated = state.with_channel("green", 99)

        self.assertEqual(updated.as_channels(), (("red", 12), ("green", 99), ("white", 56)))
        self.assertEqual(updated.value_for("green"), 99)

    def test_interface_value_objects_reject_invalid_runtime_state(self):
        with self.assertRaisesRegex(ValueError, "axis"):
            StripeGeometryInput(
                axis="Z",
                start_position=0,
                end_position=100,
                first_event_position=10,
                event_pitch=5,
                event_count=3,
            )
        with self.assertRaisesRegex(ValueError, "raw_bayer_linear"):
            RawBayerFocusFrameInput(
                encoding="preview",
                width=2,
                height=2,
                bayer_pattern="RGGB",
                rows=((1.0, 2.0), (3.0, 4.0)),
            )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            FocusCorrectionSample(
                scan_id="scan-a",
                stripe_id=1,
                focus_error_um=2.5,
                reference_z_um=10.0,
                frame_id=42,
                position_count=100,
            )
        with self.assertRaisesRegex(ValueError, "between 0 and 255"):
            LedBrightnessState(red=256)
        with self.assertRaisesRegex(ValueError, "channel"):
            LedBrightnessState().with_channel("blue", 1)


if __name__ == "__main__":
    unittest.main()
