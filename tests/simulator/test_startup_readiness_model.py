import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.readiness.evaluator import evaluate_startup_readiness  # noqa: E402
from scanner_firmware.planning.readiness.types import StartupSelfCheckInput  # noqa: E402


def selfcheck(**overrides) -> StartupSelfCheckInput:
    values = dict(
        config_schema_valid=True,
        platform_profile_valid=True,
        printer_config_present=True,
        safe_defaults_declared=True,
        inactive_outputs_declared=True,
        output_ownership_unambiguous=True,
        camera_mode_valid=True,
        camera_crop_valid=True,
        scan_preflight_accepted=True,
        scanner_sync_metadata_ready=True,
        homing_complete=True,
        hardware_outputs_armed=False,
    )
    values.update(overrides)
    return StartupSelfCheckInput(**values)


class StartupReadinessModelTests(unittest.TestCase):
    def test_blocks_until_required_config_domains_are_valid(self):
        decision = evaluate_startup_readiness(
            selfcheck(config_schema_valid=False, safe_defaults_declared=False)
        )

        self.assertEqual(decision.stage, "CONFIG_REQUIRED")
        self.assertEqual(decision.status, "blocked")
        self.assertEqual(
            decision.blockers,
            ("config_schema_valid", "safe_defaults_declared"),
        )

    def test_stays_safe_disabled_until_homing_and_metadata_are_ready(self):
        decision = evaluate_startup_readiness(
            selfcheck(homing_complete=False, scanner_sync_metadata_ready=False)
        )

        self.assertEqual(decision.stage, "IDLE_SAFE_DISABLED")
        self.assertEqual(decision.status, "safe_disabled")
        self.assertEqual(
            decision.warnings,
            ("homing_incomplete", "scanner_sync_metadata_not_ready"),
        )
        self.assertEqual(
            decision.reason_codes,
            (
                "board_homing_incomplete",
                "scanner_sync_metadata_not_ready",
                "live_test_approval_not_granted",
            ),
        )

    def test_stays_safe_disabled_when_homing_feasibility_is_unknown(self):
        decision = evaluate_startup_readiness(
            selfcheck(
                homing_complete=True,
                homing_feasibility_status="unknown",
            )
        )

        self.assertEqual(decision.stage, "IDLE_SAFE_DISABLED")
        self.assertEqual(decision.status, "safe_disabled")
        self.assertEqual(decision.warnings, ("homing_feasibility_unknown",))
        self.assertEqual(
            decision.reason_codes,
            (
                "board_homing_feasibility_unknown",
                "live_test_approval_not_granted",
            ),
        )
        self.assertFalse(decision.can_prepare_scan)

    def test_ready_without_hardware_arm_is_not_scan_prepare(self):
        decision = evaluate_startup_readiness(selfcheck())

        self.assertEqual(decision.stage, "READY")
        self.assertEqual(decision.status, "safe_disabled")
        self.assertEqual(decision.reason_codes, ("live_test_approval_not_granted",))
        self.assertFalse(decision.can_prepare_scan)

    def test_hardware_outputs_arm_blocks_software_only_readiness(self):
        decision = evaluate_startup_readiness(selfcheck(hardware_outputs_armed=True))

        self.assertEqual(decision.stage, "IDLE_SAFE_DISABLED")
        self.assertEqual(decision.status, "blocked")
        self.assertEqual(decision.blockers, ("hardware_outputs_armed",))
        self.assertEqual(
            decision.reason_codes,
            (
                "live_hardware_outputs_armed",
                "live_test_approval_not_granted",
            ),
        )
        self.assertFalse(decision.can_prepare_scan)

    def test_rejects_non_bool_hardware_arm_state(self):
        with self.assertRaisesRegex(ValueError, "hardware_outputs_armed"):
            selfcheck(hardware_outputs_armed="false")

    def test_rejects_unknown_homing_feasibility_status_value(self):
        with self.assertRaisesRegex(ValueError, "homing_feasibility_status"):
            selfcheck(homing_feasibility_status="accepted")


if __name__ == "__main__":
    unittest.main()
