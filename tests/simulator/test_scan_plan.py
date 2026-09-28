import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.trigger_scheduler.errors import ScanPlanError  # noqa: E402
from scanner_firmware.planning.trigger_scheduler.recipe_builder import (  # noqa: E402
    build_stripe_schedule,
    build_stripe_schedules,
)


class ScanPlanTests(unittest.TestCase):
    def test_builds_valid_x_stripe_with_defaults(self):
        recipe = {
            "scan_id": "scan-plan-a",
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 100,
                    "first_event": 20,
                    "event_pitch": 20,
                    "event_count": 3,
                    "pattern_sequence": ["BF_WHITE", "AF_RED_GREEN"],
                }
            ],
        }

        schedule = build_stripe_schedule(recipe)

        self.assertEqual(schedule.scan_id, "scan-plan-a")
        self.assertEqual(schedule.stripe_id, 1)
        self.assertEqual(schedule.axis, "X")
        self.assertEqual(schedule.start_position, 0)
        self.assertEqual(schedule.end_position, 100)
        self.assertEqual(schedule.first_event_position, 20)
        self.assertEqual(schedule.event_pitch, 20)
        self.assertEqual(schedule.event_count, 3)
        self.assertEqual(schedule.pattern_sequence, ("BF_WHITE", "AF_RED_GREEN"))
        self.assertEqual(schedule.coordinate_source, "step_indexed")
        self.assertTrue(schedule.dry_run)
        self.assertFalse(schedule.hardware_outputs_enabled)

    def test_builds_valid_y_stripe_with_position_field_names(self):
        recipe = {
            "scan_id": "scan-plan-b",
            "dry_run": True,
            "hardware_outputs_enabled": False,
            "stripes": [
                {
                    "stripe_id": 2,
                    "axis": "Y",
                    "start_position": 10,
                    "end_position": 70,
                    "first_event_position": 30,
                    "event_pitch": 20,
                    "event_count": 2,
                    "pattern_sequence": ["BF_WHITE"],
                    "coordinate_source": "hybrid",
                }
            ],
        }

        schedule = build_stripe_schedule(recipe)

        self.assertEqual(schedule.axis, "Y")
        self.assertEqual(schedule.start_position, 10)
        self.assertEqual(schedule.end_position, 70)
        self.assertEqual(schedule.first_event_position, 30)
        self.assertEqual(schedule.event_pitch, 20)
        self.assertEqual(schedule.event_count, 2)
        self.assertEqual(schedule.pattern_sequence, ("BF_WHITE",))
        self.assertEqual(schedule.coordinate_source, "hybrid")

    def test_builds_valid_reverse_stripe(self):
        recipe = {
            "scan_id": "scan-plan-c",
            "stripes": [
                {
                    "stripe_id": 3,
                    "axis": "X",
                    "start": 100,
                    "end": 0,
                    "first_event": 80,
                    "event_pitch": -20,
                    "event_count": 4,
                    "pattern_sequence": ["BF_WHITE"],
                }
            ],
        }

        schedule = build_stripe_schedule(recipe)

        self.assertEqual(schedule.start_position, 100)
        self.assertEqual(schedule.end_position, 0)
        self.assertEqual(schedule.first_event_position, 80)
        self.assertEqual(schedule.event_pitch, -20)
        self.assertEqual(schedule.event_count, 4)

    def test_builds_all_stripes(self):
        recipe = {
            "scan_id": "scan-plan-d",
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 2,
                    "pattern_sequence": ["BF_WHITE"],
                },
                {
                    "stripe_id": 2,
                    "axis": "Y",
                    "start": 20,
                    "end": 0,
                    "first_event": 10,
                    "event_pitch": -10,
                    "event_count": 1,
                    "pattern_sequence": ["AF_RED_GREEN"],
                },
            ],
        }

        schedules = build_stripe_schedules(recipe)

        self.assertEqual([schedule.stripe_id for schedule in schedules], [1, 2])
        self.assertEqual([schedule.axis for schedule in schedules], ["X", "Y"])

    def test_builds_pattern_level_led_timing_profiles_from_recipe_and_stripe_override(self):
        recipe = {
            "scan_id": "scan-plan-led-timing",
            "pattern_led_timing": {
                "BF_WHITE": {
                    "exposure_start_offset_us": 100,
                    "exposure_us": 1000,
                    "gate_pulse_us": 200,
                    "settle_us": 50,
                    "frame_period_us": 2500,
                    "trigger_pulse_us": 80,
                    "brightness_by_gate": {"led_white": 0.5},
                },
                "AF_RED_GREEN": {
                    "exposure_start_offset_us": 200,
                    "exposure_us": 600,
                    "gate_pulse_us": 0,
                    "frame_period_us": 2000,
                    "trigger_pulse_us": 200,
                    "gate_pre_trigger_us": 150,
                    "gate_post_exposure_us": 75,
                    "baseline_gate_names": ["led_white"],
                    "baseline_suppress_pre_gate_us": 25,
                    "baseline_restore_post_gate_us": 50,
                    "brightness_by_gate": {"led_red": 0.8, "led_green": 0.3},
                },
            },
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 1,
                    "pattern_sequence": ["BF_WHITE"],
                },
                {
                    "stripe_id": 2,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 1,
                    "pattern_sequence": ["AF_RED_GREEN"],
                    "pattern_led_timing": {
                        "AF_RED_GREEN": {
                            "exposure_start_offset_us": 25,
                            "exposure_us": 500,
                            "gate_pulse_us": 0,
                            "trigger_pulse_us": 100,
                            "gate_pre_trigger_us": 50,
                            "gate_post_exposure_us": 25,
                        },
                    },
                },
            ],
        }

        first, second = build_stripe_schedules(recipe)

        self.assertIsNotNone(first.pattern_led_timing)
        self.assertEqual(first.pattern_led_timing.patterns, ("BF_WHITE", "AF_RED_GREEN"))
        bf_profile = first.pattern_led_timing.profile_for("BF_WHITE")
        af_profile = first.pattern_led_timing.profile_for("AF_RED_GREEN")
        self.assertEqual(bf_profile.exposure_start_offset_us, 100)
        self.assertEqual(bf_profile.frame_period_us, 2500)
        self.assertEqual(bf_profile.trigger_pulse_us, 80)
        self.assertEqual(bf_profile.brightness_by_gate, {"led_white": 0.5})
        self.assertEqual(af_profile.exposure_start_offset_us, 200)
        self.assertEqual(af_profile.frame_period_us, 2000)
        self.assertEqual(af_profile.trigger_pulse_us, 200)
        self.assertEqual(af_profile.gate_pre_trigger_us, 150)
        self.assertEqual(af_profile.gate_post_exposure_us, 75)
        self.assertEqual(af_profile.baseline_gate_names, ("led_white",))
        self.assertEqual(af_profile.baseline_suppress_pre_gate_us, 25)
        self.assertEqual(af_profile.baseline_restore_post_gate_us, 50)
        self.assertEqual(af_profile.brightness_by_gate, {"led_red": 0.8, "led_green": 0.3})
        self.assertIsNotNone(second.pattern_led_timing)
        override_profile = second.pattern_led_timing.profile_for("AF_RED_GREEN")
        self.assertEqual(second.pattern_led_timing.patterns, ("BF_WHITE", "AF_RED_GREEN"))
        self.assertEqual(override_profile.exposure_start_offset_us, 25)
        self.assertEqual(override_profile.exposure_us, 500)
        self.assertIsNone(override_profile.brightness_by_gate)
        self.assertEqual(
            second.pattern_led_timing.profile_for("BF_WHITE").exposure_start_offset_us,
            100,
        )

    def test_rejects_hardware_shaped_led_timing_fields(self):
        recipe = {
            "scan_id": "scan-plan-led-timing-rejects-hardware",
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 1,
                    "pattern_sequence": ["BF_WHITE"],
                    "pattern_led_timing": {
                        "BF_WHITE": {
                            "exposure_start_offset_us": 100,
                            "exposure_us": 1000,
                            "gate_pulse_us": 200,
                            "gpio_pin": "PA9",
                        },
                    },
                }
            ],
        }

        with self.assertRaisesRegex(ScanPlanError, "unknown fields: gpio_pin"):
            build_stripe_schedule(recipe)

    def test_rejects_legacy_flat_led_timing_recipe_field(self):
        recipe = {
            "scan_id": "scan-plan-led-timing-legacy",
            "led_timing": {
                "exposure_start_offset_us": 100,
                "exposure_us": 1000,
                "gate_pulse_us": 200,
            },
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 1,
                    "pattern_sequence": ["BF_WHITE"],
                }
            ],
        }

        with self.assertRaisesRegex(ScanPlanError, "pattern_led_timing"):
            build_stripe_schedule(recipe)

    def test_validates_stripes_against_optional_soft_limits(self):
        recipe = {
            "scan_id": "scan-plan-soft-limits",
            "soft_limits": {
                "X": {"min": 0, "max": 100},
                "Y": {"min": -20, "max": 20},
            },
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 100,
                    "first_event": 20,
                    "event_pitch": 20,
                    "event_count": 3,
                    "pattern_sequence": ["BF_WHITE"],
                },
                {
                    "stripe_id": 2,
                    "axis": "Y",
                    "start": -20,
                    "end": 20,
                    "first_event": 0,
                    "event_pitch": 10,
                    "event_count": 2,
                    "pattern_sequence": ["BF_WHITE"],
                },
            ],
        }

        schedules = build_stripe_schedules(recipe)

        self.assertEqual(len(schedules), 2)

    def test_rejects_stripe_outside_optional_soft_limits(self):
        recipe = {
            "scan_id": "scan-plan-soft-limit-fail",
            "soft_limits": {"X": {"min": 0, "max": 90}},
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 100,
                    "first_event": 20,
                    "event_pitch": 20,
                    "event_count": 3,
                    "pattern_sequence": ["BF_WHITE"],
                },
            ],
        }

        with self.assertRaisesRegex(ScanPlanError, "soft limits"):
            build_stripe_schedule(recipe)

    def test_rejects_malformed_soft_limits(self):
        valid_stripe = {
            "stripe_id": 1,
            "axis": "X",
            "start": 0,
            "end": 20,
            "first_event": 10,
            "event_pitch": 10,
            "event_count": 1,
            "pattern_sequence": ["BF_WHITE"],
        }

        for soft_limits in (
            [],
            {"X": []},
            {"X": {"min": 10, "max": 0}},
            {"X": {"min": True, "max": 10}},
        ):
            with self.subTest(soft_limits=soft_limits):
                with self.assertRaises(ScanPlanError):
                    build_stripe_schedule(
                        {
                            "scan_id": "scan-plan-bad-soft-limits",
                            "soft_limits": soft_limits,
                            "stripes": [valid_stripe],
                        }
                    )

    def test_rejects_hardware_outputs_enabled_at_recipe_level(self):
        recipe = {
            "scan_id": "scan-plan-e",
            "hardware_outputs_enabled": True,
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 1,
                    "pattern_sequence": ["BF_WHITE"],
                }
            ],
        }

        with self.assertRaisesRegex(ScanPlanError, "hardware_outputs_enabled"):
            build_stripe_schedule(recipe)

    def test_rejects_hardware_outputs_enabled_at_stripe_level(self):
        recipe = {
            "scan_id": "scan-plan-f",
            "stripes": [
                {
                    "stripe_id": 1,
                    "axis": "X",
                    "start": 0,
                    "end": 20,
                    "first_event": 10,
                    "event_pitch": 10,
                    "event_count": 1,
                    "pattern_sequence": ["BF_WHITE"],
                    "hardware_outputs_enabled": True,
                }
            ],
        }

        with self.assertRaisesRegex(ScanPlanError, "hardware_outputs_enabled"):
            build_stripe_schedule(recipe)

    def test_rejects_invalid_required_fields(self):
        valid_stripe = {
            "stripe_id": 1,
            "axis": "X",
            "start": 0,
            "end": 20,
            "first_event": 10,
            "event_pitch": 10,
            "event_count": 1,
            "pattern_sequence": ["BF_WHITE"],
        }

        invalid_cases = [
            {"scan_id": "", "stripes": [valid_stripe]},
            {
                "scan_id": "scan-plan-g",
                "stripes": [{**valid_stripe, "stripe_id": True}],
            },
            {"scan_id": "scan-plan-g", "stripes": [{**valid_stripe, "axis": "Z"}]},
            {
                "scan_id": "scan-plan-g",
                "stripes": [{**valid_stripe, "event_pitch": 0}],
            },
            {
                "scan_id": "scan-plan-g",
                "stripes": [{**valid_stripe, "event_count": -1}],
            },
            {
                "scan_id": "scan-plan-g",
                "stripes": [{**valid_stripe, "pattern_sequence": []}],
            },
            {
                "scan_id": "scan-plan-g",
                "stripes": [{**valid_stripe, "first_event": 30}],
            },
            {
                "scan_id": "scan-plan-g",
                "stripes": [{**valid_stripe, "event_pitch": -10}],
            },
        ]

        for recipe in invalid_cases:
            with self.subTest(recipe=recipe):
                with self.assertRaises(ScanPlanError):
                    build_stripe_schedule(recipe)


if __name__ == "__main__":
    unittest.main()
