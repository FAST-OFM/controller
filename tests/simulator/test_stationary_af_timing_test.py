import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.foundation.protocol.events import RunStationaryAfTestCommand  # noqa: E402
from scanner_firmware.planning.led_scheduler.stationary_af_test import (  # noqa: E402
    build_stationary_af_test_frame_events,
)


class StationaryAfTimingTestTests(unittest.TestCase):
    def test_builds_no_motion_frame_events_with_atomic_led_timing(self):
        records = build_stationary_af_test_frame_events(
            RunStationaryAfTestCommand(
                seq=30,
                scan_id="bench-af",
                stripe_id=2,
                first_frame_id=100,
                frame_count=3,
                frame_period_us=25_000,
                event_position_count=123,
                settle_us=1_000,
                xvs_trigger_pulse_us=200,
                exposure_hold_us=4_000,
            ),
            first_mcu_time_us=50_000,
            trigger_output_name="hq_xvs_sync",
        )

        self.assertEqual([record.frame_id for record in records], [100, 101, 102])
        self.assertEqual([record.mcu_time_us for record in records], [50_000, 75_000, 100_000])
        self.assertEqual({record.event_position for record in records}, {123})
        self.assertEqual({record.x_count for record in records}, {123})
        self.assertEqual({record.y_count for record in records}, {0})
        self.assertEqual({record.z_count for record in records}, {0})
        self.assertTrue(all(record.hardware_outputs_enabled is False for record in records))
        self.assertEqual({record.trigger_output_name for record in records}, {"hq_xvs_sync"})

        first_timing = records[0].led_timing
        assert first_timing is not None
        self.assertEqual(first_timing["pattern"], "AF_RED_GREEN")
        self.assertEqual(first_timing["frame_start_us"], 50_000)
        self.assertEqual(first_timing["trigger_start_us"], 50_000)
        self.assertEqual(first_timing["trigger_end_us"], 50_200)
        self.assertEqual(first_timing["exposure_end_us"], 54_000)
        self.assertEqual(
            [(item["gate_name"], item["start_us"], item["end_us"]) for item in first_timing["gate_windows"]],
            [("led_red", 49_000, 54_000), ("led_green", 49_000, 54_000)],
        )
        self.assertEqual(
            [(item["gate_name"], item["time_us"], item["state"]) for item in first_timing["baseline_transitions"]],
            [("led_white", 49_000, "inactive"), ("led_white", 54_000, "active")],
        )

    def test_supports_stationary_y_axis_traceability_without_motion(self):
        (record,) = build_stationary_af_test_frame_events(
            RunStationaryAfTestCommand(
                seq=30,
                scan_id="bench-af",
                stripe_id=2,
                first_frame_id=100,
                frame_count=1,
                frame_period_us=25_000,
                position_axis="Y",
                event_position_count=123,
                settle_us=1_000,
                xvs_trigger_pulse_us=200,
                exposure_hold_us=4_000,
            )
        )

        self.assertEqual(record.position_axis, "Y")
        self.assertEqual(record.x_count, 0)
        self.assertEqual(record.y_count, 123)


if __name__ == "__main__":
    unittest.main()
