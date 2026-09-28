from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (  # noqa: E402
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (  # noqa: E402
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.cli import main  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (  # noqa: E402
    build_scanner_sync_capture_report,
)
from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    CANONICAL_PROTOCOL_VERSION,
    FrameEventRecord,
    ProtocolRecord,
    SchedulerTerminalRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
    to_canonical_v1_json_dict,
)
from scanner_firmware.foundation.protocol.parsing import (  # noqa: E402
    decode_protocol_json_lines,
)


STOPPED_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "frame_event_replay_protocol_v1.jsonl"
CLEAN_COMPLETION_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "frame_event_replay_protocol_v1_clean_completion.jsonl"
)
FAULT_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "frame_event_replay_protocol_v1_fault_terminal.jsonl"
)
FIXTURE_PATH = STOPPED_FIXTURE_PATH
FIXTURE_PATHS = (
    STOPPED_FIXTURE_PATH,
    CLEAN_COMPLETION_FIXTURE_PATH,
    FAULT_FIXTURE_PATH,
)
SIMULATOR_SCAN_ID = "simulator-frame-event-replay"
SIMULATOR_CLEAN_SCAN_ID = "simulator-frame-event-replay-clean"
SIMULATOR_FAULT_SCAN_ID = "simulator-frame-event-replay-fault"
PROTOCOL_RECORD_TYPES = {
    "FRAME_EVENT": FrameEventRecord,
    "Z_SCHEDULED": ZScheduledRecord,
    "Z_APPLIED": ZAppliedRecord,
    "Z_REJECTED": ZRejectedRecord,
    "SCHEDULER_TERMINAL": SchedulerTerminalRecord,
}


