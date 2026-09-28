from __future__ import annotations

from dataclasses import replace
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.foundation.protocol.events import FrameEventRecord  # noqa: E402
from scanner_firmware.planning.led_scheduler.atomic_window import (  # noqa: E402
    MksV1AtomicIlluminationWindowConfig,
    build_mks_v1_no_motion_af_window,
    validate_frame_event_mks_v1_atomic_illumination_window,
    validate_mks_v1_atomic_illumination_window,
)
from scanner_firmware.planning.led_scheduler.errors import LedTimingError  # noqa: E402
from scanner_firmware.planning.led_scheduler.types import (  # noqa: E402
    DisabledOutputLedTimingContract,
    LedBaselineTransition,
    LedGateWindow,
)


class AtomicIlluminationWindowTests(unittest.TestCase):
    def test_builds_v1_no_motion_af_window_as_disabled_output_contract(self):
        window = build_mks_v1_no_motion_af_window(
            MksV1AtomicIlluminationWindowConfig(
                frame_start_us=20_000,
                settle_us=150,
                exposure_hold_us=800,
                xvs_trigger_pulse_us=200,
                trigger_position_count=12_345,
                frame_period_us=2_000,
                red_brightness=0.8,
                green_brightness=0.7,
            )
        )
        contract = window.contract

        self.assertEqual(window.red_green_on_us, 19_850)
        self.assertEqual(window.trigger_position_count, 12_345)
        self.assertEqual(window.xvs_trigger_us, 20_000)
        self.assertEqual(window.red_green_off_us, 20_800)
        self.assertEqual(window.white_restore_us, 20_800)
        self.assertEqual(window.settle_us, 150)
        self.assertEqual(window.exposure_hold_us, 800)
        self.assertFalse(contract.hardware_outputs_enabled)
        self.assertEqual(contract.pattern, "AF_RED_GREEN")
        self.assertEqual(contract.logical_channel_names, ("led_red", "led_green"))
        self.assertEqual(
            [(window.gate_name, window.start_us, window.end_us) for window in contract.gate_windows],
            [("led_red", 19_850, 20_800), ("led_green", 19_850, 20_800)],
        )
        self.assertEqual(
            [
                (transition.gate_name, transition.time_us, transition.state)
                for transition in contract.baseline_transitions
            ],
            [("led_white", 19_850, "inactive"), ("led_white", 20_800, "active")],
        )
        self.assertEqual(contract.trigger_start_us, 20_000)
        self.assertEqual(contract.trigger_end_us, 20_200)
        self.assertEqual(contract.exposure_start_us, 20_000)
        self.assertEqual(contract.exposure_end_us, 20_800)

    def test_validates_frame_event_payload_for_atomic_window(self):
        window = build_mks_v1_no_motion_af_window(
            MksV1AtomicIlluminationWindowConfig(
                frame_start_us=20_000,
                settle_us=150,
                exposure_hold_us=800,
                xvs_trigger_pulse_us=200,
            )
        )

        validated = validate_frame_event_mks_v1_atomic_illumination_window(
            _frame_event(
                mcu_time_us=20_000,
                led_timing=window.contract.to_json_dict(),
            )
        )

        self.assertEqual(validated.red_green_on_us, 19_850)
        self.assertEqual(validated.white_restore_us, 20_800)

    def test_rejects_non_atomic_red_green_edges(self):
        contract = _valid_contract()
        red, green = contract.gate_windows
        non_atomic_contract = replace(
            contract,
            gate_windows=(
                red,
                replace(green, start_us=red.start_us + 1),
            ),
        )

        with self.assertRaisesRegex(LedTimingError, "turn on atomically"):
            validate_mks_v1_atomic_illumination_window(non_atomic_contract)

        non_atomic_contract = replace(
            contract,
            gate_windows=(
                red,
                replace(green, end_us=red.end_us + 1),
            ),
        )

        with self.assertRaisesRegex(LedTimingError, "turn off atomically"):
            validate_mks_v1_atomic_illumination_window(non_atomic_contract)

    def test_rejects_missing_white_suppress_restore(self):
        contract = _valid_contract()

        with self.assertRaisesRegex(LedTimingError, "suppress led_white"):
            validate_mks_v1_atomic_illumination_window(
                replace(
                    contract,
                    baseline_gate_names=(),
                    baseline_transitions=(),
                )
            )

        with self.assertRaisesRegex(LedTimingError, "led_white must restore"):
            validate_mks_v1_atomic_illumination_window(
                replace(
                    contract,
                    baseline_transitions=(
                        LedBaselineTransition(
                            gate_name="led_white",
                            time_us=contract.gate_windows[0].start_us,
                            state="inactive",
                            reason="test",
                        ),
                        LedBaselineTransition(
                            gate_name="led_white",
                            time_us=contract.gate_windows[0].end_us + 1,
                            state="active",
                            reason="test",
                        ),
                    ),
                )
            )

    def test_rejects_enabled_outputs_and_physical_pin_names(self):
        contract = _valid_contract()

        with self.assertRaisesRegex(LedTimingError, "hardware outputs disabled"):
            validate_mks_v1_atomic_illumination_window(
                replace(contract, hardware_outputs_enabled=True)
            )

        with self.assertRaisesRegex(LedTimingError, "red and green logical gates"):
            validate_mks_v1_atomic_illumination_window(
                DisabledOutputLedTimingContract(
                    pattern="AF_RED_GREEN",
                    frame_use="autofocus",
                    logical_channel_names=("PA10", "PA9"),
                    frame_start_us=20_000,
                    exposure_start_us=20_000,
                    exposure_end_us=20_800,
                    brightness_setpoints=(),
                    gate_windows=(
                        LedGateWindow(
                            gate_name="led_red",
                            start_us=19_850,
                            end_us=20_800,
                            polarity="active_high",
                        ),
                        LedGateWindow(
                            gate_name="led_green",
                            start_us=19_850,
                            end_us=20_800,
                            polarity="active_high",
                        ),
                    ),
                    baseline_gate_names=("led_white",),
                    baseline_transitions=contract.baseline_transitions,
                    trigger_start_us=20_000,
                    trigger_end_us=20_200,
                )
            )

    def test_rejects_trigger_without_settle_or_hold(self):
        with self.assertRaisesRegex(LedTimingError, "settle_us must be positive"):
            build_mks_v1_no_motion_af_window(
                MksV1AtomicIlluminationWindowConfig(
                    frame_start_us=20_000,
                    settle_us=0,
                    exposure_hold_us=800,
                    xvs_trigger_pulse_us=200,
                )
            )

        with self.assertRaisesRegex(LedTimingError, "fit inside exposure_hold_us"):
            build_mks_v1_no_motion_af_window(
                MksV1AtomicIlluminationWindowConfig(
                    frame_start_us=20_000,
                    settle_us=150,
                    exposure_hold_us=100,
                    xvs_trigger_pulse_us=200,
                )
            )

        with self.assertRaisesRegex(LedTimingError, "trigger_position_count"):
            build_mks_v1_no_motion_af_window(
                MksV1AtomicIlluminationWindowConfig(
                    frame_start_us=20_000,
                    settle_us=150,
                    exposure_hold_us=800,
                    xvs_trigger_pulse_us=200,
                    trigger_position_count=-1,
                )
            )


