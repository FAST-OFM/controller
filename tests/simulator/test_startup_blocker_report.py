from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.readiness.result import LiveTestApproval  # noqa: E402
from scanner_firmware.planning.readiness.startup_blockers import (  # noqa: E402
    FirmwareStartupBlockerReport,
    StartupBlockerCheck,
    build_issue_093_startup_blocker_report,
    validate_startup_blocker_report,
)


FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "firmware_startup_blocker_report_issue_093_v1.json"
)
FIXTURE_GENERATED_AT = "2026-07-02T00:00:00Z"
FIXTURE_TARGET = "scanner-firmware-issue-093-startup-blockers"
REQUIRED_DOMAINS = {"controller", "trigger", "led"}


class StartupBlockerReportTests(unittest.TestCase):
    def test_issue_093_fixture_matches_builder_and_preserves_blockers(self):
        payload = _load_fixture()
        emitted = build_issue_093_startup_blocker_report(
            generated_at=FIXTURE_GENERATED_AT,
            target=FIXTURE_TARGET,
        ).to_json_dict()

        self.assertEqual(payload, emitted)
        self.assertEqual(payload["issue_id"], "093")
        self.assertEqual(payload["readiness_state"], "blocked")
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertEqual(
            payload["live_test_approval"],
            {"required": True, "approved": False, "issue_or_pr": None},
        )
        self.assertEqual(
            {unknown["domain"] for unknown in payload["unknowns"]},
            REQUIRED_DOMAINS,
        )
        self.assertEqual(
            {blocker["domain"] for blocker in payload["blockers"]},
            REQUIRED_DOMAINS,
        )

    def test_static_validator_accepts_saved_report_shape_without_live_approval(self):
        validation = validate_startup_blocker_report(_load_fixture())

        self.assertTrue(validation.accepted)
        self.assertEqual(validation.blockers, ())

    def test_static_validator_rejects_missing_controller_trigger_or_led_unknowns(self):
        payload = _load_fixture()
        payload["unknowns"] = [
            unknown for unknown in payload["unknowns"] if unknown["domain"] != "trigger"
        ]

        validation = validate_startup_blocker_report(payload)

        self.assertFalse(validation.accepted)
        self.assertIn("trigger_unknown_missing", validation.blockers)

    def test_static_validator_rejects_live_outputs_or_approval_claims(self):
        payload = _load_fixture()
        payload["hardware_outputs_enabled"] = True
        payload["live_test_approval"]["approved"] = True

        validation = validate_startup_blocker_report(payload)

        self.assertFalse(validation.accepted)
        self.assertIn("hardware_outputs_enabled_must_be_false", validation.blockers)
        self.assertIn("live_test_approval_must_not_be_approved", validation.blockers)

    def test_report_model_rejects_live_test_promotion_semantics(self):
        check = StartupBlockerCheck(
            id="software_only_gate",
            domain="live_output_gate",
            status="pass",
            evidence="unit-test",
            message="software-only",
        )

        with self.assertRaisesRegex(ValueError, "cannot approve live tests"):
            LiveTestApproval(required=True, approved=True)

        with self.assertRaisesRegex(ValueError, "hardware_outputs_enabled"):
            FirmwareStartupBlockerReport(
                generated_at=FIXTURE_GENERATED_AT,
                target=FIXTURE_TARGET,
                issue_id="093",
                readiness_state="safe_disabled",
                checks=(check,),
                unknowns=(),
                blockers=(),
                hardware_outputs_enabled=True,
            )


def _load_fixture() -> dict:
    return copy.deepcopy(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
