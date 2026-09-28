import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.platform_config.model import (  # noqa: E402
    IoConfig,
    MotionConfig,
    PlatformProfile,
    ScanRecipeConfig,
    ScannerPlatformConfig,
)
from scanner_firmware.planning.scan_preflight.evaluator import evaluate_scan_preflight  # noqa: E402
from scanner_firmware.planning.scan_preflight.platform_config_adapter import scan_preflight_input_from_platform_config  # noqa: E402


class PlatformConfigModelTests(unittest.TestCase):
    def test_maps_domain_config_into_scan_preflight(self):
        config = ScannerPlatformConfig(
            profile=PlatformProfile(
                board_id="kingroon_mono_v2",
                controller_kind="klipper_mks",
                printer_config_present=True,
                safe_defaults_declared=True,
            ),
            motion=MotionConfig(
                homed_axes=("X", "Y", "Z"),
                soft_limits_configured=True,
                scan_roi_within_limits=True,
                coordinate_source_valid=True,
                homing_feasibility_status="implemented",
                homing_enabled=True,
            ),
            io=IoConfig(
                camera_trigger_config_valid=True,
                led_pattern_valid=True,
                inactive_output_states_declared=True,
                output_ownership_unambiguous=True,
                hardware_outputs_armed=False,
            ),
            scan_recipe=ScanRecipeConfig(
                dry_run=True,
                requested_scan_mode="stop_and_capture",
                z_policy_valid=True,
            ),
        )

        preflight = scan_preflight_input_from_platform_config(config)
        decision = evaluate_scan_preflight(preflight)

        self.assertTrue(decision.accepted)
        self.assertFalse(preflight.hardware_outputs_enabled)
        self.assertEqual(config.to_scan_preflight_input(), preflight)

    def test_invalid_io_blocks_preflight_coordinate_source_gate(self):
        config = ScannerPlatformConfig(
            profile=PlatformProfile(
                board_id="kingroon_mono_v2",
                controller_kind="klipper_mks",
                printer_config_present=True,
                safe_defaults_declared=True,
            ),
            motion=MotionConfig(
                homed_axes=("X", "Y", "Z"),
                soft_limits_configured=True,
                scan_roi_within_limits=True,
                coordinate_source_valid=True,
                homing_feasibility_status="implemented",
                homing_enabled=True,
            ),
            io=IoConfig(
                camera_trigger_config_valid=True,
                led_pattern_valid=True,
                inactive_output_states_declared=False,
                output_ownership_unambiguous=True,
                hardware_outputs_armed=False,
            ),
            scan_recipe=ScanRecipeConfig(
                dry_run=True,
                requested_scan_mode="stop_and_capture",
                z_policy_valid=True,
            ),
        )

        decision = evaluate_scan_preflight(scan_preflight_input_from_platform_config(config))

        self.assertFalse(decision.accepted)
        self.assertIn("coordinate source must be valid", decision.errors[0])

    def test_current_mks_config_can_disable_homing_for_dry_run_only(self):
        config = ScannerPlatformConfig(
            profile=PlatformProfile(
                board_id="kingroon_mono_v2",
                controller_kind="klipper_mks",
                printer_config_present=True,
                safe_defaults_declared=True,
            ),
            motion=MotionConfig(
                homed_axes=(),
                soft_limits_configured=True,
                scan_roi_within_limits=True,
                coordinate_source_valid=True,
                homing_feasibility_status="not_implemented",
                homing_enabled=False,
            ),
            io=IoConfig(
                camera_trigger_config_valid=True,
                led_pattern_valid=True,
                inactive_output_states_declared=True,
                output_ownership_unambiguous=True,
                hardware_outputs_armed=False,
            ),
            scan_recipe=ScanRecipeConfig(
                dry_run=True,
                requested_scan_mode="stop_and_capture",
                z_policy_valid=True,
            ),
        )

        preflight = scan_preflight_input_from_platform_config(config)
        decision = evaluate_scan_preflight(preflight)

        self.assertFalse(preflight.homing_enabled)
        self.assertEqual(preflight.homing_feasibility_status, "not_implemented")
        self.assertTrue(decision.accepted)
        self.assertIn(
            "dry-run scan accepted with homing is disabled by configuration",
            decision.warnings,
        )
        self.assertIn(
            "dry-run scan accepted with homing implementation is not implemented",
            decision.warnings,
        )

    def test_current_mks_homing_disabled_config_blocks_hardware_outputs(self):
        config = ScannerPlatformConfig(
            profile=PlatformProfile(
                board_id="kingroon_mono_v2",
                controller_kind="klipper_mks",
                printer_config_present=True,
                safe_defaults_declared=True,
            ),
            motion=MotionConfig(
                homed_axes=(),
                soft_limits_configured=True,
                scan_roi_within_limits=True,
                coordinate_source_valid=True,
                homing_feasibility_status="not_implemented",
                homing_enabled=False,
            ),
            io=IoConfig(
                camera_trigger_config_valid=True,
                led_pattern_valid=True,
                inactive_output_states_declared=True,
                output_ownership_unambiguous=True,
                hardware_outputs_armed=True,
            ),
            scan_recipe=ScanRecipeConfig(
                dry_run=False,
                requested_scan_mode="stop_and_capture",
                z_policy_valid=True,
            ),
        )

        decision = evaluate_scan_preflight(scan_preflight_input_from_platform_config(config))

        self.assertFalse(decision.accepted)
        self.assertIn("homing is disabled by configuration", decision.errors)
        self.assertIn("homing implementation is not implemented", decision.errors)
        self.assertIn(
            "hardware outputs cannot be enabled until all required axes are homed",
            decision.errors,
        )


if __name__ == "__main__":
    unittest.main()