def _valid_contract():
    return build_mks_v1_no_motion_af_window(
        MksV1AtomicIlluminationWindowConfig(
            frame_start_us=20_000,
            settle_us=150,
            exposure_hold_us=800,
            xvs_trigger_pulse_us=200,
        )
    ).contract


def _frame_event(
    *,
    mcu_time_us: int,
    led_timing: dict,
) -> FrameEventRecord:
    return FrameEventRecord(
        protocol_version="1.0.0",
        scan_id="mks-atomic-illumination-window-fixture",
        stripe_id=4,
        frame_id=300,
        stripe_frame_index=0,
        pattern="AF_RED_GREEN",
        led_gate_names=("led_red", "led_green"),
        led_timing=led_timing,
        trigger_output_name="camera_or_sync_trigger",
        coordinate_source_used="step_indexed",
        position_axis="X",
        event_position=1000,
        sample_position=1000,
        position_overshoot_count=0,
        x_count=1000,
        y_count=80,
        z_count=0,
        x_step_commanded=1000,
        y_step_commanded=80,
        z_step_commanded=0,
        x_encoder_count=None,
        y_encoder_count=None,
        coordinate_flags=(),
        mcu_time_us=mcu_time_us,
        hardware_outputs_enabled=False,
        status="OK",
    )


if __name__ == "__main__":
    unittest.main()
