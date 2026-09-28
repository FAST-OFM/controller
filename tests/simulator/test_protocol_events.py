import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    FrameEventRecord,
    ProtocolSerializationError,
    ScheduleZCommand,
    SchedulerTerminalRecord,
    ScannerSyncStartCommand,
    ScannerSyncStopCommand,
    TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG,
    TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG,
    TimedOutputSequenceStatusRecord,
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
    canonicalize_protocol_v1_payload,
    scheduler_event_to_protocol_record,
    to_canonical_v1_json_dict,
    to_json,
    to_json_dict,
)
from scanner_firmware.foundation.protocol.parsing import (  # noqa: E402
    decode_protocol_json_lines,
)
from scanner_firmware.planning.trigger_scheduler.types import (  # noqa: E402
    FrameEvent as SchedulerFrameEvent,
)


class ProtocolEventTests(unittest.TestCase):
    def test_frame_event_serializes_dry_run_scheduler_shape(self):
        scheduler_event = SimpleNamespace(
            type="FRAME_EVENT",
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=7,
            frame_id=100,
            stripe_frame_index=2,
            pattern="AF_RED_GREEN",
            led_gate_names=("led_red", "led_green"),
            trigger_output_name="camera_or_sync_trigger",
            coordinate_source_used="step_indexed",
            position_axis="X",
            event_position=40,
            sample_position=45,
            position_overshoot_count=5,
            x_count=40,
            y_count=8,
            z_count=3,
            x_step_commanded=45,
            y_step_commanded=8,
            z_step_commanded=3,
            x_encoder_count=None,
            y_encoder_count=None,
            coordinate_flags=("sample_overshot_event_position",),
            mcu_time_us=1234,
            hardware_outputs_enabled=False,
            status="ok",
        )

        record = FrameEventRecord.from_scheduler_event(scheduler_event)
        payload = record.to_json_dict()

        self.assertEqual(payload["type"], "FRAME_EVENT")
        self.assertEqual(payload["scan_id"], "scan-a")
        self.assertEqual(payload["stripe_id"], 7)
        self.assertEqual(payload["frame_id"], 100)
        self.assertEqual(payload["stripe_frame_index"], 2)
        self.assertEqual(payload["event_position"], 40)
        self.assertEqual(payload["sample_position"], 45)
        self.assertEqual(payload["position_overshoot_count"], 5)
        self.assertEqual(payload["x_count"], 40)
        self.assertEqual(payload["y_count"], 8)
        self.assertEqual(payload["z_count"], 3)
        self.assertEqual(payload["x_step_commanded"], 45)
        self.assertEqual(payload["y_step_commanded"], 8)
        self.assertEqual(payload["z_step_commanded"], 3)
        self.assertIsNone(payload["x_encoder_count"])
        self.assertIsNone(payload["y_encoder_count"])
        self.assertEqual(payload["mcu_time_us"], 1234)
        self.assertEqual(payload["coordinate_flags"], ["sample_overshot_event_position"])
        self.assertEqual(payload["led_gate_names"], ["led_red", "led_green"])
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertEqual(json.loads(record.to_json())["type"], "FRAME_EVENT")

        typed_scheduler_event = SchedulerFrameEvent(**scheduler_event.__dict__)
        self.assertEqual(typed_scheduler_event.to_protocol_record(), record)

        scheduler_event.hardware_outputs_enabled = True
        with self.assertRaisesRegex(
            ProtocolSerializationError, "hardware_outputs_enabled"
        ):
            FrameEventRecord.from_scheduler_event(scheduler_event)

    def test_frame_event_serializes_timed_output_event_flags(self):
        event_flags = (
            TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG
            | TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG
        )

        record = _frame_event_record(event_flags=event_flags)
        payload = record.to_json_dict()

        self.assertEqual(payload["event_flags"], event_flags)
        self.assertEqual(payload["event_flag_names"], ["frame_event", "xvs_rising"])

    def test_frame_event_rejects_unknown_or_mismatched_event_flags(self):
        with self.assertRaisesRegex(ValueError, "unknown timed-output-sequence flags"):
            _frame_event_record(event_flags=0x8000)

        with self.assertRaisesRegex(ValueError, "event_flag_names must match"):
            _frame_event_record(
                event_flags=TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG,
                event_flag_names=("xvs_rising",),
            )

    def test_canonical_v1_export_bridges_bootstrap_compatibility_fields(self):
        record = FrameEventRecord(
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=7,
            frame_id=100,
            stripe_frame_index=2,
            pattern="AF_RED_GREEN",
            led_gate_names=("led_red", "led_green"),
            trigger_output_name="camera_or_sync_trigger",
            coordinate_source_used="step_indexed",
            position_axis="X",
            event_position=40,
            sample_position=45,
            position_overshoot_count=5,
            x_count=40,
            y_count=8,
            z_count=3,
            x_step_commanded=45,
            y_step_commanded=8,
            z_step_commanded=3,
            x_encoder_count=None,
            y_encoder_count=None,
            coordinate_flags=("sample_overshot_event_position",),
            mcu_time_us=1234,
            hardware_outputs_enabled=False,
            status="ok",
        )

        payload = to_canonical_v1_json_dict(record)

        self.assertEqual(payload["protocol_version"], "1.0.0")
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["frame_id"], 100)
        self.assertEqual(payload["led_gate_names"], ["led_red", "led_green"])

    def test_canonical_v1_export_adds_missing_protocol_version_for_z_records(self):
        payload = to_canonical_v1_json_dict(ZScheduledRecord(seq=101))

        self.assertEqual(payload["protocol_version"], "1.0.0")
        self.assertEqual(payload["type"], "Z_SCHEDULED")
        self.assertEqual(payload["status"], "accepted")

    def test_timed_output_sequence_status_round_trips_canonical_jsonl(self):
        record = TimedOutputSequenceStatusRecord(
            protocol_version="1.0.0",
            scan_id="bench-sync-sink",
            seq=48,
            stripe_id=7,
            seq_id=9001,
            status="completed",
            reason="finite_completion",
            repeat_index=2,
            step_index=0,
            mcu_time_us=25_000,
        )

        decoded = decode_protocol_json_lines([to_json(record)])[0]

        self.assertIsInstance(decoded, TimedOutputSequenceStatusRecord)
        self.assertEqual(decoded.type, "TIMED_OUTPUT_SEQUENCE_STATUS")
        self.assertEqual(decoded.scan_id, "bench-sync-sink")
        self.assertEqual(decoded.seq, 48)
        self.assertEqual(decoded.stripe_id, 7)
        self.assertEqual(decoded.seq_id, 9001)
        self.assertEqual(decoded.status, "completed")
        self.assertEqual(decoded.reason, "finite_completion")
        self.assertEqual(decoded.repeat_index, 2)
        self.assertEqual(decoded.step_index, 0)
        self.assertEqual(decoded.mcu_time_us, 25_000)
        self.assertFalse(decoded.hardware_outputs_enabled)

    def test_canonical_v1_export_normalizes_prototype_protocol_fields(self):
        payloads = [
            {
                "type": "FRAME_EVENT",
                "protocol_version": 1,
                "status": "ok",
            },
            {
                "type": "SCHEDULER_TERMINAL",
                "protocol_version": 1,
                "status": "stopped",
            },
            {
                "type": "Z_APPLIED",
                "status": "ok",
            },
        ]

        canonical_payloads = [
            canonicalize_protocol_v1_payload(payload) for payload in payloads
        ]

        self.assertEqual(
            [payload["protocol_version"] for payload in canonical_payloads],
            ["1.0.0", "1.0.0", "1.0.0"],
        )
        self.assertEqual(canonical_payloads[0]["status"], "OK")
        self.assertEqual(canonical_payloads[1]["status"], "stopped")
        self.assertEqual(canonical_payloads[2]["status"], "ok")
        self.assertEqual(payloads[0]["protocol_version"], 1)
        self.assertNotIn("protocol_version", payloads[2])

    def test_z_records_preserve_canonical_fixture_version_without_runtime_churn(self):
        runtime_payload = ZScheduledRecord(seq=101).to_json_dict()
        fixture_payload = ZScheduledRecord(
            seq=101,
            protocol_version="1.0.0",
        ).to_json_dict()

        self.assertNotIn("protocol_version", runtime_payload)
        self.assertEqual(fixture_payload["protocol_version"], "1.0.0")

    def test_canonical_v1_export_rejects_unowned_protocol_versions(self):
        with self.assertRaisesRegex(ProtocolSerializationError, "unsupported"):
            canonicalize_protocol_v1_payload(
                {
                    "type": "FRAME_EVENT",
                    "protocol_version": "0.5.0",
                    "status": "ok",
                }
            )

    def test_protocol_jsonl_decoder_rejects_noncanonical_persisted_evidence(self):
        canonical = {
            "type": "FRAME_EVENT",
            "protocol_version": "1.0.0",
            "scan_id": "scan-a",
            "stripe_id": 7,
            "frame_id": 100,
            "stripe_frame_index": 2,
            "pattern": "AF_RED_GREEN",
            "coordinate_source_used": "step_indexed",
            "position_axis": "X",
            "event_position": 40,
            "sample_position": 45,
            "position_overshoot_count": 5,
            "x_count": 40,
            "y_count": 8,
            "z_count": 3,
            "x_step_commanded": 45,
            "y_step_commanded": 8,
            "z_step_commanded": 3,
            "x_encoder_count": None,
            "y_encoder_count": None,
            "coordinate_flags": ["sample_overshot_event_position"],
            "led_gate_names": ["led_red", "led_green"],
            "trigger_output_name": "camera_or_sync_trigger",
            "mcu_time_us": 1234,
            "hardware_outputs_enabled": False,
            "status": "OK",
        }
        noncanonical_payloads = (
            {**canonical, "protocol_version": 1},
            {**canonical, "status": "ok"},
            {
                key: value
                for key, value in canonical.items()
                if key != "protocol_version"
            },
        )

        for payload in noncanonical_payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(
                    ProtocolSerializationError, "noncanonical protocol-v1 evidence"
                ):
                    decode_protocol_json_lines([json.dumps(payload)])

    def test_terminal_event_defaults_to_hardware_outputs_disabled(self):
        record = SchedulerTerminalRecord(
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=7,
            status="stopped",
            reason_code="host_stop",
            emitted_frame_count=2,
            expected_frame_count=5,
            last_frame_id=101,
            next_frame_id=102,
            next_stripe_frame_index=2,
            mcu_time_us=900,
            message="stop requested during stripe execution",
        )

        payload = record.to_json_dict()

        self.assertEqual(payload["type"], "SCHEDULER_TERMINAL")
        self.assertEqual(payload["next_frame_id"], 102)
        self.assertFalse(payload["hardware_outputs_enabled"])

    def test_terminal_event_rejects_complete_status(self):
        terminal_fields = dict(
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=7,
            reason_code="host_stop",
            emitted_frame_count=2,
            expected_frame_count=5,
            last_frame_id=101,
            next_frame_id=102,
            next_stripe_frame_index=2,
            mcu_time_us=900,
            message="stop requested during stripe execution",
        )

        with self.assertRaisesRegex(ValueError, "stopped or fault"):
            SchedulerTerminalRecord(status="complete", **terminal_fields)
        with self.assertRaisesRegex(ValueError, "reason_code"):
            SchedulerTerminalRecord(
                status="stopped",
                reason_code="complete",
                **{
                    key: value
                    for key, value in terminal_fields.items()
                    if key != "reason_code"
                },
            )

    def test_scheduler_event_dispatches_frame_and_terminal_records(self):
        frame = SimpleNamespace(
            type="FRAME_EVENT",
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=7,
            frame_id=1,
            stripe_frame_index=0,
            pattern="BF_WHITE",
            coordinate_source_used="step_indexed",
            position_axis="Y",
            event_position=20,
            sample_position=20,
            position_overshoot_count=0,
            x_count=5,
            y_count=20,
            z_count=0,
            x_step_commanded=5,
            y_step_commanded=20,
            z_step_commanded=0,
            x_encoder_count=None,
            y_encoder_count=None,
            coordinate_flags=(),
            mcu_time_us=10,
            hardware_outputs_enabled=False,
            status="ok",
        )
        terminal = SimpleNamespace(
            type="SCHEDULER_TERMINAL",
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=7,
            status="fault",
            reason_code="scheduler_fault",
            emitted_frame_count=1,
            expected_frame_count=3,
            last_frame_id=1,
            next_frame_id=2,
            next_stripe_frame_index=1,
            mcu_time_us=12,
            hardware_outputs_enabled=False,
            message="simulated scheduler fault",
        )

        self.assertIsInstance(
            scheduler_event_to_protocol_record(frame), FrameEventRecord
        )
        self.assertIsInstance(
            scheduler_event_to_protocol_record(terminal), SchedulerTerminalRecord
        )

        with self.assertRaises(ProtocolSerializationError):
            scheduler_event_to_protocol_record(SimpleNamespace(type="OTHER"))

    def test_schedule_z_matches_command_payload_and_requires_a_target(self):
        command = ScheduleZCommand(
            seq=101,
            scan_id="scan_001",
            stripe_id=42,
            apply_at_position_count=1234567,
            apply_at_position_um=123.4567,
            apply_at_frame_id=1842,
            z_target_um=42.5,
            source="two_color_oblique_af",
            confidence=0.86,
            latency_model_id="lat_2026_07_01",
        )

        payload = command.to_json_dict()

        self.assertEqual(payload["cmd"], "scanner_sync_schedule_z")
        self.assertEqual(payload["seq"], 101)
        self.assertEqual(payload["apply_at_position_count"], 1234567)
        self.assertEqual(payload["apply_at_position_um"], 123.4567)
        self.assertEqual(payload["apply_at_frame_id"], 1842)
        self.assertEqual(payload["z_target_um"], 42.5)
        self.assertEqual(payload["latency_model_id"], "lat_2026_07_01")
        self.assertEqual(
            ScheduleZCommand.from_json_dict(payload).to_json_dict(), payload
        )

        with self.assertRaisesRegex(
            ProtocolSerializationError, "scanner_sync_schedule_z"
        ):
            ScheduleZCommand.from_json_dict({**payload, "cmd": "schedule_z"})

        with self.assertRaises(ValueError):
            ScheduleZCommand(
                seq=102,
                scan_id="scan_001",
                stripe_id=42,
                z_target_um=1.0,
            )

    def test_start_and_stop_commands_validate_canonical_payloads(self):
        start = ScannerSyncStartCommand(
            seq=10,
            scan_id="scan_001",
            stripe_id=42,
            next_frame_id=1000,
        )
        stop = ScannerSyncStopCommand(
            seq=11,
            scan_id="scan_001",
            stripe_id=42,
            reason="host_stop",
        )

        self.assertEqual(start.to_json_dict()["cmd"], "scanner_sync_start")
        self.assertEqual(start.to_json_dict()["next_frame_id"], 1000)
        self.assertEqual(
            ScannerSyncStartCommand.from_json_dict(start.to_json_dict()),
            start,
        )
        self.assertEqual(stop.to_json_dict()["cmd"], "scanner_sync_stop")
        self.assertEqual(stop.to_json_dict()["reason"], "host_stop")
        self.assertEqual(
            ScannerSyncStopCommand.from_json_dict(stop.to_json_dict()),
            stop,
        )

        with self.assertRaisesRegex(ProtocolSerializationError, "scanner_sync_start"):
            ScannerSyncStartCommand.from_json_dict({**start.to_json_dict(), "cmd": "start"})
        with self.assertRaisesRegex(ProtocolSerializationError, "scanner_sync_stop"):
            ScannerSyncStopCommand.from_json_dict({**stop.to_json_dict(), "cmd": "stop"})
        with self.assertRaisesRegex(ValueError, "seq"):
            ScannerSyncStartCommand(
                seq=-1,
                scan_id="scan_001",
                stripe_id=42,
                next_frame_id=1000,
            )
        with self.assertRaisesRegex(ValueError, "scan_id"):
            ScannerSyncStopCommand(
                seq=11,
                scan_id="",
                stripe_id=42,
                reason="host_stop",
            )
        with self.assertRaisesRegex(ValueError, "reason"):
            ScannerSyncStopCommand(
                seq=11,
                scan_id="scan_001",
                stripe_id=42,
                reason="unsupported",
            )

    def test_z_ack_records_are_json_safe_and_metadata_only_by_default(self):
        scheduled = ZScheduledRecord(seq=101)
        applied = ZAppliedRecord(
            seq=101,
            frame_id=1842,
            z_target_steps=3456,
            scan_id="scan_001",
            stripe_id=42,
            apply_target_kind="frame",
            apply_at_frame_id=1842,
        )
        rejected = ZRejectedRecord(seq=102, reason="too_late")

        self.assertEqual(scheduled.to_json_dict()["type"], "Z_SCHEDULED")
        self.assertEqual(scheduled.to_json_dict()["status"], "accepted")
        self.assertFalse(scheduled.to_json_dict()["hardware_outputs_enabled"])

        applied_payload = applied.to_json_dict()
        self.assertEqual(applied_payload["type"], "Z_APPLIED")
        self.assertEqual(applied_payload["frame_id"], 1842)
        self.assertEqual(applied_payload["z_target_steps"], 3456)
        self.assertEqual(applied_payload["z_cmd_count"], 3456)
        self.assertEqual(applied.z_cmd_count, applied.z_target_steps)
        self.assertFalse(applied_payload["hardware_outputs_enabled"])

        rejected_payload = json.loads(to_json(rejected))
        self.assertEqual(rejected_payload["type"], "Z_REJECTED")
        self.assertEqual(rejected_payload["reason"], "too_late")
        self.assertFalse(rejected_payload["hardware_outputs_enabled"])

    def test_z_ack_helpers_wrap_scheduler_decision_and_applied_event_shapes(self):
        accepted_decision = SimpleNamespace(
            accepted=True,
            status="accepted",
            reason=None,
            hardware_outputs_enabled=False,
            command=SimpleNamespace(
                scan_id="scan-a",
                stripe_id=7,
                command_id="z-1",
            ),
        )
        rejected_decision = SimpleNamespace(
            accepted=False,
            status="rejected",
            reason="insufficient_lookahead",
            hardware_outputs_enabled=False,
            command=SimpleNamespace(
                scan_id="scan-a",
                stripe_id=7,
                command_id="z-2",
            ),
        )
        applied_event = SimpleNamespace(
            type="Z_APPLIED",
            scan_id="scan-a",
            stripe_id=7,
            command_id="z-1",
            apply_target_kind="position",
            apply_at_frame_id=None,
            apply_at_position_count=80,
            frame_id=14,
            position=80,
            z_target_steps=25,
            hardware_outputs_enabled=False,
            status="ok",
        )

        scheduled = ZScheduledRecord.from_scheduler_decision(
            accepted_decision, seq=201
        )
        rejected = ZRejectedRecord.from_scheduler_decision(
            rejected_decision, seq=202
        )
        applied = ZAppliedRecord.from_scheduler_event(applied_event, seq=201)

        self.assertEqual(scheduled.to_json_dict()["command_id"], "z-1")
        self.assertEqual(rejected.to_json_dict()["reason"], "insufficient_lookahead")
        self.assertEqual(applied.to_json_dict()["z_cmd_count"], 25)
        self.assertEqual(applied.to_json_dict()["z_target_steps"], 25)
        self.assertEqual(applied.z_target_steps, 25)
        self.assertEqual(applied.to_json_dict()["apply_target_kind"], "position")

    def test_generic_to_json_dict_rejects_non_json_safe_values(self):
        self.assertEqual(to_json_dict({"ok": ("a", "b")}), {"ok": ["a", "b"]})

        with self.assertRaises(ProtocolSerializationError):
            to_json_dict({"bad": object()})


def _frame_event_record(
    *,
    event_flags: int = 0,
    event_flag_names=(),
) -> FrameEventRecord:
    return FrameEventRecord(
        protocol_version=1,
        scan_id="scan-a",
        stripe_id=7,
        frame_id=100,
        stripe_frame_index=2,
        pattern="AF_RED_GREEN",
        coordinate_source_used="step_indexed",
        position_axis="X",
        event_position=40,
        sample_position=40,
        position_overshoot_count=0,
        x_count=40,
        y_count=8,
        z_count=3,
        x_step_commanded=40,
        y_step_commanded=8,
        z_step_commanded=3,
        mcu_time_us=1234,
        event_flags=event_flags,
        event_flag_names=event_flag_names,
    )


if __name__ == "__main__":
    unittest.main()
