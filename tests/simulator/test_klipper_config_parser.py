import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.config_parser import (  # noqa: E402
    ScannerSyncConfigError,
    parse_scanner_sync_config,
)


class KlipperConfigParserTests(unittest.TestCase):
    def test_parses_current_stage_a_scanner_sync_section(self):
        config = parse_scanner_sync_config(
            """
[mcu]
serial: /dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0

[scanner_sync]
enable: false
protocol_version: 1

[printer]
kinematics: cartesian
"""
        )

        self.assertTrue(config.section_present)
        self.assertFalse(config.enable)
        self.assertEqual(config.protocol_version, 1)
        self.assertTrue(config.metadata_only_mode)
        self.assertFalse(config.mode_present)
        self.assertFalse(config.hardware_outputs_enabled)
        self.assertFalse(config.hardware_outputs_enabled_present)
        self.assertFalse(config.safety_fields_present)
        self.assertFalse(config.output_pins_configured)
        self.assertEqual(config.configured_output_keys, ())

    def test_parses_safety_fields_when_present(self):
        config = parse_scanner_sync_config(
            """
[scanner_sync]
enable: true
protocol_version: 1
mode: metadata_only
hardware_outputs_enabled: false
"""
        )

        self.assertTrue(config.enable)
        self.assertTrue(config.metadata_only_mode)
        self.assertTrue(config.mode_present)
        self.assertFalse(config.hardware_outputs_enabled)
        self.assertTrue(config.hardware_outputs_enabled_present)
        self.assertTrue(config.safety_fields_present)
        self.assertFalse(config.output_pins_configured)

    def test_non_metadata_mode_is_not_silently_treated_as_safe(self):
        config = parse_scanner_sync_config(
            """
[scanner_sync]
enable: true
mode: hardware_outputs
hardware_outputs_enabled: true
"""
        )

        self.assertFalse(config.metadata_only_mode)
        self.assertTrue(config.mode_present)
        self.assertTrue(config.hardware_outputs_enabled)
        self.assertTrue(config.hardware_outputs_enabled_present)
        self.assertTrue(config.safety_fields_present)

    def test_reports_configured_scanner_sync_output_keys(self):
        config = parse_scanner_sync_config(
            """
[scanner_sync]
enable: true
mode: metadata_only
hardware_outputs_enabled: false
camera_trigger_pin: none
led_white_output: PB13
green_strobe_pin: PA9
"""
        )

        self.assertTrue(config.output_pins_configured)
        self.assertEqual(
            config.configured_output_keys,
            ("green_strobe_pin", "led_white_output"),
        )

    def test_reports_missing_section_without_guessing_enable_state(self):
        config = parse_scanner_sync_config("[printer]\nkinematics: cartesian\n")

        self.assertFalse(config.section_present)
        self.assertFalse(config.enable)

    def test_rejects_invalid_boolean_or_protocol_version(self):
        with self.assertRaisesRegex(ScannerSyncConfigError, "enable"):
            parse_scanner_sync_config("[scanner_sync]\nenable: maybe\n")

        with self.assertRaisesRegex(ScannerSyncConfigError, "protocol_version"):
            parse_scanner_sync_config("[scanner_sync]\nprotocol_version: 0\n")


if __name__ == "__main__":
    unittest.main()
