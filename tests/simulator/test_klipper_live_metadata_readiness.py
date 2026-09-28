import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (  # noqa: E402
    EXPECTED_COMMAND_FORMATS,
    EXPECTED_RESPONSE_FORMATS,
    LiveKlipperScannerSyncObservation,
    evaluate_live_metadata_readiness,
)


class KlipperLiveMetadataReadinessTests(unittest.TestCase):
    def test_current_mks_stage_a_state_is_safe_disabled_not_ready(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=False,
                mcu_connected=True,
                mcu_command_formats=frozenset(),
            )
        )

        self.assertEqual(readiness.stage, "host_extra_loaded_disabled")
        self.assertEqual(readiness.status, "safe_disabled")
        self.assertFalse(readiness.can_enable_scanner_sync)
        self.assertEqual(readiness.blockers, ())
        self.assertEqual(readiness.missing_command_formats, EXPECTED_COMMAND_FORMATS)

    def test_enabled_config_without_mcu_commands_is_blocked(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(),
            )
        )

        self.assertEqual(readiness.stage, "host_extra_enabled_without_mcu")
        self.assertEqual(readiness.status, "blocked")
        self.assertEqual(readiness.blockers, ("scanner_sync_mcu_commands_missing",))
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_ready_requires_host_config_mcu_connection_and_command_formats(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
                response_dispatch_available=True,
            )
        )

        self.assertEqual(readiness.stage, "ready_to_enable")
        self.assertEqual(readiness.status, "ready")
        self.assertTrue(readiness.can_enable_scanner_sync)
        self.assertEqual(readiness.missing_command_formats, ())

    def test_missing_live_prerequisites_are_blockers(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=False,
                config_section_present=False,
                config_enable=False,
                mcu_connected=False,
            )
        )

        self.assertEqual(readiness.stage, "not_installed")
        self.assertEqual(readiness.status, "blocked")
        self.assertEqual(
            readiness.blockers,
            (
                "mcu_not_connected",
                "host_extra_missing",
                "config_section_missing",
            ),
        )

    def test_response_formats_are_reported_without_marking_disabled_stage_ready(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=False,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(),
            )
        )

        self.assertEqual(readiness.status, "safe_disabled")
        self.assertEqual(readiness.missing_response_formats, EXPECTED_RESPONSE_FORMATS)

    def test_missing_responses_block_enabled_metadata_readiness(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(),
                response_dispatch_available=True,
            )
        )

        self.assertEqual(readiness.stage, "host_extra_enabled_without_responses")
        self.assertEqual(readiness.status, "blocked")
        self.assertEqual(readiness.blockers, ("scanner_sync_response_formats_missing",))
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_missing_mcu_config_format_blocks_enabled_metadata_readiness(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_config_format_present=False,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
                response_dispatch_available=True,
            )
        )

        self.assertEqual(readiness.stage, "host_extra_enabled_without_mcu")
        self.assertEqual(readiness.status, "blocked")
        self.assertEqual(readiness.blockers, ("scanner_sync_mcu_config_format_missing",))
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_missing_response_dispatch_blocks_enabled_metadata_readiness(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
                response_dispatch_available=False,
            )
        )

        self.assertEqual(readiness.stage, "host_extra_enabled_without_responses")
        self.assertEqual(readiness.blockers, ("scanner_sync_response_dispatch_missing",))

    def test_hardware_outputs_or_non_metadata_mode_block_readiness(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
                response_dispatch_available=True,
                metadata_only_mode=False,
                hardware_outputs_enabled=True,
            )
        )

        self.assertEqual(readiness.stage, "unsafe_hardware_outputs")
        self.assertEqual(
            readiness.blockers,
            ("metadata_only_mode_required", "hardware_outputs_must_be_disabled"),
        )

    def test_enabled_config_requires_explicit_metadata_safety_fields(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
                response_dispatch_available=True,
                config_safety_fields_present=False,
            )
        )

        self.assertEqual(readiness.stage, "unsafe_hardware_outputs")
        self.assertEqual(readiness.status, "blocked")
        self.assertEqual(readiness.blockers, ("scanner_sync_safety_fields_missing",))
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_enabled_config_blocks_configured_output_pins(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
                registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
                response_dispatch_available=True,
                configured_output_keys=("led_white_output",),
            )
        )

        self.assertEqual(readiness.stage, "unsafe_hardware_outputs")
        self.assertEqual(readiness.status, "blocked")
        self.assertEqual(readiness.blockers, ("scanner_sync_output_pins_configured",))
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_unsupported_protocol_blocks_readiness(self):
        readiness = evaluate_live_metadata_readiness(
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=True,
                mcu_connected=True,
                protocol_version=2,
            )
        )

        self.assertEqual(readiness.stage, "unsupported_protocol")
        self.assertEqual(readiness.blockers, ("unsupported_protocol_version",))

    def test_rejects_invalid_protocol_version(self):
        with self.assertRaisesRegex(ValueError, "protocol_version"):
            LiveKlipperScannerSyncObservation(
                host_extra_present=True,
                config_section_present=True,
                config_enable=False,
                mcu_connected=True,
                protocol_version=0,
            )


if __name__ == "__main__":
    unittest.main()
