import sys
import unittest
from fractions import Fraction
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.board_profile.kinematics import (  # noqa: E402
    MotionKinematicsError,
    UNKNOWN,
    derive_motion_kinematics,
    validate_profile_derived_kinematics,
)


BOARD_PROFILE_PATH = REPO_ROOT / "boards" / "kingroon_mono_v2" / "pins.yaml"
KINEMATICS_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "board_profile_kinematics_fixture.yaml"


class BoardProfileKinematicsTests(unittest.TestCase):
    def test_derives_current_kingroon_motion_resolution_from_profile_inputs(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))

        kinematics = derive_motion_kinematics(profile)

        self.assertEqual(kinematics.x.steps_per_mm, Fraction(1600, 1))
        self.assertEqual(kinematics.y.steps_per_mm, Fraction(1600, 1))
        self.assertEqual(kinematics.z.steps_per_mm, Fraction(6400, 1))
        self.assertEqual(kinematics.z.steps_per_um, Fraction(32, 5))
        self.assertEqual(kinematics.axis("z"), kinematics.z)

    def test_validates_documented_derived_values_against_inputs(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))

        validate_profile_derived_kinematics(profile)

    def test_does_not_require_stored_derived_values_as_source_of_truth(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        del profile["mechanics"]["derived_values"]

        validate_profile_derived_kinematics(profile)

    def test_derives_motion_resolution_from_supplied_fixture_inputs(self):
        profile = yaml.safe_load(KINEMATICS_FIXTURE_PATH.read_text(encoding="utf-8"))
        mechanics = profile["mechanics"]
        expected_x = Fraction(
            mechanics["motor_full_steps_per_rev"] * mechanics["configured_microsteps"],
            mechanics["x_travel_per_rev_mm"],
        )

        kinematics = derive_motion_kinematics(profile)
        profile["mechanics"]["configured_microsteps"] = mechanics["configured_microsteps"] // 2
        updated = derive_motion_kinematics(profile)

        self.assertEqual(kinematics.x.steps_per_mm, expected_x)
        self.assertEqual(updated.x.steps_per_mm, expected_x / 2)

    def test_rejects_stale_documented_derived_values(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["mechanics"]["derived_values"]["x_steps_per_mm"] = 3200

        with self.assertRaisesRegex(MotionKinematicsError, "x_steps_per_mm"):
            validate_profile_derived_kinematics(profile)

    def test_rejects_independent_kinematics_constants_outside_derived_values(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["mechanics"]["kinematics"] = {"x_steps_per_mm": 1234}

        with self.assertRaisesRegex(MotionKinematicsError, "independent motion kinematics"):
            validate_profile_derived_kinematics(profile)

    def test_preserves_unknown_motion_sources_and_derived_values(self):
        profile = {
            "mechanics": {
                "motor_full_steps_per_rev": "unknown",
                "configured_microsteps": "unknown",
                "x_travel_per_rev_mm": "unknown",
                "y_travel_per_rev_mm": "unknown",
                "z_travel_per_rev_mm": "unknown",
                "derived_values": {
                    "x_steps_per_mm": "unknown",
                    "y_steps_per_mm": "unknown",
                    "z_steps_per_mm": "unknown",
                    "z_steps_per_um": "unknown",
                },
            }
        }

        kinematics = derive_motion_kinematics(profile)

        self.assertEqual(kinematics.x.steps_per_mm, UNKNOWN)
        self.assertEqual(kinematics.z.steps_per_um, UNKNOWN)
        validate_profile_derived_kinematics(profile)

    def test_rejects_guessed_derived_value_when_source_motion_is_unknown(self):
        profile = {
            "mechanics": {
                "motor_full_steps_per_rev": "unknown",
                "configured_microsteps": "unknown",
                "x_travel_per_rev_mm": "unknown",
                "y_travel_per_rev_mm": "unknown",
                "z_travel_per_rev_mm": "unknown",
                "derived_values": {
                    "x_steps_per_mm": 1600,
                    "y_steps_per_mm": "unknown",
                    "z_steps_per_mm": "unknown",
                    "z_steps_per_um": "unknown",
                },
            }
        }

        with self.assertRaisesRegex(MotionKinematicsError, "must stay unknown"):
            validate_profile_derived_kinematics(profile)

    def test_rejects_missing_or_invalid_motion_inputs(self):
        profile = yaml.safe_load(BOARD_PROFILE_PATH.read_text(encoding="utf-8"))
        profile["mechanics"]["configured_microsteps"] = 0

        with self.assertRaisesRegex(MotionKinematicsError, "configured_microsteps"):
            derive_motion_kinematics(profile)


if __name__ == "__main__":
    unittest.main()
