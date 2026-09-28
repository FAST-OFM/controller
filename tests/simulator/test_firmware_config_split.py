from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.platform_config.cli import main  # noqa: E402
from scanner_firmware.domain.platform_config.config_split import (  # noqa: E402
    check_firmware_config_split_files,
    check_firmware_config_split_from_mapping,
    discover_static_config_paths,
)


VALID_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "firmware_config_split_valid.json"
VALID_FIXTURE_REPORT_PATH = "tests/fixtures/firmware_config_split_valid.json"


class FirmwareConfigSplitTests(unittest.TestCase):
    def test_accepts_firmware_owned_controller_scheduler_protocol_config(self):
        report = check_firmware_config_split_files((VALID_FIXTURE,))

        self.assertTrue(report.accepted)
        self.assertEqual(report.violations, ())
        self.assertEqual(report.checked_paths, (VALID_FIXTURE_REPORT_PATH,))

    def test_rejects_pi_runtime_config_fields_in_firmware_config(self):
        report = check_firmware_config_split_from_mapping(
            {
                "controller": {"kind": "klipper_mks"},
                "scheduler": {
                    "camera": {
                        "sensor_width": 4056,
                        "crop": {"x": 0, "y": 0, "width": 100, "height": 100},
                        "exposure_us": 1000,
                    },
                    "image_processing": {"flatfield": "active"},
                    "acquisition": {"frame_queue": 4},
                    "autofocus": {"worker": "pi"},
                    "tiling": {"tile_width": 512},
                    "calibration_registry": {"active": "current"},
                    "scan_recipe": {"roi": "slide"},
                },
                "protocol": {"trigger_output_name": "camera_or_sync_trigger"},
            },
            source="bad.json",
        )

        field_paths = [violation.field_path for violation in report.violations]
        self.assertFalse(report.accepted)
        self.assertEqual(
            field_paths,
            [
                "scheduler.acquisition",
                "scheduler.acquisition.frame_queue",
                "scheduler.autofocus",
                "scheduler.calibration_registry",
                "scheduler.camera",
                "scheduler.camera.crop",
                "scheduler.camera.exposure_us",
                "scheduler.camera.sensor_width",
                "scheduler.image_processing",
                "scheduler.image_processing.flatfield",
                "scheduler.scan_recipe",
                "scheduler.tiling",
                "scheduler.tiling.tile_width",
            ],
        )

    def test_rejects_pi_runtime_fields_nested_inside_sequences(self):
        report = check_firmware_config_split_from_mapping(
            {
                "scheduler": {
                    "stages": [
                        {
                            "name": "metadata",
                            "camera_modes": [{"exposure_us": 1000}],
                        }
                    ],
                },
                "protocol": {"trigger_output_name": "camera_or_sync_trigger"},
            },
            source="nested.json",
        )

        self.assertFalse(report.accepted)
        self.assertEqual(
            [violation.field_path for violation in report.violations],
            [
                "scheduler.stages[0].camera_modes",
                "scheduler.stages[0].camera_modes[0].exposure_us",
            ],
        )

    def test_preserves_unknown_hardware_values_and_rejects_placeholders(self):
        accepted = check_firmware_config_split_from_mapping(
            {
                "pins": {
                    "x_step": "unknown",
                    "x_dir": "unknown",
                    "rail_5v": "unknown",
                },
                "homing": {"feasibility_outcome": {"x": "unknown"}},
            },
            source="unknowns.yaml",
        )
        rejected = check_firmware_config_split_from_mapping(
            {
                "pins": {
                    "x_step": "TODO",
                    "rail_5v": "TBD",
                },
                "homing": {"feasibility_outcome": {"x": "PLACEHOLDER"}},
            },
            source="placeholders.yaml",
        )

        self.assertTrue(accepted.accepted)
        self.assertFalse(rejected.accepted)
        self.assertEqual(
            [violation.field_path for violation in rejected.violations],
            [
                "homing.feasibility_outcome.x",
                "pins.rail_5v",
                "pins.x_step",
            ],
        )

    def test_allows_camera_trigger_alias_without_camera_runtime_config(self):
        report = check_firmware_config_split_from_mapping(
            {
                "protocol": {
                    "trigger_output_name": "camera_or_sync_trigger",
                    "events": ["FRAME_EVENT"],
                },
                "io": {
                    "camera_or_sync_trigger": "PD6",
                    "camera_trigger_config_valid": True,
                },
            }
        )

        self.assertTrue(report.accepted)

    def test_cli_writes_deterministic_report_to_output_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.json"

            code = main(["--check-static", str(VALID_FIXTURE), "--output", str(output_path)])

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["checked_paths"], [VALID_FIXTURE_REPORT_PATH])
            self.assertEqual(payload["violations"], [])
            self.assertIn("scheduler", payload["firmware_owned_config_sections"])
            self.assertIn("protocol", payload["firmware_owned_config_sections"])
            self.assertIn("motor_controller", payload["firmware_owned_config_sections"])

    def test_cli_returns_nonzero_for_pi_runtime_fields(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as config:
            config.write(json.dumps({"camera": {"exposure_us": 1000}}))
            config.flush()

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--check-static", config.name])

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["accepted"])
        self.assertEqual(
            [violation["field_path"] for violation in payload["violations"]],
            ["camera", "camera.exposure_us"],
        )

    def test_default_static_discovery_checks_firmware_config_candidates(self):
        with patch("pathlib.Path.cwd", return_value=REPO_ROOT):
            paths = discover_static_config_paths(REPO_ROOT)
            report = check_firmware_config_split_files(paths)

        self.assertIn(REPO_ROOT / "boards" / "kingroon_mono_v2" / "pins.yaml", paths)
        self.assertIn(REPO_ROOT / "arduino" / "led_brightness_controller" / "hardware-config.yaml", paths)
        self.assertTrue(report.accepted)


if __name__ == "__main__":
    unittest.main()