class FrameEventReplayFixtureTests(unittest.TestCase):
    def test_replay_fixture_is_jsonl_protocol_records_only(self):
        records = _load_fixture_records()

        self.assertEqual(
            [record["type"] for record in records],
            [
                "FRAME_EVENT",
                "Z_SCHEDULED",
                "FRAME_EVENT",
                "Z_APPLIED",
                "FRAME_EVENT",
                "Z_REJECTED",
                "SCHEDULER_TERMINAL",
            ],
        )
        self.assertTrue(all(record["scan_id"] == SIMULATOR_SCAN_ID for record in records))
        self.assertTrue(
            all(record["hardware_outputs_enabled"] is False for record in records)
        )

    def test_replay_fixture_is_canonical_protocol_v1_without_normalization(self):
        records = _load_all_fixture_records()
        frames = _records_of_type(records, "FRAME_EVENT")

        self.assertEqual(
            [to_canonical_v1_json_dict(record) for record in records],
            records,
        )
        self.assertTrue(
            all(
                record["protocol_version"] == CANONICAL_PROTOCOL_VERSION
                for record in records
            )
        )
        self.assertTrue(all(frame["status"] == "OK" for frame in frames))
        self.assertTrue(
            all(record["status"] == "ok" for record in _records_of_type(records, "Z_APPLIED"))
        )

    def test_frame_ids_and_stripe_indices_are_contiguous(self):
        records = _load_fixture_records()
        frames = _records_of_type(records, "FRAME_EVENT")

        self.assertEqual([frame["frame_id"] for frame in frames], [300, 301, 302])
        self.assertEqual(
            [frame["stripe_frame_index"] for frame in frames],
            list(range(len(frames))),
        )
        self.assertEqual(
            [frame["event_position"] for frame in frames],
            [1000, 1200, 1400],
        )
        self.assertEqual(frames[1]["position_overshoot_count"], 3)
        self.assertEqual(frames[1]["sample_position"], 1203)
        self.assertEqual(frames[2]["z_count"], 18)

    def test_frame_events_match_current_protocol_model(self):
        records = _load_fixture_records()
        decoded_records = _decode_protocol_fixture_records(records)
        frames = [
            record
            for record in decoded_records
            if isinstance(record, FrameEventRecord)
        ]

        self.assertEqual(
            [(frame.frame_id, frame.x_count, frame.y_count, frame.z_count) for frame in frames],
            [(300, 1000, 80, 0), (301, 1200, 80, 0), (302, 1400, 80, 18)],
        )
        self.assertEqual(
            [frame.led_gate_names for frame in frames],
            [("led_white",), ("led_red", "led_green"), ("led_white",)],
        )
        self.assertTrue(
            all(frame.trigger_output_name == "camera_or_sync_trigger" for frame in frames)
        )
        self.assertTrue(all(frame.hardware_outputs_enabled is False for frame in frames))
        self.assertEqual(
            [frame.to_json_dict() for frame in frames],
            _records_of_type(records, "FRAME_EVENT"),
        )

    def test_terminal_counts_match_emitted_frames(self):
        records = _load_fixture_records()
        frames = _records_of_type(records, "FRAME_EVENT")
        terminal = _single_record_of_type(records, "SCHEDULER_TERMINAL")

        self.assertEqual(terminal["status"], "stopped")
        self.assertEqual(terminal["reason_code"], "host_stop")
        self.assertEqual(terminal["emitted_frame_count"], len(frames))
        self.assertEqual(terminal["expected_frame_count"], 5)
        self.assertEqual(terminal["last_frame_id"], frames[-1]["frame_id"])
        self.assertEqual(terminal["next_frame_id"], frames[-1]["frame_id"] + 1)
        self.assertEqual(terminal["next_stripe_frame_index"], len(frames))

    def test_z_ack_records_are_ordered_for_replay(self):
        records = _load_fixture_records()
        scheduled_index = _record_index(records, "Z_SCHEDULED", seq=700)
        applied_index = _record_index(records, "Z_APPLIED", seq=700)
        target_frame_index = _record_index(records, "FRAME_EVENT", frame_id=302)
        rejected = _single_record_of_type(records, "Z_REJECTED")

        self.assertLess(scheduled_index, applied_index)
        self.assertLess(applied_index, target_frame_index)
        self.assertEqual(records[applied_index]["frame_id"], 302)
        self.assertEqual(records[applied_index]["apply_at_frame_id"], 302)
        self.assertEqual(records[applied_index]["z_cmd_count"], 18)
        self.assertEqual(records[applied_index]["z_target_steps"], 18)
        self.assertEqual(records[applied_index]["status"], "ok")
        self.assertEqual(rejected["seq"], 701)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["reason"], "insufficient_lookahead")

    def test_replay_fixture_validates_as_protocol_sequence(self):
        decoded_records = _decode_protocol_fixture_records(_load_fixture_records())

        validation = validate_scanner_sync_event_sequence(decoded_records)

        self.assertEqual(validation.frame_count, 3)
        self.assertEqual(validation.terminal_count, 1)
        self.assertEqual(validation.first_frame_id, 300)
        self.assertEqual(validation.last_frame_id, 302)
        self.assertEqual(validation.next_frame_id, 303)
        self.assertEqual(validation.stripes_seen, (4,))
        self.assertEqual(validation.z_scheduled_count, 1)
        self.assertEqual(validation.z_applied_count, 1)
        self.assertEqual(validation.z_rejected_count, 1)

    def test_canonical_replay_fixture_corpus_validates_as_protocol_sequences(self):
        expected_counts = {
            STOPPED_FIXTURE_PATH.name: (3, 1, (4,), 1, 1, 1),
            CLEAN_COMPLETION_FIXTURE_PATH.name: (5, 0, (10, 11), 1, 1, 0),
            FAULT_FIXTURE_PATH.name: (2, 1, (12,), 0, 0, 0),
        }

        for fixture_path in FIXTURE_PATHS:
            with self.subTest(fixture=fixture_path.name):
                decoded_records = _decode_protocol_fixture_records(
                    _load_fixture_records(fixture_path)
                )

                validation = validate_scanner_sync_event_sequence(decoded_records)

                self.assertEqual(
                    (
                        validation.frame_count,
                        validation.terminal_count,
                        validation.stripes_seen,
                        validation.z_scheduled_count,
                        validation.z_applied_count,
                        validation.z_rejected_count,
                    ),
                    expected_counts[fixture_path.name],
                )

    def test_clean_completion_fixture_has_no_terminal_and_reverse_multistripe_z(self):
        records = _load_fixture_records(CLEAN_COMPLETION_FIXTURE_PATH)
        frames = _records_of_type(records, "FRAME_EVENT")
        decoded_records = _decode_protocol_fixture_records(records)

        validation = validate_scanner_sync_event_sequence(decoded_records)

        self.assertEqual([frame["scan_id"] for frame in frames], [SIMULATOR_CLEAN_SCAN_ID] * 5)
        self.assertEqual([frame["frame_id"] for frame in frames], [400, 401, 402, 403, 404])
        self.assertEqual([frame["stripe_id"] for frame in frames], [10, 10, 11, 11, 11])
        self.assertEqual([frame["stripe_frame_index"] for frame in frames], [0, 1, 0, 1, 2])
        self.assertEqual(
            [frame["event_position"] for frame in frames if frame["stripe_id"] == 11],
            [2200, 2000, 1800],
        )
        self.assertEqual(validation.terminal_count, 0)
        self.assertEqual(validation.stripes_seen, (10, 11))
        self.assertEqual(validation.next_frame_id, 405)
        self.assertEqual(validation.z_outcomes[0].apply_target_kind, "position")
        self.assertEqual(validation.z_outcomes[0].apply_at_position_count, 1800)
        self.assertEqual(validation.z_outcomes[0].applied_frame_id, 404)
        self.assertEqual(validation.z_outcomes[0].z_target_steps, 24)

    def test_fault_terminal_fixture_reports_remaining_expected_count(self):
        records = _load_fixture_records(FAULT_FIXTURE_PATH)
        frames = _records_of_type(records, "FRAME_EVENT")
        terminal = _single_record_of_type(records, "SCHEDULER_TERMINAL")

        validation = validate_scanner_sync_event_sequence(
            _decode_protocol_fixture_records(records)
        )

        self.assertTrue(all(frame["scan_id"] == SIMULATOR_FAULT_SCAN_ID for frame in frames))
        self.assertEqual(terminal["status"], "fault")
        self.assertEqual(terminal["reason_code"], "coordinate_source_error")
        self.assertEqual(terminal["emitted_frame_count"], len(frames))
        self.assertEqual(terminal["expected_frame_count"], 4)
        self.assertEqual(terminal["last_frame_id"], frames[-1]["frame_id"])
        self.assertEqual(terminal["next_frame_id"], frames[-1]["frame_id"] + 1)
        self.assertEqual(terminal["next_stripe_frame_index"], len(frames))
        self.assertEqual(validation.terminal_count, 1)

    def test_replay_fixture_rejects_frame_after_terminal(self):
        records = _load_fixture_records()
        trailing_frame = dict(_records_of_type(records, "FRAME_EVENT")[-1])
        trailing_frame["frame_id"] = 303
        trailing_frame["stripe_frame_index"] = 3
        trailing_frame["event_position"] = 1600
        trailing_frame["sample_position"] = 1600
        trailing_frame["x_count"] = 1600
        trailing_frame["x_step_commanded"] = 1600
        decoded_records = _decode_protocol_fixture_records(records + [trailing_frame])

        with self.assertRaisesRegex(
            ScannerSyncEventStreamError, "follows SCHEDULER_TERMINAL"
        ):
            validate_scanner_sync_event_sequence(decoded_records)

    def test_fault_fixture_rejects_frame_after_terminal(self):
        records = _load_fixture_records(FAULT_FIXTURE_PATH)
        trailing_frame = dict(_records_of_type(records, "FRAME_EVENT")[-1])
        trailing_frame["frame_id"] = 502
        trailing_frame["stripe_frame_index"] = 2
        trailing_frame["event_position"] = 5400
        trailing_frame["sample_position"] = 5400
        trailing_frame["x_count"] = 5400
        trailing_frame["x_step_commanded"] = 5400
        decoded_records = _decode_protocol_fixture_records(records + [trailing_frame])

        with self.assertRaisesRegex(
            ScannerSyncEventStreamError, "follows SCHEDULER_TERMINAL"
        ):
            validate_scanner_sync_event_sequence(decoded_records)

    def test_clean_completion_fixture_policy_uses_no_terminal_record(self):
        records = _records_of_type(_load_fixture_records(), "FRAME_EVENT")
        decoded_records = _decode_protocol_fixture_records(records)

        validation = validate_scanner_sync_event_sequence(decoded_records)

        self.assertEqual(validation.frame_count, 3)
        self.assertEqual(validation.terminal_count, 0)
        self.assertEqual(validation.last_frame_id, 302)
        self.assertEqual(validation.next_frame_id, 303)

    def test_replay_fixture_rejects_terminal_as_clean_completion(self):
        records = _load_fixture_records()
        terminal = _single_record_of_type(records, "SCHEDULER_TERMINAL")
        terminal["expected_frame_count"] = terminal["emitted_frame_count"]

        decoded_records = _decode_protocol_fixture_records(records)

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "clean completion"):
            validate_scanner_sync_event_sequence(decoded_records)

    def test_clean_completion_fixture_rejects_dangling_z_scheduled(self):
        records = [
            record
            for record in _load_fixture_records(CLEAN_COMPLETION_FIXTURE_PATH)
            if record["type"] != "Z_APPLIED"
        ]
        decoded_records = _decode_protocol_fixture_records(records)

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "terminal outcome"):
            validate_scanner_sync_event_sequence(decoded_records)

    def test_replay_fixture_predictive_z_report_is_deterministic(self):
        decoded_records = decode_protocol_json_lines(
            FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        )

        report = build_scanner_sync_capture_report(decoded_records).to_json_dict()

        self.assertEqual(report["record_count"], 7)
        self.assertEqual(report["z_scheduled_count"], 1)
        self.assertEqual(report["z_applied_count"], 1)
        self.assertEqual(report["z_rejected_count"], 1)
        self.assertEqual(
            report["z_outcomes"],
            [
                {
                    "seq": 700,
                    "outcome": "applied",
                    "scan_id": SIMULATOR_SCAN_ID,
                    "stripe_id": 4,
                    "command_id": "z-frame-302",
                    "apply_target_kind": "frame",
                    "apply_at_frame_id": 302,
                    "apply_at_position_count": None,
                    "applied_frame_id": 302,
                    "applied_position": 1400,
                    "z_target_steps": 18,
                },
                {
                    "seq": 701,
                    "outcome": "rejected",
                    "scan_id": SIMULATOR_SCAN_ID,
                    "stripe_id": 4,
                    "command_id": "z-too-late",
                    "apply_target_kind": None,
                    "apply_at_frame_id": None,
                    "apply_at_position_count": None,
                    "applied_frame_id": None,
                    "applied_position": None,
                    "z_target_steps": None,
                },
            ],
        )

    def test_cli_validates_protocol_record_fixture_to_output_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "predictive-z-report.json"

            code = main(
                [
                    str(FIXTURE_PATH),
                    "--input-format",
                    "protocol-records",
                    "--summary-json",
                    "--output",
                    str(output_path),
                    "--expect-record-count",
                    "7",
                    "--expect-frame-count",
                    "3",
                    "--expect-terminal-count",
                    "1",
                    "--expect-first-frame-id",
                    "300",
                    "--expect-last-frame-id",
                    "302",
                    "--expect-stripes-seen",
                    "4",
                ]
            )

            self.assertEqual(code, 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["z_outcomes"][0]["seq"], 700)
            self.assertEqual(payload["z_outcomes"][0]["outcome"], "applied")

    def test_cli_validates_clean_completion_fixture_to_output_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "clean-completion-report.json"

            code = main(
                [
                    str(CLEAN_COMPLETION_FIXTURE_PATH),
                    "--input-format",
                    "protocol-records",
                    "--summary-json",
                    "--output",
                    str(output_path),
                    "--expect-record-count",
                    "7",
                    "--expect-frame-count",
                    "5",
                    "--expect-terminal-count",
                    "0",
                    "--expect-first-frame-id",
                    "400",
                    "--expect-last-frame-id",
                    "404",
                    "--expect-stripes-seen",
                    "10,11",
                ]
            )

            self.assertEqual(code, 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["terminal_count"], 0)
            self.assertEqual(payload["z_outcomes"][0]["apply_target_kind"], "position")


