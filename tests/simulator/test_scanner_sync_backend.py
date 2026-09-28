import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.scan_preflight.axes import REQUIRED_SCAN_AXES  # noqa: E402
from scanner_firmware.adapters.scanner_sync.backend import DryRunScannerSyncBackend  # noqa: E402
from scanner_firmware.planning.scanner_sync.interfaces import (  # noqa: E402
    ScanExecutionBackend,
    ScanPreflightInput,
)
from scanner_firmware.planning.trigger_scheduler.types import PositionSample  # noqa: E402


class ScannerSyncBackendTests(unittest.TestCase):
    def test_dry_run_backend_satisfies_scan_execution_backend_flow(self):
        backend: ScanExecutionBackend = DryRunScannerSyncBackend.create(first_frame_id=100)

        loaded = backend.load_scan_recipe(_recipe())
        decision = backend.run_preflight(
            ScanPreflightInput(
                required_axes=REQUIRED_SCAN_AXES,
                homed_axes=(),
                dry_run=True,
                hardware_outputs_enabled=False,
            )
        )
        records = backend.start_stripe_from_source(
            0,
            StaticPositionSampleSource(
                samples=(
                    PositionSample(0, 0, mcu_time_us=0),
                    PositionSample(20, 0, mcu_time_us=100),
                    PositionSample(40, 0, mcu_time_us=200),
                )
            ),
        )

        self.assertEqual(loaded.scan_id, "backend-dry-run")
        self.assertTrue(decision.accepted)
        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([record.frame_id for record in records], [100, 101])
        self.assertTrue(all(record.hardware_outputs_enabled is False for record in records))

    def test_dry_run_backend_produces_validated_synthetic_capture(self):
        backend = DryRunScannerSyncBackend.create(first_frame_id=200)
        backend.load_scan_recipe(_recipe(event_count=3))
        backend.run_preflight(
            ScanPreflightInput(
                required_axes=REQUIRED_SCAN_AXES,
                homed_axes=(),
                dry_run=True,
                hardware_outputs_enabled=False,
            )
        )

        capture = backend.start_validated_capture_from_source(
            0,
            StaticPositionSampleSource(
                samples=(
                    PositionSample(0, 0, mcu_time_us=0),
                    PositionSample(20, 0, mcu_time_us=100),
                    PositionSample(40, 0, mcu_time_us=200),
                    PositionSample(60, 0, mcu_time_us=300),
                )
            ),
            stop_after_events=2,
        )

        self.assertEqual([record.type for record in capture.records], [
            "FRAME_EVENT",
            "FRAME_EVENT",
            "SCHEDULER_TERMINAL",
        ])
        self.assertEqual([record.type for record in capture.decoded_records], [
            "FRAME_EVENT",
            "FRAME_EVENT",
            "SCHEDULER_TERMINAL",
        ])
        self.assertEqual(capture.validation.frame_count, 2)
        self.assertEqual(capture.validation.terminal_count, 1)
        self.assertEqual(capture.validation.last_frame_id, 201)
        self.assertTrue(all("event_type" in line for line in capture.callback_json_lines))


def _recipe(event_count=2):
    return {
        "scan_id": "backend-dry-run",
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
