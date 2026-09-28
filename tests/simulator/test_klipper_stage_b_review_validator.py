from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.stage_b_review import (  # noqa: E402
    summarize_stage_b_review_yaml,
    validate_stage_b_review_package,
    validate_stage_b_review_yaml,
)


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "klipper_stage_b_review_complete.yaml"
INCOMPLETE_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "klipper_stage_b_review_incomplete.yaml"
)
UNSAFE_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "klipper_stage_b_review_unsafe.yaml"
APPROVAL_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "klipper_stage_b_review_approval_claiming.yaml"
)


class KlipperStageBReviewValidatorTests(unittest.TestCase):
    def test_accepts_complete_metadata_only_review_yaml(self):
        result = validate_stage_b_review_yaml(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertTrue(result.accepted)
        self.assertEqual(result.blockers, ())

    def test_rejects_incomplete_review_package(self):
        payload = _fixture_payload()
        del payload["stage_b_review"]["firmware_flash"]["rollback_method"]

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("firmware_flash.rollback_method_missing", result.blockers)

    def test_rejects_unknown_values_in_required_live_plan_fields(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["firmware_build"]["output_artifact"] = "UNKNOWN"

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("firmware_build.output_artifact_unknown", result.blockers)

    def test_rejects_unsafe_output_pin_values(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["printer_cfg"]["camera_trigger_pin"] = "PC4"

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("printer_cfg.camera_trigger_pin_must_be_unset", result.blockers)

    def test_rejects_output_pins_configured_claim(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["printer_cfg"]["output_pins_configured"] = True

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("printer_cfg.output_pins_configured_must_be_false", result.blockers)

    def test_rejects_hardware_outputs_enabled_or_non_metadata_mode(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["printer_cfg"]["mode"] = "hardware"
        payload["stage_b_review"]["printer_cfg"]["hardware_outputs_enabled"] = True

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("printer_cfg.mode_must_be_metadata_only", result.blockers)
        self.assertIn("printer_cfg.hardware_outputs_enabled_must_be_false", result.blockers)

    def test_rejects_approval_claims(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["approved_for_live_execution"] = True

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn(
            "stage_b_review.approved_for_live_execution_must_not_claim_approval",
            result.blockers,
        )

    def test_rejects_top_level_approval_claims(self):
        payload = _fixture_payload()
        payload["live_execution_approved"] = True

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("live_execution_approved_must_not_claim_approval", result.blockers)

    def test_rejects_missing_required_scanner_sync_formats(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["expected_scanner_sync_formats"]["responses"].pop()

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("expected_scanner_sync_formats.responses_incomplete", result.blockers)

    def test_rejects_inconsistent_expected_capture_summary(self):
        payload = _fixture_payload()
        payload["stage_b_review"]["expected_capture"]["expected_last_frame_id"] = 1369

        result = validate_stage_b_review_package(payload)

        self.assertFalse(result.accepted)
        self.assertIn("expected_capture.frame_id_range_must_match_frame_count", result.blockers)

    def test_complete_review_adapts_to_passive_observation_summary(self):
        summary = summarize_stage_b_review_yaml(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(summary.readiness_state, "passive_observation_ready")
        self.assertTrue(summary.review_accepted)
        self.assertEqual(summary.blockers, ())
        self.assertTrue(summary.static_simulator_only)
        self.assertFalse(summary.live_testing_approved)
        self.assertFalse(summary.can_execute_live_stage_b)
        self.assertFalse(summary.can_enable_scanner_sync)
        self.assertIsNotNone(summary.observation)
        observation = summary.observation
        assert observation is not None
        self.assertEqual(observation.review_issue_or_pr, _fixture_payload()["stage_b_review"]["review_issue_or_pr"])
        self.assertTrue(observation.scanner_sync_enable)
        self.assertTrue(observation.metadata_only_mode)
        self.assertFalse(observation.hardware_outputs_enabled)
        self.assertFalse(observation.output_pins_configured)
        self.assertEqual(observation.expected_record_count, 7)
        self.assertEqual(observation.expected_frame_count, 5)
        self.assertEqual(observation.expected_terminal_count, 1)
        self.assertEqual(observation.expected_first_frame_id, 1360)
        self.assertEqual(observation.expected_last_frame_id, 1364)
        self.assertEqual(observation.expected_stripes_seen, (6,))

    def test_blocked_review_fixtures_do_not_produce_observation_summaries(self):
        fixture_expectations = (
            (
                INCOMPLETE_FIXTURE_PATH,
                "firmware_flash.rollback_method_missing",
            ),
            (
                UNSAFE_FIXTURE_PATH,
                "printer_cfg.hardware_outputs_enabled_must_be_false",
            ),
            (
                APPROVAL_FIXTURE_PATH,
                "stage_b_review.approved_for_live_execution_must_not_claim_approval",
            ),
        )

        for fixture_path, expected_blocker in fixture_expectations:
            with self.subTest(fixture=fixture_path.name):
                summary = summarize_stage_b_review_yaml(fixture_path.read_text(encoding="utf-8"))

                self.assertEqual(summary.readiness_state, "blocked")
                self.assertFalse(summary.review_accepted)
                self.assertIsNone(summary.observation)
                self.assertIn(expected_blocker, summary.blockers)
                self.assertTrue(summary.static_simulator_only)
                self.assertFalse(summary.live_testing_approved)
                self.assertFalse(summary.can_execute_live_stage_b)
                self.assertFalse(summary.can_enable_scanner_sync)


def _fixture_payload() -> dict:
    return copy.deepcopy(yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
