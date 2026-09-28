from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.platform_config.loader import load_platform_config_from_mapping  # noqa: E402
from scanner_firmware.domain.platform_config.model import PlatformConfigError  # noqa: E402


def valid_config() -> dict[str, object]:
    return {
        "profile": {
            "board_id": "kingroon_mono_v2",
            "controller_kind": "klipper_mks",
            "printer_config_present": True,
            "safe_defaults_declared": True,
        },
        "motion": {
            "homed_axes": ["X", "Y", "Z"],
            "soft_limits_configured": True,
            "scan_roi_within_limits": True,
            "coordinate_source_valid": True,
            "homing_feasibility_status": "implemented",
            "homing_enabled": True,
        },
        "io": {
            "camera_trigger_config_valid": True,
            "led_pattern_valid": True,
            "inactive_output_states_declared": True,
            "output_ownership_unambiguous": True,
            "hardware_outputs_armed": False,
        },
        "scan_recipe": {
            "dry_run": True,
            "requested_scan_mode": "stop_and_capture",
            "z_policy_valid": True,
        },
    }


class PlatformConfigLoaderTests(unittest.TestCase):
    def test_loads_nested_mapping_into_validated_platform_config(self):
        config = load_platform_config_from_mapping(valid_config())

        self.assertEqual(config.profile.board_id, "kingroon_mono_v2")
        self.assertEqual(config.motion.homed_axes, ("X", "Y", "Z"))
        self.assertTrue(config.motion.homing_enabled)
        self.assertEqual(config.motion.homing_feasibility_status, "implemented")
        self.assertFalse(config.io.hardware_outputs_armed)
        self.assertTrue(config.scan_recipe.dry_run)

    def test_rejects_legacy_camera_mode_section(self):
        data = valid_config()
        data["camera"] = {
            "camera_id": "main",
            "sensor_width": 4056,
            "sensor_height": 3040,
            "output_width": 1000,
            "output_height": 500,
            "pixel_format": "raw_bayer_linear",
            "exposure_us": 1000,
            "frame_period_us": 10000,
            "crop": {"x": 100, "y": 200, "width": 2000, "height": 1000},
        }

        with self.assertRaisesRegex(PlatformConfigError, "platform_config unknown.*camera"):
            load_platform_config_from_mapping(data)

    def test_rejects_unknown_top_level_or_nested_fields(self):
        data = valid_config()
        data["unknown"] = {}
        with self.assertRaisesRegex(PlatformConfigError, "platform_config unknown"):
            load_platform_config_from_mapping(data)

        data = valid_config()
        profile = data["profile"]
        assert isinstance(profile, dict)
        profile["extra"] = True
        with self.assertRaisesRegex(PlatformConfigError, "profile unknown"):
            load_platform_config_from_mapping(data)

        data = valid_config()
        scan_recipe = data["scan_recipe"]
        assert isinstance(scan_recipe, dict)
        scan_recipe["extra"] = True
        with self.assertRaisesRegex(PlatformConfigError, "scan_recipe unknown"):
            load_platform_config_from_mapping(data)

    def test_rejects_missing_required_fields(self):
        data = valid_config()
        motion = data["motion"]
        assert isinstance(motion, dict)
        del motion["coordinate_source_valid"]

        with self.assertRaisesRegex(PlatformConfigError, "motion missing required"):
            load_platform_config_from_mapping(data)

    def test_rejects_non_string_field_names(self):
        data = valid_config()
        profile = data["profile"]
        assert isinstance(profile, dict)
        profile[1] = "not-a-field-name"

        with self.assertRaisesRegex(PlatformConfigError, "field names must be strings"):
            load_platform_config_from_mapping(data)

    def test_rejects_malformed_section_and_axes(self):
        data = valid_config()
        data["io"] = []
        with self.assertRaisesRegex(PlatformConfigError, "io must be a mapping"):
            load_platform_config_from_mapping(data)

        data = valid_config()
        motion = data["motion"]
        assert isinstance(motion, dict)
        motion["homed_axes"] = "XYZ"
        with self.assertRaisesRegex(PlatformConfigError, "homed_axes must be a sequence"):
            load_platform_config_from_mapping(data)

    def test_rejects_invalid_domain_values_from_models(self):
        data = valid_config()
        io = data["io"]
        assert isinstance(io, dict)
        io["hardware_outputs_armed"] = "no"
        with self.assertRaisesRegex(PlatformConfigError, "hardware_outputs_armed"):
            load_platform_config_from_mapping(data)

        data = valid_config()
        motion = data["motion"]
        assert isinstance(motion, dict)
        motion["homing_enabled"] = "yes"
        with self.assertRaisesRegex(PlatformConfigError, "homing_enabled"):
            load_platform_config_from_mapping(data)

        data = valid_config()
        motion = data["motion"]
        assert isinstance(motion, dict)
        motion["homing_feasibility_status"] = "a4988_sensorless_ready"
        with self.assertRaisesRegex(PlatformConfigError, "homing_feasibility_status"):
            load_platform_config_from_mapping(data)


if __name__ == "__main__":
    unittest.main()
