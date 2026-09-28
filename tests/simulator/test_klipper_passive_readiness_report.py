import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.passive_report import (  # noqa: E402
    PASSIVE_KLIPPER_READINESS_REPORT_SCHEMA_ID,
    build_passive_klipper_readiness_report,
    build_passive_klipper_readiness_report_from_paths,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (  # noqa: E402
    ScannerSyncDecodeContext,
)


DICTIONARY_PATH = REPO_ROOT / "tests/fixtures/klipper_passive_readiness_dictionary_v1.txt"
CONFIG_PATH = REPO_ROOT / "tests/fixtures/klipper_passive_readiness_scanner_sync_config_v1.cfg"
STAGE_B_REVIEW_PATH = REPO_ROOT / "tests/fixtures/klipper_stage_b_review_complete.yaml"
CAPTURE_PATH = REPO_ROOT / "tests/fixtures/scanner_sync_stage_b_metadata_capture_v1.jsonl"
REPORT_FIXTURE_PATH = REPO_ROOT / "tests/fixtures/klipper_passive_readiness_report_v1.json"
SCAN_ID = "stage-b-synthetic-scanner-sync-metadata-capture"
PATTERNS = ("BF_WHITE", "AF_RED_GREEN")


class KlipperPassiveReadinessReportTests(unittest.TestCase):
    def test_composes_passive_readiness_report_from_saved_evidence(self):
        report = _build_report()
        payload = report.to_json_dict()

        self.assertEqual(payload["schema_id"], PASSIVE_KLIPPER_READINESS_REPORT_SCHEMA_ID)
        self.assertTrue(payload["software_only"])
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertFalse(payload["live_hardware_access_used"])
        self.assertFalse(payload["scanner_sync_enabled_by_report"])
        self.assertFalse(payload["ready_for_live_hardware"])
        self.assertTrue(payload["ready_for_passive_metadata"])
        self.assertEqual(payload["blockers"], [])

        self.assertTrue(payload["dictionary"]["config_format_present"])
        self.assertTrue(payload["dictionary"]["has_all_required_commands"])
        self.assertTrue(payload["dictionary"]["has_all_required_responses"])
        self.assertEqual(payload["dictionary"]["missing_command_formats"], [])
        self.assertEqual(payload["dictionary"]["missing_response_formats"], [])

        self.assertTrue(payload["config"]["section_present"])
        self.assertTrue(payload["config"]["enable"])
        self.assertTrue(payload["config"]["metadata_only_mode"])
        self.assertTrue(payload["config"]["safety_fields_present"])
        self.assertFalse(payload["config"]["hardware_outputs_enabled"])
        self.assertEqual(payload["config"]["configured_output_keys"], [])

        self.assertEqual(payload["live_metadata_readiness"]["status"], "ready")
        self.assertEqual(payload["live_metadata_readiness"]["stage"], "ready_to_enable")
        self.assertTrue(payload["live_metadata_readiness"]["can_enable_scanner_sync"])

        self.assertEqual(payload["stage_b_review"]["readiness_state"], "passive_observation_ready")
        self.assertTrue(payload["stage_b_review"]["review_accepted"])
        self.assertFalse(payload["stage_b_review"]["live_testing_approved"])
        self.assertFalse(payload["stage_b_review"]["can_execute_live_stage_b"])
        self.assertFalse(payload["stage_b_review"]["can_enable_scanner_sync"])

        self.assertTrue(payload["event_stream"]["accepted"])
        self.assertEqual(payload["event_stream"]["record_count"], 7)
        self.assertEqual(payload["event_stream"]["frame_count"], 3)
        self.assertEqual(payload["event_stream"]["terminal_count"], 1)
        self.assertEqual(payload["event_stream"]["z_scheduled_count"], 1)
        self.assertEqual(payload["event_stream"]["z_applied_count"], 1)
        self.assertEqual(payload["event_stream"]["z_rejected_count"], 1)

        serialized = json.dumps(payload).lower()
        for forbidden in ("/dev/", "serial_port", "gpiochip", "flash_firmware"):
            self.assertNotIn(forbidden, serialized)

    def test_checked_in_report_fixture_matches_builder(self):
        expected = _build_report().to_json_dict()
        actual = json.loads(REPORT_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(actual, expected)

    def test_missing_response_dispatch_blocks_report(self):
        report = build_passive_klipper_readiness_report(
            dictionary_text=DICTIONARY_PATH.read_text(encoding="utf-8"),
            scanner_sync_config_text=CONFIG_PATH.read_text(encoding="utf-8"),
            stage_b_review_text=STAGE_B_REVIEW_PATH.read_text(encoding="utf-8"),
            capture_jsonl_text=CAPTURE_PATH.read_text(encoding="utf-8"),
            decode_context=_decode_context(),
            response_dispatch_available=False,
        )

        payload = report.to_json_dict()

        self.assertFalse(payload["ready_for_passive_metadata"])
        self.assertIn("live_metadata:scanner_sync_response_dispatch_missing", payload["blockers"])
        self.assertIn("scanner_sync_response_dispatch_missing", payload["blockers"])

    def test_configured_output_blocks_report(self):
        unsafe_config = CONFIG_PATH.read_text(encoding="utf-8").replace(
            "led_white_output: none",
            "led_white_output: PB1",
        )

        report = build_passive_klipper_readiness_report(
            dictionary_text=DICTIONARY_PATH.read_text(encoding="utf-8"),
            scanner_sync_config_text=unsafe_config,
            stage_b_review_text=STAGE_B_REVIEW_PATH.read_text(encoding="utf-8"),
            capture_jsonl_text=CAPTURE_PATH.read_text(encoding="utf-8"),
            decode_context=_decode_context(),
            response_dispatch_available=True,
        )

        payload = report.to_json_dict()

        self.assertFalse(payload["ready_for_passive_metadata"])
        self.assertIn("live_metadata:scanner_sync_output_pins_configured", payload["blockers"])
        self.assertEqual(payload["config"]["configured_output_keys"], ["led_white_output"])

    def test_report_writer_persists_stable_json(self):
        report = _build_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "passive-readiness.json"

            report.write_json(output_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), report.to_json_dict())


def _build_report():
    return build_passive_klipper_readiness_report_from_paths(
        dictionary_path=DICTIONARY_PATH,
        scanner_sync_config_path=CONFIG_PATH,
        stage_b_review_path=STAGE_B_REVIEW_PATH,
        capture_jsonl_path=CAPTURE_PATH,
        decode_context=_decode_context(),
        response_dispatch_available=True,
    )


def _decode_context() -> ScannerSyncDecodeContext:
    return ScannerSyncDecodeContext(scan_id=SCAN_ID, pattern_names=PATTERNS)


if __name__ == "__main__":
    unittest.main()
