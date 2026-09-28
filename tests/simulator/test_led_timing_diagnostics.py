from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.led_scheduler.diagnostics import (  # noqa: E402
    LedTimingDiagnosticConfig,
    LedTimingDiagnosticPlanner,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError  # noqa: E402
from scanner_firmware.planning.led_scheduler.types import LedPatternTimingProfile  # noqa: E402


class LedTimingDiagnosticTests(unittest.TestCase):
    def test_no_motion_diagnostic_repeats_same_af_window_at_configured_period(self):
        contracts = LedTimingDiagnosticPlanner().plan(
            LedTimingDiagnosticConfig(
                timing_profile=LedPatternTimingProfile(
                    pattern="AF_RED_GREEN",
                    exposure_start_offset_us=200,
                    exposure_us=600,
                    gate_pulse_us=0,
                    trigger_pulse_us=200,
                    gate_pre_trigger_us=150,
                    gate_post_exposure_us=75,
                    baseline_gate_names=("led_white",),
                    baseline_suppress_pre_gate_us=25,
                    baseline_restore_post_gate_us=50,
                    brightness_by_gate={"led_red": 0.8, "led_green": 0.3},
                ),
                frame_start_us=10_000,
                repeat_period_us=2_000,
                repeat_count=3,
            )
        )

        self.assertEqual([contract.frame_start_us for contract in contracts], [10_000, 12_000, 14_000])
        self.assertEqual([contract.frame_period_us for contract in contracts], [2_000, 2_000, 2_000])
        self.assertTrue(all(contract.hardware_outputs_enabled is False for contract in contracts))
        self.assertEqual(
            [
                (transition.gate_name, transition.time_us, transition.state)
                for transition in contracts[0].baseline_transitions
            ],
            [("led_white", 9_825, "inactive"), ("led_white", 10_925, "active")],
        )
        self.assertEqual(
            [(window.gate_name, window.start_us, window.end_us) for window in contracts[1].gate_windows],
            [("led_red", 11_850, 12_875), ("led_green", 11_850, 12_875)],
        )

    def test_diagnostic_contract_rejects_live_hardware_approval_claims(self):
        with self.assertRaisesRegex(LedTimingError, "hardware outputs disabled"):
            LedTimingDiagnosticConfig(
                timing_profile=LedPatternTimingProfile(
                    pattern="AF_RED_GREEN",
                    exposure_start_offset_us=200,
                    exposure_us=600,
                    gate_pulse_us=0,
                ),
                frame_start_us=0,
                repeat_period_us=1_000,
                repeat_count=1,
                hardware_outputs_enabled=True,
            )

    def test_diagnostic_repeat_period_must_not_overlap_led_windows(self):
        with self.assertRaisesRegex(LedTimingError, "overlaps"):
            LedTimingDiagnosticPlanner().plan(
                LedTimingDiagnosticConfig(
                    timing_profile=LedPatternTimingProfile(
                        pattern="AF_RED_GREEN",
                        exposure_start_offset_us=200,
                        exposure_us=600,
                        gate_pulse_us=0,
                        trigger_pulse_us=200,
                        gate_pre_trigger_us=150,
                        gate_post_exposure_us=75,
                        baseline_gate_names=("led_white",),
                        baseline_suppress_pre_gate_us=25,
                        baseline_restore_post_gate_us=50,
                    ),
                    frame_start_us=10_000,
                    repeat_period_us=1_000,
                    repeat_count=2,
                )
            )


if __name__ == "__main__":
    unittest.main()
