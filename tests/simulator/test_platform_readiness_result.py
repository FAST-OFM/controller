from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.readiness.result import (  # noqa: E402
    LiveTestApproval,
    PlatformReadinessCheck,
    PlatformReadinessResult,
    emit_firmware_platform_readiness_result,
)
from scanner_firmware.planning.readiness.types import StartupSelfCheckInput  # noqa: E402


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "firmware_platform_readiness_result_v1.json"
FIXTURE_GENERATED_AT = "2026-07-02T00:00:00Z"
FIXTURE_TARGET = "scanner-firmware-simulator-static-readiness"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_id",
    "schema_version",
    "generated_at",
    "owner_repo",
    "target",
    "readiness_state",
    "hardware_outputs_enabled",
    "live_test_approval",
    "reasons",
    "checks",
    "unknowns",
    "blockers",
}
ALLOWED_STATES = {
    "config_invalid",
    "interface_unbound",
    "safe_disabled",
    "ready_for_dry_run",
    "ready_for_live_test",
    "faulted",
}
ALLOWED_CHECK_STATUSES = {"pass", "fail", "blocked", "skipped"}
ALLOWED_CHECK_SCOPES = {
    "config",
    "interface_binding",
    "protocol",
    "calibration",
    "homing",
    "controller_discovery",
    "live_test_gate",
}
ALLOWED_BLOCKER_SEVERITIES = {"p0", "p1", "p2"}
ALLOWED_REASON_DOMAINS = {"board", "scanner_sync", "live_test_gate"}
ALLOWED_REASON_CATEGORIES = {"blocker", "unknown", "safety_gate"}


