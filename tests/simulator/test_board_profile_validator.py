import sys
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.board_profile.state_machine import (  # noqa: E402
    BoardProfileStateError,
    profile_state,
)
from scanner_firmware.domain.board_profile.validator import (  # noqa: E402
    BoardProfileError,
    validate_board_profile,
)


BOARD_PROFILE_PATH = REPO_ROOT / "boards" / "kingroon_mono_v2" / "pins.yaml"
SKR_PICO_PROFILE_PATH = REPO_ROOT / "boards" / "skr_pico" / "pins.yaml"


class BoardProfileValidatorTests(unittest.TestCase):
    def test_current_kingroon_profile_uses_active_led_aliases(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))

        validate_board_profile(profile)

        self.assertEqual(profile_state(profile), "pinmap_candidate")
        self.assertEqual(profile["pins"]["camera_or_sync_trigger"], "PD6")
        self.assertEqual(profile["pins"]["led_green"], "PA9")
        self.assertEqual(profile["pins"]["led_red"], "PA10")
        self.assertEqual(profile["pins"]["led_white"], "PB13")

    def test_placeholder_board_profile_preserves_explicit_unknowns(self):
        profile = yaml.safe_load(SKR_PICO_PROFILE_PATH.read_text(encoding="utf-8"))

        validate_board_profile(profile)

        self.assertEqual(profile_state(profile), "placeholder")
        self.assertEqual(profile["pins"]["camera_or_sync_trigger"], "unknown")
        self.assertEqual(profile["mechanics"]["derived_values"]["x_steps_per_mm"], "unknown")

    def test_rejects_unknown_board_profile_state(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["profile_state"] = "probably_verified"

        with self.assertRaisesRegex(BoardProfileStateError, "profile_state"):
            validate_board_profile(profile)

    def test_rejects_active_superseded_board_profile(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["profile_state"] = "superseded"

        with self.assertRaisesRegex(BoardProfileStateError, "superseded"):
            validate_board_profile(profile)

    def test_allows_inactive_superseded_board_profile_as_archive(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["profile_state"] = "superseded"
        profile["profile_active"] = False

        validate_board_profile(profile)

    def test_rejects_pinmap_verified_without_voltage_load_and_boot_evidence(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["profile_state"] = "pinmap_verified"

        with self.assertRaisesRegex(
            BoardProfileStateError,
            "voltage, load and boot/default-state evidence",
        ):
            validate_board_profile(profile)

    def test_rejects_pinmap_verified_when_evidence_is_incomplete(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["profile_state"] = "pinmap_verified"
        profile["verification_evidence"] = {
            "voltage_levels_measured": True,
            "load_behavior_tested": False,
            "boot_default_states_measured": True,
        }

        with self.assertRaisesRegex(BoardProfileStateError, "load_behavior_tested"):
            validate_board_profile(profile)

    def test_rejects_hardware_tested_without_reviewed_test_evidence(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["profile_state"] = "hardware_tested"
        profile["verification_evidence"] = {
            "voltage_levels_measured": True,
            "load_behavior_tested": True,
            "boot_default_states_measured": True,
            "hardware_test_report": "unknown",
            "safe_test_procedure_reviewed": True,
        }

        with self.assertRaisesRegex(BoardProfileStateError, "hardware_test_report"):
            validate_board_profile(profile)

    def test_rejects_superseded_led_pin_as_active_alias(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["pins"]["led_white"] = "PB1"

        with self.assertRaises(BoardProfileError):
            validate_board_profile(profile)

    def test_rejects_legacy_position_event_as_trigger_alias(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["pins"]["camera_or_sync_trigger"] = "PC4"

        with self.assertRaises(BoardProfileError):
            validate_board_profile(profile)

    def test_rejects_placeholder_words_for_unknown_hardware_values(self):
        profile = yaml.safe_load(SKR_PICO_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["pins"]["x_step"] = "TODO"
        profile["homing"]["feasibility_outcome"]["x"] = "TBD"
        profile["mechanics"]["configured_microsteps"] = "PLACEHOLDER"

        with self.assertRaisesRegex(
            BoardProfileError,
            "mechanics.configured_microsteps.*pins.x_step",
        ):
            validate_board_profile(profile)

    def test_rejects_stale_derived_motion_resolution(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["mechanics"]["derived_values"]["z_steps_per_um"] = 3.2

        with self.assertRaises(ValueError):
            validate_board_profile(profile)


if __name__ == "__main__":
    unittest.main()
