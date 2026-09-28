import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.homing.simulator import (  # noqa: E402
    HomingConfig,
    HomingConfigError,
    HomingFault,
    HomingSample,
    simulate_homing,
)
from scanner_firmware.adapters.homing.feasibility import (  # noqa: E402
    HomingFeasibilitySnapshot,
    axis_feasibility_from_driver,
    current_mks_a4988_homing_feasibility,
    sensorless_support_for_driver,
)


class HomingSimulatorTests(unittest.TestCase):
    def test_physical_switch_homing_success(self):
        result = simulate_homing(
            HomingConfig(
                axis="X",
                source="physical_switch",
                seek_direction=-1,
                max_travel_counts=100,
                backoff_counts=10,
            ),
            [
                HomingSample(50),
                HomingSample(30),
                HomingSample(10, switch_active=True),
                HomingSample(25, switch_active=False),
            ],
        )

        self.assertTrue(result.homed)
        self.assertEqual(result.machine_zero_count, 10)

    def test_sensorless_homing_success(self):
        result = simulate_homing(
            HomingConfig(
                axis="Y",
                source="sensorless",
                seek_direction=1,
                max_travel_counts=100,
                backoff_counts=5,
                driver_supports_sensorless=True,
            ),
            [
                HomingSample(0),
                HomingSample(20),
                HomingSample(40, sensorless_triggered=True),
                HomingSample(30, sensorless_triggered=False),
            ],
        )

        self.assertTrue(result.homed)
        self.assertEqual(result.activation_count, 40)

    def test_encoder_index_homing_success(self):
        result = simulate_homing(
            HomingConfig(
                axis="X",
                source="encoder_index",
                seek_direction=1,
                max_travel_counts=100,
                backoff_counts=5,
            ),
            [
                HomingSample(0),
                HomingSample(10),
                HomingSample(20, encoder_index_seen=True),
                HomingSample(10, encoder_index_seen=False),
            ],
        )

        self.assertTrue(result.homed)
        self.assertEqual(result.machine_zero_count, 20)

    def test_fault_when_trigger_active_before_start(self):
        result = simulate_homing(
            HomingConfig(
                axis="X",
                source="physical_switch",
                seek_direction=-1,
                max_travel_counts=100,
                backoff_counts=10,
            ),
            [HomingSample(50, switch_active=True)],
        )

        self.assertFalse(result.homed)
        self.assertEqual(result.fault, HomingFault.ENDSTOP_ACTIVE_BEFORE_START)

    def test_fault_when_wrong_direction(self):
        result = simulate_homing(
            HomingConfig(
                axis="X",
                source="physical_switch",
                seek_direction=-1,
                max_travel_counts=100,
                backoff_counts=10,
            ),
            [HomingSample(50), HomingSample(55)],
        )

        self.assertFalse(result.homed)
        self.assertEqual(result.fault, HomingFault.WRONG_DIRECTION)

    def test_fault_when_z_policy_missing(self):
        result = simulate_homing(
            HomingConfig(
                axis="Z",
                source="sensorless",
                seek_direction=-1,
                max_travel_counts=100,
                backoff_counts=10,
                z_policy_configured=False,
                driver_supports_sensorless=True,
            ),
            [HomingSample(50), HomingSample(40, sensorless_triggered=True)],
        )

        self.assertFalse(result.homed)
        self.assertEqual(result.fault, HomingFault.Z_POLICY_MISSING)

    def test_sensorless_homing_rejects_driver_without_capability(self):
        with self.assertRaises(HomingConfigError):
            simulate_homing(
                HomingConfig(
                    axis="X",
                    source="sensorless",
                    seek_direction=-1,
                    max_travel_counts=100,
                    backoff_counts=10,
                    driver_supports_sensorless=False,
                ),
                [HomingSample(0), HomingSample(-10, sensorless_triggered=True)],
            )

    def test_current_mks_a4988_feasibility_keeps_homing_not_implemented(self):
        snapshot = current_mks_a4988_homing_feasibility()

        self.assertEqual(snapshot.implementation_status, "not_implemented")
        self.assertEqual(snapshot.scan_preflight_status, "not_implemented")
        self.assertEqual(snapshot.missing_axes, ("X", "Y", "Z"))
        self.assertTrue(
            all(axis.driver_type == "A4988" for axis in snapshot.axes)
        )
        self.assertTrue(
            all(axis.sensorless == "not_supported" for axis in snapshot.axes)
        )
        self.assertTrue(
            all(axis.sensorless_support == "not_supported" for axis in snapshot.axes)
        )

    def test_a4988_sensorless_support_is_not_assumed(self):
        axis = axis_feasibility_from_driver("X", driver_type="A4988")

        self.assertEqual(sensorless_support_for_driver("A4988"), "not_supported")
        self.assertEqual(axis.sensorless, "not_supported")
        self.assertEqual(axis.physical_switch, "unknown")
        self.assertEqual(axis.encoder_index, "unknown")
        self.assertFalse(axis.has_accepted_source)

    def test_unknown_hardware_values_are_preserved_as_unknown(self):
        axis = axis_feasibility_from_driver("Y", driver_type="unknown")
        snapshot = HomingFeasibilitySnapshot(
            axes=(axis,),
            implementation_status="unknown",
            notes=("driver model unknown",),
        )

        self.assertEqual(axis.driver_type, "unknown")
        self.assertEqual(axis.sensorless, "unknown")
        self.assertEqual(axis.sensorless_support, "unknown")
        self.assertEqual(snapshot.scan_preflight_status, "unknown")


if __name__ == "__main__":
    unittest.main()
