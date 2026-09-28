import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_core.predictive_z.types import (  # noqa: E402
    StripeContext,
    ZCommand,
    ZNoCorrectionWindow,
    ZSchedulerConfig,
)
from scanner_firmware.planning.z_scheduler.scheduler import PredictiveZSchedulerSimulator  # noqa: E402
from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
)
from scanner_firmware.planning.z_scheduler.predictive import (  # noqa: E402
    ApplyPositionCountBasis,
    convert_apply_position_um_to_count,
)


class ZSchedulerModelTests(unittest.TestCase):
    def _scheduler(self) -> PredictiveZSchedulerSimulator:
        return PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_frames=2,
                settle_frames=1,
                lead_position_steps=10,
                settle_position_steps=5,
            ),
            StripeContext(
                scan_id="scan-a",
                stripe_id=7,
                start_position=0,
                end_position=100,
                current_frame_id=10,
            ),
        )

    def test_accepts_and_applies_future_frame_command_without_hardware_outputs(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                command_id="z-1",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=14,
                z_target_steps=25,
            ),
            seq=101,
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(scheduler.queued_count, 1)
        self.assertEqual(scheduler.advance_to(frame_id=13), [])

        events = scheduler.advance_to(frame_id=14)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "Z_APPLIED")
        self.assertEqual(events[0].apply_target_kind, "frame")
        self.assertEqual(events[0].frame_id, 14)
        self.assertEqual(events[0].z_target_steps, 25)
        self.assertFalse(events[0].hardware_outputs_enabled)
        self.assertEqual(
            [outcome.outcome for outcome in scheduler.outcomes],
            ["accepted", "applied"],
        )
        self.assertEqual(scheduler.terminal_outcome_by_seq[101].outcome, "applied")
        scheduler.validate_terminal_outcomes()

    def test_records_rejected_schedule_z_as_terminal_outcome(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                command_id="z-too-soon",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=scheduler.current_frame_id,
                z_target_steps=25,
            ),
            seq=102,
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "target_already_passed")
        self.assertEqual(scheduler.queued_count, 0)
        self.assertEqual(
            [outcome.outcome for outcome in scheduler.outcomes],
            ["rejected"],
        )
        self.assertEqual(
            scheduler.terminal_outcome_by_seq[102].reason,
            "target_already_passed",
        )
        scheduler.validate_terminal_outcomes()

    def test_pending_accepted_schedule_z_requires_terminal_apply_outcome(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                command_id="z-pending",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=14,
                z_target_steps=25,
            ),
            seq=103,
        )

        self.assertTrue(decision.accepted)
        with self.assertRaisesRegex(ValueError, "terminal outcome.*103"):
            scheduler.validate_terminal_outcomes()

        scheduler.advance_to(frame_id=14)
        scheduler.validate_terminal_outcomes()

    def test_scheduler_model_has_no_immediate_move_z_now_surface(self):
        scheduler = self._scheduler()

        self.assertFalse(hasattr(scheduler, "move_z_now"))

    def test_scheduler_decisions_and_events_adapt_to_protocol_ack_records(self):
        scheduler = self._scheduler()

        accepted = scheduler.schedule(
            ZCommand(
                command_id="z-accepted",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=14,
                z_target_steps=25,
            ),
            seq=104,
        )
        rejected = scheduler.schedule(
            ZCommand(
                command_id="z-rejected",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=11,
                z_target_steps=25,
            ),
            seq=105,
        )
        applied_event = scheduler.advance_to(frame_id=14)[0]

        scheduled_record = ZScheduledRecord.from_scheduler_decision(
            accepted,
            seq=accepted.seq,
        )
        rejected_record = ZRejectedRecord.from_scheduler_decision(
            rejected,
            seq=rejected.seq,
        )
        applied_record = ZAppliedRecord.from_scheduler_event(
            applied_event,
            seq=applied_event.seq,
        )

        self.assertEqual(scheduled_record.status, "accepted")
        self.assertEqual(scheduled_record.command_id, "z-accepted")
        self.assertEqual(rejected_record.status, "rejected")
        self.assertEqual(rejected_record.reason, "insufficient_lookahead")
        self.assertEqual(applied_record.status, "ok")
        self.assertEqual(applied_record.apply_at_frame_id, 14)
        self.assertFalse(applied_record.hardware_outputs_enabled)

    def test_accepts_and_applies_future_position_command(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                command_id="z-pos",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=20,
                z_target_steps=-12,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(scheduler.advance_to(position=19), [])

        events = scheduler.advance_to(position=20)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].apply_target_kind, "position")
        self.assertEqual(events[0].position, 20)
        self.assertEqual(events[0].z_target_steps, -12)
        self.assertFalse(events[0].hardware_outputs_enabled)

    def test_position_command_is_not_applied_by_frame_progress_only(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                command_id="z-pos",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=20,
                z_target_steps=-12,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(scheduler.advance_to(frame_id=100), [])
        self.assertEqual(scheduler.queued_count, 1)

        events = scheduler.advance_to(position=20)

        self.assertEqual([event.command_id for event in events], ["z-pos"])

    def test_queued_position_commands_apply_in_stripe_progress_order(self):
        scheduler = self._scheduler()

        for command_id, target in (("z-30", 30), ("z-20", 20), ("z-40", 40)):
            decision = scheduler.schedule(
                ZCommand(
                    command_id=command_id,
                    scan_id="scan-a",
                    stripe_id=7,
                    apply_at_position_count=target,
                    z_target_steps=target,
                )
            )
            self.assertTrue(decision.accepted)

        self.assertEqual(scheduler.advance_to(position=19), [])

        events = scheduler.advance_to(position=30)

        self.assertEqual([event.command_id for event in events], ["z-20", "z-30"])
        self.assertEqual(scheduler.queued_count, 1)

    def test_duplicate_position_targets_apply_in_schedule_order(self):
        scheduler = self._scheduler()

        for command_id, z_target in (("first", 10), ("second", 20), ("third", 30)):
            decision = scheduler.schedule(
                ZCommand(
                    command_id=command_id,
                    scan_id="scan-a",
                    stripe_id=7,
                    apply_at_position_count=20,
                    z_target_steps=z_target,
                )
            )
            self.assertTrue(decision.accepted)

        events = scheduler.advance_to(position=20)

        self.assertEqual(
            [event.command_id for event in events],
            ["first", "second", "third"],
        )
        self.assertEqual([event.z_target_steps for event in events], [10, 20, 30])

    def test_accepts_and_applies_position_target_at_stripe_end(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                command_id="end",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=100,
                z_target_steps=5,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(scheduler.advance_to(position=99), [])

        events = scheduler.advance_to(position=100)

        self.assertEqual([event.command_id for event in events], ["end"])
        self.assertEqual(events[0].position, 100)

    def test_rejects_rounded_physical_target_outside_stripe_without_clamping(self):
        scheduler = self._scheduler()
        rounded_count = convert_apply_position_um_to_count(
            101.025,
            basis=ApplyPositionCountBasis(counts_per_um=10),
            scan_direction_count=1,
        )

        decision = scheduler.schedule(
            ZCommand(
                command_id="outside",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=rounded_count,
                z_target_steps=5,
            )
        )

        self.assertEqual(rounded_count, 1011)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "target_outside_stripe")

    def test_negative_direction_position_command_uses_reversed_progress(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=0,
                max_z_steps=100,
                lead_position_steps=5,
                settle_position_steps=5,
            ),
            StripeContext(
                scan_id="scan-b",
                stripe_id=2,
                start_position=100,
                end_position=0,
                current_position=100,
            ),
        )

        decision = scheduler.schedule(
            ZCommand(
                scan_id="scan-b",
                stripe_id=2,
                apply_at_position_count=80,
                z_target_steps=10,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(scheduler.advance_to(position=81), [])
        self.assertEqual(len(scheduler.advance_to(position=80)), 1)

    def test_reverse_direction_queued_position_commands_apply_in_progress_order(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=0,
                max_z_steps=100,
                lead_position_steps=5,
                settle_position_steps=5,
            ),
            StripeContext(
                scan_id="scan-b",
                stripe_id=2,
                start_position=100,
                end_position=0,
                current_position=100,
            ),
        )

        for command_id, target in (("z-80", 80), ("z-90", 90), ("z-70", 70)):
            decision = scheduler.schedule(
                ZCommand(
                    command_id=command_id,
                    scan_id="scan-b",
                    stripe_id=2,
                    apply_at_position_count=target,
                    z_target_steps=target,
                )
            )
            self.assertTrue(decision.accepted)

        self.assertEqual(scheduler.advance_to(position=91), [])

        events = scheduler.advance_to(position=80)

        self.assertEqual([event.command_id for event in events], ["z-90", "z-80"])
        self.assertEqual(scheduler.queued_count, 1)

    def test_accepts_and_applies_reverse_position_target_at_stripe_end(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=0,
                max_z_steps=100,
                lead_position_steps=5,
                settle_position_steps=5,
            ),
            StripeContext(
                scan_id="scan-b",
                stripe_id=2,
                start_position=100,
                end_position=0,
                current_position=100,
            ),
        )

        decision = scheduler.schedule(
            ZCommand(
                command_id="reverse-end",
                scan_id="scan-b",
                stripe_id=2,
                apply_at_position_count=0,
                z_target_steps=10,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(scheduler.advance_to(position=1), [])

        events = scheduler.advance_to(position=0)

        self.assertEqual([event.command_id for event in events], ["reverse-end"])
        self.assertEqual(events[0].position, 0)

    def test_rejects_target_that_has_already_passed_by_frame_or_position(self):
        scheduler = self._scheduler()

        by_frame = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=10,
                z_target_steps=0,
            )
        )
        by_position = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=0,
                z_target_steps=0,
            )
        )

        self.assertFalse(by_frame.accepted)
        self.assertEqual(by_frame.reason, "target_already_passed")
        self.assertFalse(by_position.accepted)
        self.assertEqual(by_position.reason, "target_already_passed")

    def test_rejects_current_frame_and_current_position_targets_as_non_predictive(self):
        scheduler = self._scheduler()

        current_frame = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=scheduler.current_frame_id,
                z_target_steps=0,
            )
        )
        current_position = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=scheduler.current_position,
                z_target_steps=0,
            )
        )

        self.assertFalse(current_frame.accepted)
        self.assertEqual(current_frame.reason, "target_already_passed")
        self.assertFalse(current_position.accepted)
        self.assertEqual(current_position.reason, "target_already_passed")

    def test_rejects_scan_or_stripe_mismatch(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                scan_id="scan-other",
                stripe_id=7,
                apply_at_frame_id=20,
                z_target_steps=0,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "scan_or_stripe_mismatch")
        self.assertEqual(scheduler.queued_count, 0)

    def test_rejects_when_settle_requirement_does_not_fit_lookahead(self):
        scheduler = self._scheduler()

        by_frame = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=12,
                z_target_steps=0,
            )
        )
        by_position = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=14,
                z_target_steps=0,
            )
        )

        self.assertFalse(by_frame.accepted)
        self.assertEqual(by_frame.reason, "insufficient_lookahead")
        self.assertFalse(by_position.accepted)
        self.assertEqual(by_position.reason, "insufficient_lookahead")

    def test_rejects_z_target_outside_limits(self):
        scheduler = self._scheduler()

        decision = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=20,
                z_target_steps=101,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "z_limit_exceeded")

    def test_rejects_frame_target_inside_no_correction_window(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_frames=1,
                no_correction_windows=(
                    ZNoCorrectionWindow(target_kind="frame", start=18, end=20),
                ),
            ),
            StripeContext(
                scan_id="scan-a",
                stripe_id=7,
                start_position=0,
                end_position=100,
                current_frame_id=10,
            ),
        )

        decision = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=19,
                z_target_steps=0,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "no_correction_window")

    def test_rejects_position_target_inside_no_correction_window(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_position_steps=5,
                no_correction_windows=(
                    ZNoCorrectionWindow(target_kind="position", start=40, end=50),
                ),
            ),
            StripeContext(
                scan_id="scan-a",
                stripe_id=7,
                start_position=0,
                end_position=100,
            ),
        )

        decision = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=45,
                z_target_steps=0,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "no_correction_window")

    def test_no_correction_window_boundaries_are_inclusive_for_frames(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_frames=1,
                no_correction_windows=(
                    ZNoCorrectionWindow(target_kind="frame", start=18, end=20),
                ),
            ),
            StripeContext(
                scan_id="scan-a",
                stripe_id=7,
                start_position=0,
                end_position=100,
                current_frame_id=10,
            ),
        )

        before_window = scheduler.schedule(
            ZCommand(
                command_id="before",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=17,
                z_target_steps=0,
            )
        )
        at_start = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=18,
                z_target_steps=0,
            )
        )
        at_end = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=20,
                z_target_steps=0,
            )
        )
        after_window = scheduler.schedule(
            ZCommand(
                command_id="after",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=21,
                z_target_steps=0,
            )
        )

        self.assertTrue(before_window.accepted)
        self.assertFalse(at_start.accepted)
        self.assertEqual(at_start.reason, "no_correction_window")
        self.assertFalse(at_end.accepted)
        self.assertEqual(at_end.reason, "no_correction_window")
        self.assertTrue(after_window.accepted)

    def test_no_correction_window_boundaries_are_inclusive_for_positions(self):
        scheduler = PredictiveZSchedulerSimulator(
            ZSchedulerConfig(
                min_z_steps=-100,
                max_z_steps=100,
                lead_position_steps=5,
                no_correction_windows=(
                    ZNoCorrectionWindow(target_kind="position", start=40, end=50),
                ),
            ),
            StripeContext(
                scan_id="scan-a",
                stripe_id=7,
                start_position=0,
                end_position=100,
            ),
        )

        before_window = scheduler.schedule(
            ZCommand(
                command_id="before",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=39,
                z_target_steps=0,
            )
        )
        at_start = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=40,
                z_target_steps=0,
            )
        )
        at_end = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=50,
                z_target_steps=0,
            )
        )
        after_window = scheduler.schedule(
            ZCommand(
                command_id="after",
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=51,
                z_target_steps=0,
            )
        )

        self.assertTrue(before_window.accepted)
        self.assertFalse(at_start.accepted)
        self.assertEqual(at_start.reason, "no_correction_window")
        self.assertFalse(at_end.accepted)
        self.assertEqual(at_end.reason, "no_correction_window")
        self.assertTrue(after_window.accepted)

    def test_rejects_commands_without_exactly_one_future_target(self):
        scheduler = self._scheduler()

        no_target = scheduler.schedule(
            ZCommand(scan_id="scan-a", stripe_id=7, z_target_steps=0)
        )
        two_targets = scheduler.schedule(
            ZCommand(
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=20,
                apply_at_position_count=20,
                z_target_steps=0,
            )
        )

        self.assertFalse(no_target.accepted)
        self.assertEqual(no_target.reason, "invalid_target")
        self.assertFalse(two_targets.accepted)
        self.assertEqual(two_targets.reason, "invalid_target")

    def test_simulator_refuses_hardware_outputs(self):
        with self.assertRaises(ValueError):
            ZSchedulerConfig(
                min_z_steps=0,
                max_z_steps=1,
                hardware_outputs_enabled=True,
            )

    def test_rejects_invalid_no_correction_window(self):
        with self.assertRaises(ValueError):
            ZNoCorrectionWindow(target_kind="position", start=20, end=10)


if __name__ == "__main__":
    unittest.main()
