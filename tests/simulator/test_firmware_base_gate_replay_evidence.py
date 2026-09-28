from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.firmware_base.gate_replay_evidence import (  # noqa: E402
    ADVANCED_SPIKE_GATES,
    FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_SCHEMA_ID,
    FirmwareBaseGateReplayEvidenceError,
    build_firmware_base_gate_replay_evidence_from_paths,
)


REPLAY_FIXTURE_SOURCES = (
    "tests/fixtures/frame_event_replay_protocol_v1.jsonl",
    "tests/fixtures/frame_event_replay_protocol_v1_clean_completion.jsonl",
    "tests/fixtures/frame_event_replay_protocol_v1_fault_terminal.jsonl",
)
REPORT_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "firmware_base_gate_replay_evidence_v1.json"
)


class FirmwareBaseGateReplayEvidenceTests(unittest.TestCase):
    def test_builds_software_only_gate_replay_evidence(self):
        report = _build_report()
        payload = report.to_json_dict()

        self.assertEqual(payload["schema_id"], FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_SCHEMA_ID)
        self.assertTrue(payload["software_only"])
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertFalse(payload["live_hardware_access_used"])
        self.assertFalse(payload["live_readiness_claimed"])
        self.assertFalse(payload["final_firmware_base_selected"])
        self.assertEqual(payload["candidate_coverage"], "common_protocol_fixture_only")
        self.assertEqual(tuple(payload["advanced_spike_gates"]), ADVANCED_SPIKE_GATES)
        self.assertTrue(payload["safe_stop_fault_terminal_check_passed"])
        self.assertTrue(payload["scheduled_z_ack_path_check_passed"])
        self.assertTrue(payload["z_rejection_path_observed"])
        self.assertTrue(payload["software_replay_evidence_passed"])
        self.assertIn(
            "safe_stop_or_fault_terminal_behavior_per_candidate",
            payload["remaining_spike_gates_before_close"],
        )
        self.assertIn(
            "scheduled_z_bidirectional_ack_path",
            payload["remaining_spike_gates_before_close"],
        )

    def test_fixture_summaries_cover_stop_clean_fault_and_z_ack_paths(self):
        payload = _build_report().to_json_dict()
        fixtures_by_name = {
            Path(fixture["fixture"]).name: fixture for fixture in payload["fixtures"]
        }

        stopped = fixtures_by_name["frame_event_replay_protocol_v1.jsonl"]
        clean = fixtures_by_name["frame_event_replay_protocol_v1_clean_completion.jsonl"]
        fault = fixtures_by_name["frame_event_replay_protocol_v1_fault_terminal.jsonl"]

        self.assertEqual(stopped["terminal_statuses"], ["stopped"])
        self.assertEqual(stopped["terminal_reason_codes"], ["host_stop"])
        self.assertEqual(stopped["z_scheduled_count"], 1)
        self.assertEqual(stopped["z_applied_count"], 1)
        self.assertEqual(stopped["z_rejected_count"], 1)
        self.assertEqual(clean["terminal_count"], 0)
        self.assertEqual(clean["z_outcomes"][0]["apply_target_kind"], "position")
        self.assertEqual(fault["terminal_statuses"], ["fault"])
        self.assertEqual(fault["terminal_reason_codes"], ["coordinate_source_error"])
        self.assertTrue(all(not fixture["hardware_outputs_enabled"] for fixture in payload["fixtures"]))

    def test_checked_in_report_fixture_matches_builder(self):
        expected = _build_report().to_json_dict()
        actual = json.loads(REPORT_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(actual, expected)

    def test_rejects_hardware_enabled_fixture(self):
        source = (REPO_ROOT / REPLAY_FIXTURE_SOURCES[0]).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path = Path(tmpdir) / "hardware-enabled.jsonl"
            fixture_path.write_text(
                source.replace(
                    '"hardware_outputs_enabled":false',
                    '"hardware_outputs_enabled":true',
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                FirmwareBaseGateReplayEvidenceError,
                "hardware_outputs_enabled",
            ):
                build_firmware_base_gate_replay_evidence_from_paths((fixture_path,))

    def test_report_writer_persists_stable_json(self):
        report = _build_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "firmware-base-gate-replay-evidence.json"

            report.write_json(output_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), report.to_json_dict())


def _build_report():
    return build_firmware_base_gate_replay_evidence_from_paths(REPLAY_FIXTURE_SOURCES)


if __name__ == "__main__":
    unittest.main()
