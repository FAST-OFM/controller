import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.dry_run_pipeline.scanner_sync_session import (  # noqa: E402
    ScannerSyncSessionError,
    StripeRunControl,
    run_scanner_sync_dry_run_session,
)
from scanner_firmware.planning.trigger_scheduler.types import PositionSample  # noqa: E402


class ScannerSyncDryRunSessionTests(unittest.TestCase):
    def test_runs_clean_multistripe_session_without_terminal_record(self):
        result = run_scanner_sync_dry_run_session(
            _recipe(),
            _SampleSource(),
            first_frame_id=100,
        )

        self.assertEqual(result.scan_id, "multi-stripe-dry-run")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.stripe_count, 2)
        self.assertEqual(result.started_stripe_count, 2)
        self.assertEqual(result.frame_event_count, 4)
        self.assertEqual(result.terminal_record_count, 0)
        self.assertEqual(result.next_frame_id, 104)
        self.assertEqual(
            [(stripe.stripe_id, stripe.status, stripe.frame_event_count) for stripe in result.stripes],
            [(11, "completed", 2), (12, "completed", 2)],
        )
        self.assertEqual(
            [record.frame_id for record in result.records if record.type == "FRAME_EVENT"],
            [100, 101, 102, 103],
        )
        self.assertEqual(
            [record.stripe_frame_index for record in result.records],
            [0, 1, 0, 1],
        )
        self.assertTrue(all(not record.hardware_outputs_enabled for record in result.records))

        payloads = [json.loads(line) for line in result.json_lines]
        self.assertEqual([payload["type"] for payload in payloads], ["FRAME_EVENT"] * 4)
        summary = result.to_summary_json_dict()
        self.assertEqual(summary["status"], "completed")
        self.assertFalse(summary["hardware_outputs_enabled"])

    def test_clean_multistripe_session_matches_checked_in_fixtures(self):
        result = run_scanner_sync_dry_run_session(
            _recipe(),
            _SampleSource(),
            first_frame_id=100,
        )

        _assert_matches_session_fixtures(
            self,
            result,
            "scanner_sync_multistripe_session_v1.jsonl",
            "scanner_sync_multistripe_session_summary_v1.json",
        )

    def test_session_recipe_led_timing_reaches_frame_event_jsonl(self):
        result = run_scanner_sync_dry_run_session(
            _led_timing_recipe(),
            _SampleSource(),
            first_frame_id=100,
        )

        payloads = [json.loads(line) for line in result.json_lines]

        self.assertEqual([payload["pattern"] for payload in payloads], ["BF_WHITE", "DARK"])
        self.assertIn("led_timing", payloads[0])
        self.assertIn("led_timing", payloads[1])
        self.assertEqual(payloads[0]["led_timing"]["logical_channel_names"], ["led_white"])
        self.assertEqual(payloads[0]["led_timing"]["gate_windows"][0]["gate_name"], "led_white")
        self.assertEqual(payloads[0]["led_timing"]["frame_start_us"], payloads[0]["mcu_time_us"])
        self.assertEqual(payloads[1]["led_gate_names"], [])
        self.assertEqual(payloads[1]["led_timing"]["logical_channel_names"], [])
        self.assertEqual(payloads[1]["led_timing"]["brightness_setpoints"], [])
        self.assertEqual(payloads[1]["led_timing"]["gate_windows"], [])
        self.assertFalse(payloads[0]["led_timing"]["hardware_outputs_enabled"])
        self.assertFalse(payloads[1]["led_timing"]["hardware_outputs_enabled"])

    def test_stop_terminal_stops_session_before_later_stripes(self):
        result = run_scanner_sync_dry_run_session(
            _recipe(),
            _SampleSource(),
            first_frame_id=100,
            controls={0: StripeRunControl(stop_after_events=1)},
        )

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.started_stripe_count, 1)
        self.assertEqual([record.type for record in result.records], ["FRAME_EVENT", "SCHEDULER_TERMINAL"])
        self.assertEqual(result.records[-1].reason_code, "host_stop")
        self.assertEqual(result.records[-1].emitted_frame_count, 1)
        self.assertEqual(result.stripes[0].terminal_reason_code, "host_stop")
        self.assertEqual(result.next_frame_id, 101)
        _assert_matches_session_fixtures(
            self,
            result,
            "scanner_sync_multistripe_session_stopped_v1.jsonl",
            "scanner_sync_multistripe_session_stopped_summary_v1.json",
        )

    def test_fault_terminal_stops_session_with_summary_reason(self):
        result = run_scanner_sync_dry_run_session(
            _recipe(),
            _SampleSource(),
            first_frame_id=100,
            controls={
                1: StripeRunControl(
                    fault_after_events=1,
                    fault_message="simulated fault after second stripe first frame",
                )
            },
        )

        self.assertEqual(result.status, "fault")
        self.assertEqual(result.started_stripe_count, 2)
        self.assertEqual(result.frame_event_count, 3)
        self.assertEqual(result.terminal_record_count, 1)
        self.assertEqual(result.records[-1].type, "SCHEDULER_TERMINAL")
        self.assertEqual(result.records[-1].reason_code, "scheduler_fault")
        self.assertEqual(
            result.stripes[-1].terminal_message,
            "simulated fault after second stripe first frame",
        )
        self.assertEqual(result.next_frame_id, 103)
        _assert_matches_session_fixtures(
            self,
            result,
            "scanner_sync_multistripe_session_fault_v1.jsonl",
            "scanner_sync_multistripe_session_fault_summary_v1.json",
        )

    def test_rejects_control_for_missing_stripe(self):
        with self.assertRaisesRegex(ScannerSyncSessionError, "outside loaded plan"):
            run_scanner_sync_dry_run_session(
                _recipe(),
                _SampleSource(),
                controls={2: StripeRunControl(stop_after_events=0)},
            )


