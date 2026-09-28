import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.trigger_scheduler.scheduler import (  # noqa: E402
    DryRunPositionEventScheduler,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError  # noqa: E402
from scanner_firmware.planning.led_scheduler.timing import (  # noqa: E402
    validate_frame_event_led_timing_contract,
)
from scanner_firmware.planning.led_scheduler.types import (  # noqa: E402
    LedPatternTimingProfile,
    LedPatternTimingSet,
)
from scanner_firmware.planning.trigger_scheduler.metadata_queue.queue import (  # noqa: E402
    MetadataQueueOverflow,
    queue_scheduler_metadata_events,
)
from scanner_firmware.planning.trigger_scheduler.types import (  # noqa: E402
    PositionSample,
    ScheduleError,
    StripeSchedule,
)


class DryRunSchedulerTests(unittest.TestCase):
    def test_positive_x_stripe_emits_expected_events(self):
        schedule = StripeSchedule(
            scan_id="scan-a",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=3,
            pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
        )
        samples = [
            PositionSample(x_step_commanded=0, y_step_commanded=5, mcu_time_us=0),
            PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=10),
            PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=20),
            PositionSample(x_step_commanded=60, y_step_commanded=5, mcu_time_us=30),
        ]

        events = DryRunPositionEventScheduler(first_frame_id=100).run(
            schedule, samples
        )

        self.assertEqual([event.frame_id for event in events], [100, 101, 102])
        self.assertEqual([event.stripe_frame_index for event in events], [0, 1, 2])
        self.assertEqual(
            [event.pattern for event in events],
            ["BF_WHITE", "AF_RED_GREEN", "BF_WHITE"],
        )
        self.assertEqual(
            [event.led_gate_names for event in events],
            [("led_white",), ("led_red", "led_green"), ("led_white",)],
        )
        self.assertTrue(
            all(event.trigger_output_name == "camera_or_sync_trigger" for event in events)
        )
        self.assertEqual(
            [event.x_step_commanded for event in events],
            [20, 40, 60],
        )
        self.assertEqual([event.position_axis for event in events], ["X", "X", "X"])
        self.assertEqual([event.event_position for event in events], [20, 40, 60])
        self.assertEqual([event.sample_position for event in events], [20, 40, 60])
        self.assertEqual([event.position_overshoot_count for event in events], [0, 0, 0])
        self.assertEqual([event.x_count for event in events], [20, 40, 60])
        self.assertEqual([event.y_count for event in events], [5, 5, 5])
        self.assertEqual([event.coordinate_flags for event in events], [(), (), ()])
        self.assertTrue(schedule.dry_run)
        self.assertFalse(schedule.hardware_outputs_enabled)
        self.assertTrue(all(not event.hardware_outputs_enabled for event in events))

    def test_led_timing_metadata_is_attached_to_dry_run_frame_events(self):
        schedule = StripeSchedule(
            scan_id="scan-led-timing",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=3,
            pattern_sequence=("BF_WHITE", "AF_RED_GREEN", "DARK"),
            pattern_led_timing=LedPatternTimingSet(
                profiles=(
                    LedPatternTimingProfile(
                        pattern="BF_WHITE",
                        exposure_start_offset_us=100,
                        exposure_us=1000,
                        gate_pulse_us=200,
                        settle_us=50,
                        frame_period_us=2500,
                        trigger_pulse_us=80,
                        brightness_by_gate={"led_white": 0.6},
                    ),
                    LedPatternTimingProfile(
                        pattern="AF_RED_GREEN",
                        exposure_start_offset_us=200,
                        exposure_us=600,
                        gate_pulse_us=0,
                        frame_period_us=2000,
                        trigger_pulse_us=200,
                        gate_pre_trigger_us=150,
                        gate_post_exposure_us=75,
                        baseline_gate_names=("led_white",),
                        baseline_suppress_pre_gate_us=25,
                        baseline_restore_post_gate_us=50,
                        brightness_by_gate={"led_red": 0.4, "led_green": 0.5},
                    ),
                    LedPatternTimingProfile(
                        pattern="DARK",
                        exposure_start_offset_us=25,
                        exposure_us=500,
                        gate_pulse_us=0,
                        frame_period_us=1500,
                    ),
                )
            ),
        )
        samples = [
            PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=1000),
            PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=2000),
            PositionSample(x_step_commanded=60, y_step_commanded=5, mcu_time_us=3000),
        ]

        events = DryRunPositionEventScheduler(first_frame_id=100).run(
            schedule,
            samples,
        )

        white = events[0]
        red_green = events[1]
        dark = events[2]
        self.assertIsNotNone(white.led_timing)
        self.assertIsNotNone(red_green.led_timing)
        self.assertIsNotNone(dark.led_timing)
        white_contract = validate_frame_event_led_timing_contract(
            white.to_protocol_record()
        )
        red_green_contract = validate_frame_event_led_timing_contract(
            red_green.to_protocol_record()
        )
        dark_contract = validate_frame_event_led_timing_contract(
            dark.to_protocol_record()
        )

        self.assertEqual(white_contract.logical_channel_names, ("led_white",))
        self.assertEqual(
            [window.gate_name for window in white_contract.gate_windows],
            ["led_white"],
        )
        self.assertEqual(white_contract.frame_start_us, 1000)
        self.assertEqual(white_contract.exposure_start_us, 1100)
        self.assertEqual(white_contract.exposure_end_us, 2100)
        self.assertEqual(white_contract.frame_period_us, 2500)
        self.assertEqual(white_contract.trigger_start_us, 1000)
        self.assertEqual(white_contract.trigger_end_us, 1080)
        self.assertFalse(white_contract.hardware_outputs_enabled)
        self.assertEqual(
            [
                (window.gate_name, window.start_us, window.end_us)
                for window in red_green_contract.gate_windows
            ],
            [("led_red", 1850, 2875), ("led_green", 1850, 2875)],
        )
        self.assertEqual(
            [
                (setpoint.gate_name, setpoint.brightness)
                for setpoint in red_green_contract.brightness_setpoints
            ],
            [("led_red", 0.4), ("led_green", 0.5)],
        )
        self.assertEqual(red_green_contract.frame_period_us, 2000)
        self.assertEqual(red_green_contract.trigger_start_us, 2000)
        self.assertEqual(red_green_contract.trigger_end_us, 2200)
        self.assertEqual(red_green_contract.exposure_start_us, 2200)
        self.assertEqual(red_green_contract.exposure_end_us, 2800)
        self.assertEqual(red_green_contract.baseline_gate_names, ("led_white",))
        self.assertEqual(dark.led_gate_names, ())
        self.assertEqual(dark_contract.logical_channel_names, ())
        self.assertEqual(dark_contract.gate_windows, ())
        self.assertEqual(dark_contract.brightness_setpoints, ())
        self.assertEqual(dark_contract.frame_period_us, 1500)
        self.assertEqual(dark_contract.exposure_start_us, 3025)
        self.assertEqual(dark_contract.exposure_end_us, 3525)

    def test_af_led_timing_metadata_carries_white_preview_baseline_override(self):
        schedule = StripeSchedule(
            scan_id="scan-af-window",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("AF_RED_GREEN",),
            pattern_led_timing=LedPatternTimingSet(
                profiles=(
                    LedPatternTimingProfile(
                        pattern="AF_RED_GREEN",
                        exposure_start_offset_us=200,
                        exposure_us=600,
                        gate_pulse_us=0,
                        frame_period_us=2000,
                        trigger_pulse_us=200,
                        gate_pre_trigger_us=150,
                        gate_post_exposure_us=75,
                        baseline_gate_names=("led_white",),
                        baseline_suppress_pre_gate_us=25,
                        baseline_restore_post_gate_us=50,
                        brightness_by_gate={
                            "led_red": 0.8,
                            "led_green": 0.3,
                        },
                    ),
                )
            ),
        )

        events = DryRunPositionEventScheduler(first_frame_id=100).run(
            schedule,
            [PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=10_000)],
        )

        contract = validate_frame_event_led_timing_contract(events[0].to_protocol_record())
        self.assertEqual(contract.pattern, "AF_RED_GREEN")
        self.assertEqual(contract.logical_channel_names, ("led_red", "led_green"))
        self.assertEqual(contract.baseline_gate_names, ("led_white",))
        self.assertEqual(contract.trigger_start_us, 10_000)
        self.assertEqual(contract.trigger_end_us, 10_200)
        self.assertEqual(contract.exposure_start_us, 10_200)
        self.assertEqual(contract.exposure_end_us, 10_800)
        self.assertEqual(
            [(window.gate_name, window.start_us, window.end_us) for window in contract.gate_windows],
            [("led_red", 9_850, 10_875), ("led_green", 9_850, 10_875)],
        )
        self.assertEqual(
            [
                (transition.gate_name, transition.time_us, transition.state)
                for transition in contract.baseline_transitions
            ],
            [("led_white", 9_825, "inactive"), ("led_white", 10_925, "active")],
        )
        self.assertEqual(
            [setpoint.gate_name for setpoint in contract.brightness_setpoints],
            ["led_red", "led_green"],
        )

    def test_white_preview_baseline_override_is_limited_to_autofocus_frames(self):
        schedule = StripeSchedule(
            scan_id="scan-bf-window",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            pattern_led_timing=LedPatternTimingSet(
                profiles=(
                    LedPatternTimingProfile(
                        pattern="BF_WHITE",
                        exposure_start_offset_us=200,
                        exposure_us=600,
                        gate_pulse_us=200,
                        trigger_pulse_us=200,
                        gate_pre_trigger_us=150,
                        gate_post_exposure_us=75,
                        baseline_gate_names=("led_white",),
                        baseline_suppress_pre_gate_us=25,
                        baseline_restore_post_gate_us=50,
                        brightness_by_gate={"led_white": 1.0},
                    ),
                )
            ),
        )

        events = DryRunPositionEventScheduler(first_frame_id=100).run(
            schedule,
            [PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=10_000)],
        )

        contract = validate_frame_event_led_timing_contract(events[0].to_protocol_record())
        self.assertEqual(contract.pattern, "BF_WHITE")
        self.assertEqual(contract.logical_channel_names, ("led_white",))
        self.assertEqual(contract.baseline_gate_names, ())
        self.assertEqual(contract.baseline_transitions, ())

    def test_overlong_led_timing_emits_scheduler_fault_without_frame(self):
        schedule = StripeSchedule(
            scan_id="scan-led-overlong",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("AF_RED_GREEN",),
            pattern_led_timing=LedPatternTimingSet(
                profiles=(
                    LedPatternTimingProfile(
                        pattern="AF_RED_GREEN",
                        exposure_start_offset_us=0,
                        exposure_us=300,
                        gate_pulse_us=200,
                        settle_us=0,
                    ),
                )
            ),
        )

        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(x_step_commanded=20, y_step_commanded=5)],
        )

        self.assertEqual([event.type for event in events], ["SCHEDULER_TERMINAL"])
        terminal = events[0]
        self.assertEqual(terminal.status, "fault")
        self.assertEqual(terminal.reason_code, "scheduler_fault")
        self.assertIn("LED gate pulses", terminal.message)
        self.assertFalse(terminal.hardware_outputs_enabled)

    def test_led_timing_rejects_unused_brightness_gate_names(self):
        schedule = StripeSchedule(
            scan_id="scan-led-unused-gate",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            pattern_led_timing=LedPatternTimingSet(
                profiles=(
                    LedPatternTimingProfile(
                        pattern="BF_WHITE",
                        exposure_start_offset_us=0,
                        exposure_us=500,
                        gate_pulse_us=200,
                        brightness_by_gate={"led_whiet": 0.1},
                    ),
                )
            ),
        )

        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(x_step_commanded=20, y_step_commanded=5)],
        )

        self.assertEqual([event.type for event in events], ["SCHEDULER_TERMINAL"])
        self.assertEqual(events[0].reason_code, "scheduler_fault")
        self.assertIn("not used by schedule", events[0].message)

    def test_pattern_led_timing_requires_profiles_for_all_scheduled_patterns(self):
        schedule = StripeSchedule(
            scan_id="scan-led-missing-profile",
            stripe_id=7,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=2,
            pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
            pattern_led_timing=LedPatternTimingSet(
                profiles=(
                    LedPatternTimingProfile(
                        pattern="BF_WHITE",
                        exposure_start_offset_us=0,
                        exposure_us=500,
                        gate_pulse_us=200,
                    ),
                )
            ),
        )

        with self.assertRaisesRegex(ScheduleError, "missing LED timing profile"):
            DryRunPositionEventScheduler().run(
                schedule,
                [PositionSample(x_step_commanded=20, y_step_commanded=5)],
            )

    def test_pattern_led_timing_profile_rejects_invalid_brightness_values(self):
        with self.assertRaisesRegex(LedTimingError, "must be numeric"):
            LedPatternTimingProfile(
                pattern="BF_WHITE",
                exposure_start_offset_us=0,
                exposure_us=500,
                gate_pulse_us=200,
                brightness_by_gate={"led_white": "bright"},
            )
        with self.assertRaisesRegex(LedTimingError, "between 0.0 and 1.0"):
            LedPatternTimingProfile(
                pattern="BF_WHITE",
                exposure_start_offset_us=0,
                exposure_us=500,
                gate_pulse_us=200,
                brightness_by_gate={"led_white": 2.0},
            )

    def test_negative_x_stripe_uses_reversed_comparison(self):
        schedule = StripeSchedule(
            scan_id="scan-a",
            stripe_id=8,
            axis="X",
            start_position=100,
            end_position=0,
            first_event_position=80,
            event_pitch=-20,
            event_count=3,
            pattern_sequence=("BF_WHITE",),
        )
        samples = [
            PositionSample(x_step_commanded=100, y_step_commanded=0),
            PositionSample(x_step_commanded=80, y_step_commanded=0),
            PositionSample(x_step_commanded=60, y_step_commanded=0),
            PositionSample(x_step_commanded=40, y_step_commanded=0),
        ]

        events = DryRunPositionEventScheduler().run(schedule, samples)

        self.assertEqual([event.x_step_commanded for event in events], [80, 60, 40])

    def test_overshot_sample_keeps_scheduled_event_positions(self):
        schedule = StripeSchedule(
            scan_id="scan-overshoot",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=3,
            pattern_sequence=("BF_WHITE",),
        )

        events = DryRunPositionEventScheduler().run(
            schedule, [PositionSample(x_step_commanded=100, y_step_commanded=5)]
        )

        self.assertEqual([event.event_position for event in events], [20, 40, 60])
        self.assertEqual([event.sample_position for event in events], [100, 100, 100])
        self.assertEqual([event.position_overshoot_count for event in events], [80, 60, 40])
        self.assertEqual([event.x_count for event in events], [20, 40, 60])
        self.assertEqual([event.y_count for event in events], [5, 5, 5])
        self.assertEqual([event.x_step_commanded for event in events], [100, 100, 100])
        self.assertTrue(
            all("sample_overshot_event_position" in event.coordinate_flags for event in events)
        )

    def test_reverse_overshot_sample_reports_signed_position_delta(self):
        schedule = StripeSchedule(
            scan_id="scan-reverse-overshoot",
            stripe_id=1,
            axis="X",
            start_position=100,
            end_position=0,
            first_event_position=80,
            event_pitch=-20,
            event_count=3,
            pattern_sequence=("BF_WHITE",),
        )

        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(x_step_commanded=0, y_step_commanded=5)],
        )

        self.assertEqual([event.event_position for event in events], [80, 60, 40])
        self.assertEqual([event.sample_position for event in events], [0, 0, 0])
        self.assertEqual([event.position_overshoot_count for event in events], [-80, -60, -40])
        self.assertEqual([event.x_count for event in events], [80, 60, 40])
        self.assertTrue(
            all("sample_overshot_event_position" in event.coordinate_flags for event in events)
        )

    def test_reverse_y_overshot_sample_reports_signed_position_delta(self):
        schedule = StripeSchedule(
            scan_id="scan-reverse-y-overshoot",
            stripe_id=1,
            axis="Y",
            start_position=100,
            end_position=0,
            first_event_position=80,
            event_pitch=-20,
            event_count=2,
            pattern_sequence=("BF_WHITE",),
        )

        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(x_step_commanded=7, y_step_commanded=35)],
        )

        self.assertEqual([event.event_position for event in events], [80, 60])
        self.assertEqual([event.sample_position for event in events], [35, 35])
        self.assertEqual([event.position_overshoot_count for event in events], [-45, -25])
        self.assertEqual([event.y_count for event in events], [80, 60])
        self.assertEqual([event.x_count for event in events], [7, 7])
        self.assertTrue(
            all("sample_overshot_event_position" in event.coordinate_flags for event in events)
        )

    def test_y_stripe_uses_y_position(self):
        schedule = StripeSchedule(
            scan_id="scan-b",
            stripe_id=1,
            axis="Y",
            start_position=0,
            end_position=50,
            first_event_position=25,
            event_pitch=25,
            event_count=2,
            pattern_sequence=("BF_WHITE",),
        )
        samples = [
            PositionSample(x_step_commanded=10, y_step_commanded=20),
            PositionSample(x_step_commanded=10, y_step_commanded=25),
            PositionSample(x_step_commanded=10, y_step_commanded=50),
        ]

        events = DryRunPositionEventScheduler().run(schedule, samples)

        self.assertEqual([event.y_step_commanded for event in events], [25, 50])
        self.assertEqual([event.x_step_commanded for event in events], [10, 10])

    def test_frame_id_continues_across_stripes(self):
        scheduler = DryRunPositionEventScheduler(first_frame_id=5)
        schedule_a = StripeSchedule(
            scan_id="scan-c",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=10,
            first_event_position=10,
            event_pitch=10,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
        )
        schedule_b = StripeSchedule(
            scan_id="scan-c",
            stripe_id=2,
            axis="X",
            start_position=0,
            end_position=10,
            first_event_position=10,
            event_pitch=10,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
        )

        events_a = scheduler.run(schedule_a, [PositionSample(10, 0)])
        events_b = scheduler.run(schedule_b, [PositionSample(10, 0)])

        self.assertEqual(events_a[0].frame_id, 5)
        self.assertEqual(events_b[0].frame_id, 6)
        self.assertEqual(events_b[0].stripe_frame_index, 0)

    def test_stop_prevents_further_events(self):
        schedule = StripeSchedule(
            scan_id="scan-d",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=4,
            pattern_sequence=("BF_WHITE",),
        )
        samples = [PositionSample(100, 0)]

        events = DryRunPositionEventScheduler().run(
            schedule, samples, stop_after_events=2
        )

        self.assertEqual([event.type for event in events], [
            "FRAME_EVENT",
            "FRAME_EVENT",
            "SCHEDULER_TERMINAL",
        ])
        self.assertEqual([event.frame_id for event in events[:2]], [0, 1])
        terminal = events[-1]
        self.assertEqual(terminal.status, "stopped")
        self.assertEqual(terminal.reason_code, "host_stop")
        self.assertEqual(terminal.emitted_frame_count, 2)
        self.assertEqual(terminal.expected_frame_count, 4)
        self.assertEqual(terminal.last_frame_id, 1)
        self.assertEqual(terminal.next_frame_id, 2)
        self.assertEqual(terminal.next_stripe_frame_index, 2)
        self.assertEqual(terminal.mcu_time_us, 0)
        self.assertFalse(terminal.hardware_outputs_enabled)

    def test_stop_before_first_event_emits_terminal_record(self):
        schedule = StripeSchedule(
            scan_id="scan-d0",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=4,
            pattern_sequence=("BF_WHITE",),
        )

        scheduler = DryRunPositionEventScheduler(first_frame_id=42)
        events = scheduler.run(schedule, [PositionSample(100, 0)], stop_after_events=0)

        self.assertEqual(len(events), 1)
        terminal = events[0]
        self.assertEqual(terminal.type, "SCHEDULER_TERMINAL")
        self.assertEqual(terminal.status, "stopped")
        self.assertEqual(terminal.reason_code, "host_stop")
        self.assertEqual(terminal.emitted_frame_count, 0)
        self.assertIsNone(terminal.last_frame_id)
        self.assertEqual(terminal.next_frame_id, 42)
        self.assertEqual(terminal.next_stripe_frame_index, 0)
        self.assertEqual(scheduler.next_frame_id, 42)

    def test_stop_after_all_events_is_normal_completion(self):
        schedule = StripeSchedule(
            scan_id="scan-d1",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=40,
            first_event_position=20,
            event_pitch=20,
            event_count=2,
            pattern_sequence=("BF_WHITE",),
        )

        events = DryRunPositionEventScheduler().run(
            schedule, [PositionSample(40, 0)], stop_after_events=2
        )

        self.assertEqual([event.type for event in events], ["FRAME_EVENT", "FRAME_EVENT"])

    def test_exhausted_position_stream_emits_fault_terminal(self):
        schedule = StripeSchedule(
            scan_id="scan-exhausted",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=4,
            pattern_sequence=("BF_WHITE",),
        )

        scheduler = DryRunPositionEventScheduler(first_frame_id=50)
        events = scheduler.run(
            schedule,
            [
                PositionSample(20, 0, mcu_time_us=100),
                PositionSample(40, 0, mcu_time_us=200),
            ],
        )

        self.assertEqual(
            [event.type for event in events],
            ["FRAME_EVENT", "FRAME_EVENT", "SCHEDULER_TERMINAL"],
        )
        terminal = events[-1]
        self.assertEqual(terminal.status, "fault")
        self.assertEqual(terminal.reason_code, "position_stream_exhausted")
        self.assertEqual(terminal.emitted_frame_count, 2)
        self.assertEqual(terminal.expected_frame_count, 4)
        self.assertEqual(terminal.last_frame_id, 51)
        self.assertEqual(terminal.next_frame_id, 52)
        self.assertEqual(terminal.next_stripe_frame_index, 2)
        self.assertEqual(terminal.mcu_time_us, 200)
        self.assertEqual(scheduler.next_frame_id, 52)

    def test_simulated_fault_emits_terminal_record(self):
        schedule = StripeSchedule(
            scan_id="scan-fault",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=4,
            pattern_sequence=("BF_WHITE",),
        )

        scheduler = DryRunPositionEventScheduler(first_frame_id=10)
        events = scheduler.run(
            schedule,
            [PositionSample(100, 0, mcu_time_us=123)],
            fault_after_events=1,
            fault_message="simulated host-visible fault",
        )

        self.assertEqual([event.type for event in events], [
            "FRAME_EVENT",
            "SCHEDULER_TERMINAL",
        ])
        terminal = events[-1]
        self.assertEqual(terminal.status, "fault")
        self.assertEqual(terminal.reason_code, "scheduler_fault")
        self.assertEqual(terminal.emitted_frame_count, 1)
        self.assertEqual(terminal.last_frame_id, 10)
        self.assertEqual(terminal.next_frame_id, 11)
        self.assertEqual(terminal.next_stripe_frame_index, 1)
        self.assertEqual(terminal.mcu_time_us, 123)
        self.assertEqual(terminal.message, "simulated host-visible fault")
        self.assertEqual(scheduler.next_frame_id, 11)

    def test_rejects_invalid_schedules(self):
        valid = dict(
            scan_id="scan-e",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
        )

        with self.assertRaises(ScheduleError):
            DryRunPositionEventScheduler().run(
                StripeSchedule(event_pitch=0, **valid), []
            )
        with self.assertRaises(ScheduleError):
            DryRunPositionEventScheduler().run(
                StripeSchedule(event_pitch=-20, **valid), []
            )
        with self.assertRaises(ScheduleError):
            DryRunPositionEventScheduler().run(
                StripeSchedule(
                    event_pitch=20,
                    first_event_position=120,
                    **{key: value for key, value in valid.items() if key != "first_event_position"},
                ),
                [],
            )

    def test_rejects_hardware_outputs_in_phase_zero(self):
        schedule = StripeSchedule(
            scan_id="scan-f",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            hardware_outputs_enabled=True,
        )

        with self.assertRaisesRegex(ScheduleError, "approved backend"):
            DryRunPositionEventScheduler().run(schedule, [PositionSample(20, 0)])

    def test_rejects_non_dry_run_schedule(self):
        schedule = StripeSchedule(
            scan_id="scan-g",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            dry_run=False,
        )

        with self.assertRaisesRegex(ScheduleError, "dry_run must be true"):
            DryRunPositionEventScheduler().run(schedule, [PositionSample(20, 0)])

    def test_encoder_indexed_faults_when_encoder_counts_are_missing(self):
        schedule = StripeSchedule(
            scan_id="scan-h",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            coordinate_source="encoder_indexed",
        )

        events = DryRunPositionEventScheduler().run(
            schedule, [PositionSample(20, 0, mcu_time_us=55)]
        )

        self.assertEqual(len(events), 1)
        terminal = events[0]
        self.assertEqual(terminal.type, "SCHEDULER_TERMINAL")
        self.assertEqual(terminal.status, "fault")
        self.assertEqual(terminal.reason_code, "coordinate_source_error")
        self.assertEqual(terminal.emitted_frame_count, 0)
        self.assertIsNone(terminal.last_frame_id)
        self.assertEqual(terminal.next_frame_id, 0)
        self.assertEqual(terminal.next_stripe_frame_index, 0)
        self.assertEqual(terminal.mcu_time_us, 55)
        self.assertIn("requires X and Y encoder counts", terminal.message)

    def test_encoder_indexed_uses_encoder_metadata_when_present(self):
        schedule = StripeSchedule(
            scan_id="scan-i",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            coordinate_source="encoder_indexed",
        )

        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(20, 5, x_encoder_count=201, y_encoder_count=52)],
        )

        self.assertEqual(events[0].coordinate_source_used, "encoder_indexed")
        self.assertEqual(events[0].x_count, 201)
        self.assertEqual(events[0].y_count, 52)
        self.assertEqual(events[0].z_count, 0)
        self.assertEqual(events[0].x_step_commanded, 20)
        self.assertEqual(events[0].y_step_commanded, 5)
        self.assertEqual(events[0].x_encoder_count, 201)
        self.assertEqual(events[0].y_encoder_count, 52)
        self.assertEqual(events[0].coordinate_flags, ())

    def test_encoder_indexed_overshoot_keeps_encoder_sample_counts(self):
        schedule = StripeSchedule(
            scan_id="scan-i2",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            coordinate_source="encoder_indexed",
        )

        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(100, 5, x_encoder_count=901, y_encoder_count=52)],
        )

        self.assertEqual(events[0].event_position, 20)
        self.assertEqual(events[0].sample_position, 100)
        self.assertEqual(events[0].position_overshoot_count, 80)
        self.assertEqual(events[0].x_count, 901)
        self.assertEqual(events[0].y_count, 52)
        self.assertEqual(events[0].x_step_commanded, 100)
        self.assertEqual(events[0].coordinate_flags, ("sample_overshot_event_position",))

    def test_hybrid_preserves_commanded_counts_and_flags_missing_encoders(self):
        schedule = StripeSchedule(
            scan_id="scan-j",
            stripe_id=1,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=1,
            pattern_sequence=("BF_WHITE",),
            coordinate_source="hybrid",
        )

        events = DryRunPositionEventScheduler().run(
            schedule, [PositionSample(20, 5)]
        )

        self.assertEqual(events[0].coordinate_source_used, "hybrid")
        self.assertEqual(events[0].x_count, 20)
        self.assertEqual(events[0].y_count, 5)
        self.assertEqual(events[0].z_count, 0)
        self.assertEqual(events[0].x_step_commanded, 20)
        self.assertEqual(events[0].y_step_commanded, 5)
        self.assertIsNone(events[0].x_encoder_count)
        self.assertIsNone(events[0].y_encoder_count)
        self.assertEqual(
            events[0].coordinate_flags,
            ("x_encoder_missing", "y_encoder_missing"),
        )

    def test_metadata_queue_preserves_scheduler_frame_identity_and_coordinates(self):
        schedule = StripeSchedule(
            scan_id="scan-queue",
            stripe_id=2,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=2,
            pattern_sequence=("BF_WHITE",),
        )
        events = DryRunPositionEventScheduler(first_frame_id=70).run(
            schedule,
            [
                PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=100),
                PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=200),
            ],
        )

        queue = queue_scheduler_metadata_events(tuple(events), max_depth=2)
        queued = queue.snapshot()
        records = queue.snapshot_protocol_records()

        self.assertEqual(queue.queued_count, 2)
        self.assertEqual([item.sequence_id for item in queued], [0, 1])
        self.assertTrue(all(item.metadata_only for item in queued))
        self.assertTrue(all(not item.hardware_outputs_enabled for item in queued))
        self.assertEqual([record.type for record in records], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([record.frame_id for record in records], [70, 71])
        self.assertEqual([record.stripe_frame_index for record in records], [0, 1])
        self.assertEqual([record.event_position for record in records], [20, 40])
        self.assertEqual([record.x_count for record in records], [20, 40])
        self.assertEqual([record.y_count for record in records], [5, 5])
        self.assertEqual([record.mcu_time_us for record in records], [100, 200])
        self.assertTrue(all(not record.hardware_outputs_enabled for record in records))

        drained = queue.drain_protocol_records()
        self.assertEqual([record.frame_id for record in drained], [70, 71])
        self.assertEqual(queue.queued_count, 0)

    def test_metadata_queue_is_bounded(self):
        schedule = StripeSchedule(
            scan_id="scan-queue-overflow",
            stripe_id=2,
            axis="X",
            start_position=0,
            end_position=100,
            first_event_position=20,
            event_pitch=20,
            event_count=2,
            pattern_sequence=("BF_WHITE",),
        )
        events = DryRunPositionEventScheduler().run(
            schedule,
            [PositionSample(x_step_commanded=100, y_step_commanded=5)],
        )

        with self.assertRaisesRegex(MetadataQueueOverflow, "metadata queue capacity"):
            queue_scheduler_metadata_events(tuple(events), max_depth=1)


if __name__ == "__main__":
    unittest.main()
