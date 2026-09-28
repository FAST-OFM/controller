import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.homing.feasibility import (  # noqa: E402
    REQUIRED_HOMING_AXES,
)
from scanner_firmware.adapters.homing.readiness import (  # noqa: E402
    AxisHomingReadiness,
    HomingReadinessInput,
    current_mks_a4988_homing_readiness,
    evaluate_homing_readiness,
    future_pico_homing_readiness_candidate,
)


class HomingReadinessContractTests(unittest.TestCase):
    def test_position_setting_override_does_not_satisfy_physical_homing(self):
        decision = evaluate_homing_readiness(current_mks_a4988_homing_readiness())

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.status, "blocked")
        self.assertEqual(decision.physically_homed_axes, ())
        self.assertEqual(decision.missing_axes, REQUIRED_HOMING_AXES)
        self.assertIn(
            "physical homing is missing for required axes: X, Y, Z",
            decision.blockers,
        )
        self.assertIn(
            "homing override only sets position and does not physically home axes: "
            "X, Y, Z",
            decision.blockers,
        )
        self.assertIn(
            "hardware outputs cannot be enabled until homing is ready",
            decision.blockers,
        )

    def test_incomplete_physical_homing_blocks_required_axes(self):
        decision = evaluate_homing_readiness(
            HomingReadinessInput(
                axes=(
                    AxisHomingReadiness(axis="X", homed_by=("physical_switch",)),
                    AxisHomingReadiness(axis="Y", homed_by=("encoder_index",)),
                    AxisHomingReadiness(axis="Z"),
                ),
                hardware_outputs_enabled=False,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.physically_homed_axes, ("X", "Y"))
        self.assertEqual(decision.missing_axes, ("Z",))
        self.assertEqual(
            decision.blockers,
            ("physical homing is missing for required axes: Z",),
        )

    def test_simulator_safe_disabled_mode_warns_instead_of_accepting_live_readiness(self):
        decision = evaluate_homing_readiness(
            current_mks_a4988_homing_readiness(
                simulator_mode=True,
                hardware_outputs_enabled=False,
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.status, "simulator_safe_disabled")
        self.assertEqual(decision.missing_axes, REQUIRED_HOMING_AXES)
        self.assertEqual(decision.blockers, ())
        self.assertTrue(
            all(
                warning.startswith("simulator safe-disabled mode accepted")
                for warning in decision.warnings
            )
        )

    def test_z_policy_missing_blocks_even_when_axes_are_homed(self):
        decision = evaluate_homing_readiness(
            HomingReadinessInput(
                axes=tuple(
                    AxisHomingReadiness(axis=axis, homed_by=("physical_switch",))
                    for axis in REQUIRED_HOMING_AXES
                ),
                z_policy_configured=False,
                hardware_outputs_enabled=False,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, ())
        self.assertEqual(
            decision.blockers,
            ("Z homing policy must be configured before scan start",),
        )

    def test_future_pico_candidate_remains_unknown_not_homed(self):
        candidate = future_pico_homing_readiness_candidate(hardware_outputs_enabled=False)
        decision = evaluate_homing_readiness(candidate)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.missing_axes, REQUIRED_HOMING_AXES)
        self.assertEqual(
            decision.blockers,
            (
                "physical homing is missing for required axes: X, Y, Z",
                "Z homing policy must be configured before scan start",
            ),
        )


if __name__ == "__main__":
    unittest.main()
