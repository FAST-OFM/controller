import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.harness.dry_run import DryRunKlipperScannerSyncHarness  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.event_streaming.parsing import (  # noqa: E402
    decode_scanner_sync_json_lines,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (  # noqa: E402
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext  # noqa: E402
from scanner_firmware.foundation.protocol.events import ScheduleZCommand  # noqa: E402
from scanner_firmware.planning.trigger_scheduler.types import PositionSample  # noqa: E402


class KlipperScannerSyncDryRunHarnessTests(unittest.TestCase):
    def test_registers_fake_klipper_and_runs_dry_run_stripe(self):
        harness = DryRunKlipperScannerSyncHarness(first_frame_id=20)

        loaded = harness.load_scan_recipe(_recipe())
        harness.accept_simulator_preflight()
        records = harness.start_stripe(
            0,
            [
                PositionSample(x_step_commanded=0, y_step_commanded=5, mcu_time_us=0),
                PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=100),
                PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=200),
            ],
        )

        self.assertEqual(loaded.scan_id, "klipper-harness-dry-run")
        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([record.frame_id for record in records], [20, 21])
        self.assertTrue(all(record.hardware_outputs_enabled is False for record in records))

        status = harness.status
        self.assertEqual(status.mcu_phase, "configured")
        self.assertEqual(status.registration_oid, 1)
        self.assertEqual(status.registered_command_count, 6)
        self.assertEqual(status.registered_response_count, 5)
        self.assertEqual(status.next_frame_id, 22)

    def test_encodes_schedule_z_against_registered_oid_without_sending(self):
        harness = DryRunKlipperScannerSyncHarness()
        harness.load_scan_recipe(_recipe())

        encoded = harness.encode_schedule_z(
            ScheduleZCommand(
                seq=7,
                scan_id="klipper-harness-dry-run",
                stripe_id=1,
                apply_at_position_count=80,
                z_target_um=12.25,
            )
        )

        self.assertEqual(encoded.name, "scanner_sync_schedule_z")
        self.assertEqual(encoded.args, (1, 7, 1, 1, 80, 12250))

    def test_decodes_synthetic_frame_event_with_recipe_pattern_names(self):
        harness = DryRunKlipperScannerSyncHarness(first_frame_id=20)
        harness.load_scan_recipe(_recipe())
        harness.accept_simulator_preflight()

        record = harness.decode_response(
            "FRAME_EVENT",
            {
                "frame_id": 30,
                "stripe_id": 1,
                "stripe_frame_index": 1,
                "pattern_id": 1,
                "position_axis": 0,
                "event_position": 40,
                "x_count": 40,
                "y_count": 5,
                "z_count": 0,
                "mcu_time_us": 200,
                "status": 0,
                "flags": 0,
            },
        )

        self.assertEqual(record.type, "FRAME_EVENT")
        self.assertEqual(record.scan_id, "klipper-harness-dry-run")
        self.assertEqual(record.pattern, "AF_RED_GREEN")
        self.assertFalse(record.hardware_outputs_enabled)

    def test_decode_requires_loaded_recipe(self):
        harness = DryRunKlipperScannerSyncHarness()

        with self.assertRaisesRegex(ValueError, "load_scan_recipe"):
            harness.decode_response("Z_SCHEDULED", {"seq": 1})

    def test_replays_synthetic_callback_capture_through_decoder_and_validator(self):
        harness = DryRunKlipperScannerSyncHarness(first_frame_id=20)
        harness.load_scan_recipe(_replay_recipe())
        harness.accept_simulator_preflight()
        protocol_records = harness.start_stripe(
            0,
            [
                PositionSample(x_step_commanded=0, y_step_commanded=5, mcu_time_us=0),
                PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=100),
                PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=200),
            ],
            stop_after_events=2,
        )

        raw_json_lines = harness.to_synthetic_callback_json_lines(protocol_records)
        decoded_records = decode_scanner_sync_json_lines(
            raw_json_lines,
            context=ScannerSyncDecodeContext(
                scan_id="klipper-harness-replay",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
            ),
        )
        validation = validate_scanner_sync_event_sequence(decoded_records)

        self.assertEqual([record.type for record in decoded_records], [
            "FRAME_EVENT",
            "FRAME_EVENT",
            "SCHEDULER_TERMINAL",
        ])
        self.assertEqual(validation.frame_count, 2)
        self.assertEqual(validation.terminal_count, 1)
        self.assertEqual(validation.first_frame_id, 20)
        self.assertEqual(validation.last_frame_id, 21)
        self.assertTrue(all(record.hardware_outputs_enabled is False for record in decoded_records))


def _recipe():
    return {
        "scan_id": "klipper-harness-dry-run",
        "stripes": [
            {
                "stripe_id": 1,
                "axis": "X",
                "start": 0,
                "end": 80,
                "first_event": 20,
                "event_pitch": 20,
                "event_count": 2,
                "pattern_sequence": ["BF_WHITE", "AF_RED_GREEN"],
            }
        ],
    }


def _replay_recipe():
    return {
        "scan_id": "klipper-harness-replay",
        "stripes": [
            {
                "stripe_id": 0,
                "axis": "X",
                "start": 0,
                "end": 80,
                "first_event": 20,
                "event_pitch": 20,
                "event_count": 3,
                "pattern_sequence": ["BF_WHITE", "AF_RED_GREEN"],
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
