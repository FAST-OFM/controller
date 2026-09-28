import sys
import unittest
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.dictionary import (  # noqa: E402
    observation_from_dictionary,
    scan_scanner_sync_dictionary,
)
from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (  # noqa: E402
    EXPECTED_COMMAND_FORMATS,
    EXPECTED_RESPONSE_FORMATS,
    evaluate_live_metadata_readiness,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (  # noqa: E402
    SCANNER_SYNC_CONFIG_FORMAT,
)


class KlipperDictionaryCapabilitiesTests(unittest.TestCase):
    def test_detects_complete_scanner_sync_dictionary(self):
        capabilities = scan_scanner_sync_dictionary(_dictionary_with_scanner_sync())

        self.assertTrue(capabilities.has_all_required_commands)
        self.assertTrue(capabilities.has_all_required_responses)
        self.assertTrue(capabilities.config_format_present)
        self.assertEqual(capabilities.command_formats, frozenset(EXPECTED_COMMAND_FORMATS))
        self.assertEqual(capabilities.response_formats, frozenset(EXPECTED_RESPONSE_FORMATS))

    def test_detects_real_klipper_json_dictionary_sections(self):
        capabilities = scan_scanner_sync_dictionary(_json_dictionary_with_scanner_sync())

        self.assertTrue(capabilities.has_all_required_commands)
        self.assertTrue(capabilities.has_all_required_responses)
        self.assertTrue(capabilities.config_format_present)
        self.assertEqual(capabilities.command_formats, frozenset(EXPECTED_COMMAND_FORMATS))
        self.assertEqual(capabilities.response_formats, frozenset(EXPECTED_RESPONSE_FORMATS))

    def test_missing_scanner_sync_formats_block_live_readiness(self):
        observation = observation_from_dictionary(
            _current_mks_dictionary_without_scanner_sync(),
            host_extra_present=True,
            config_section_present=True,
            config_enable=True,
            mcu_connected=True,
            response_dispatch_available=True,
        )
        readiness = evaluate_live_metadata_readiness(observation)

        self.assertEqual(readiness.stage, "host_extra_enabled_without_mcu")
        self.assertEqual(readiness.missing_command_formats, EXPECTED_COMMAND_FORMATS)
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_complete_dictionary_can_feed_software_ready_observation(self):
        observation = observation_from_dictionary(
            _dictionary_with_scanner_sync(),
            host_extra_present=True,
            config_section_present=True,
            config_enable=True,
            mcu_connected=True,
            response_dispatch_available=True,
        )
        readiness = evaluate_live_metadata_readiness(observation)

        self.assertEqual(readiness.stage, "ready_to_enable")
        self.assertTrue(readiness.can_enable_scanner_sync)

    def test_old_config_format_blocks_live_readiness(self):
        observation = observation_from_dictionary(
            _dictionary_with_old_config_format(),
            host_extra_present=True,
            config_section_present=True,
            config_enable=True,
            mcu_connected=True,
            response_dispatch_available=True,
        )
        readiness = evaluate_live_metadata_readiness(observation)

        self.assertEqual(readiness.stage, "host_extra_enabled_without_mcu")
        self.assertEqual(readiness.blockers, ("scanner_sync_mcu_config_format_missing",))
        self.assertFalse(readiness.can_enable_scanner_sync)

    def test_dictionary_does_not_replace_response_dispatch_gate(self):
        observation = observation_from_dictionary(
            _dictionary_with_scanner_sync(),
            host_extra_present=True,
            config_section_present=True,
            config_enable=True,
            mcu_connected=True,
            response_dispatch_available=False,
        )
        readiness = evaluate_live_metadata_readiness(observation)

        self.assertEqual(readiness.stage, "host_extra_enabled_without_responses")
        self.assertEqual(readiness.blockers, ("scanner_sync_response_dispatch_missing",))

    def test_quoted_dictionary_lines_are_detected(self):
        capabilities = scan_scanner_sync_dictionary(
            "\n".join(f'"{msgformat}",' for msgformat in EXPECTED_COMMAND_FORMATS)
        )

        self.assertEqual(capabilities.command_formats, frozenset(EXPECTED_COMMAND_FORMATS))
        self.assertFalse(capabilities.has_all_required_responses)

    def test_partial_or_prose_matches_do_not_count_as_dictionary_formats(self):
        text = "\n".join(
            (
                f"log mentions {EXPECTED_COMMAND_FORMATS[0]} but not as a dictionary line",
                EXPECTED_COMMAND_FORMATS[1].replace("reason=%c", "reason=%u"),
                EXPECTED_RESPONSE_FORMATS[0] + " extra=%u",
            )
        )

        capabilities = scan_scanner_sync_dictionary(text)

        self.assertEqual(capabilities.command_formats, frozenset())
        self.assertEqual(capabilities.response_formats, frozenset())


def _dictionary_with_scanner_sync() -> str:
    return "\n".join(
        (
            "config_scanner_sync oid=%c protocol_version=%c",
            SCANNER_SYNC_CONFIG_FORMAT,
            *EXPECTED_COMMAND_FORMATS,
            *EXPECTED_RESPONSE_FORMATS,
        )
    )


def _json_dictionary_with_scanner_sync() -> str:
    return json.dumps(
        {
            "app": "Klipper",
            "commands": {
                SCANNER_SYNC_CONFIG_FORMAT: 16,
                **{msgformat: index for index, msgformat in enumerate(EXPECTED_COMMAND_FORMATS)},
            },
            "responses": {
                msgformat: index for index, msgformat in enumerate(EXPECTED_RESPONSE_FORMATS)
            },
        }
    )


def _dictionary_with_old_config_format() -> str:
    return "\n".join(
        (
            "config_scanner_sync oid=%c protocol_version=%c",
            *EXPECTED_COMMAND_FORMATS,
            *EXPECTED_RESPONSE_FORMATS,
        )
    )


def _current_mks_dictionary_without_scanner_sync() -> str:
    return "\n".join(
        (
            "config_pwm_out oid=%c pin=%u cycle_ticks=%u value=%hu default_value=%hu",
            "config_digital_out oid=%c pin=%u value=%c default_value=%c",
            "reset_step_clock oid=%c clock=%u",
        )
    )


if __name__ == "__main__":
    unittest.main()
