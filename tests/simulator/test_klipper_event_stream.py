import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.event_streaming.cli import main  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (  # noqa: E402
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.parsing import (  # noqa: E402
    decode_scanner_sync_json_lines,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (  # noqa: E402
    build_scanner_sync_capture_report,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (  # noqa: E402
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext  # noqa: E402
from scanner_firmware.foundation.protocol.events import TimedOutputSequenceStatusRecord  # noqa: E402


class KlipperEventStreamTests(unittest.TestCase):
    def test_decodes_jsonl_frame_event_to_protocol_record(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "FRAME_EVENT",
                        "params": {
                            "frame_id": 12,
                            "stripe_id": 7,
                            "stripe_frame_index": 2,
                            "pattern_id": 1,
                            "position_axis": 0,
                            "event_position": 200,
                            "x_count": 200,
                            "y_count": 12,
                            "z_count": 5,
                            "mcu_time_us": 4000,
                            "status": 0,
                            "flags": 0,
                        },
                    }
                )
            ],
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
                trigger_output_name="mks_z_plus",
            ),
        )

        self.assertEqual(len(records), 1)
        payload = records[0].to_json_dict()
        self.assertEqual(payload["type"], "FRAME_EVENT")
        self.assertEqual(payload["pattern"], "AF_RED_GREEN")
        self.assertEqual(payload["trigger_output_name"], "mks_z_plus")
        self.assertEqual(payload["coordinate_source_used"], "step_indexed")
        self.assertFalse(payload["hardware_outputs_enabled"])

    def test_decodes_jsonl_z_rejected_alias_type(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "type": "Z_REJECTED",
                        "params": {"seq": 42, "reason": 3, "status": 1},
                    }
                )
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        payload = records[0].to_json_dict()
        self.assertEqual(payload["type"], "Z_REJECTED")
        self.assertEqual(payload["scan_id"], "scan-a")
        self.assertEqual(payload["reason"], "insufficient_lookahead")
        self.assertFalse(payload["hardware_outputs_enabled"])

    def test_rejects_malformed_jsonl_with_line_number(self):
        with self.assertRaisesRegex(ScannerSyncEventStreamError, "line 2"):
            decode_scanner_sync_json_lines(
                [
                    "",
                    '{"event_type": "FRAME_EVENT", "params": 1}',
                ],
                context=ScannerSyncDecodeContext(scan_id="scan-a"),
            )

    def test_cli_outputs_protocol_jsonl_from_stdin(self):
        raw_event = json.dumps(
            {
                "event_type": "Z_SCHEDULED",
                "params": {"seq": 9, "stripe_id": 2, "status": 0},
            }
        )
        stdout = io.StringIO()

        with patch("sys.stdin", io.StringIO(raw_event)), contextlib.redirect_stdout(stdout):
            code = main(["-", "--scan-id", "scan-a"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["type"], "Z_SCHEDULED")
        self.assertEqual(payload["seq"], 9)
        self.assertEqual(payload["scan_id"], "scan-a")
        self.assertEqual(payload["protocol_version"], "1.0.0")
        self.assertFalse(payload["hardware_outputs_enabled"])

    def test_cli_exports_canonical_frame_event_jsonl_from_raw_input(self):
        stdout = io.StringIO()

        with (
            patch(
                "sys.stdin",
                io.StringIO(_frame_event_json(frame_id=20, stripe_frame_index=0)),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = main(["-", "--scan-id", "scan-a"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["type"], "FRAME_EVENT")
        self.assertEqual(payload["protocol_version"], "1.0.0")
        self.assertEqual(payload["status"], "OK")

    def test_validates_contiguous_frame_stream_and_terminal_counts(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=21, stripe_frame_index=1),
                json.dumps(
                    {
                        "event_type": "SCHEDULER_TERMINAL",
                        "params": {
                            "status": 0,
                            "reason": 0,
                            "emitted_frame_count": 2,
                            "expected_frame_count": 3,
                            "last_frame_id": 21,
                            "next_frame_id": 22,
                            "next_stripe_frame_index": 2,
                            "mcu_time_us": 9000,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        validation = validate_scanner_sync_event_sequence(records)

        self.assertEqual(validation.frame_count, 2)
        self.assertEqual(validation.terminal_count, 1)
        self.assertEqual(validation.first_frame_id, 20)
        self.assertEqual(validation.last_frame_id, 21)
        self.assertEqual(validation.next_frame_id, 22)
        self.assertEqual(validation.stripes_seen, (0,))

    def test_builds_capture_acceptance_report_from_valid_stream(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=21, stripe_frame_index=1),
                _terminal_json(emitted_frame_count=2, last_frame_id=21, next_frame_id=22),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        report = build_scanner_sync_capture_report(records)

        self.assertTrue(report.accepted)
        self.assertEqual(report.record_count, 3)
        self.assertEqual(report.event_types, (
            "FRAME_EVENT",
            "FRAME_EVENT",
            "SCHEDULER_TERMINAL",
        ))
        self.assertEqual(
            report.to_json_dict(),
            {
                "accepted": True,
                "record_count": 3,
                "event_types": [
                    "FRAME_EVENT",
                    "FRAME_EVENT",
                    "SCHEDULER_TERMINAL",
                ],
                "frame_count": 2,
                "terminal_count": 1,
                "first_frame_id": 20,
                "last_frame_id": 21,
                "next_frame_id": 22,
                "stripes_seen": [0],
                "z_scheduled_count": 0,
                "z_applied_count": 0,
                "z_rejected_count": 0,
                "timed_output_sequence_status_count": 0,
                "z_outcomes": [],
            },
        )

    def test_decodes_and_counts_timed_output_sequence_status_events(self):
        records = decode_scanner_sync_json_lines(
            [
                _timed_output_status_json("accepted"),
                _timed_output_status_json("started"),
                _timed_output_status_json("completed"),
            ],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        validation = validate_scanner_sync_event_sequence(records)
        report = build_scanner_sync_capture_report(records)

        self.assertEqual(records[0].type, "TIMED_OUTPUT_SEQUENCE_STATUS")
        self.assertEqual(validation.timed_output_sequence_status_count, 3)
        self.assertEqual(report.to_json_dict()["timed_output_sequence_status_count"], 3)

    def test_accepts_rejected_timed_output_sequence_status_as_terminal(self):
        records = decode_scanner_sync_json_lines(
            [_timed_output_status_json("rejected")],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        validation = validate_scanner_sync_event_sequence(records)

        self.assertEqual(validation.timed_output_sequence_status_count, 1)

    def test_incremental_dispatch_can_validate_timed_output_status_before_terminal(self):
        records = decode_scanner_sync_json_lines(
            [_timed_output_status_json("accepted"), _timed_output_status_json("started")],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        validation = validate_scanner_sync_event_sequence(
            records,
            require_timed_output_sequence_terminal_outcomes=False,
        )

        self.assertEqual(validation.timed_output_sequence_status_count, 2)

    def test_rejects_timed_output_terminal_before_accepted_or_started(self):
        completed_before_accepted = decode_scanner_sync_json_lines(
            [_timed_output_status_json("completed")],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )
        completed_before_started = decode_scanner_sync_json_lines(
            [_timed_output_status_json("accepted"), _timed_output_status_json("completed")],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "completed before accepted"):
            validate_scanner_sync_event_sequence(completed_before_accepted)
        with self.assertRaisesRegex(ScannerSyncEventStreamError, "completed before started"):
            validate_scanner_sync_event_sequence(completed_before_started)

    def test_rejects_timed_output_duplicate_terminal_or_status_after_terminal(self):
        duplicate_terminal = decode_scanner_sync_json_lines(
            [
                _timed_output_status_json("accepted"),
                _timed_output_status_json("started"),
                _timed_output_status_json("completed"),
                _timed_output_status_json("completed"),
            ],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )
        after_terminal = decode_scanner_sync_json_lines(
            [
                _timed_output_status_json("accepted"),
                _timed_output_status_json("started"),
                _timed_output_status_json("completed"),
                _timed_output_status_json("started"),
            ],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "appears after terminal"):
            validate_scanner_sync_event_sequence(duplicate_terminal)
        with self.assertRaisesRegex(ScannerSyncEventStreamError, "appears after terminal"):
            validate_scanner_sync_event_sequence(after_terminal)

    def test_rejects_timed_output_identity_mismatch_and_missing_terminal(self):
        stripe_mismatch = decode_scanner_sync_json_lines(
            [
                _timed_output_status_json("accepted", stripe_id=7),
                _timed_output_status_json("started", stripe_id=8),
            ],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )
        missing_terminal = decode_scanner_sync_json_lines(
            [_timed_output_status_json("accepted"), _timed_output_status_json("started")],
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "stripe_id changed"):
            validate_scanner_sync_event_sequence(stripe_mismatch)
        with self.assertRaisesRegex(ScannerSyncEventStreamError, "missing terminal status"):
            validate_scanner_sync_event_sequence(missing_terminal)

    def test_rejects_timed_output_hardware_outputs_enabled_true(self):
        with self.assertRaisesRegex(ScannerSyncEventStreamError, "hardware outputs"):
            validate_scanner_sync_event_sequence(
                [
                    TimedOutputSequenceStatusRecord(
                        seq_id=9001,
                        status="accepted",
                        hardware_outputs_enabled=True,
                    )
                ]
            )

    def test_rejects_dropped_or_duplicated_frame_ids(self):
        dropped = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=22, stripe_frame_index=1),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )
        duplicate = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=20, stripe_frame_index=1),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "frame_id"):
            validate_scanner_sync_event_sequence(dropped)
        with self.assertRaisesRegex(ScannerSyncEventStreamError, "frame_id"):
            validate_scanner_sync_event_sequence(duplicate)

    def test_rejects_non_contiguous_stripe_frame_index(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=21, stripe_frame_index=2),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "stripe_frame_index"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_stripe_frame_index_that_does_not_start_at_zero(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=3),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "stripe_frame_index"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_terminal_count_mismatch(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                json.dumps(
                    {
                        "event_type": "SCHEDULER_TERMINAL",
                        "params": {
                            "status": 0,
                            "reason": 0,
                            "emitted_frame_count": 2,
                            "expected_frame_count": 2,
                            "next_frame_id": 21,
                            "mcu_time_us": 9000,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "emitted_frame_count"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_terminal_next_stripe_frame_index_reset_after_frames(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                json.dumps(
                    {
                        "event_type": "SCHEDULER_TERMINAL",
                        "params": {
                            "stripe_id": 0,
                            "status": 0,
                            "reason": 0,
                            "emitted_frame_count": 1,
                            "expected_frame_count": 2,
                            "last_frame_id": 20,
                            "next_frame_id": 21,
                            "next_stripe_frame_index": 0,
                            "mcu_time_us": 9000,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "next_stripe_frame_index"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_frame_after_terminal_for_same_stripe(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _terminal_json(emitted_frame_count=1, last_frame_id=20, next_frame_id=21),
                _frame_event_json(frame_id=21, stripe_frame_index=1),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "follows SCHEDULER_TERMINAL"):
            validate_scanner_sync_event_sequence(records)

    def test_clean_completion_policy_is_frames_without_terminal(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=21, stripe_frame_index=1),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        validation = validate_scanner_sync_event_sequence(records)

        self.assertEqual(validation.frame_count, 2)
        self.assertEqual(validation.terminal_count, 0)
        self.assertEqual(validation.next_frame_id, 22)

    def test_rejects_stopped_terminal_that_reports_clean_completion(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _terminal_json(
                    emitted_frame_count=1,
                    expected_frame_count=1,
                    last_frame_id=20,
                    next_frame_id=21,
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "clean completion"):
            validate_scanner_sync_event_sequence(records)

    def test_fault_terminal_uses_remaining_expected_count(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _terminal_json(
                    status=1,
                    reason=1,
                    emitted_frame_count=1,
                    expected_frame_count=3,
                    last_frame_id=20,
                    next_frame_id=21,
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        validation = validate_scanner_sync_event_sequence(records)

        self.assertEqual(validation.frame_count, 1)
        self.assertEqual(validation.terminal_count, 1)

    def test_rejects_duplicate_terminal_for_same_stripe(self):
        records = decode_scanner_sync_json_lines(
            [
                _terminal_json(emitted_frame_count=0, last_frame_id=None, next_frame_id=20),
                _terminal_json(emitted_frame_count=0, last_frame_id=None, next_frame_id=20),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "duplicate"):
            validate_scanner_sync_event_sequence(records)

    def test_cli_validate_stream_returns_nonzero_for_invalid_sequence(self):
        raw_events = "\n".join(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=22, stripe_frame_index=1),
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("sys.stdin", io.StringIO(raw_events)),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = main(["-", "--scan-id", "scan-a", "--validate-stream"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("frame_id", stderr.getvalue())

    def test_cli_acceptance_requires_event_type_key(self):
        raw_event = json.dumps(
            {
                "type": "Z_REJECTED",
                "params": {"seq": 42, "reason": 3, "status": 1},
            }
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("sys.stdin", io.StringIO(raw_event)),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = main(["-", "--scan-id", "scan-a", "--validate-stream"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("event_type", stderr.getvalue())

    def test_cli_rejects_unsupported_protocol_version(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("sys.stdin", io.StringIO(_frame_event_json(frame_id=20, stripe_frame_index=0))),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = main(["-", "--scan-id", "scan-a", "--protocol-version", "2"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("unsupported protocol_version", stderr.getvalue())

    def test_cli_summary_json_outputs_capture_acceptance_report(self):
        raw_events = "\n".join(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=21, stripe_frame_index=1),
                _terminal_json(emitted_frame_count=2, last_frame_id=21, next_frame_id=22),
            ]
        )
        stdout = io.StringIO()

        with patch("sys.stdin", io.StringIO(raw_events)), contextlib.redirect_stdout(stdout):
            code = main(["-", "--scan-id", "scan-a", "--summary-json"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["accepted"], True)
        self.assertEqual(payload["record_count"], 3)
        self.assertEqual(payload["frame_count"], 2)
        self.assertEqual(payload["last_frame_id"], 21)
        self.assertEqual(payload["stripes_seen"], [0])
        self.assertEqual(payload["z_outcomes"], [])

    def test_cli_summary_json_enforces_expected_capture_counts(self):
        raw_events = "\n".join(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _frame_event_json(frame_id=21, stripe_frame_index=1),
                _terminal_json(emitted_frame_count=2, last_frame_id=21, next_frame_id=22),
            ]
        )
        stdout = io.StringIO()

        with patch("sys.stdin", io.StringIO(raw_events)), contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "-",
                    "--scan-id",
                    "scan-a",
                    "--summary-json",
                    "--expect-record-count",
                    "3",
                    "--expect-frame-count",
                    "2",
                    "--expect-terminal-count",
                    "1",
                    "--expect-first-frame-id",
                    "20",
                    "--expect-last-frame-id",
                    "21",
                    "--expect-stripes-seen",
                    "0",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["accepted"])

    def test_cli_expectations_return_nonzero_on_mismatch(self):
        raw_events = "\n".join(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _terminal_json(emitted_frame_count=1, last_frame_id=20, next_frame_id=21),
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("sys.stdin", io.StringIO(raw_events)),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = main(
                [
                    "-",
                    "--scan-id",
                    "scan-a",
                    "--summary-json",
                    "--expect-frame-count",
                    "2",
                    "--expect-stripes-seen",
                    "0,1",
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("frame_count expectation failed", stderr.getvalue())

    def test_validates_z_scheduled_then_applied_sequence(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {"seq": 9, "stripe_id": 2, "status": 0},
                    }
                ),
                json.dumps(
                    {
                        "event_type": "Z_APPLIED",
                        "params": {
                            "seq": 9,
                            "frame_id": 42,
                            "z_cmd_count": 123,
                            "status": 0,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        validation = validate_scanner_sync_event_sequence(records)

        self.assertEqual(validation.frame_count, 0)
        self.assertEqual(validation.z_scheduled_count, 1)
        self.assertEqual(validation.z_applied_count, 1)
        self.assertEqual(validation.z_rejected_count, 0)
        self.assertEqual(validation.z_outcomes[0].seq, 9)
        self.assertEqual(validation.z_outcomes[0].outcome, "applied")

    def test_rejects_z_applied_without_prior_scheduled_ack(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_APPLIED",
                        "params": {
                            "seq": 9,
                            "frame_id": 42,
                            "z_cmd_count": 123,
                            "status": 0,
                        },
                    }
                )
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "prior Z_SCHEDULED"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_z_rejected_then_applied_for_same_seq(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_REJECTED",
                        "params": {"seq": 9, "reason": 3, "status": 1},
                    }
                ),
                json.dumps(
                    {
                        "event_type": "Z_APPLIED",
                        "params": {
                            "seq": 9,
                            "frame_id": 42,
                            "z_cmd_count": 123,
                            "status": 0,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "prior Z_SCHEDULED"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_duplicate_z_scheduled_ack_for_same_seq(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {"seq": 9, "stripe_id": 2, "status": 0},
                    }
                ),
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {"seq": 9, "stripe_id": 2, "status": 0},
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "duplicates"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_z_scheduled_without_terminal_outcome(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {"seq": 9, "stripe_id": 2, "status": 0},
                    }
                )
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "terminal outcome"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_z_applied_scan_or_stripe_identity_mismatch(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {
                            "seq": 9,
                            "stripe_id": 2,
                            "command_id": "z-9",
                            "status": 0,
                        },
                    }
                ),
                json.dumps(
                    {
                        "event_type": "Z_APPLIED",
                        "params": {
                            "seq": 9,
                            "stripe_id": 3,
                            "command_id": "z-9",
                            "frame_id": 42,
                            "z_cmd_count": 123,
                            "status": 0,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "stripe_id mismatch"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_z_applied_frame_target_that_is_not_future(self):
        records = decode_scanner_sync_json_lines(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {"seq": 9, "stripe_id": 0, "status": 0},
                    }
                ),
                json.dumps(
                    {
                        "event_type": "Z_APPLIED",
                        "params": {
                            "seq": 9,
                            "stripe_id": 0,
                            "apply_target_kind": "frame",
                            "apply_at_frame_id": 20,
                            "frame_id": 20,
                            "z_cmd_count": 123,
                            "status": 0,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "not after Z_SCHEDULED"):
            validate_scanner_sync_event_sequence(records)

    def test_rejects_z_applied_target_mismatch(self):
        records = decode_scanner_sync_json_lines(
            [
                json.dumps(
                    {
                        "event_type": "Z_SCHEDULED",
                        "params": {"seq": 9, "stripe_id": 0, "status": 0},
                    }
                ),
                json.dumps(
                    {
                        "event_type": "Z_APPLIED",
                        "params": {
                            "seq": 9,
                            "stripe_id": 0,
                            "apply_target_kind": "frame",
                            "apply_at_frame_id": 42,
                            "frame_id": 43,
                            "z_cmd_count": 123,
                            "status": 0,
                        },
                    }
                ),
            ],
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "must match"):
            validate_scanner_sync_event_sequence(records)

    def test_cli_writes_summary_json_output_file(self):
        raw_events = "\n".join(
            [
                _frame_event_json(frame_id=20, stripe_frame_index=0),
                _terminal_json(emitted_frame_count=1, last_frame_id=20, next_frame_id=21),
            ]
        )
        stdout = io.StringIO()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            with (
                patch("sys.stdin", io.StringIO(raw_events)),
                contextlib.redirect_stdout(stdout),
            ):
                code = main(
                    [
                        "-",
                        "--scan-id",
                        "scan-a",
                        "--summary-json",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 2)
            self.assertEqual(payload["z_outcomes"], [])


def _frame_event_json(*, frame_id: int, stripe_frame_index: int) -> str:
    return json.dumps(
        {
            "event_type": "FRAME_EVENT",
            "params": {
                "frame_id": frame_id,
                "stripe_id": 0,
                "stripe_frame_index": stripe_frame_index,
                "pattern_id": 0,
                "position_axis": 0,
                "event_position": frame_id * 100,
                "x_count": frame_id * 100,
                "y_count": 0,
                "z_count": 0,
                "mcu_time_us": frame_id * 1000,
                "status": 0,
                "flags": 0,
            },
        }
    )


def _terminal_json(
    *,
    emitted_frame_count: int,
    last_frame_id: int | None,
    next_frame_id: int,
    expected_frame_count: int | None = None,
    status: int = 0,
    reason: int = 0,
) -> str:
    if expected_frame_count is None:
        expected_frame_count = emitted_frame_count + 1
    return json.dumps(
        {
            "event_type": "SCHEDULER_TERMINAL",
            "params": {
                "stripe_id": 0,
                "status": status,
                "reason": reason,
                "emitted_frame_count": emitted_frame_count,
                "expected_frame_count": expected_frame_count,
                "last_frame_id": last_frame_id,
                "next_frame_id": next_frame_id,
                "next_stripe_frame_index": emitted_frame_count,
                "mcu_time_us": 9000,
            },
        }
    )


def _timed_output_status_json(
    status: str,
    *,
    seq: int = 48,
    stripe_id: int = 7,
    seq_id: int = 9001,
) -> str:
    reasons = {
        "accepted": "accepted",
        "rejected": "invalid_command",
        "started": "started",
        "completed": "finite_completion",
        "stopped": "host_stop",
        "fault": "fault",
    }
    return json.dumps(
        {
            "event_type": "TIMED_OUTPUT_SEQUENCE_STATUS",
            "params": {
                "seq": seq,
                "stripe_id": stripe_id,
                "seq_id": seq_id,
                "status": status,
                "reason": reasons[status],
                "repeat_index": 0,
                "step_index": 0,
                "mcu_time_us": 25_000,
            },
        }
    )


if __name__ == "__main__":
    unittest.main()
