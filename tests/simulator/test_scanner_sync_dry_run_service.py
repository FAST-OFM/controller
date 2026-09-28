import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.scanner_sync.service import (  # noqa: E402
    DryRunScannerSyncService,
    ScannerSyncServiceError,
)
from scanner_firmware.planning.scan_preflight.axes import REQUIRED_SCAN_AXES  # noqa: E402
from scanner_firmware.planning.scan_preflight.decisions import ScanPreflightInput  # noqa: E402
from scanner_firmware.planning.trigger_scheduler.metadata_queue.queue import (  # noqa: E402
    MetadataQueueOverflow,
)
from scanner_firmware.planning.trigger_scheduler.types import PositionSample  # noqa: E402


class DryRunScannerSyncServiceTests(unittest.TestCase):
    def test_loads_recipe_and_emits_frame_protocol_records(self):
        service = DryRunScannerSyncService(first_frame_id=10)

        loaded = service.load_scan_recipe(_recipe())
        decision = service.run_preflight(
            ScanPreflightInput(
                required_axes=REQUIRED_SCAN_AXES,
                homed_axes=REQUIRED_SCAN_AXES,
                dry_run=True,
                hardware_outputs_enabled=False,
            )
        )
        records = service.start_stripe(
            0,
            [
                PositionSample(x_step_commanded=0, y_step_commanded=5, mcu_time_us=0),
                PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=100),
                PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=200),
            ],
        )

        self.assertEqual(loaded.scan_id, "sync-dry-run")
        self.assertEqual(loaded.stripe_count, 1)
        self.assertTrue(decision.accepted)
        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([record.frame_id for record in records], [10, 11])
        self.assertEqual([record.pattern for record in records], ["BF_WHITE", "AF_RED_GREEN"])
        self.assertTrue(all(record.hardware_outputs_enabled is False for record in records))
        self.assertEqual(service.next_frame_id, 12)

    def test_json_lines_are_protocol_records(self):
        service = DryRunScannerSyncService()
        service.load_scan_recipe(_recipe())
        service.accept_simulator_preflight()

        lines = service.start_stripe_json_lines(
            0,
            [PositionSample(20, 0, mcu_time_us=100), PositionSample(40, 0, mcu_time_us=200)],
        )

        payloads = [json.loads(line) for line in lines]
        self.assertEqual([payload["type"] for payload in payloads], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual(payloads[0]["trigger_output_name"], "camera_or_sync_trigger")
        self.assertFalse(payloads[0]["hardware_outputs_enabled"])

    def test_starts_stripe_from_injected_position_sample_source(self):
        service = DryRunScannerSyncService(first_frame_id=30)
        service.load_scan_recipe(_recipe())
        service.accept_simulator_preflight()

        records = service.start_stripe_from_source(
            0,
            StaticPositionSampleSource(
                samples=(
                    PositionSample(0, 0, mcu_time_us=0),
                    PositionSample(20, 0, mcu_time_us=100),
                    PositionSample(40, 0, mcu_time_us=200),
                )
            ),
        )

        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([record.frame_id for record in records], [30, 31])

    def test_starts_stripe_through_metadata_queue(self):
        service = DryRunScannerSyncService(first_frame_id=50, metadata_queue_depth=4)
        service.load_scan_recipe(_recipe())
        service.accept_simulator_preflight()

        queue = service.start_stripe_metadata_queue(
            0,
            [
                PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=100),
                PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=200),
            ],
        )

        queued = queue.snapshot()
        records = queue.snapshot_protocol_records()
        self.assertEqual(service.metadata_queue_depth, 4)
        self.assertEqual([item.sequence_id for item in queued], [0, 1])
        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([record.frame_id for record in records], [50, 51])
        self.assertEqual([record.event_position for record in records], [20, 40])
        self.assertEqual([record.x_count for record in records], [20, 40])
        self.assertTrue(all(not record.hardware_outputs_enabled for record in records))
        self.assertEqual(service.next_frame_id, 52)

    def test_metadata_queue_depth_bounds_service_output(self):
        service = DryRunScannerSyncService(metadata_queue_depth=1)
        service.load_scan_recipe(_recipe())
        service.accept_simulator_preflight()

        with self.assertRaisesRegex(MetadataQueueOverflow, "metadata queue capacity"):
            service.start_stripe(
                0,
                [
                    PositionSample(x_step_commanded=20, y_step_commanded=5),
                    PositionSample(x_step_commanded=40, y_step_commanded=5),
                ],
            )
        self.assertEqual(service.next_frame_id, 0)

    def test_stop_emits_terminal_protocol_record(self):
        service = DryRunScannerSyncService()
        service.load_scan_recipe(_recipe(event_count=3))
        service.accept_simulator_preflight()

        records = service.start_stripe(
            0,
            [PositionSample(60, 0, mcu_time_us=300)],
            stop_after_events=1,
        )

        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "SCHEDULER_TERMINAL"])
        terminal = records[-1]
        self.assertEqual(terminal.status, "stopped")
        self.assertEqual(terminal.reason_code, "host_stop")
        self.assertEqual(terminal.emitted_frame_count, 1)
        self.assertFalse(terminal.hardware_outputs_enabled)

    def test_requires_loaded_recipe_and_valid_stripe_index(self):
        service = DryRunScannerSyncService()

        with self.assertRaisesRegex(ScannerSyncServiceError, "load_scan_recipe"):
            service.start_stripe(0, [])

        service.load_scan_recipe(_recipe())
        with self.assertRaisesRegex(ScannerSyncServiceError, "stripe_index"):
            service.start_stripe(1, [])

    def test_requires_accepted_preflight_before_starting_stripe(self):
        service = DryRunScannerSyncService()
        service.load_scan_recipe(_recipe())

        with self.assertRaisesRegex(ScannerSyncServiceError, "preflight"):
            service.start_stripe(0, [])

    def test_simulator_preflight_bypasses_homing_only_with_outputs_disabled(self):
        service = DryRunScannerSyncService()
        service.load_scan_recipe(_recipe())

        decision = service.accept_simulator_preflight(homed_axes=("X",))

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.missing_axes, ("Y", "Z"))
        self.assertIn("dry-run scan accepted", decision.warnings[0])

    def test_rejects_recipe_with_hardware_outputs_enabled(self):
        service = DryRunScannerSyncService()
        recipe = _recipe()
        recipe["hardware_outputs_enabled"] = True

        with self.assertRaisesRegex(ValueError, "hardware_outputs_enabled"):
            service.load_scan_recipe(recipe)


def _recipe(event_count=2):
    return {
        "scan_id": "sync-dry-run",
        "stripes": [
            {
                "stripe_id": 1,
                "axis": "X",
                "start": 0,
                "end": 80,
                "first_event": 20,
                "event_pitch": 20,
                "event_count": event_count,
                "pattern_sequence": ["BF_WHITE", "AF_RED_GREEN"],
            }
        ],
    }


@dataclass(frozen=True)
class StaticPositionSampleSource:
    samples: tuple[PositionSample, ...]

    def samples_for_stripe(self, stripe_index):
        if stripe_index != 0:
            return ()
        return self.samples


if __name__ == "__main__":
    unittest.main()
