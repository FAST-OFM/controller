from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.firmware_base.comparison_report import (  # noqa: E402
    EXPECTED_CANDIDATES,
    FIRMWARE_BASE_PHASE0_COMPARISON_SCHEMA_ID,
    FirmwareBaseComparisonError,
    build_firmware_base_phase0_comparison_report,
    build_firmware_base_phase0_comparison_report_from_path,
)


PHASE0_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "firmware_base_phase0_expected.json"
PHASE0_FIXTURE_SOURCE = "tests/fixtures/firmware_base_phase0_expected.json"
REPORT_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "firmware_base_phase0_comparison_report_v1.json"
)


class FirmwareBaseComparisonReportTests(unittest.TestCase):
    def test_builds_software_only_phase0_comparison_report(self):
        report = _build_report()
        payload = report.to_json_dict()

        self.assertEqual(payload["schema_id"], FIRMWARE_BASE_PHASE0_COMPARISON_SCHEMA_ID)
        self.assertTrue(payload["software_only"])
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertFalse(payload["live_hardware_access_used"])
        self.assertFalse(payload["final_firmware_base_selected"])
        self.assertEqual(payload["recommendation_state"], "not_ready_for_final_selection")
        self.assertTrue(payload["phase0_metadata_gate_passed"])
        self.assertEqual(set(payload["candidate_names"]), set(EXPECTED_CANDIDATES))

        for candidate in payload["candidates"]:
            self.assertGreater(candidate["event_count"], 0)
            self.assertTrue(candidate["frame_ids_contiguous"])
            self.assertTrue(candidate["stripe_frame_indices_contiguous"])
            self.assertEqual(candidate["coordinate_sources"], ["step_indexed"])
            self.assertEqual(candidate["trigger_output_names"], ["camera_or_sync_trigger"])
            self.assertEqual(candidate["max_position_overshoot_count"], 0)
            self.assertEqual(candidate["dry_run_adapter_signal"], "common_scheduler_fixture_passed")
            self.assertFalse(candidate["hardware_outputs_enabled"])
            self.assertFalse(candidate["live_hardware_access_used"])
            self.assertTrue(candidate["passed_phase0_metadata_gate"])

        self.assertIn("position_indexed_output_jitter_measurement", payload["remaining_spike_gates"])
        self.assertIn("fork_or_plugin_maintenance_cost", payload["remaining_spike_gates"])

    def test_checked_in_report_fixture_matches_builder(self):
        expected = _build_report().to_json_dict()
        actual = json.loads(REPORT_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(actual, expected)

    def test_path_builder_reads_phase0_fixture(self):
        report = build_firmware_base_phase0_comparison_report_from_path(PHASE0_FIXTURE_PATH)

        self.assertEqual(set(report.candidate_names), set(EXPECTED_CANDIDATES))
        self.assertTrue(report.phase0_metadata_gate_passed)

    def test_rejects_hardware_enabled_phase0_payload(self):
        payload = _phase0_payload()
        payload["hardware_outputs_enabled"] = True

        with self.assertRaisesRegex(FirmwareBaseComparisonError, "hardware_outputs_enabled"):
            build_firmware_base_phase0_comparison_report(
                payload,
                source_fixture=str(PHASE0_FIXTURE_PATH),
            )

    def test_rejects_missing_candidate_coverage(self):
        payload = _phase0_payload()
        del payload["candidates"]["grblhal"]

        with self.assertRaisesRegex(FirmwareBaseComparisonError, "candidates must cover exactly"):
            build_firmware_base_phase0_comparison_report(
                payload,
                source_fixture=str(PHASE0_FIXTURE_PATH),
            )

    def test_report_writer_persists_stable_json(self):
        report = _build_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "firmware-base-phase0-comparison.json"

            report.write_json(output_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), report.to_json_dict())


def _phase0_payload() -> dict:
    return json.loads(PHASE0_FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_report():
    return build_firmware_base_phase0_comparison_report(
        _phase0_payload(),
        source_fixture=PHASE0_FIXTURE_SOURCE,
    )


if __name__ == "__main__":
    unittest.main()
