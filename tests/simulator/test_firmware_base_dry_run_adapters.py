import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.firmware_base.dry_run_adapters import (  # noqa: E402
    DryRunAdapterError,
    GrblHalPlannerSnapshot,
    KlipperCommandedPositionSample,
    StepDirPulse,
    grblhal_planner_snapshots_to_samples,
    klipper_commanded_positions_to_samples,
    step_dir_pulses_to_samples,
)
from scanner_firmware.planning.trigger_scheduler.scheduler import (  # noqa: E402
    DryRunPositionEventScheduler,
)
from scanner_firmware.planning.trigger_scheduler.types import (  # noqa: E402
    StripeSchedule,
)


class FirmwareBaseDryRunAdapterTests(unittest.TestCase):
    def test_klipper_like_samples_feed_common_scheduler(self):
        samples = klipper_commanded_positions_to_samples(
            [
                KlipperCommandedPositionSample(0, 0, event_time_s=0.0),
                KlipperCommandedPositionSample(20, 0, event_time_s=0.001),
                KlipperCommandedPositionSample(40, 0, event_time_s=0.002),
            ]
        )
        schedule = StripeSchedule(
            scan_id="dry-klipper",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=40,
            first_event_position=20,
            event_pitch=20,
            event_count=2,
            pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
        )

        events = DryRunPositionEventScheduler().run(schedule, samples)

        self.assertEqual([event.x_step_commanded for event in events], [20, 40])
        self.assertEqual([event.mcu_time_us for event in events], [1000, 2000])
        self.assertTrue(all(not event.hardware_outputs_enabled for event in events))

    def test_grblhal_like_samples_feed_common_scheduler(self):
        samples = grblhal_planner_snapshots_to_samples(
            [
                GrblHalPlannerSnapshot(0, 5, tick_us=0),
                GrblHalPlannerSnapshot(25, 5, tick_us=25),
                GrblHalPlannerSnapshot(50, 5, tick_us=50),
            ]
        )
        schedule = StripeSchedule(
            scan_id="dry-grblhal",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=50,
            first_event_position=25,
            event_pitch=25,
            event_count=2,
            pattern_sequence=("BF_WHITE",),
        )

        events = DryRunPositionEventScheduler().run(schedule, samples)

        self.assertEqual([event.x_step_commanded for event in events], [25, 50])
        self.assertEqual([event.y_step_commanded for event in events], [5, 5])

    def test_step_dir_pulses_feed_common_scheduler(self):
        samples = step_dir_pulses_to_samples(
            [
                StepDirPulse(axis="X", direction=1, timestamp_us=10, pulse_count=10),
                StepDirPulse(axis="X", direction=1, timestamp_us=20, pulse_count=10),
                StepDirPulse(axis="X", direction=1, timestamp_us=30, pulse_count=10),
            ]
        )
        schedule = StripeSchedule(
            scan_id="dry-sync-board",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=30,
            first_event_position=10,
            event_pitch=10,
            event_count=3,
            pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
        )

        events = DryRunPositionEventScheduler().run(schedule, samples)

        self.assertEqual([event.x_step_commanded for event in events], [10, 20, 30])
        self.assertEqual(
            [event.pattern for event in events],
            ["BF_WHITE", "AF_RED_GREEN", "BF_WHITE"],
        )

    def test_step_dir_adapter_handles_reverse_direction(self):
        samples = step_dir_pulses_to_samples(
            [
                StepDirPulse(axis="X", direction=-1, timestamp_us=10, pulse_count=10),
                StepDirPulse(axis="X", direction=-1, timestamp_us=20, pulse_count=10),
            ],
            x_start_count=100,
        )

        self.assertEqual([sample.x_step_commanded for sample in samples], [90, 80])

    def test_klipper_seconds_to_microseconds_uses_explicit_tie_rounding(self):
        samples = klipper_commanded_positions_to_samples(
            [
                KlipperCommandedPositionSample(0, 0, event_time_s=0.0000005),
                KlipperCommandedPositionSample(0, 0, event_time_s=0.0000015),
            ]
        )

        self.assertEqual([sample.mcu_time_us for sample in samples], [1, 2])

    def test_rejects_invalid_candidate_streams(self):
        with self.assertRaises(DryRunAdapterError):
            klipper_commanded_positions_to_samples(
                [KlipperCommandedPositionSample(0, 0, event_time_s=-0.001)]
            )
        with self.assertRaises(DryRunAdapterError):
            step_dir_pulses_to_samples(
                [StepDirPulse(axis="X", direction=1, timestamp_us=0, pulse_count=0)]
            )


if __name__ == "__main__":
    unittest.main()
