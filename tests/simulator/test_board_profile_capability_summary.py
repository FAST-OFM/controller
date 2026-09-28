import json
import sys
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.board_profile.capability_summary import (  # noqa: E402
    BOARD_PROFILE_CAPABILITY_SUMMARY_SCHEMA_ID,
    ControllerDiscoverySummary,
    build_board_profile_capability_summary,
    load_board_profile_capability_summary,
)


BOARD_PROFILE_PATH = REPO_ROOT / "boards" / "kingroon_mono_v2" / "pins.yaml"
SKR_PICO_PROFILE_PATH = REPO_ROOT / "boards" / "skr_pico" / "pins.yaml"
SUMMARY_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "board_profile_capability_summary_v1.json"
)


class BoardProfileCapabilitySummaryTests(unittest.TestCase):
    def test_summarizes_current_kingroon_profile_without_promoting_candidates(self):
        summary = load_board_profile_capability_summary(BOARD_PROFILE_PATH)
        payload = summary.to_json_dict()

        self.assertEqual(payload["schema_id"], BOARD_PROFILE_CAPABILITY_SUMMARY_SCHEMA_ID)
        self.assertEqual(payload["board"], "kingroon_mono_v2")
        self.assertEqual(payload["profile_state"], "pinmap_candidate")
        self.assertTrue(payload["profile_valid"])
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertFalse(payload["live_hardware_access_used"])
        self.assertFalse(payload["ready_for_live_hardware"])
        self.assertTrue(payload["ready_for_output_simulation"])

        self.assertEqual(payload["motion_kinematics"]["x"]["steps_per_mm"], 1600)
        self.assertEqual(payload["motion_kinematics"]["y"]["steps_per_mm"], 1600)
        self.assertEqual(payload["motion_kinematics"]["z"]["steps_per_mm"], 6400)
        self.assertEqual(payload["motion_kinematics"]["z"]["steps_per_um"], 6.4)

        self.assertEqual(payload["camera_or_sync_trigger"]["pin"], "PD6")
        self.assertEqual(
            {output["alias"]: output["pin"] for output in payload["led_outputs"]},
            {"led_green": "PA9", "led_red": "PA10", "led_white": "PB13"},
        )
        self.assertIn("pinmap_not_verified", payload["blockers"])
        self.assertIn("homing_not_enabled", payload["blockers"])
        self.assertIn("homing_not_verified", payload["blockers"])
        self.assertIn("controller_discovery_unknown", payload["blockers"])
        self.assertIn("printer_config_not_confirmed", payload["blockers"])
        self.assertIn("led_green_load_not_tested", payload["blockers"])
        self.assertIn("led_red_load_not_tested", payload["blockers"])
        self.assertIn("led_white_load_not_tested", payload["blockers"])
        self.assertIn("TC1 SCK/PB13 boot/reset state", payload["open_unknowns"])

    def test_accepts_static_only_controller_discovery_without_live_access(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        summary = build_board_profile_capability_summary(
            profile,
            controller_discovery=ControllerDiscoverySummary(
                controller_kind="klipper",
                status="static_only",
                printer_config_present=True,
            ),
        )
        payload = summary.to_json_dict()

        self.assertEqual(payload["controller_discovery"]["controller_kind"], "klipper")
        self.assertEqual(payload["controller_discovery"]["status"], "static_only")
        self.assertFalse(payload["controller_discovery"]["live_access_performed"])
        self.assertIn("controller_discovery_static_only", payload["capabilities"])
        self.assertIn("controller_discovery_static_only", payload["blockers"])
        self.assertNotIn("printer_config_not_confirmed", payload["blockers"])

    def test_rejects_live_or_output_enabled_controller_discovery(self):
        with self.assertRaisesRegex(ValueError, "live hardware access"):
            ControllerDiscoverySummary(live_access_performed=True)
        with self.assertRaisesRegex(ValueError, "hardware outputs"):
            ControllerDiscoverySummary(hardware_outputs_enabled=True)

    def test_placeholder_profile_preserves_unknowns_and_blocks_outputs(self):
        payload = load_board_profile_capability_summary(SKR_PICO_PROFILE_PATH).to_json_dict()

        self.assertEqual(payload["board"], "skr_pico")
        self.assertEqual(payload["profile_state"], "placeholder")
        self.assertFalse(payload["ready_for_output_simulation"])
        self.assertEqual(payload["camera_or_sync_trigger"]["pin"], "unknown")
        self.assertEqual(payload["motion_kinematics"]["x"]["steps_per_mm"], "unknown")
        self.assertEqual(payload["motion_kinematics"]["z"]["steps_per_um"], "unknown")
        self.assertIn("camera_or_sync_trigger_unknown", payload["blockers"])
        self.assertIn("led_green_pin_unknown", payload["blockers"])
        self.assertIn("led_red_pin_unknown", payload["blockers"])
        self.assertIn("led_white_pin_unknown", payload["blockers"])

    def test_rejects_active_superseded_output_alias(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["pins"]["led_white"] = "PB1"

        with self.assertRaisesRegex(ValueError, "superseded"):
            build_board_profile_capability_summary(profile)

    def test_rejects_legacy_position_event_as_current_trigger(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["pins"]["camera_or_sync_trigger"] = "PC4"

        with self.assertRaisesRegex(ValueError, "legacy_position_event_gpio"):
            build_board_profile_capability_summary(profile)

    def test_rejects_placeholder_words_for_unknown_hardware_facts(self):
        profile = yaml.safe_load(SKR_PICO_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["pins"]["led_green"] = "TODO"

        with self.assertRaisesRegex(ValueError, "explicit 'unknown'"):
            build_board_profile_capability_summary(profile)

    def test_checked_in_summary_fixture_matches_builder(self):
        expected = json.loads(SUMMARY_FIXTURE_PATH.read_text(encoding="utf-8"))
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        actual = build_board_profile_capability_summary(
            profile,
            controller_discovery=ControllerDiscoverySummary(
                controller_kind="klipper",
                status="static_only",
                printer_config_present=True,
            ),
        ).to_json_dict()

        self.assertEqual(actual, expected)

    def test_report_writer_persists_stable_json(self):
        summary = load_board_profile_capability_summary(BOARD_PROFILE_PATH)
        output_path = REPO_ROOT / "tests" / "fixtures" / ".tmp-board-profile-summary.json"
        try:
            summary.write_json(output_path)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")),
                summary.to_json_dict(),
            )
        finally:
            output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
