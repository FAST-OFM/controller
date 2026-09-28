import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.sync_codec.command_boundary import (  # noqa: E402
    POLICY,
    ScannerSyncCommandBoundaryContext,
    ScannerSyncCommandBoundaryError,
    parse_validated_scanner_sync_commands,
    parse_validated_schedule_z_commands,
    validate_host_command_records,
)
from scanner_firmware.planning.z_scheduler.predictive import ApplyPositionCountBasis  # noqa: E402
from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    RunStationaryAfTestCommand,
    RunTimedOutputSequenceCommand,
    ScannerSyncStartCommand,
    ScannerSyncStopCommand,
    ScheduleZCommand,
    TIMED_OUTPUT_SEQUENCE_END_FLAG,
    TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
    TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
    TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US,
)


class KlipperScannerSyncCommandBoundaryTests(unittest.TestCase):
    def test_accepts_future_schedule_z_records_as_pure_data(self):
        report = validate_host_command_records(
            [
                {
                    "cmd": "scanner_sync_schedule_z",
                    "seq": 10,
                    "scan_id": "scan-a",
                    "stripe_id": 1,
                    "apply_at_frame_id": 12,
                    "z_target_um": 42.5,
                    "hardware_outputs_enabled": False,
                },
                {
                    "cmd": "scanner_sync_schedule_z",
                    "seq": 11,
                    "scan_id": "scan-a",
                    "stripe_id": 1,
                    "apply_at_position_count": 1200,
                    "z_target_um": -3,
                },
            ],
            context=ScannerSyncCommandBoundaryContext(expected_scan_id="scan-a"),
        )

        self.assertTrue(report.accepted)
        self.assertEqual(report.record_count, 2)
        self.assertEqual(
            report.command_names,
            ("scanner_sync_schedule_z", "scanner_sync_schedule_z"),
        )
        self.assertEqual(report.seqs, (10, 11))
        self.assertEqual(report.start_count, 0)
        self.assertEqual(report.stop_count, 0)
        self.assertEqual(report.schedule_z_count, 2)
        self.assertFalse(report.hardware_outputs_enabled)
        self.assertEqual(
            report.to_json_dict(),
            {
                "accepted": True,
                "record_count": 2,
                "command_names": [
                    "scanner_sync_schedule_z",
                    "scanner_sync_schedule_z",
                ],
                "seqs": [10, 11],
                "start_count": 0,
                "stop_count": 0,
                "schedule_z_count": 2,
                "stationary_af_test_count": 0,
                "timed_output_sequence_count": 0,
                "dry_run": True,
                "replay": True,
                "hardware_outputs_enabled": False,
            },
        )

    def test_parses_validated_schedule_z_records_to_typed_commands(self):
        commands = parse_validated_schedule_z_commands(
            [
                {
                    "cmd": "scanner_sync_schedule_z",
                    "seq": 3,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "apply_at_frame_id": 9,
                    "z_target_um": 1.25,
                    "source": "autofocus",
                    "confidence": 0.75,
                }
            ],
            context=ScannerSyncCommandBoundaryContext(expected_first_seq=3),
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].seq, 3)
        self.assertEqual(commands[0].scan_id, "scan-a")
        self.assertEqual(commands[0].apply_at_frame_id, 9)
        self.assertIsNone(commands[0].apply_at_position_count)
        self.assertEqual(commands[0].z_target_um, 1.25)
        self.assertEqual(commands[0].cmd, "scanner_sync_schedule_z")

    def test_normalizes_physical_apply_position_with_explicit_rounding_basis(self):
        commands = parse_validated_schedule_z_commands(
            [
                {
                    "cmd": "scanner_sync_schedule_z",
                    "seq": 3,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "apply_at_position_um": 100.325,
                    "z_target_um": 1.25,
                    "source": "autofocus",
                    "latency_model_id": "lat-model-a",
                }
            ],
            context=ScannerSyncCommandBoundaryContext(
                expected_first_seq=3,
                current_position_count=1000,
                position_direction=1,
                apply_position_count_basis=ApplyPositionCountBasis(
                    counts_per_um=10,
                    position_um_origin=0,
                    position_count_origin=0,
                ),
            ),
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].apply_at_position_count, 1004)
        self.assertEqual(commands[0].apply_at_position_um, 100.325)
        self.assertEqual(commands[0].latency_model_id, "lat-model-a")

    def test_reverse_physical_apply_position_rounds_down_by_count_direction(self):
        commands = parse_validated_schedule_z_commands(
            [
                {
                    "cmd": "scanner_sync_schedule_z",
                    "seq": 3,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "apply_at_position_um": 100.325,
                    "z_target_um": 1.25,
                }
            ],
            context=ScannerSyncCommandBoundaryContext(
                expected_first_seq=3,
                current_position_count=1200,
                position_direction=-1,
                apply_position_count_basis=ApplyPositionCountBasis(
                    counts_per_um=10,
                    position_um_origin=0,
                    position_count_origin=0,
                ),
            ),
        )

        self.assertEqual(commands[0].apply_at_position_count, 1003)

    def test_integer_count_target_wins_over_physical_traceability(self):
        commands = parse_validated_schedule_z_commands(
            [
                {
                    "cmd": "scanner_sync_schedule_z",
                    "seq": 3,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "apply_at_position_count": 1005,
                    "apply_at_position_um": 100.325,
                    "z_target_um": 1.25,
                }
            ],
            context=ScannerSyncCommandBoundaryContext(
                expected_first_seq=3,
                current_position_count=1000,
                position_direction=1,
            ),
        )

        self.assertEqual(commands[0].apply_at_position_count, 1005)
        self.assertEqual(commands[0].apply_at_position_um, 100.325)

    def test_rejects_schedule_z_with_both_frame_and_position_target_kinds(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "one target kind"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_schedule_z",
                        "seq": 3,
                        "scan_id": "scan-a",
                        "stripe_id": 7,
                        "apply_at_frame_id": 9,
                        "apply_at_position_count": 1005,
                        "z_target_um": 1.25,
                    }
                ],
                context=ScannerSyncCommandBoundaryContext(expected_first_seq=3),
            )

    def test_rejects_physical_apply_position_without_explicit_basis_or_direction(self):
        physical_record = {
            "cmd": "scanner_sync_schedule_z",
            "seq": 3,
            "scan_id": "scan-a",
            "stripe_id": 7,
            "apply_at_position_um": 100.325,
            "z_target_um": 1.25,
        }

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "basis"):
            validate_host_command_records(
                [physical_record],
                context=ScannerSyncCommandBoundaryContext(position_direction=1),
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "position_direction"):
            validate_host_command_records(
                [physical_record],
                context=ScannerSyncCommandBoundaryContext(
                    apply_position_count_basis=ApplyPositionCountBasis(counts_per_um=10),
                ),
            )

    def test_accepts_start_stop_and_schedule_z_as_typed_command_dtos(self):
        commands = parse_validated_scanner_sync_commands(
            [
                {
                    "cmd": "scanner_sync_start",
                    "seq": 20,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "next_frame_id": 100,
                },
                _schedule_z(
                    seq=21,
                    scan_id="scan-a",
                    stripe_id=7,
                    apply_at_frame_id=110,
                ),
                {
                    "cmd": "scanner_sync_stop",
                    "seq": 22,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "reason": "host_stop",
                },
            ],
            context=ScannerSyncCommandBoundaryContext(
                expected_scan_id="scan-a",
                expected_stripe_id=7,
                expected_first_seq=20,
            ),
        )

        self.assertIsInstance(commands[0], ScannerSyncStartCommand)
        self.assertIsInstance(commands[1], ScheduleZCommand)
        self.assertIsInstance(commands[2], ScannerSyncStopCommand)
        self.assertEqual(commands[0].next_frame_id, 100)
        self.assertEqual(commands[2].reason, "host_stop")

        report = validate_host_command_records(
            [command.to_json_dict() for command in commands],
            context=ScannerSyncCommandBoundaryContext(
                expected_scan_id="scan-a",
                expected_stripe_id=7,
                expected_first_seq=20,
            ),
        )
        self.assertEqual(
            report.command_names,
            (
                "scanner_sync_start",
                "scanner_sync_schedule_z",
                "scanner_sync_stop",
            ),
        )
        self.assertEqual(report.start_count, 1)
        self.assertEqual(report.stop_count, 1)
        self.assertEqual(report.schedule_z_count, 1)
        self.assertEqual(report.stationary_af_test_count, 0)

    def test_accepts_stationary_af_timing_test_as_diagnostic_data(self):
        records = [
            {
                "cmd": "scanner_sync_run_stationary_af_test",
                "seq": 30,
                "scan_id": "scan-a",
                "stripe_id": 7,
                "first_frame_id": 100,
                "frame_count": 5,
                "frame_period_us": 25_000,
                "position_axis": "X",
                "event_position_count": 120,
                "pattern_id": 1,
                "settle_us": 1_000,
                "xvs_trigger_pulse_us": 200,
                "exposure_hold_us": 4_000,
                "diagnostic_only": True,
                "hardware_outputs_enabled": False,
            }
        ]

        commands = parse_validated_scanner_sync_commands(
            records,
            context=ScannerSyncCommandBoundaryContext(
                expected_scan_id="scan-a",
                expected_stripe_id=7,
                expected_first_seq=30,
            ),
        )
        report = validate_host_command_records(records)

        self.assertIsInstance(commands[0], RunStationaryAfTestCommand)
        self.assertEqual(commands[0].frame_period_us, 25_000)
        self.assertEqual(report.stationary_af_test_count, 1)
        self.assertEqual(report.schedule_z_count, 0)

    def test_accepts_timed_output_sequence_as_diagnostic_replay_data(self):
        record = _timed_output_sequence(seq=40)

        commands = parse_validated_scanner_sync_commands(
            [record],
            context=ScannerSyncCommandBoundaryContext(
                expected_scan_id="scan-a",
                expected_stripe_id=7,
                expected_first_seq=40,
            ),
        )
        report = validate_host_command_records([record])

        self.assertIsInstance(commands[0], RunTimedOutputSequenceCommand)
        self.assertEqual(commands[0].seq_id, 9001)
        self.assertEqual(commands[0].repeat_count, 1)
        self.assertEqual(len(commands[0].steps), 2)
        self.assertEqual(commands[0].safe_output_values, 0)
        self.assertEqual(commands[0].idle_output_values, TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT)
        self.assertEqual(report.timed_output_sequence_count, 1)
        self.assertEqual(report.stationary_af_test_count, 0)
        self.assertFalse(report.hardware_outputs_enabled)

    def test_rejects_timed_output_sequence_hardware_outputs_in_dry_run(self):
        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "hardware_outputs_enabled",
        ):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "hardware_outputs_enabled": True,
                    }
                ]
            )

        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "unsafe hardware output",
        ):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "steps": [
                            {
                                "output_mask": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                                "output_values": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                                "delay_us": 100,
                                "may_access_gpio": True,
                            }
                        ],
                    }
                ]
            )

    def test_rejects_timed_output_sequence_v1_position_armed_modes(self):
        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "mode must be diagnostic_immediate in V1",
        ):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "mode": "position_armed",
                    }
                ]
            )

        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "start_condition must be immediate in V1",
        ):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "start_condition": "position_count",
                        "start_position_count": 1200,
                    }
                ]
            )

        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "diagnostic-only",
        ):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "diagnostic_only": False,
                    }
                ]
            )

    def test_rejects_invalid_timed_output_sequence_steps_and_states(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "requires steps"):
            validate_host_command_records([{**_timed_output_sequence(seq=40), "steps": []}])

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "steps\\[0\\]"):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "steps": [
                            {
                                "output_mask": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                                "output_values": TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
                                "delay_us": 100,
                            }
                        ],
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "unknown"):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "steps": [
                            {
                                "output_mask": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                                "output_values": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                                "delay_us": 100,
                                "event_flags": 0x8000,
                            }
                        ],
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "delay_us must be <="):
            payload = _timed_output_sequence(seq=40)
            payload["steps"] = [
                {
                    "output_mask": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                    "output_values": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                    "delay_us": TIMED_OUTPUT_SEQUENCE_MAX_STEP_DELAY_US + 1,
                }
            ]
            validate_host_command_records([payload])

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "idle_output_values"):
            validate_host_command_records(
                [
                    {
                        **_timed_output_sequence(seq=40),
                        "idle_output_mask": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                        "idle_output_values": TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT,
                    }
                ]
            )

    def test_rejects_invalid_stationary_af_timing_test(self):
        record = {
            "cmd": "scanner_sync_run_stationary_af_test",
            "seq": 30,
            "scan_id": "scan-a",
            "stripe_id": 7,
            "first_frame_id": 100,
            "frame_count": 5,
            "frame_period_us": 2_000,
            "event_position_count": 120,
            "settle_us": 1_000,
            "xvs_trigger_pulse_us": 200,
            "exposure_hold_us": 4_000,
        }

        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "fit inside frame_period_us",
        ):
            validate_host_command_records([record])

        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "diagnostic-only",
        ):
            validate_host_command_records(
                [
                    {
                        **record,
                        "frame_period_us": 25_000,
                        "diagnostic_only": False,
                    }
                ]
            )

    def test_accepts_legacy_schedule_z_alias_only_at_adapter_boundary(self):
        commands = parse_validated_schedule_z_commands(
            [
                {
                    "cmd": "schedule_z",
                    "seq": 3,
                    "scan_id": "scan-a",
                    "stripe_id": 7,
                    "apply_at_frame_id": 9,
                    "z_target_um": 1.25,
                }
            ],
            context=ScannerSyncCommandBoundaryContext(
                expected_first_seq=3,
                allow_legacy_alias_at_adapter_boundary=True,
            ),
        )

        self.assertEqual(commands[0].cmd, "scanner_sync_schedule_z")

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "alias is stale"):
            parse_validated_schedule_z_commands(
                [
                    {
                        "cmd": "schedule_z",
                        "seq": 3,
                        "scan_id": "scan-a",
                        "stripe_id": 7,
                        "apply_at_frame_id": 9,
                        "z_target_um": 1.25,
                    }
                ],
                context=ScannerSyncCommandBoundaryContext(expected_first_seq=3),
            )

    def test_policy_artifact_drives_command_names_and_safety_fields(self):
        self.assertEqual(
            POLICY["canonical_commands"],
            [
                "scanner_sync_start",
                "scanner_sync_schedule_z",
                "scanner_sync_run_stationary_af_test",
                "scanner_sync_run_timed_output_sequence",
                "scanner_sync_stop",
            ],
        )
        self.assertEqual(
            POLICY["legacy_aliases"]["schedule_z"]["allowed_only_when_context_field"],
            "allow_legacy_alias_at_adapter_boundary",
        )

        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "forbidden hardware/runtime field",
        ):
            validate_host_command_records(
                [
                    {
                        **_schedule_z(seq=1),
                        "serial_port": "/dev/ttyUSB0",
                    }
                ]
            )

    def test_rejects_missing_required_schedule_z_fields(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "missing seq"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_schedule_z",
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                        "apply_at_frame_id": 12,
                        "z_target_um": 42.5,
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "z_target_um"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_schedule_z",
                        "seq": 1,
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                        "apply_at_frame_id": 12,
                    }
                ]
            )

    def test_rejects_missing_required_start_and_stop_fields(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "next_frame_id"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_start",
                        "seq": 1,
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "missing reason"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_stop",
                        "seq": 1,
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "unsupported"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_stop",
                        "seq": 1,
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                        "reason": "not_a_stop_reason",
                    }
                ]
            )

    def test_rejects_schedule_z_without_any_future_target(self):
        base_record = {
            "cmd": "scanner_sync_schedule_z",
            "seq": 1,
            "scan_id": "scan-a",
            "stripe_id": 1,
            "z_target_um": 10.0,
        }

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "at least one"):
            validate_host_command_records([base_record])

    def test_rejects_current_or_past_targets_when_progress_context_is_known(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "future"):
            validate_host_command_records(
                [_schedule_z(seq=1, apply_at_frame_id=12)],
                context=ScannerSyncCommandBoundaryContext(current_frame_id=12),
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "future"):
            validate_host_command_records(
                [_schedule_z(seq=1, apply_at_position_count=1200)],
                context=ScannerSyncCommandBoundaryContext(current_position_count=1200),
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "future"):
            validate_host_command_records(
                [_schedule_z(seq=1, apply_at_position_count=1000)],
                context=ScannerSyncCommandBoundaryContext(
                    current_position_count=1200,
                    position_direction=1,
                ),
            )

    def test_rejects_seq_gaps_duplicates_and_scan_mismatch(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "seq correlation"):
            validate_host_command_records(
                [
                    _schedule_z(seq=5),
                    _schedule_z(seq=7),
                ],
                context=ScannerSyncCommandBoundaryContext(expected_first_seq=5),
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "duplicate seq"):
            validate_host_command_records(
                [
                    _schedule_z(seq=5),
                    _schedule_z(seq=5),
                ],
                context=ScannerSyncCommandBoundaryContext(require_contiguous_seq=False),
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "scan_id mismatch"):
            validate_host_command_records(
                [_schedule_z(seq=5, scan_id="scan-b")],
                context=ScannerSyncCommandBoundaryContext(expected_scan_id="scan-a"),
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "stripe_id mismatch"):
            validate_host_command_records(
                [_schedule_z(seq=5, stripe_id=2)],
                context=ScannerSyncCommandBoundaryContext(expected_stripe_id=1),
            )

    def test_rejects_immediate_move_z_now_command(self):
        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "move_z_now"):
            validate_host_command_records(
                [
                    {
                        "cmd": "move_z_now",
                        "seq": 1,
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                        "z_target_um": 50.0,
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "unsupported"):
            validate_host_command_records(
                [
                    {
                        "cmd": "scanner_sync_pause",
                        "seq": 1,
                        "scan_id": "scan-a",
                        "stripe_id": 1,
                    }
                ]
            )

    def test_rejects_hardware_outputs_enabled_in_replay_or_dry_run(self):
        with self.assertRaisesRegex(
            ScannerSyncCommandBoundaryError,
            "hardware_outputs_enabled",
        ):
            validate_host_command_records(
                [
                    {
                        **_schedule_z(seq=1),
                        "hardware_outputs_enabled": True,
                    }
                ]
            )

        with self.assertRaisesRegex(ScannerSyncCommandBoundaryError, "boolean"):
            validate_host_command_records(
                [
                    {
                        **_schedule_z(seq=1),
                        "hardware_outputs_enabled": 1,
                    }
                ]
            )


def _schedule_z(
    *,
    seq: int,
    scan_id: str = "scan-a",
    stripe_id: int = 1,
    apply_at_frame_id: int | None = None,
    apply_at_position_count: int | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "cmd": "scanner_sync_schedule_z",
        "seq": seq,
        "scan_id": scan_id,
        "stripe_id": stripe_id,
        "z_target_um": 42.5,
    }
    if apply_at_position_count is not None:
        record["apply_at_position_count"] = apply_at_position_count
    else:
        record["apply_at_frame_id"] = (
            12 + seq if apply_at_frame_id is None else apply_at_frame_id
        )
    return record


def _timed_output_sequence(
    *,
    seq: int,
    scan_id: str = "scan-a",
    stripe_id: int = 7,
) -> dict[str, object]:
    led_mask = (
        TIMED_OUTPUT_SEQUENCE_LED_RED_BIT
        | TIMED_OUTPUT_SEQUENCE_LED_GREEN_BIT
        | TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT
    )
    return {
        "cmd": "scanner_sync_run_timed_output_sequence",
        "seq": seq,
        "scan_id": scan_id,
        "stripe_id": stripe_id,
        "seq_id": 9001,
        "repeat_count": 1,
        "frame_id_base": 200,
        "pattern_id": 1,
        "safe_output_mask": led_mask | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
        "safe_output_values": 0,
        "idle_output_mask": led_mask | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
        "idle_output_values": TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
        "diagnostic_only": True,
        "hardware_outputs_enabled": False,
        "steps": [
            {
                "output_mask": led_mask,
                "output_values": TIMED_OUTPUT_SEQUENCE_LED_RED_BIT,
                "delay_us": 1_000,
            },
            {
                "output_mask": led_mask | TIMED_OUTPUT_SEQUENCE_HQ_XVS_SYNC_BIT,
                "output_values": TIMED_OUTPUT_SEQUENCE_LED_WHITE_BIT,
                "delay_us": 1_000,
                "event_flags": TIMED_OUTPUT_SEQUENCE_END_FLAG,
            },
        ],
    }
