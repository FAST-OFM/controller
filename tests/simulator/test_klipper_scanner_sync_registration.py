import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.testing.fake import DryRunKlipperMcu, KlipperHardwareAccessError  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (  # noqa: E402
    COMMAND_BINDINGS,
    EXPERIMENTAL_COMMAND_BINDINGS,
    EXPERIMENTAL_RESPONSE_BINDINGS,
    RESPONSE_BINDINGS,
    RESPONSE_EVENT_BY_MSGFORMAT,
    SCANNER_SYNC_CONFIG_COMMAND,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.registration import (  # noqa: E402
    ScannerSyncKlipperRegistration,
)


class KlipperScannerSyncRegistrationTests(unittest.TestCase):
    def test_registers_scanner_sync_commands_and_responses(self):
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )

        registration = ScannerSyncKlipperRegistration(mcu, protocol_version=1)

        self.assertEqual(registration.oid, 1)
        self.assertEqual(mcu.phase, "collecting")

        mcu.run_config_callbacks()

        self.assertEqual(
            mcu.config_commands[0].cmd,
            "config_scanner_sync oid=1 protocol_version=1 hardware_outputs_enabled=0",
        )
        self.assertTrue(mcu.config_commands[0].is_init)
        self.assertEqual(
            set(registration.commands),
            {
                "start",
                "stop",
                "schedule_z",
                "arm_af_window",
                "fire_af_window_now",
                "run_stationary_af_test",
            },
        )
        self.assertEqual(
            [record.msgformat for record in mcu.command_lookups],
            [binding.msgformat for binding in COMMAND_BINDINGS],
        )
        self.assertTrue(
            all(record.required and record.available for record in mcu.command_lookups)
        )
        self.assertEqual(
            [record.msgformat for record in mcu.serial_responses],
            [binding.msgformat for binding in RESPONSE_BINDINGS],
        )
        self.assertEqual({record.oid for record in mcu.serial_responses}, {1})

    def test_snapshot_uses_uniform_protocol_event_names(self):
        mcu = DryRunKlipperMcu()

        registration = ScannerSyncKlipperRegistration(mcu, protocol_version=1)
        snapshot = registration.snapshot

        self.assertEqual(snapshot.oid, 1)
        self.assertEqual(snapshot.protocol_version, 1)
        self.assertFalse(snapshot.hardware_outputs_enabled)
        self.assertFalse(snapshot.timed_output_sequence_enabled)
        self.assertEqual(
            snapshot.config_command,
            SCANNER_SYNC_CONFIG_COMMAND.format(
                oid=1,
                version=1,
                hardware_outputs_enabled=0,
            ),
        )
        self.assertEqual(
            [binding.protocol_event_type for binding in snapshot.response_bindings],
            [
                "FRAME_EVENT",
                "SCHEDULER_TERMINAL",
                "Z_SCHEDULED",
                "Z_APPLIED",
                "Z_REJECTED",
            ],
        )
        self.assertNotIn("run_timed_output_sequence", set(registration.commands))

    def test_can_explicitly_enable_timed_output_sequence_registration(self):
        all_commands = COMMAND_BINDINGS + EXPERIMENTAL_COMMAND_BINDINGS
        all_responses = RESPONSE_BINDINGS + EXPERIMENTAL_RESPONSE_BINDINGS
        seen = []
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in all_commands]
        )
        registration = ScannerSyncKlipperRegistration(
            mcu,
            enable_timed_output_sequence=True,
            response_handler=lambda event_type, params: seen.append((event_type, params)),
        )

        snapshot = registration.snapshot
        mcu.run_config_callbacks()

        self.assertTrue(snapshot.timed_output_sequence_enabled)
        self.assertEqual(
            [binding.msgformat for binding in snapshot.command_bindings],
            [binding.msgformat for binding in all_commands],
        )
        self.assertEqual(
            [binding.msgformat for binding in mcu.command_lookups],
            [binding.msgformat for binding in all_commands],
        )
        self.assertEqual(
            [record.msgformat for record in mcu.serial_responses],
            [binding.msgformat for binding in all_responses],
        )
        self.assertIn("run_timed_output_sequence", registration.commands)

        status_binding = EXPERIMENTAL_RESPONSE_BINDINGS[0]
        mcu.emit_serial_response(
            status_binding.msgformat,
            {"seq": 48, "seq_id": 9001},
            oid=registration.oid,
        )

        self.assertEqual(seen, [("TIMED_OUTPUT_SEQUENCE_STATUS", {"seq": 48, "seq_id": 9001})])

    def test_timed_output_sequence_registration_is_disabled_by_default(self):
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )
        registration = ScannerSyncKlipperRegistration(mcu)

        mcu.run_config_callbacks()

        self.assertNotIn("run_timed_output_sequence", registration.commands)
        self.assertEqual(
            [record.msgformat for record in mcu.command_lookups],
            [binding.msgformat for binding in COMMAND_BINDINGS],
        )
        self.assertEqual(
            [record.msgformat for record in mcu.serial_responses],
            [binding.msgformat for binding in RESPONSE_BINDINGS],
        )

    def test_enabled_timed_output_sequence_requires_matching_klipper_command(self):
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )
        registration = ScannerSyncKlipperRegistration(
            mcu,
            enable_timed_output_sequence=True,
        )

        with self.assertRaisesRegex(ValueError, "required Klipper command"):
            mcu.run_config_callbacks()

        self.assertNotIn("run_timed_output_sequence", registration.commands)

    def test_response_callbacks_preserve_protocol_event_type(self):
        seen = []
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )
        registration = ScannerSyncKlipperRegistration(
            mcu,
            response_handler=lambda event_type, params: seen.append((event_type, params)),
        )

        mcu.run_config_callbacks()

        for binding in RESPONSE_BINDINGS:
            mcu.emit_serial_response(
                binding.msgformat,
                {"seq": len(seen)},
                oid=registration.oid,
            )

        self.assertEqual(
            [event_type for event_type, _params in seen],
            [binding.protocol_event_type for binding in RESPONSE_BINDINGS],
        )
        self.assertEqual(
            RESPONSE_EVENT_BY_MSGFORMAT,
            {binding.msgformat: binding.protocol_event_type for binding in RESPONSE_BINDINGS},
        )

    def test_registered_commands_remain_inert_in_dry_run_fake(self):
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )
        registration = ScannerSyncKlipperRegistration(mcu)

        mcu.run_config_callbacks()

        with self.assertRaisesRegex(KlipperHardwareAccessError, "send is disabled"):
            registration.commands["start"].send([registration.oid, 0])
        with self.assertRaisesRegex(KlipperHardwareAccessError, "send_wait_ack is disabled"):
            registration.commands["schedule_z"].send_wait_ack(
                [registration.oid, 1, 1, 0, 100, 5000]
            )

    def test_rejects_invalid_protocol_version(self):
        with self.assertRaisesRegex(ValueError, "protocol_version"):
            ScannerSyncKlipperRegistration(DryRunKlipperMcu(), protocol_version=0)

        with self.assertRaisesRegex(ValueError, "unsupported protocol_version"):
            ScannerSyncKlipperRegistration(DryRunKlipperMcu(), protocol_version=2)

    def test_rejects_hardware_outputs_in_metadata_only_dry_run_registration(self):
        with self.assertRaisesRegex(ValueError, "hardware_outputs_enabled"):
            ScannerSyncKlipperRegistration(
                DryRunKlipperMcu(),
                hardware_outputs_enabled=True,
            )


if __name__ == "__main__":
    unittest.main()
