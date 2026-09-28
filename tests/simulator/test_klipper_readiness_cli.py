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

from scanner_firmware.adapters.klipper_adapter.readiness.cli import main  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (  # noqa: E402
    EXPECTED_COMMAND_FORMATS,
    EXPECTED_RESPONSE_FORMATS,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (  # noqa: E402
    SCANNER_SYNC_CONFIG_FORMAT,
)


class KlipperReadinessCliTests(unittest.TestCase):
    def test_reports_ready_json_for_complete_dictionary(self):
        output = io.StringIO()
        with tempfile.NamedTemporaryFile("w+", delete=False) as dictionary:
            dictionary.write(_complete_dictionary())
            dictionary.flush()
            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        dictionary.name,
                        "--host-extra-present",
                        "--config-section-present",
                        "--config-enable",
                        "--mcu-connected",
                        "--response-dispatch-available",
                        "--require-ready",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["stage"], "ready_to_enable")
        self.assertTrue(payload["can_enable_scanner_sync"])
        self.assertTrue(payload["has_all_required_commands"])
        self.assertTrue(payload["has_all_required_responses"])

    def test_require_ready_returns_nonzero_for_missing_scanner_sync_commands(self):
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO("config_digital_out oid=%c pin=%u")):
            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        "-",
                        "--host-extra-present",
                        "--config-section-present",
                        "--config-enable",
                        "--mcu-connected",
                        "--response-dispatch-available",
                        "--require-ready",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["stage"], "host_extra_enabled_without_mcu")
        self.assertFalse(payload["can_enable_scanner_sync"])
        self.assertEqual(payload["missing_command_formats"], list(EXPECTED_COMMAND_FORMATS))

    def test_hardware_outputs_flag_blocks_even_with_complete_dictionary(self):
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO(_complete_dictionary())):
            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        "-",
                        "--host-extra-present",
                        "--config-section-present",
                        "--config-enable",
                        "--mcu-connected",
                        "--response-dispatch-available",
                        "--hardware-outputs-enabled",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["stage"], "unsafe_hardware_outputs")
        self.assertEqual(
            payload["blockers"],
            ["metadata_only_mode_required", "hardware_outputs_must_be_disabled"],
        )

    def test_config_file_supplies_scanner_sync_enable_and_protocol_fields(self):
        output = io.StringIO()
        with tempfile.NamedTemporaryFile("w+", delete=False) as dictionary:
            dictionary.write(_complete_dictionary())
            dictionary.flush()
            with tempfile.NamedTemporaryFile("w+", delete=False) as config:
                config.write("[scanner_sync]\nenable: false\nprotocol_version: 1\n")
                config.flush()
                with contextlib.redirect_stdout(output):
                    code = main(
                        [
                            dictionary.name,
                            "--config-file",
                            config.name,
                            "--host-extra-present",
                            "--mcu-connected",
                            "--response-dispatch-available",
                        ]
                    )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["config_source"], "file")
        self.assertEqual(payload["stage"], "host_extra_loaded_disabled")
        self.assertFalse(payload["can_enable_scanner_sync"])

    def test_enabled_config_file_requires_explicit_safety_fields(self):
        output = io.StringIO()
        with tempfile.NamedTemporaryFile("w+", delete=False) as dictionary:
            dictionary.write(_complete_dictionary())
            dictionary.flush()
            with tempfile.NamedTemporaryFile("w+", delete=False) as config:
                config.write("[scanner_sync]\nenable: true\nprotocol_version: 1\n")
                config.flush()
                with contextlib.redirect_stdout(output):
                    code = main(
                        [
                            dictionary.name,
                            "--config-file",
                            config.name,
                            "--host-extra-present",
                            "--mcu-connected",
                            "--response-dispatch-available",
                            "--require-ready",
                        ]
                    )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["stage"], "unsafe_hardware_outputs")
        self.assertEqual(payload["blockers"], ["scanner_sync_safety_fields_missing"])
        self.assertFalse(payload["can_enable_scanner_sync"])

    def test_enabled_config_file_blocks_configured_output_pins(self):
        output = io.StringIO()
        with tempfile.NamedTemporaryFile("w+", delete=False) as dictionary:
            dictionary.write(_complete_dictionary())
            dictionary.flush()
            with tempfile.NamedTemporaryFile("w+", delete=False) as config:
                config.write(
                    "[scanner_sync]\n"
                    "enable: true\n"
                    "protocol_version: 1\n"
                    "mode: metadata_only\n"
                    "hardware_outputs_enabled: false\n"
                    "camera_trigger_pin: none\n"
                    "led_white_output: PB13\n"
                )
                config.flush()
                with contextlib.redirect_stdout(output):
                    code = main(
                        [
                            dictionary.name,
                            "--config-file",
                            config.name,
                            "--host-extra-present",
                            "--mcu-connected",
                            "--response-dispatch-available",
                            "--require-ready",
                        ]
                    )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["stage"], "unsafe_hardware_outputs")
        self.assertEqual(payload["blockers"], ["scanner_sync_output_pins_configured"])
        self.assertEqual(payload["configured_output_keys"], ["led_white_output"])
        self.assertFalse(payload["can_enable_scanner_sync"])

    def test_config_alias_supplies_scanner_sync_config_file(self):
        output = io.StringIO()
        with tempfile.NamedTemporaryFile("w+", delete=False) as dictionary:
            dictionary.write(_complete_dictionary())
            dictionary.flush()
            with tempfile.NamedTemporaryFile("w+", delete=False) as config:
                config.write(
                    "[scanner_sync]\n"
                    "enable: true\n"
                    "protocol_version: 1\n"
                    "mode: metadata_only\n"
                    "hardware_outputs_enabled: false\n"
                )
                config.flush()
                with contextlib.redirect_stdout(output):
                    code = main(
                        [
                            dictionary.name,
                            "--config",
                            config.name,
                            "--host-extra-present",
                            "--mcu-connected",
                            "--response-dispatch-available",
                        ]
                    )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["config_source"], "file")
        self.assertEqual(payload["stage"], "ready_to_enable")
        self.assertTrue(payload["can_enable_scanner_sync"])


def _complete_dictionary() -> str:
    return "\n".join((SCANNER_SYNC_CONFIG_FORMAT, *EXPECTED_COMMAND_FORMATS, *EXPECTED_RESPONSE_FORMATS))


if __name__ == "__main__":
    unittest.main()