def _load_fixture_records(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_all_fixture_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for fixture_path in FIXTURE_PATHS:
        records.extend(_load_fixture_records(fixture_path))
    return records


def _records_of_type(records: list[dict[str, Any]], record_type: str) -> list[dict[str, Any]]:
    return [record for record in records if record["type"] == record_type]


def _single_record_of_type(records: list[dict[str, Any]], record_type: str) -> dict[str, Any]:
    matches = _records_of_type(records, record_type)
    if len(matches) != 1:
        raise AssertionError(f"expected one {record_type} record, found {len(matches)}")
    return matches[0]


def _record_index(records: list[dict[str, Any]], record_type: str, **fields: Any) -> int:
    for index, record in enumerate(records):
        if record["type"] != record_type:
            continue
        if all(record.get(key) == value for key, value in fields.items()):
            return index
    raise AssertionError(f"missing {record_type} record with fields {fields}")


def _decode_protocol_fixture_records(records: list[dict[str, Any]]) -> list[ProtocolRecord]:
    return [_decode_protocol_fixture_record(record) for record in records]


def _decode_protocol_fixture_record(record: dict[str, Any]) -> ProtocolRecord:
    record_type = record.get("type")
    if record_type not in PROTOCOL_RECORD_TYPES:
        raise AssertionError(f"unsupported fixture record type: {record_type!r}")
    record_class = PROTOCOL_RECORD_TYPES[record_type]
    init_field_names = {field.name for field in fields(record_class) if field.init}
    return record_class(
        **{key: value for key, value in record.items() if key in init_field_names}
    )


if __name__ == "__main__":
    unittest.main()
