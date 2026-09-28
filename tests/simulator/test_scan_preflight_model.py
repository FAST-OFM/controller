import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.scan_preflight.axes import REQUIRED_SCAN_AXES  # noqa: E402
from scanner_firmware.planning.scan_preflight.decisions import (  # noqa: E402
    ScanPreflightError,
    ScanPreflightInput,
)
from scanner_firmware.planning.scan_preflight.evaluator import evaluate_scan_preflight  # noqa: E402
from scanner_firmware.planning.scan_preflight.platform_config_adapter import (  # noqa: E402
    scan_preflight_input_from_platform_config,
)

from scanner_firmware.domain.platform_config.model import (  # noqa: E402
    IoConfig,
    MotionConfig,
    PlatformProfile,
    ScanRecipeConfig,
    ScannerPlatformConfig,
)


def preflight(**overrides):
    values = dict(
        required_axes=REQUIRED_SCAN_AXES,
        homed_axes=REQUIRED_SCAN_AXES,
        dry_run=False,
        hardware_outputs_enabled=True,
    )
    values.update(overrides)
    return ScanPreflightInput(**values)


class ScanPreflightModelTests(unittest.TestCase):
    def test_accepts_when_all_required_axes_are_homed(self):
        decision = evaluate_scan_preflight(preflight())

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(decision.warnings, ())
        self.assertEqual(decision.errors, ())

    def test_accepts_dry_run_missing_homing_when_hardware_outputs_disabled(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=("X",),
                dry_run=True,
                hardware_outputs_enabled=False,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.missing_axes, ("Y", "Z"))
        self.assertIn("dry-run scan accepted", decision.warnings[0])
        self.assertIn("hardware outputs are disabled", decision.warnings[1])
        self.assertEqual(decision.errors, ())

    def test_rejects_non_dry_run_when_homing_is_missing(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=("X", "Y"),
                dry_run=False,
                hardware_outputs_enabled=False,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ("Z",))
        self.assertIn("non-dry-run", decision.errors[1])

    def test_rejects_non_dry_run_when_homing_feasibility_is_unknown(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=REQUIRED_SCAN_AXES,
                dry_run=False,
                hardware_outputs_enabled=False,
                homing_feasibility_status="unknown",
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(
            decision.errors,
            (
                "homing feasibility is unknown",
                "non-dry-run scan workflows require all axes to be homed",
            ),
        )

    def test_rejects_non_dry_run_when_homing_is_not_implemented(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=REQUIRED_SCAN_AXES,
                dry_run=False,
                hardware_outputs_enabled=False,
                homing_feasibility_status="not_implemented",
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(
            decision.errors,
            (
                "homing implementation is not implemented",
                "non-dry-run scan workflows require all axes to be homed",
            ),
        )

    def test_accepts_dry_run_with_unknown_homing_only_when_outputs_disabled(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=(),
                dry_run=True,
                hardware_outputs_enabled=False,
                homing_feasibility_status="unknown",
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.missing_axes, REQUIRED_SCAN_AXES)
        self.assertEqual(
            decision.warnings,
            (
                "dry-run scan accepted with missing homing for axes: X, Y, Z",
                "dry-run scan accepted with homing feasibility is unknown",
                "hardware outputs are disabled; simulator-only homing bypass is active",
            ),
        )

    def test_homing_disabled_by_config_blocks_real_scan_and_warns_in_dry_run(self):
        real_decision = evaluate_scan_preflight(
            preflight(
                homed_axes=(),
                dry_run=False,
                hardware_outputs_enabled=False,
                homing_enabled=False,
            )
        )

        self.assertFalse(real_decision.accepted)
        self.assertEqual(real_decision.missing_axes, REQUIRED_SCAN_AXES)
        self.assertEqual(
            real_decision.errors,
            (
                "homing is disabled by configuration",
                "homing is missing for required axes: X, Y, Z",
                "non-dry-run scan workflows require all axes to be homed",
            ),
        )

        dry_run_decision = evaluate_scan_preflight(
            preflight(
                homed_axes=(),
                dry_run=True,
                hardware_outputs_enabled=False,
                homing_enabled=False,
            )
        )

        self.assertTrue(dry_run_decision.accepted)
        self.assertEqual(
            dry_run_decision.warnings,
            (
                "dry-run scan accepted with homing is disabled by configuration",
                "dry-run scan accepted with missing homing for axes: X, Y, Z",
                "hardware outputs are disabled; simulator-only homing bypass is active",
            ),
        )

    def test_rejects_hardware_outputs_enabled_when_homing_is_missing(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=("X", "Z"),
                dry_run=True,
                hardware_outputs_enabled=True,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ("Y",))
        self.assertIn("hardware outputs cannot be enabled", decision.errors[1])
        self.assertEqual(decision.warnings, ())

    def test_rejects_hardware_outputs_enabled_when_homing_feasibility_unknown(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=REQUIRED_SCAN_AXES,
                dry_run=True,
                hardware_outputs_enabled=True,
                homing_feasibility_status="unknown",
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(
            decision.errors,
            (
                "homing feasibility is unknown",
                "hardware outputs cannot be enabled until all required axes are homed",
            ),
        )

    def test_rejects_missing_soft_limits_even_in_dry_run(self):
        decision = evaluate_scan_preflight(
            preflight(
                homed_axes=("X",),
                dry_run=True,
                hardware_outputs_enabled=False,
                soft_limits_configured=False,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ("Y", "Z"))
        self.assertEqual(
            decision.errors,
            ("soft limits must be configured before scan start",),
        )
        self.assertEqual(decision.warnings, ())

    def test_rejects_invalid_recipe_or_signal_preconditions(self):
        decision = evaluate_scan_preflight(
            preflight(
                scan_roi_within_limits=False,
                led_pattern_valid=False,
                camera_trigger_config_valid=False,
                coordinate_source_valid=False,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(
            decision.errors,
            (
                "scan ROI must be within configured soft limits",
                "LED pattern must be valid before scan start",
                "camera trigger config must be valid before scan start",
                "coordinate source must be valid before scan start",
            ),
        )

    def test_rejects_missing_z_policy_as_explicit_blocker(self):
        decision = evaluate_scan_preflight(
            preflight(
                dry_run=True,
                hardware_outputs_enabled=False,
                z_policy_configured=False,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(
            decision.errors,
            ("Z policy must be configured before scan start",),
        )

    def test_rejects_required_axes_that_do_not_include_x_y_z(self):
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(
                preflight(required_axes=("X", "Y"), homed_axes=("X", "Y"))
            )

    def test_rejects_malformed_preflight_values(self):
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(preflight(homed_axes=("X", "Q")))
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(preflight(dry_run="true"))
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(preflight(soft_limits_configured="true"))
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(preflight(homing_enabled="true"))
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(preflight(z_policy_configured="true"))
        with self.assertRaises(ScanPreflightError):
            evaluate_scan_preflight(preflight(homing_feasibility_status="accepted"))

    def test_builds_preflight_input_from_platform_config(self):
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
                homing_feasibility_status="not_implemented",
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

        preflight_input = scan_preflight_input_from_platform_config(config)

        self.assertEqual(preflight_input.required_axes, REQUIRED_SCAN_AXES)
        self.assertEqual(preflight_input.homed_axes, REQUIRED_SCAN_AXES)
        self.assertEqual(preflight_input.homing_feasibility_status, "not_implemented")
        self.assertTrue(evaluate_scan_preflight(preflight_input).accepted)

    def test_platform_config_adapter_preserves_z_policy_blocker(self):
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
                homing_feasibility_status="not_implemented",
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
                z_policy_valid=False,
            ),
        )

        preflight_input = scan_preflight_input_from_platform_config(config)
        decision = evaluate_scan_preflight(preflight_input)

        self.assertTrue(preflight_input.coordinate_source_valid)
        self.assertFalse(preflight_input.z_policy_configured)
        self.assertFalse(decision.accepted)
        self.assertEqual(
            decision.errors,
            ("Z policy must be configured before scan start",),
        )


if __name__ == "__main__":
    unittest.main()
