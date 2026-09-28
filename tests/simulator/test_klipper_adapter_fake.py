import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.testing.fake import (  # noqa: E402
    DryRunKlipperMcu,
    KlipperAdapterError,
    KlipperHardwareAccessError,
    KlipperRegistrationOrderError,
)


class KlipperAdapterFakeTests(unittest.TestCase):
    def test_scanner_sync_style_registration_uses_safe_klipper_surface(self):
        mcu = DryRunKlipperMcu(
            available_commands=[
                "scanner_sync_start oid=%c next_frame_id=%u",
                "scanner_sync_query oid=%c",
            ]
        )
        adapter = _FutureScannerSyncKlipperAdapterProbe(mcu)

        mcu.run_config_callbacks()

        self.assertEqual(adapter.oid, 1)
        self.assertIsNotNone(adapter.start_cmd)
        self.assertTrue(adapter.has_query_cmd)
        self.assertEqual(
            [record.cmd for record in mcu.config_commands],
            ["config_scanner_sync oid=1"],
        )
        self.assertEqual(
            [(record.msgformat, record.queue_id, record.required, record.available) for record in mcu.command_lookups],
            [
                ("scanner_sync_start oid=%c next_frame_id=%u", 1, True, True),
                ("scanner_sync_query oid=%c", None, False, True),
            ],
        )
        self.assertEqual(
            [(record.msgformat, record.oid) for record in mcu.serial_responses],
            [("scanner_sync_status oid=%c status=%c clock=%u", 1)],
        )
        self.assertEqual(
            [call.name for call in mcu.api_calls],
            [
                "create_oid",
                "alloc_command_queue",
                "register_config_callback",
                "run_config_callback",
                "add_config_cmd",
                "lookup_command",
                "try_lookup_command",
                "register_serial_response",
            ],
        )

    def test_registration_time_calls_are_rejected_outside_config_callback(self):
        mcu = DryRunKlipperMcu()

        with self.assertRaisesRegex(KlipperRegistrationOrderError, "add_config_cmd"):
            mcu.add_config_cmd("config_scanner_sync oid=1")
        with self.assertRaisesRegex(KlipperRegistrationOrderError, "lookup_command"):
            mcu.lookup_command("scanner_sync_start oid=%c")
        with self.assertRaisesRegex(KlipperRegistrationOrderError, "register_serial_response"):
            mcu.register_serial_response(lambda params: None, "scanner_sync_status oid=%c")

    def test_config_callbacks_run_in_registration_order_once(self):
        mcu = DryRunKlipperMcu()
        seen = []

        mcu.register_config_callback(lambda: seen.append("first"))
        mcu.register_config_callback(lambda: seen.append("second"))

        mcu.run_config_callbacks()

        self.assertEqual(seen, ["first", "second"])
        self.assertEqual(mcu.phase, "configured")
        with self.assertRaisesRegex(KlipperRegistrationOrderError, "run_config_callbacks"):
            mcu.run_config_callbacks()
        with self.assertRaisesRegex(KlipperRegistrationOrderError, "register_config_callback"):
            mcu.register_config_callback(lambda: None)

    def test_optional_and_required_command_availability_are_explicit(self):
        mcu = DryRunKlipperMcu(available_commands=["scanner_sync_start oid=%c"])
        queue = mcu.alloc_command_queue()

        def build_config():
            self.assertFalse(mcu.try_lookup_command("scanner_sync_query oid=%c"))
            with self.assertRaisesRegex(KlipperAdapterError, "unavailable"):
                mcu.lookup_command("scanner_sync_query oid=%c", cq=queue)

        mcu.register_config_callback(build_config)
        mcu.run_config_callbacks()

        self.assertEqual(
            [(record.msgformat, record.required, record.available) for record in mcu.command_lookups],
            [
                ("scanner_sync_query oid=%c", False, False),
                ("scanner_sync_query oid=%c", True, False),
            ],
        )

    def test_dry_run_fake_blocks_serial_and_command_send_paths(self):
        mcu = DryRunKlipperMcu()
        queue = mcu.alloc_command_queue()
        captured = {}

        def build_config():
            captured["cmd"] = mcu.lookup_command("scanner_sync_start oid=%c", cq=queue)

        mcu.register_config_callback(build_config)
        mcu.run_config_callbacks()

        with self.assertRaisesRegex(KlipperHardwareAccessError, "serial"):
            mcu.get_serial()
        with self.assertRaisesRegex(KlipperHardwareAccessError, "send is disabled"):
            captured["cmd"].send([1])
        with self.assertRaisesRegex(KlipperHardwareAccessError, "send_wait_ack is disabled"):
            captured["cmd"].send_wait_ack([1])


class _FutureScannerSyncKlipperAdapterProbe:
    def __init__(self, mcu):
        self._mcu = mcu
        self.oid = mcu.create_oid()
        self.command_queue = mcu.alloc_command_queue()
        self.start_cmd = None
        self.has_query_cmd = False
        mcu.register_config_callback(self._build_config)

    def _build_config(self):
        self._mcu.add_config_cmd(f"config_scanner_sync oid={self.oid}")
        self.start_cmd = self._mcu.lookup_command(
            "scanner_sync_start oid=%c next_frame_id=%u",
            cq=self.command_queue,
        )
        self.has_query_cmd = self._mcu.try_lookup_command("scanner_sync_query oid=%c")
        self._mcu.register_serial_response(
            self._handle_status,
            "scanner_sync_status oid=%c status=%c clock=%u",
            self.oid,
        )

    def _handle_status(self, params):
        raise AssertionError("dry-run tests must not dispatch serial responses")


if __name__ == "__main__":
    unittest.main()
