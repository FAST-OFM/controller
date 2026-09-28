from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    RunTimedOutputSequenceCommand,
    TIMED_OUTPUT_SEQUENCE_END_FLAG,
    TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG,
    TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG,
    TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
    TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK,
    TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
    TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG,
    TimedOutputSequenceStep,
)
from scanner_firmware.planning.scanner_sync.timed_output_sequence import (  # noqa: E402
    TimedOutputSequenceSimulator,
    simulate_timed_output_sequence,
)


class TimedOutputSequenceSimulatorTests(unittest.TestCase):
    def test_finite_sequence_latches_outputs_pause_steps_and_completes_idle(self):
        command = _command(
            repeat_count=2,
            idle_output_values=TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
        )

        result = simulate_timed_output_sequence(command)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.reason_code, "finite_completion")
        self.assertEqual(result.repeat_count_executed, 2)
        self.assertFalse(result.bounded_by_simulator_max)
        self.assertEqual(result.elapsed_us, 30)
        self.assertEqual(result.frame_event_marker_count, 2)
        self.assertTrue(all(not step.hardware_outputs_enabled for step in result.step_trace))
        self.assertEqual(
            [
                (
                    step.repeat_index,
                    step.step_index,
                    step.latched_outputs_before,
                    step.latched_outputs_after,
                )
                for step in result.step_trace
            ],
            [
                (0, 0, 0, TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT),
                (
                    0,
                    1,
                    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                ),
                (0, 2, TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT, TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT),
                (1, 0, TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT, TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT),
                (
                    1,
                    1,
                    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                ),
                (1, 2, TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT, TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT),
            ],
        )
        self.assertEqual(result.final_state_source, "idle")
        self.assertEqual(
            result.final_latched_outputs_before_terminal_state,
            TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
        )
        self.assertEqual(
            result.final_latched_outputs_after_terminal_state,
            TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
        )

    def test_event_flag_trace_decodes_flags_and_counts_frame_markers(self):
        result = simulate_timed_output_sequence(_command(repeat_count=1))

        self.assertEqual(
            [
                (event.step_index, event.event_flag_names, event.frame_event_marker)
                for event in result.event_flag_trace
            ],
            [
                (0, ("exposure_start",), False),
                (1, ("frame_event", "xvs_rising"), True),
                (2, ("end",), False),
            ],
        )
        self.assertEqual(result.frame_event_marker_count, 1)

    def test_zero_repeat_count_is_bounded_by_simulator_max_and_ends_safe(self):
        command = _command(
            repeat_count=0,
            safe_output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
        )

        result = TimedOutputSequenceSimulator(max_infinite_repeats=3).run(command)

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.reason_code, "simulator_repeat_bound")
        self.assertTrue(result.bounded_by_simulator_max)
        self.assertEqual(result.repeat_count_requested, 0)
        self.assertEqual(result.repeat_count_executed, 3)
        self.assertEqual(len(result.step_trace), 9)
        self.assertEqual(result.frame_event_marker_count, 3)
        self.assertEqual(result.final_state_source, "safe")
        self.assertEqual(
            result.final_latched_outputs_after_terminal_state,
            TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
        )

    def test_stop_applies_safe_state_after_last_emitted_step(self):
        command = _command(
            repeat_count=4,
            safe_output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
        )

        result = simulate_timed_output_sequence(command, stop_after_steps=2)

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.reason_code, "host_stop")
        self.assertEqual(len(result.step_trace), 2)
        self.assertEqual(result.repeat_count_executed, 0)
        self.assertEqual(
            result.final_latched_outputs_before_terminal_state,
            TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
        )
        self.assertEqual(
            result.final_latched_outputs_after_terminal_state,
            TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
        )

    def test_fault_applies_safe_state_before_first_step_when_requested(self):
        command = _command(
            repeat_count=1,
            safe_output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
        )

        result = simulate_timed_output_sequence(command, fault_after_steps=0)

        self.assertEqual(result.status, "fault")
        self.assertEqual(result.reason_code, "simulator_fault")
        self.assertEqual(result.step_trace, ())
        self.assertEqual(result.event_flag_trace, ())
        self.assertEqual(result.final_state_source, "safe")
        self.assertEqual(
            result.final_latched_outputs_after_terminal_state,
            TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
        )


def _command(
    *,
    repeat_count: int,
    safe_output_values: int = 0,
    idle_output_values: int = 0,
) -> RunTimedOutputSequenceCommand:
    return RunTimedOutputSequenceCommand(
        seq=41,
        scan_id="timed-output-sim",
        stripe_id=7,
        seq_id=3,
        repeat_count=repeat_count,
        frame_id_base=100,
        pattern_id=2,
        safe_output_mask=TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK,
        safe_output_values=safe_output_values,
        idle_output_mask=TIMED_OUTPUT_SEQUENCE_KNOWN_OUTPUT_MASK,
        idle_output_values=idle_output_values,
        steps=(
            TimedOutputSequenceStep(
                output_mask=TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT
                | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                output_values=TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                delay_us=5,
                event_flags=TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG,
            ),
            TimedOutputSequenceStep(
                output_mask=0,
                output_values=0,
                delay_us=3,
                event_flags=TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG
                | TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG,
            ),
            TimedOutputSequenceStep(
                output_mask=TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT
                | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                output_values=TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                delay_us=7,
                event_flags=TIMED_OUTPUT_SEQUENCE_END_FLAG,
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
