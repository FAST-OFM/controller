import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.sync_codec.decode import (  # noqa: E402
    decode_scanner_sync_response,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.encode import (  # noqa: E402
    encode_arm_af_window_command,
    encode_fire_af_window_now_command,
    encode_run_stationary_af_test_command,
    encode_run_timed_output_sequence_command,
    encode_scanner_sync_command,
    encode_schedule_z_command,
    encode_start_command,
    encode_stop_command,
    encode_timed_output_sequence_steps,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (  # noqa: E402
    ScannerSyncCodecError,
    ScannerSyncDecodeContext,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (  # noqa: E402
    RESPONSE_BINDINGS,
    EXPERIMENTAL_RESPONSE_BINDINGS,
    SCANNER_SYNC_ARM_AF_WINDOW_COMMAND,
    SCANNER_SYNC_FIRE_AF_WINDOW_NOW_COMMAND,
    SCANNER_SYNC_RUN_STATIONARY_AF_TEST_COMMAND,
    SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
    SCANNER_SYNC_START_COMMAND,
    SCANNER_SYNC_STOP_COMMAND,
    SCANNER_SYNC_SCHEDULE_Z_COMMAND,
    SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE_STATUS_RESPONSE,
)
from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    TIMED_OUTPUT_SEQUENCE_END_FLAG,
    TIMED_OUTPUT_SEQUENCE_EXPOSURE_END_FLAG,
    TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG,
    TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG,
    TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
    TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US,
    TIMED_OUTPUT_SEQUENCE_XVS_FALLING_FLAG,
    TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG,
    ArmAfWindowCommand,
    FireAfWindowNowCommand,
    RunStationaryAfTestCommand,
    RunTimedOutputSequenceCommand,
    ScannerSyncStartCommand,
    ScannerSyncStopCommand,
    ScheduleZCommand,
    TimedOutputSequenceStep,
    to_canonical_v1_json_dict,
)


class KlipperScannerSyncCodecTests(unittest.TestCase):
    def test_decode_context_rejects_unsupported_protocol_version(self):
        with self.assertRaisesRegex(ScannerSyncCodecError, "unsupported protocol_version"):
            ScannerSyncDecodeContext(scan_id="scan-a", protocol_version=2)

        with self.assertRaisesRegex(ScannerSyncCodecError, "led_gate_names"):
            ScannerSyncDecodeContext(  # type: ignore[arg-type]
                scan_id="scan-a",
                led_gate_names=["led_red"],
            )
        with self.assertRaisesRegex(ScannerSyncCodecError, "pattern_led_gate_names"):
            ScannerSyncDecodeContext(  # type: ignore[arg-type]
                scan_id="scan-a",
                pattern_led_gate_names=(["led_red"],),
            )

    def test_encodes_schedule_z_position_command_without_sending(self):
        encoded = encode_schedule_z_command(
            oid=3,
            command=ScheduleZCommand(
                seq=41,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=1200,
                z_target_um=42.125,
            ),
        )

        self.assertEqual(encoded.name, "scanner_sync_schedule_z")
        self.assertEqual(encoded.msgformat, SCANNER_SYNC_SCHEDULE_Z_COMMAND)
        self.assertEqual(encoded.args, (3, 41, 7, 1, 1200, 42125))

    def test_encodes_schedule_z_frame_command(self):
        encoded = encode_schedule_z_command(
            oid=3,
            command=ScheduleZCommand(
                seq=42,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=99,
                z_target_um=-3.5,
            ),
        )

        self.assertEqual(encoded.args, (3, 42, 7, 0, 99, -3500))

    def test_encodes_schedule_z_position_count_with_physical_traceability(self):
        encoded = encode_schedule_z_command(
            oid=3,
            command=ScheduleZCommand(
                seq=42,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=1200,
                apply_at_position_um=1199.75,
                z_target_um=-3.5,
            ),
        )

        self.assertEqual(encoded.args, (3, 42, 7, 1, 1200, -3500))

    def test_encodes_position_indexed_af_window_arm_command(self):
        encoded = encode_arm_af_window_command(
            oid=3,
            command=ArmAfWindowCommand(
                seq=45,
                scan_id="scan-a",
                stripe_id=7,
                frame_id=99,
                stripe_frame_index=4,
                position_axis="X",
                trigger_position_count=2400,
                pattern_id=1,
                settle_us=250,
                xvs_trigger_pulse_us=200,
                exposure_hold_us=1500,
            ),
        )

        self.assertEqual(encoded.name, "scanner_sync_arm_af_window")
        self.assertEqual(encoded.msgformat, SCANNER_SYNC_ARM_AF_WINDOW_COMMAND)
        self.assertEqual(encoded.args, (3, 45, 7, 99, 4, "X", 2400, 1, 250, 200, 1500))

    def test_encodes_diagnostic_af_window_now_command(self):
        encoded = encode_fire_af_window_now_command(
            oid=3,
            command=FireAfWindowNowCommand(
                seq=46,
                scan_id="scan-a",
                stripe_id=7,
                frame_id=100,
                stripe_frame_index=5,
                position_axis="Y",
                event_position_count=120,
                pattern_id=1,
                settle_us=250,
                xvs_trigger_pulse_us=200,
                exposure_hold_us=1500,
            ),
        )

        self.assertEqual(encoded.name, "scanner_sync_fire_af_window_now")
        self.assertEqual(encoded.msgformat, SCANNER_SYNC_FIRE_AF_WINDOW_NOW_COMMAND)
        self.assertEqual(encoded.args, (3, 46, 7, 100, 5, "Y", 120, 1, 250, 200, 1500))

    def test_encodes_stationary_af_timing_test_command(self):
        command = RunStationaryAfTestCommand(
            seq=47,
            scan_id="scan-a",
            stripe_id=7,
            first_frame_id=100,
            frame_count=5,
            frame_period_us=25_000,
            position_axis="X",
            event_position_count=120,
            pattern_id=1,
            settle_us=1_000,
            xvs_trigger_pulse_us=200,
            exposure_hold_us=4_000,
        )

        encoded = encode_run_stationary_af_test_command(oid=3, command=command)

        self.assertEqual(encoded.name, "scanner_sync_run_stationary_af_test")
        self.assertEqual(encoded.msgformat, SCANNER_SYNC_RUN_STATIONARY_AF_TEST_COMMAND)
        self.assertEqual(
            encoded.args,
            (3, 47, 7, 100, 5, 25_000, "X", 120, 1, 1_000, 200, 4_000),
        )
        self.assertEqual(encode_scanner_sync_command(oid=3, command=command), encoded)

    def test_encodes_generic_timed_output_sequence_command(self):
        rg_and_xvs_mask = (
            TIMED_OUTPUT_SEQUENCE_LED_RED_BIT
            | TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT
            | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT
        )
        red_and_green = TIMED_OUTPUT_SEQUENCE_LED_RED_BIT | TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT

        command = RunTimedOutputSequenceCommand(
            seq=48,
            scan_id="bench-sync-sink",
            stripe_id=7,
            seq_id=9001,
            repeat_count=0,
            frame_id_base=200,
            pattern_id=1,
            idle_output_values=TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
            steps=(
                TimedOutputSequenceStep(
                    output_mask=rg_and_xvs_mask | TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                    output_values=red_and_green,
                    delay_us=1_000,
                ),
                TimedOutputSequenceStep(
                    output_mask=TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                    output_values=TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                    delay_us=200,
                    event_flags=(
                        TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG
                        | TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG
                        | TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG
                    ),
                ),
                TimedOutputSequenceStep(
                    output_mask=TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                    output_values=0,
                    delay_us=23_800,
                    event_flags=TIMED_OUTPUT_SEQUENCE_XVS_FALLING_FLAG,
                ),
                TimedOutputSequenceStep(
                    output_mask=0,
                    output_values=0,
                    delay_us=1_000,
                    event_flags=TIMED_OUTPUT_SEQUENCE_EXPOSURE_END_FLAG,
                ),
                TimedOutputSequenceStep(
                    output_mask=rg_and_xvs_mask | TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                    output_values=TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                    delay_us=1_000,
                    event_flags=TIMED_OUTPUT_SEQUENCE_END_FLAG,
                ),
            ),
        )

        encoded = encode_run_timed_output_sequence_command(oid=3, command=command)
        encoded_steps = encode_timed_output_sequence_steps(command.steps)

        self.assertEqual(encoded.name, "scanner_sync_run_timed_output_sequence")
        self.assertEqual(
            encoded.msgformat,
            SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
        )
        self.assertEqual(
            encoded.args[:15],
            (
                3,
                48,
                7,
                9001,
                0,
                0,
                -1,
                0,
                200,
                1,
                15,
                0,
                15,
                TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                5,
            ),
        )
        self.assertEqual(encoded.args[-1], encoded_steps)
        self.assertEqual(
            encoded_steps,
            b"\x0f\x06\xe8\x03\x00\x00\x00\x00"
            b"\x08\x08\xc8\x00\x00\x00\x13\x00"
            b"\x08\x00\xf8\\\x00\x00\x04\x00"
            b"\x00\x00\xe8\x03\x00\x00 \x00"
            b"\x0f\x01\xe8\x03\x00\x00\x08\x00",
        )
        self.assertEqual(encode_scanner_sync_command(oid=3, command=command), encoded)

    def test_rejects_invalid_timed_output_sequence_bits(self):
        with self.assertRaisesRegex(ValueError, "outside output_mask"):
            TimedOutputSequenceStep(
                output_mask=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                output_values=TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
                delay_us=100,
            )

        with self.assertRaisesRegex(ValueError, "unknown timed-output-sequence flags"):
            TimedOutputSequenceStep(
                output_mask=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                delay_us=100,
                event_flags=0x8000,
            )

        with self.assertRaisesRegex(ValueError, "unknown timed-output-sequence outputs"):
            TimedOutputSequenceStep(
                output_mask=0x80,
                output_values=0,
                delay_us=100,
            )

        with self.assertRaisesRegex(ValueError, "delay_us must be <="):
            TimedOutputSequenceStep(
                output_mask=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                delay_us=TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US + 1,
            )

        with self.assertRaisesRegex(ValueError, "diagnostic_immediate mode"):
            RunTimedOutputSequenceCommand(
                seq=48,
                scan_id="bench-sync-sink",
                stripe_id=7,
                seq_id=9001,
                repeat_count=1,
                mode="position_armed",
                start_condition="position_count",
                start_position_count=1200,
                steps=(
                    TimedOutputSequenceStep(
                        output_mask=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                        output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                        delay_us=100,
                    ),
                ),
            )

        with self.assertRaisesRegex(ValueError, "diagnostic-only"):
            RunTimedOutputSequenceCommand(
                seq=48,
                scan_id="bench-sync-sink",
                stripe_id=7,
                seq_id=9001,
                repeat_count=1,
                steps=(
                    TimedOutputSequenceStep(
                        output_mask=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                        output_values=TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                        delay_us=100,
                    ),
                ),
                diagnostic_only=False,
            )

    def test_rejects_non_diagnostic_fire_af_window_now_command(self):
        with self.assertRaisesRegex(ValueError, "diagnostic-only"):
            FireAfWindowNowCommand(
                seq=46,
                scan_id="scan-a",
                stripe_id=7,
                frame_id=100,
                stripe_frame_index=5,
                event_position_count=120,
                settle_us=250,
                xvs_trigger_pulse_us=200,
                exposure_hold_us=1500,
                diagnostic_only=False,
            )

    def test_rejects_schedule_z_with_both_frame_and_position_wire_targets(self):
        ambiguous_commands = (
            ScheduleZCommand(
                seq=42,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_count=1200,
                apply_at_frame_id=99,
                z_target_um=-3.5,
            ),
            ScheduleZCommand(
                seq=43,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_position_um=1199.75,
                apply_at_frame_id=99,
                z_target_um=-3.5,
            ),
        )

        for command in ambiguous_commands:
            with self.subTest(seq=command.seq):
                with self.assertRaisesRegex(
                    ScannerSyncCodecError, "both frame and position"
                ):
                    encode_schedule_z_command(oid=3, command=command)

    def test_encodes_start_and_stop_commands_without_sending(self):
        start = encode_start_command(
            oid=3,
            command=ScannerSyncStartCommand(
                seq=40,
                scan_id="scan-a",
                stripe_id=7,
                next_frame_id=99,
            ),
        )
        stop = encode_stop_command(
            oid=3,
            command=ScannerSyncStopCommand(
                seq=41,
                scan_id="scan-a",
                stripe_id=7,
                reason="host_stop",
            ),
        )

        self.assertEqual(start.name, "scanner_sync_start")
        self.assertEqual(start.msgformat, SCANNER_SYNC_START_COMMAND)
        self.assertEqual(start.args, (3, 99))
        self.assertEqual(stop.name, "scanner_sync_stop")
        self.assertEqual(stop.msgformat, SCANNER_SYNC_STOP_COMMAND)
        self.assertEqual(stop.args, (3, 0))

    def test_dispatches_typed_command_encoding_and_rejects_unsupported_dto(self):
        start = ScannerSyncStartCommand(
            seq=40,
            scan_id="scan-a",
            stripe_id=7,
            next_frame_id=99,
        )

        self.assertEqual(
            encode_scanner_sync_command(oid=3, command=start),
            encode_start_command(oid=3, command=start),
        )
        arm = ArmAfWindowCommand(
            seq=45,
            scan_id="scan-a",
            stripe_id=7,
            frame_id=99,
            stripe_frame_index=4,
            trigger_position_count=2400,
            settle_us=250,
            xvs_trigger_pulse_us=200,
            exposure_hold_us=1500,
        )
        self.assertEqual(
            encode_scanner_sync_command(oid=3, command=arm),
            encode_arm_af_window_command(oid=3, command=arm),
        )
        with self.assertRaisesRegex(ScannerSyncCodecError, "unsupported"):
            encode_scanner_sync_command(oid=3, command=object())  # type: ignore[arg-type]

    def test_encodes_schedule_z_nanometers_with_explicit_tie_rounding(self):
        positive = encode_schedule_z_command(
            oid=3,
            command=ScheduleZCommand(
                seq=43,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=99,
                z_target_um=0.0005,
            ),
        )
        negative = encode_schedule_z_command(
            oid=3,
            command=ScheduleZCommand(
                seq=44,
                scan_id="scan-a",
                stripe_id=7,
                apply_at_frame_id=99,
                z_target_um=-0.0005,
            ),
        )

        self.assertEqual(positive.args[-1], 1)
        self.assertEqual(negative.args[-1], -1)

    def test_decodes_frame_event_response_as_metadata_only_protocol_record(self):
        record = decode_scanner_sync_response(
            "FRAME_EVENT",
            {
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
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
                pattern_led_gate_names=(("led_white",), ("led_red", "led_green")),
                trigger_output_name="mks_pd6",
            ),
        )

        self.assertEqual(record.type, "FRAME_EVENT")
        self.assertEqual(record.scan_id, "scan-a")
        self.assertEqual(record.stripe_id, 7)
        self.assertEqual(record.frame_id, 12)
        self.assertEqual(record.stripe_frame_index, 2)
        self.assertEqual(record.pattern, "AF_RED_GREEN")
        self.assertEqual(record.led_gate_names, ("led_red", "led_green"))
        self.assertEqual(record.trigger_output_name, "mks_pd6")
        self.assertEqual(record.coordinate_source_used, "step_indexed")
        self.assertEqual(record.position_axis, "X")
        self.assertEqual(record.event_position, 200)
        self.assertEqual(record.sample_position, 200)
        self.assertEqual(record.x_count, 200)
        self.assertEqual(record.y_count, 12)
        self.assertEqual(record.z_count, 5)
        self.assertEqual(record.x_step_commanded, 200)
        self.assertEqual(record.y_step_commanded, 12)
        self.assertEqual(record.z_step_commanded, 5)
        self.assertEqual(record.mcu_time_us, 4000)
        self.assertIsNone(record.x_encoder_count)
        self.assertIsNone(record.y_encoder_count)
        self.assertEqual(record.coordinate_flags, ())
        self.assertFalse(record.hardware_outputs_enabled)
        self.assertNotIn("linux_arrival_time_ns", record.to_json_dict())
        self.assertNotIn("host_wall_clock", record.to_json_dict())

    def test_decodes_timed_output_frame_event_flags_as_host_metadata(self):
        event_flags = (
            TIMED_OUTPUT_SEQUENCE_FRAME_EVENT_FLAG
            | TIMED_OUTPUT_SEQUENCE_EXPOSURE_START_FLAG
            | TIMED_OUTPUT_SEQUENCE_XVS_RISING_FLAG
        )

        record = decode_scanner_sync_response(
            "FRAME_EVENT",
            {
                "frame_id": 200,
                "stripe_id": 7,
                "stripe_frame_index": 0,
                "pattern_id": 1,
                "position_axis": 0,
                "event_position": 1200,
                "x_count": 1200,
                "y_count": 80,
                "z_count": 0,
                "mcu_time_us": 25_000,
                "status": 0,
                "flags": event_flags,
            },
            context=ScannerSyncDecodeContext(
                scan_id="bench-sync-sink",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
            ),
        )

        self.assertEqual(record.event_flags, event_flags)
        self.assertEqual(
            record.event_flag_names,
            ("frame_event", "xvs_rising", "exposure_start"),
        )
        payload = record.to_json_dict()
        self.assertEqual(payload["event_flags"], event_flags)
        self.assertEqual(
            payload["event_flag_names"],
            ["frame_event", "xvs_rising", "exposure_start"],
        )
        self.assertEqual(record.mcu_time_us, 25_000)
        self.assertNotIn("linux_arrival_time_ns", payload)
        self.assertNotIn("host_wall_clock", payload)

    def test_rejects_unknown_frame_event_flags(self):
        with self.assertRaisesRegex(
            ScannerSyncCodecError,
            "unsupported frame event flags",
        ):
            decode_scanner_sync_response(
                "FRAME_EVENT",
                {
                    "frame_id": 200,
                    "stripe_id": 7,
                    "stripe_frame_index": 0,
                    "pattern_id": 1,
                    "position_axis": 0,
                    "event_position": 1200,
                    "x_count": 1200,
                    "y_count": 80,
                    "z_count": 0,
                    "mcu_time_us": 25_000,
                    "status": 0,
                    "flags": 0x8000,
                },
                context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
            )

    def test_decodes_frame_event_response_with_live_coordinate_metadata(self):
        record = decode_scanner_sync_response(
            "FRAME_EVENT",
            {
                "frame_id": 12,
                "stripe_id": 7,
                "stripe_frame_index": 2,
                "pattern_id": 1,
                "position_axis": 0,
                "event_position": 200,
                "sample_position": 203,
                "position_overshoot_count": 3,
                "x_count": 1203,
                "y_count": 412,
                "z_count": 5,
                "x_step_commanded": 203,
                "y_step_commanded": 12,
                "z_step_commanded": 6,
                "x_encoder_count": 1203,
                "y_encoder_count": 412,
                "coordinate_flags": ["sample_overshot_event_position"],
                "mcu_time_us": 4000,
                "status": 0,
                "flags": 0,
            },
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                coordinate_source_used="hybrid",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
            ),
        )

        self.assertEqual(record.coordinate_source_used, "hybrid")
        self.assertEqual(record.event_position, 200)
        self.assertEqual(record.sample_position, 203)
        self.assertEqual(record.position_overshoot_count, 3)
        self.assertEqual(record.x_count, 1203)
        self.assertEqual(record.y_count, 412)
        self.assertEqual(record.z_count, 5)
        self.assertEqual(record.x_step_commanded, 203)
        self.assertEqual(record.y_step_commanded, 12)
        self.assertEqual(record.z_step_commanded, 6)
        self.assertEqual(record.x_encoder_count, 1203)
        self.assertEqual(record.y_encoder_count, 412)
        self.assertEqual(record.coordinate_flags, ("sample_overshot_event_position",))

    def test_decodes_frame_event_derived_sample_metadata(self):
        record = decode_scanner_sync_response(
            "FRAME_EVENT",
            {
                "frame_id": 12,
                "stripe_id": 7,
                "stripe_frame_index": 2,
                "pattern_id": 1,
                "position_axis": 0,
                "event_position": 200,
                "position_overshoot_count": -3,
                "x_count": 200,
                "y_count": 12,
                "z_count": 5,
                "coordinate_flags": "sample_overshot_event_position",
                "mcu_time_us": 4000,
                "status": 0,
                "flags": 0,
            },
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        self.assertEqual(record.sample_position, 197)
        self.assertEqual(record.position_overshoot_count, -3)
        self.assertEqual(record.coordinate_flags, ("sample_overshot_event_position",))

    def test_rejects_disagreeing_frame_event_sample_metadata(self):
        payload = {
            "frame_id": 12,
            "stripe_id": 7,
            "stripe_frame_index": 2,
            "pattern_id": 1,
            "position_axis": 0,
            "event_position": 200,
            "sample_position": 203,
            "position_overshoot_count": 4,
            "x_count": 200,
            "y_count": 12,
            "z_count": 5,
            "mcu_time_us": 4000,
            "status": 0,
            "flags": 0,
        }

        with self.assertRaisesRegex(ScannerSyncCodecError, "disagree"):
            decode_scanner_sync_response(
                "FRAME_EVENT",
                payload,
                context=ScannerSyncDecodeContext(scan_id="scan-a"),
            )

    def test_decodes_canonical_frame_event_ok_status_string(self):
        record = decode_scanner_sync_response(
            "FRAME_EVENT",
            {
                "frame_id": 12,
                "stripe_id": 7,
                "stripe_frame_index": 2,
                "pattern_id": 1,
                "position_axis": "X",
                "event_position": 200,
                "x_count": 200,
                "y_count": 12,
                "z_count": 5,
                "mcu_time_us": 4000,
                "status": "OK",
                "flags": 0,
            },
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        self.assertEqual(record.status, "ok")
        self.assertEqual(record.to_json_dict()["status"], "ok")
        self.assertEqual(to_canonical_v1_json_dict(record)["status"], "OK")

    def test_decodes_scheduler_terminal_and_z_ack_records(self):
        context = ScannerSyncDecodeContext(scan_id="scan-a")

        terminal = decode_scanner_sync_response(
            "SCHEDULER_TERMINAL",
            {
                "stripe_id": 7,
                "status": 0,
                "reason": 0,
                "emitted_frame_count": 3,
                "expected_frame_count": 5,
                "last_frame_id": 102,
                "next_frame_id": 103,
                "next_stripe_frame_index": 3,
                "mcu_time_us": 9000,
            },
            context=context,
        )
        scheduled = decode_scanner_sync_response(
            "Z_SCHEDULED",
            {"seq": 10, "stripe_id": 7, "status": 0},
            context=context,
        )
        applied = decode_scanner_sync_response(
            "Z_APPLIED",
            {"seq": 10, "frame_id": 110, "z_cmd_count": 33, "status": 0},
            context=context,
        )
        rejected = decode_scanner_sync_response(
            "Z_REJECTED",
            {"seq": 11, "reason": 3, "status": 1},
            context=context,
        )

        self.assertEqual(terminal.type, "SCHEDULER_TERMINAL")
        self.assertEqual(terminal.status, "stopped")
        self.assertEqual(terminal.reason_code, "host_stop")
        self.assertEqual(terminal.stripe_id, 7)
        self.assertEqual(terminal.last_frame_id, 102)
        self.assertEqual(terminal.next_stripe_frame_index, 3)
        self.assertFalse(terminal.hardware_outputs_enabled)
        self.assertEqual(scheduled.type, "Z_SCHEDULED")
        self.assertEqual(applied.z_target_steps, 33)
        self.assertEqual(applied.z_cmd_count, 33)
        self.assertIsNone(applied.stripe_id)
        self.assertEqual(rejected.reason, "insufficient_lookahead")
        self.assertTrue(
            all(
                record.hardware_outputs_enabled is False
                for record in (terminal, scheduled, applied, rejected)
            )
        )

    def test_decodes_timed_output_sequence_status_response(self):
        record = decode_scanner_sync_response(
            "TIMED_OUTPUT_SEQUENCE_STATUS",
            {
                "seq": 48,
                "stripe_id": 7,
                "seq_id": 9001,
                "status": 3,
                "reason": 3,
                "repeat_index": 2,
                "step_index": 0,
                "mcu_time_us": 25_000,
            },
            context=ScannerSyncDecodeContext(scan_id="bench-sync-sink"),
        )

        self.assertEqual(record.type, "TIMED_OUTPUT_SEQUENCE_STATUS")
        self.assertEqual(record.scan_id, "bench-sync-sink")
        self.assertEqual(record.seq, 48)
        self.assertEqual(record.stripe_id, 7)
        self.assertEqual(record.seq_id, 9001)
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.reason, "finite_completion")
        self.assertEqual(record.repeat_index, 2)
        self.assertEqual(record.step_index, 0)
        self.assertEqual(record.mcu_time_us, 25_000)
        self.assertFalse(record.hardware_outputs_enabled)

    def test_decodes_scheduler_terminal_negative_last_frame_id_as_absent(self):
        terminal = decode_scanner_sync_response(
            "SCHEDULER_TERMINAL",
            {
                "stripe_id": 7,
                "status": 0,
                "reason": 0,
                "emitted_frame_count": 0,
                "expected_frame_count": 5,
                "last_frame_id": -1,
                "next_frame_id": 103,
                "next_stripe_frame_index": 0,
                "mcu_time_us": 9000,
            },
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        self.assertIsNone(terminal.last_frame_id)

    def test_decodes_position_stream_exhausted_terminal_reason(self):
        terminal = decode_scanner_sync_response(
            "SCHEDULER_TERMINAL",
            {
                "stripe_id": 7,
                "status": 1,
                "reason": 3,
                "emitted_frame_count": 2,
                "expected_frame_count": 5,
                "last_frame_id": 101,
                "next_frame_id": 102,
                "next_stripe_frame_index": 2,
                "mcu_time_us": 9000,
            },
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        self.assertEqual(terminal.status, "fault")
        self.assertEqual(terminal.reason_code, "position_stream_exhausted")

    def test_rejects_missing_or_unknown_response_fields(self):
        context = ScannerSyncDecodeContext(scan_id="scan-a")

        with self.assertRaisesRegex(ScannerSyncCodecError, "missing"):
            decode_scanner_sync_response("FRAME_EVENT", {"frame_id": 1}, context=context)
        with self.assertRaisesRegex(ScannerSyncCodecError, "unsupported"):
            decode_scanner_sync_response(
                "SCHEDULER_TERMINAL",
                {
                    "status": 99,
                    "reason": 0,
                    "emitted_frame_count": 0,
                    "expected_frame_count": 0,
                    "next_frame_id": 0,
                    "mcu_time_us": 0,
                },
                context=context,
            )

    def test_decodes_every_registered_response_binding_to_matching_protocol_type(self):
        context = ScannerSyncDecodeContext(scan_id="scan-a")
        payloads = {
            "FRAME_EVENT": {
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
            "SCHEDULER_TERMINAL": {
                "stripe_id": 7,
                "status": 0,
                "reason": 0,
                "emitted_frame_count": 3,
                "expected_frame_count": 5,
                "next_frame_id": 103,
                "mcu_time_us": 9000,
            },
            "Z_SCHEDULED": {"seq": 10, "stripe_id": 7, "status": 0},
            "Z_APPLIED": {
                "seq": 10,
                "frame_id": 110,
                "z_cmd_count": 33,
                "status": 0,
            },
            "Z_REJECTED": {"seq": 11, "reason": 3, "status": 1},
            "TIMED_OUTPUT_SEQUENCE_STATUS": {
                "seq": 48,
                "stripe_id": 7,
                "seq_id": 9001,
                "status": 0,
                "reason": 0,
                "repeat_index": 0,
                "step_index": 0,
                "mcu_time_us": 9000,
            },
        }

        self.assertEqual(
            [
                decode_scanner_sync_response(
                    binding.protocol_event_type,
                    payloads[binding.protocol_event_type],
                    context=context,
                ).type
                for binding in RESPONSE_BINDINGS
            ],
            [binding.protocol_event_type for binding in RESPONSE_BINDINGS],
        )

        self.assertEqual(
            [
                decode_scanner_sync_response(
                    binding.protocol_event_type,
                    payloads[binding.protocol_event_type],
                    context=context,
                ).type
                for binding in EXPERIMENTAL_RESPONSE_BINDINGS
            ],
            [binding.protocol_event_type for binding in EXPERIMENTAL_RESPONSE_BINDINGS],
        )

        self.assertEqual(
            SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE_STATUS_RESPONSE,
            "scanner_sync_timed_output_sequence_status oid=%c seq=%u stripe_id=%u "
            "seq_id=%u status=%c reason=%c repeat_index=%u step_index=%u "
            "mcu_time_us=%u",
        )

    def test_phase1_z_applied_wire_payload_does_not_require_stripe_id(self):
        context = ScannerSyncDecodeContext(scan_id="scan-a")

        record = decode_scanner_sync_response(
            "Z_APPLIED",
            {"seq": 10, "frame_id": 110, "z_cmd_count": 33, "status": 0},
            context=context,
        )

        self.assertEqual(record.type, "Z_APPLIED")
        self.assertEqual(record.scan_id, "scan-a")
        self.assertIsNone(record.stripe_id)
        self.assertEqual(record.frame_id, 110)
        self.assertEqual(record.z_target_steps, 33)
        self.assertEqual(record.z_cmd_count, 33)

    def test_decodes_canonical_z_target_steps_alias_for_z_applied(self):
        record = decode_scanner_sync_response(
            "Z_APPLIED",
            {"seq": 10, "frame_id": 110, "z_target_steps": 33, "status": 0},
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        self.assertEqual(record.type, "Z_APPLIED")
        self.assertEqual(record.z_target_steps, 33)
        self.assertEqual(record.z_cmd_count, 33)

    def test_rejects_unsupported_frame_flags_and_status_codes(self):
        context = ScannerSyncDecodeContext(scan_id="scan-a")
        payload = {
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
            "flags": 0x8000,
        }

        with self.assertRaisesRegex(ScannerSyncCodecError, "flags"):
            decode_scanner_sync_response("FRAME_EVENT", payload, context=context)

        payload = {**payload, "status": 1, "flags": 0}
        with self.assertRaisesRegex(ScannerSyncCodecError, "status"):
            decode_scanner_sync_response("FRAME_EVENT", payload, context=context)


if __name__ == "__main__":
    unittest.main()
