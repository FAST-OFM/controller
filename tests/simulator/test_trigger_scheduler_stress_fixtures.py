from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.trigger_scheduler.scheduler import (  # noqa: E402
    DryRunPositionEventScheduler,
)
from scanner_firmware.planning.trigger_scheduler.types import (  # noqa: E402
    FrameEvent,
    PositionSample,
    SchedulerEvent,
    StripeSchedule,
)


def positive_x_schedule(
    *,
    scan_id: str = "stress-positive",
    stripe_id: int = 1,
    first_event_position: int = 10,
    event_pitch: int = 10,
    event_count: int = 4,
    coordinate_source: str = "step_indexed",
) -> StripeSchedule:
    return StripeSchedule(
        scan_id=scan_id,
        stripe_id=stripe_id,
        axis="X",
        start_position=0,
        end_position=50,
        first_event_position=first_event_position,
        event_pitch=event_pitch,
        event_count=event_count,
        pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
        coordinate_source=coordinate_source,
    )


def reverse_x_schedule(
    *,
    scan_id: str = "stress-reverse",
    stripe_id: int = 2,
    first_event_position: int = 40,
    event_pitch: int = -10,
    event_count: int = 4,
    coordinate_source: str = "step_indexed",
) -> StripeSchedule:
    return StripeSchedule(
        scan_id=scan_id,
        stripe_id=stripe_id,
        axis="X",
        start_position=50,
        end_position=0,
        first_event_position=first_event_position,
        event_pitch=event_pitch,
        event_count=event_count,
        pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
        coordinate_source=coordinate_source,
    )


def positive_x_stream() -> tuple[PositionSample, ...]:
    return (
        PositionSample(x_step_commanded=0, y_step_commanded=7, mcu_time_us=100),
        PositionSample(x_step_commanded=10, y_step_commanded=7, mcu_time_us=110),
        PositionSample(x_step_commanded=20, y_step_commanded=7, mcu_time_us=120),
        PositionSample(x_step_commanded=30, y_step_commanded=7, mcu_time_us=130),
        PositionSample(x_step_commanded=40, y_step_commanded=7, mcu_time_us=140),
    )


def reverse_x_stream() -> tuple[PositionSample, ...]:
    return (
        PositionSample(x_step_commanded=50, y_step_commanded=9, mcu_time_us=200),
        PositionSample(x_step_commanded=40, y_step_commanded=9, mcu_time_us=210),
        PositionSample(x_step_commanded=30, y_step_commanded=9, mcu_time_us=220),
        PositionSample(x_step_commanded=20, y_step_commanded=9, mcu_time_us=230),
        PositionSample(x_step_commanded=10, y_step_commanded=9, mcu_time_us=240),
    )


def overshoot_burst_stream() -> tuple[PositionSample, ...]:
    return (
        PositionSample(x_step_commanded=45, y_step_commanded=11, mcu_time_us=300),
    )


def encoder_ready_then_missing_stream() -> tuple[PositionSample, ...]:
    return (
        PositionSample(
            x_step_commanded=10,
            y_step_commanded=13,
            x_encoder_count=1001,
            y_encoder_count=1301,
            mcu_time_us=410,
        ),
        PositionSample(
            x_step_commanded=20,
            y_step_commanded=13,
            x_encoder_count=1002,
            y_encoder_count=1302,
            mcu_time_us=420,
        ),
        PositionSample(
            x_step_commanded=30,
            y_step_commanded=13,
            x_encoder_count=1003,
            y_encoder_count=None,
            mcu_time_us=430,
        ),
    )


def frame_events(events: list[SchedulerEvent]) -> list[FrameEvent]:
    return [event for event in events if event.type == "FRAME_EVENT"]