class PlatformReadinessResultTests(unittest.TestCase):
    def test_fixture_matches_emitted_result_and_preserves_homing_sync_blockers(self):
        payload = _load_fixture()
        emitted = emit_firmware_platform_readiness_result(
            _fixture_selfcheck(),
            generated_at=FIXTURE_GENERATED_AT,
            target=FIXTURE_TARGET,
        ).to_json_dict()

        self.assertEqual(payload, emitted)
        self.assertEqual(payload["readiness_state"], "safe_disabled")
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertEqual(
            payload["live_test_approval"],
            {"required": False, "approved": False, "issue_or_pr": None},
        )
        self.assertEqual(
            {unknown["field"] for unknown in payload["unknowns"]},
            {
                "homing.completion",
                "homing.feasibility_status",
                "scanner_sync.live_metadata_binding",
            },
        )
        self.assertEqual(
            {blocker["id"] for blocker in payload["blockers"]},
            {
                "scanner_sync_metadata_not_ready",
                "homing_incomplete",
                "homing_feasibility_unknown",
            },
        )
        self.assertEqual(
            [reason["code"] for reason in payload["reasons"]],
            [
                "board_homing_incomplete",
                "board_homing_feasibility_unknown",
                "scanner_sync_metadata_not_ready",
                "live_test_approval_not_granted",
            ],
        )
        self.assertEqual(
            {
                reason["code"]: reason["category"]
                for reason in payload["reasons"]
                if reason["domain"] in {"board", "scanner_sync"}
            },
            {
                "board_homing_incomplete": "unknown",
                "board_homing_feasibility_unknown": "unknown",
                "scanner_sync_metadata_not_ready": "unknown",
            },
        )

    def test_fixture_shape_matches_platform_readiness_schema_v1_constraints(self):
        payload = _load_fixture()

        self.assertEqual(set(payload), REQUIRED_TOP_LEVEL_KEYS)
        self.assertEqual(payload["schema_id"], "platform_readiness_result_v1")
        self.assertEqual(payload["schema_version"], "1.1.0")
        self.assertEqual(payload["owner_repo"], "scanner-firmware")
        self.assertIn(payload["readiness_state"], ALLOWED_STATES)
        self.assertIs(payload["hardware_outputs_enabled"], False)
        self.assertIs(payload["live_test_approval"]["approved"], False)
        self.assertGreaterEqual(len(payload["checks"]), 1)
        self.assertNotEqual(payload["readiness_state"], "ready_for_live_test")

        for check in payload["checks"]:
            self.assertEqual(
                set(check) - {"id", "status", "scope", "evidence", "message"},
                set(),
            )
            self.assertIsInstance(check["id"], str)
            self.assertTrue(check["id"])
            self.assertIn(check["status"], ALLOWED_CHECK_STATUSES)
            self.assertIn(check["scope"], ALLOWED_CHECK_SCOPES)
            if check["status"] == "skipped":
                self.assertIn("evidence", check)
            else:
                self.assertIsInstance(check["evidence"], str)
                self.assertTrue(check["evidence"])

        for unknown in payload["unknowns"]:
            self.assertEqual(set(unknown), {"field", "reason"})
            self.assertTrue(unknown["field"])
            self.assertTrue(unknown["reason"])

        for reason in payload["reasons"]:
            self.assertEqual(
                set(reason),
                {"code", "domain", "category", "severity", "evidence", "message"},
            )
            self.assertTrue(reason["code"])
            self.assertIn(reason["domain"], ALLOWED_REASON_DOMAINS)
            self.assertIn(reason["category"], ALLOWED_REASON_CATEGORIES)
            self.assertIn(reason["severity"], ALLOWED_BLOCKER_SEVERITIES)
            self.assertTrue(reason["evidence"])
            self.assertTrue(reason["message"])

        for blocker in payload["blockers"]:
            self.assertEqual(set(blocker), {"id", "severity", "message"})
            self.assertTrue(blocker["id"])
            self.assertIn(blocker["severity"], ALLOWED_BLOCKER_SEVERITIES)
            self.assertTrue(blocker["message"])

    def test_complete_software_only_checks_emit_ready_for_dry_run_not_live_ready(self):
        payload = emit_firmware_platform_readiness_result(
            _ready_for_dry_run_selfcheck(),
            generated_at="2026-07-02T00:00:00Z",
            target="scanner-firmware-simulator-dry-run",
        ).to_json_dict()

        self.assertEqual(payload["readiness_state"], "ready_for_dry_run")
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertEqual(payload["unknowns"], [])
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(
            [reason["code"] for reason in payload["reasons"]],
            ["live_test_approval_not_granted"],
        )
        self.assertFalse(payload["live_test_approval"]["approved"])

    def test_hardware_outputs_armed_faults_without_claiming_enabled_outputs(self):
        payload = emit_firmware_platform_readiness_result(
            _ready_for_dry_run_selfcheck(hardware_outputs_armed=True),
            generated_at="2026-07-02T00:00:00Z",
            target="scanner-firmware-simulator-dry-run",
        ).to_json_dict()

        self.assertEqual(payload["readiness_state"], "faulted")
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertIn(
            {"id": "hardware_outputs_armed", "severity": "p0"},
            [
                {"id": blocker["id"], "severity": blocker["severity"]}
                for blocker in payload["blockers"]
            ],
        )
        self.assertEqual(_check_status(payload, "hardware_outputs_disabled"), "blocked")
        self.assertIn(
            "live_hardware_outputs_armed",
            {reason["code"] for reason in payload["reasons"]},
        )

    def test_result_rejects_live_test_promotion_or_static_approval(self):
        check = PlatformReadinessCheck(
            id="software_only_gate",
            status="pass",
            scope="live_test_gate",
            evidence="unit-test",
        )

        with self.assertRaisesRegex(ValueError, "ready_for_live_test"):
            PlatformReadinessResult(
                generated_at="2026-07-02T00:00:00Z",
                target="scanner-firmware-live",
                readiness_state="ready_for_live_test",
                checks=(check,),
                unknowns=(),
                blockers=(),
            )

        with self.assertRaisesRegex(ValueError, "cannot approve live tests"):
            LiveTestApproval(required=True, approved=True)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_selfcheck() -> StartupSelfCheckInput:
    return _ready_for_dry_run_selfcheck(
        homing_complete=False,
        homing_feasibility_status="unknown",
        scanner_sync_metadata_ready=False,
    )


def _ready_for_dry_run_selfcheck(**overrides) -> StartupSelfCheckInput:
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
        homing_feasibility_status="implemented",
    )
    values.update(overrides)
    return StartupSelfCheckInput(**values)


def _check_status(payload: dict, check_id: str) -> str:
    for check in payload["checks"]:
        if check["id"] == check_id:
            return check["status"]
    raise AssertionError(f"missing check {check_id}")


if __name__ == "__main__":
    unittest.main()
