from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_SOURCE = (
    REPO_ROOT / "docs" / "live-mks" / "timed-output-sequence" / "src" / "scanner_sync.c"
)


class LiveMksAfWindowSnapshotTests(unittest.TestCase):
    def test_rg_to_white_is_post_exposure_light_hold_before_restore(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")
        exposure_case = _case_body(source, "SS_EXPOSURE")
        rg_to_white_case = _case_body(source, "SS_RG_TO_WHITE")
        restore_case = _case_body(source, "SS_RESTORE_WHITE")

        self.assertIn("gpio_out_write(ss->xvs_pin, 0);", exposure_case)
        self.assertIn("ss->state = SS_RG_TO_WHITE;", exposure_case)
        self.assertIn("delay = ss->exposure_hold_ticks;", exposure_case)

        self.assertIn("ss->state = SS_RESTORE_WHITE;", rg_to_white_case)
        self.assertIn("delay = ss->rg_to_white_ticks;", rg_to_white_case)
        self.assertNotIn("gpio_out_write(ss->green_pin, 0);", rg_to_white_case)
        self.assertNotIn("gpio_out_write(ss->red_pin, 0);", rg_to_white_case)

        self.assertIn("gpio_out_write(ss->green_pin, 0);", restore_case)
        self.assertIn("gpio_out_write(ss->red_pin, 0);", restore_case)
        self.assertIn("gpio_out_write(ss->white_pin, 1);", restore_case)

    def test_invalid_af_window_state_fails_closed(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")
        default_case = _default_case_body(source)

        self.assertIn("scanner_sync_outputs_safe(ss);", default_case)
        self.assertIn('shutdown("scanner_sync invalid AF window state");', default_case)

    def test_xvs_rising_emits_optional_frame_event(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")
        xvs_case = _case_body(source, "SS_XVS_HIGH")

        self.assertIn("gpio_out_write(ss->xvs_pin, 1);", xvs_case)
        self.assertIn("if (ss->emit_af_frame_events)", xvs_case)
        self.assertIn("scanner_sync_queue_frame_event_at(", xvs_case)
        self.assertIn("SS_EVENT_FRAME | SS_EVENT_XVS_RISING", xvs_case)
        self.assertIn("| SS_EVENT_EXPOSURE_START", xvs_case)

    def test_af_window_command_exposes_frame_event_identity(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("seq=%u stripe_id=%u frame_id_base=%i", source)
        self.assertIn("pattern_id=%u emit_frame_events=%c", source)
        self.assertIn("ss->seq = args[10];", source)
        self.assertIn("ss->stripe_id = args[11];", source)
        self.assertIn("ss->frame_id_base = args[12];", source)
        self.assertIn("ss->pattern_id = args[13];", source)
        self.assertIn("ss->emit_af_frame_events = !!args[14];", source)

    def test_frame_event_time_is_sequence_relative_to_avoid_timer_wrap(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("scanner_sync_elapsed_us(struct scanner_sync *ss)", source)
        self.assertIn("timer_read_time() - ss->mcu_time_base", source)
        self.assertIn("pending->mcu_time_us = scanner_sync_elapsed_us(ss);", source)
        self.assertIn("ss->mcu_time_base = timer_read_time();", source)
        self.assertIn("ss->timer.waketime = ss->mcu_time_base + timer_from_us(100);", source)

    def test_safe_stop_always_forces_all_known_outputs_inactive(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")

        apply_safe_stop = _function_body(source, "scanner_sync_apply_safe_stop")
        self.assertIn("scanner_sync_outputs_safe(ss);", apply_safe_stop)
        self.assertNotIn("ss->safe_output_mask", apply_safe_stop)

        af_start = _function_body(source, "command_scanner_sync_af_window_test")
        self.assertIn("ss->safe_output_mask = SS_KNOWN_OUTPUT_MASK;", af_start)
        self.assertIn("ss->safe_output_values = 0;", af_start)

    def test_generic_timed_sequence_uses_per_event_frame_index(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")
        command_body = _function_body(source, "command_scanner_sync_run_timed_output_sequence")

        self.assertIn("event_frame_index", source)
        self.assertIn("ss->event_frame_index = 0;", command_body)
        self.assertIn("ss->event_frame_index++", source)
        self.assertIn("step->pattern_id ? step->pattern_id : ss->pattern_id", source)
        self.assertNotIn("scanner_sync_emit_frame_event(ss, step->event_flags)", source)

    def test_generic_timed_step_format_carries_pattern_and_limits_payload(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")
        decode_body = _function_body(source, "scanner_sync_decode_timed_output_step")

        self.assertIn("SS_STEP_BYTES = 10", source)
        self.assertIn("SS_MAX_STEPS = 12", source)
        self.assertIn("step->pattern_id = encoded[2];", decode_body)
        self.assertIn("if (encoded[3])", decode_body)
        self.assertIn("scanner_sync_read_u32_le(encoded + 4)", decode_body)
        self.assertIn("scanner_sync_read_u16_le(encoded + 8)", decode_body)

    def test_generic_timed_sequence_uses_staged_klipper_transport(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("command_scanner_sync_begin_timed_output_sequence", source)
        self.assertIn("command_scanner_sync_add_timed_output_step", source)
        self.assertIn("command_scanner_sync_start_timed_output_sequence", source)
        self.assertIn("scanner_sync_begin_timed_output_sequence oid=%c", source)
        self.assertIn("scanner_sync_add_timed_output_step oid=%c", source)
        self.assertIn("scanner_sync_start_timed_output_sequence oid=%c", source)

    def test_timer_path_queues_telemetry_for_task_sendf(self) -> None:
        source = SNAPSHOT_SOURCE.read_text(encoding="utf-8")

        self.assertIn("DECL_TASK(scanner_sync_task);", source)
        self.assertIn("scanner_sync_queue_frame_event_at(", source)
        self.assertIn("scanner_sync_queue_timed_sequence_status(", source)
        self.assertIn("sched_wake_task(&scanner_sync_wake);", source)


def _case_body(source: str, label: str) -> str:
    match = re.search(
        rf"case {re.escape(label)}:\n(?P<body>.*?)\n\s*break;",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing case {label}")
    return match.group("body")


def _default_case_body(source: str) -> str:
    match = re.search(
        r"default:\n(?P<body>.*?)\n\s*}",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("missing default case")
    return match.group("body")


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"\n{re.escape(name)}\([^)]*\)\n(?P<body>{{.*?\n}})",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing function {name}")
    return match.group("body")


if __name__ == "__main__":
    unittest.main()