def _recipe():
    return {
        "scan_id": "multi-stripe-dry-run",
        "stripes": [
            {
                "stripe_id": 11,
                "axis": "X",
                "start": 0,
                "end": 80,
                "first_event": 20,
                "event_pitch": 20,
                "event_count": 2,
                "pattern_sequence": ["BF_WHITE", "AF_RED_GREEN"],
            },
            {
                "stripe_id": 12,
                "axis": "Y",
                "start": 0,
                "end": 80,
                "first_event": 20,
                "event_pitch": 20,
                "event_count": 2,
                "pattern_sequence": ["BF_WHITE", "AF_RED_GREEN"],
            },
        ],
    }


def _led_timing_recipe():
    return {
        "scan_id": "led-timing-dry-run",
        "pattern_led_timing": {
            "BF_WHITE": {
                "exposure_start_offset_us": 100,
                "exposure_us": 500,
                "gate_pulse_us": 200,
                "settle_us": 20,
                "brightness_by_gate": {"led_white": 0.7},
            },
            "DARK": {
                "exposure_start_offset_us": 100,
                "exposure_us": 500,
                "gate_pulse_us": 0,
            },
        },
        "stripes": [
            {
                "stripe_id": 11,
                "axis": "X",
                "start": 0,
                "end": 80,
                "first_event": 20,
                "event_pitch": 20,
                "event_count": 2,
                "pattern_sequence": ["BF_WHITE", "DARK"],
            },
        ],
    }


@dataclass(frozen=True)
class _SampleSource:
    def samples_for_stripe(self, stripe_index):
        if stripe_index == 0:
            return (
                PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=100),
                PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=200),
            )
        if stripe_index == 1:
            return (
                PositionSample(x_step_commanded=7, y_step_commanded=20, mcu_time_us=300),
                PositionSample(x_step_commanded=7, y_step_commanded=40, mcu_time_us=400),
            )
        return ()


def _assert_matches_session_fixtures(
    test_case,
    result,
    jsonl_fixture_name,
    summary_fixture_name,
):
    expected_jsonl = (
        REPO_ROOT / "tests" / "fixtures" / jsonl_fixture_name
    ).read_text(encoding="utf-8").splitlines()
    expected_summary = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / summary_fixture_name).read_text(
            encoding="utf-8"
        )
    )

    test_case.assertEqual(list(result.json_lines), expected_jsonl)
    test_case.assertEqual(result.to_summary_json_dict(), expected_summary)


if __name__ == "__main__":
    unittest.main()