class TriggerSchedulerStressFixtureTests(unittest.TestCase):
    def test_positive_and_reverse_streams_are_deterministic_and_advance_frame_ids(self):
        scheduler = DryRunPositionEventScheduler(first_frame_id=500)

        positive_events = scheduler.run(positive_x_schedule(), positive_x_stream())
        reverse_events = scheduler.run(reverse_x_schedule(), reverse_x_stream())

        self.assertEqual(
            [event.frame_id for event in positive_events],
            [500, 501, 502, 503],
        )
        self.assertEqual(
            [event.stripe_frame_index for event in positive_events],
            [0, 1, 2, 3],
        )
        self.assertEqual(
            [event.event_position for event in positive_events],
            [10, 20, 30, 40],
        )
        self.assertEqual(
            [event.sample_position for event in positive_events],
            [10, 20, 30, 40],
        )
        self.assertEqual(
            [event.position_overshoot_count for event in positive_events],
            [0, 0, 0, 0],
        )
        self.assertEqual([event.x_count for event in positive_events], [10, 20, 30, 40])

        self.assertEqual(
            [event.frame_id for event in reverse_events],
            [504, 505, 506, 507],
        )
        self.assertEqual(
            [event.stripe_frame_index for event in reverse_events],
            [0, 1, 2, 3],
        )
        self.assertEqual(
            [event.event_position for event in reverse_events],
            [40, 30, 20, 10],
        )
        self.assertEqual(
            [event.sample_position for event in reverse_events],
            [40, 30, 20, 10],
        )
        self.assertEqual(
            [event.position_overshoot_count for event in reverse_events],
            [0, 0, 0, 0],
        )
        self.assertEqual([event.x_count for event in reverse_events], [40, 30, 20, 10])
        self.assertEqual(scheduler.next_frame_id, 508)
        self.assertTrue(
            all(
                not event.hardware_outputs_enabled
                for event in positive_events + reverse_events
            )
        )

    def test_overshoot_burst_emits_planned_positions_and_advances_next_frame_id(self):
        scheduler = DryRunPositionEventScheduler(first_frame_id=700)

        events = scheduler.run(
            positive_x_schedule(
                scan_id="stress-overshoot",
                stripe_id=3,
                first_event_position=10,
                event_pitch=10,
                event_count=4,
            ),
            overshoot_burst_stream(),
        )

        self.assertEqual([event.frame_id for event in events], [700, 701, 702, 703])
        self.assertEqual([event.event_position for event in events], [10, 20, 30, 40])
        self.assertEqual([event.sample_position for event in events], [45, 45, 45, 45])
        self.assertEqual(
            [event.position_overshoot_count for event in events],
            [35, 25, 15, 5],
        )
        self.assertEqual([event.x_count for event in events], [10, 20, 30, 40])
        self.assertEqual([event.x_step_commanded for event in events], [45, 45, 45, 45])
        self.assertTrue(
            all("sample_overshot_event_position" in event.coordinate_flags for event in events)
        )
        self.assertEqual(scheduler.next_frame_id, 704)

    def test_missing_encoder_count_fault_preserves_emitted_frame_id_advancement(self):
        scheduler = DryRunPositionEventScheduler(first_frame_id=900)

        events = scheduler.run(
            positive_x_schedule(
                scan_id="stress-encoder-readiness",
                stripe_id=4,
                event_count=3,
                coordinate_source="encoder_indexed",
            ),
            encoder_ready_then_missing_stream(),
        )

        emitted = frame_events(events)
        terminal = events[-1]
        self.assertEqual([event.frame_id for event in emitted], [900, 901])
        self.assertEqual([event.stripe_frame_index for event in emitted], [0, 1])
        self.assertEqual([event.x_count for event in emitted], [1001, 1002])
        self.assertEqual([event.y_count for event in emitted], [1301, 1302])
        self.assertEqual(terminal.type, "SCHEDULER_TERMINAL")
        self.assertEqual(terminal.status, "fault")
        self.assertEqual(terminal.reason_code, "coordinate_source_error")
        self.assertEqual(terminal.emitted_frame_count, 2)
        self.assertEqual(terminal.expected_frame_count, 3)
        self.assertEqual(terminal.last_frame_id, 901)
        self.assertEqual(terminal.next_frame_id, 902)
        self.assertEqual(terminal.next_stripe_frame_index, 2)
        self.assertEqual(terminal.mcu_time_us, 430)
        self.assertIn("requires X and Y encoder counts", terminal.message)
        self.assertEqual(scheduler.next_frame_id, 902)

        follow_up_events = scheduler.run(
            positive_x_schedule(scan_id="stress-follow-up", stripe_id=5, event_count=1),
            (PositionSample(x_step_commanded=10, y_step_commanded=17, mcu_time_us=500),),
        )

        self.assertEqual([event.type for event in follow_up_events], ["FRAME_EVENT"])
        self.assertEqual(follow_up_events[0].frame_id, 902)
        self.assertEqual(follow_up_events[0].stripe_frame_index, 0)
        self.assertEqual(scheduler.next_frame_id, 903)


if __name__ == "__main__":
    unittest.main()
