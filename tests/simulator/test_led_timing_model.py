from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.led_scheduler.constants import ACTIVE_HIGH, ACTIVE_LOW  # noqa: E402
from scanner_firmware.planning.led_scheduler.errors import LedTimingError  # noqa: E402
from scanner_firmware.planning.led_scheduler.timing import LogicalLedTimingModel  # noqa: E402
from scanner_firmware.planning.led_scheduler.timing import (  # noqa: E402
    build_disabled_output_led_timing_contract,
    validate_frame_event_led_timing_contract,
)
from scanner_firmware.planning.led_scheduler.types import (  # noqa: E402
    DisabledOutputLedTimingContract,
    LedPattern,
)
from scanner_firmware.foundation.protocol.events import FrameEventRecord  # noqa: E402


class LedTimingModelTests(unittest.TestCase):
    def test_brightness_setpoint_is_separate_from_gate_timing(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="BF_WHITE",
            frame_start_us=10_000,
            exposure_start_us=10_250,
            exposure_us=1_000,
            gate_pulse_us=400,
            settle_us=50,
            brightness_by_gate={"led_white": 0.42},
        )

        self.assertEqual(plan.exposure.start_us, 10_250)
        self.assertEqual(plan.exposure.end_us, 11_250)
        self.assertEqual(
            [(setpoint.gate_name, setpoint.brightness) for setpoint in plan.brightness_setpoints],
            [("led_white", 0.42)],
        )
        self.assertEqual(
            [
                (window.gate_name, window.start_us, window.end_us, window.polarity)
                for window in plan.gate_windows
            ],
            [("led_white", 10_300, 10_700, ACTIVE_HIGH)],
        )

    def test_active_low_polarity_is_carried_on_gate_window(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="BF_WHITE",
            frame_start_us=0,
            exposure_start_us=100,
            exposure_us=500,
            gate_pulse_us=200,
            polarity=ACTIVE_LOW,
        )

        self.assertEqual(plan.gate_windows[0].polarity, ACTIVE_LOW)
        self.assertEqual(plan.gate_windows[0].active_level, 0)

    def test_rejects_unsupported_polarity(self):
        with self.assertRaisesRegex(LedTimingError, "unsupported LED polarity"):
            LogicalLedTimingModel().plan_frame(
                pattern="BF_WHITE",
                frame_start_us=0,
                exposure_start_us=0,
                exposure_us=500,
                gate_pulse_us=200,
                polarity="active_middle",
            )

    def test_rejects_pulse_sequence_that_exceeds_exposure_window(self):
        with self.assertRaisesRegex(LedTimingError, "exceed exposure window"):
            LogicalLedTimingModel().plan_frame(
                pattern="AF_RED_GREEN",
                frame_start_us=0,
                exposure_start_us=100,
                exposure_us=500,
                gate_pulse_us=250,
                settle_us=1,
            )

    def test_dark_pattern_has_no_brightness_setpoints_or_gates(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="DARK",
            frame_start_us=0,
            exposure_start_us=100,
            exposure_us=500,
            gate_pulse_us=0,
            settle_us=20,
        )

        self.assertEqual(plan.brightness_setpoints, ())
        self.assertEqual(plan.gate_windows, ())

    def test_red_green_autofocus_order_is_deterministic(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="AF_RED_GREEN",
            frame_start_us=0,
            exposure_start_us=1_000,
            exposure_us=1_000,
            gate_pulse_us=200,
            settle_us=100,
            brightness_by_gate={"led_red": 0.6, "led_green": 0.7},
        )

        self.assertEqual(
            [(setpoint.gate_name, setpoint.brightness) for setpoint in plan.brightness_setpoints],
            [("led_red", 0.6), ("led_green", 0.7)],
        )
        self.assertEqual(
            [(window.gate_name, window.start_us, window.end_us) for window in plan.gate_windows],
            [("led_red", 1_100, 1_300), ("led_green", 1_300, 1_500)],
        )

    def test_pattern_window_can_envelope_trigger_and_exposure(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="AF_RED_GREEN",
            frame_start_us=10_000,
            exposure_start_us=10_200,
            exposure_us=600,
            gate_pulse_us=0,
            frame_period_us=2_000,
            trigger_pulse_us=200,
            gate_pre_trigger_us=150,
            gate_post_exposure_us=75,
            brightness_by_gate={"led_red": 0.8, "led_green": 0.3},
        )

        self.assertEqual(plan.frame_period_us, 2_000)
        self.assertEqual(plan.trigger_start_us, 10_000)
        self.assertEqual(plan.trigger_end_us, 10_200)
        self.assertEqual(plan.exposure.start_us, 10_200)
        self.assertEqual(plan.exposure.end_us, 10_800)
        self.assertEqual(
            [(window.gate_name, window.start_us, window.end_us) for window in plan.gate_windows],
            [("led_red", 9_850, 10_875), ("led_green", 9_850, 10_875)],
        )

        payload = build_disabled_output_led_timing_contract(plan).to_json_dict()
        self.assertEqual(payload["frame_period_us"], 2_000)
        self.assertEqual(payload["trigger_start_us"], 10_000)
        self.assertEqual(payload["trigger_end_us"], 10_200)
        validated = validate_frame_event_led_timing_contract(
            _frame_event(
                pattern="AF_RED_GREEN",
                led_gate_names=("led_red", "led_green"),
                mcu_time_us=10_000,
                led_timing=payload,
            )
        )
        self.assertEqual(validated.gate_windows[0].start_us, 9_850)
        self.assertEqual(validated.gate_windows[0].end_us, 10_875)

    def test_af_window_suppresses_and_restores_white_preview_baseline(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="AF_RED_GREEN",
            frame_start_us=10_000,
            exposure_start_us=10_200,
            exposure_us=600,
            gate_pulse_us=0,
            trigger_pulse_us=200,
            gate_pre_trigger_us=150,
            gate_post_exposure_us=75,
            baseline_gate_names=("led_white",),
            baseline_suppress_pre_gate_us=25,
            baseline_restore_post_gate_us=50,
            brightness_by_gate={"led_red": 0.8, "led_green": 0.3},
        )

        self.assertEqual(plan.trigger_start_us, 10_000)
        self.assertEqual(plan.trigger_end_us, 10_200)
        self.assertEqual(
            [(window.gate_name, window.start_us, window.end_us) for window in plan.gate_windows],
            [("led_red", 9_850, 10_875), ("led_green", 9_850, 10_875)],
        )
        self.assertEqual(plan.baseline_gate_names, ("led_white",))
        self.assertEqual(
            [
                (transition.gate_name, transition.time_us, transition.state)
                for transition in plan.baseline_transitions
            ],
            [("led_white", 9_825, "inactive"), ("led_white", 10_925, "active")],
        )

        contract = build_disabled_output_led_timing_contract(plan)
        self.assertEqual(contract.baseline_gate_names, ("led_white",))
        self.assertEqual(
            [
                (transition.gate_name, transition.time_us, transition.state)
                for transition in contract.baseline_transitions
            ],
            [("led_white", 9_825, "inactive"), ("led_white", 10_925, "active")],
        )

    def test_rejects_pattern_window_before_time_zero(self):
        with self.assertRaisesRegex(LedTimingError, "before frame time zero"):
            LogicalLedTimingModel().plan_frame(
                pattern="BF_WHITE",
                frame_start_us=100,
                exposure_start_us=200,
                exposure_us=500,
                gate_pulse_us=0,
                gate_pre_trigger_us=101,
            )

    def test_rejects_physical_pin_names_in_custom_patterns(self):
        model = LogicalLedTimingModel(
            patterns={
                "BOARD_PIN": LedPattern(
                    pattern="BOARD_PIN",
                    gate_names=("PB13",),
                    frame_use="unsafe",
                )
            }
        )

        with self.assertRaisesRegex(LedTimingError, "logical alias"):
            model.plan_frame(
                pattern="BOARD_PIN",
                frame_start_us=0,
                exposure_start_us=0,
                exposure_us=500,
                gate_pulse_us=100,
            )

    def test_rejects_brightness_setpoint_for_inactive_alias(self):
        with self.assertRaisesRegex(LedTimingError, "inactive gate"):
            LogicalLedTimingModel().plan_frame(
                pattern="BF_WHITE",
                frame_start_us=0,
                exposure_start_us=0,
                exposure_us=500,
                gate_pulse_us=100,
                brightness_by_gate={"led_red": 0.5},
            )

    def test_rejects_brightness_outside_normalized_range(self):
        with self.assertRaisesRegex(LedTimingError, "between 0.0 and 1.0"):
            LogicalLedTimingModel().plan_frame(
                pattern="BF_WHITE",
                frame_start_us=0,
                exposure_start_us=0,
                exposure_us=500,
                gate_pulse_us=100,
                brightness_by_gate={"led_white": 1.1},
            )

    def test_builds_disabled_output_protocol_timing_contract(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="AF_RED_GREEN",
            frame_start_us=12_000,
            exposure_start_us=12_100,
            exposure_us=600,
            gate_pulse_us=200,
            settle_us=20,
            brightness_by_gate={"led_red": 0.6, "led_green": 0.7},
        )

        contract = build_disabled_output_led_timing_contract(plan)
        payload = contract.to_json_dict()

        self.assertEqual(payload["contract_id"], "led_scheduler_timing_contract_v1")
        self.assertEqual(payload["backend"], "disabled_output_metadata")
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertEqual(payload["pattern"], "AF_RED_GREEN")
        self.assertEqual(payload["logical_channel_names"], ["led_red", "led_green"])
        self.assertEqual(payload["frame_start_us"], 12_000)
        self.assertEqual(payload["exposure_start_us"], 12_100)
        self.assertEqual(payload["exposure_end_us"], 12_700)
        self.assertEqual(
            [
                (window["gate_name"], window["start_us"], window["end_us"])
                for window in payload["gate_windows"]
            ],
            [("led_red", 12_120, 12_320), ("led_green", 12_320, 12_520)],
        )

    def test_validates_frame_event_led_timing_contract_against_protocol_identity(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="BF_WHITE",
            frame_start_us=10_000,
            exposure_start_us=10_100,
            exposure_us=500,
            gate_pulse_us=200,
            settle_us=20,
        )
        contract = build_disabled_output_led_timing_contract(plan)
        frame = _frame_event(
            pattern="BF_WHITE",
            led_gate_names=("led_white",),
            mcu_time_us=10_000,
            led_timing=contract.to_json_dict(),
        )

        validated = validate_frame_event_led_timing_contract(frame)

        self.assertEqual(validated.pattern, "BF_WHITE")
        self.assertEqual(validated.logical_channel_names, ("led_white",))

    def test_rejects_frame_event_led_timing_mismatch_or_enabled_output(self):
        plan = LogicalLedTimingModel().plan_frame(
            pattern="BF_WHITE",
            frame_start_us=10_000,
            exposure_start_us=10_100,
            exposure_us=500,
            gate_pulse_us=200,
        )
        payload = build_disabled_output_led_timing_contract(plan).to_json_dict()

        with self.assertRaisesRegex(LedTimingError, "logical channels"):
            validate_frame_event_led_timing_contract(
                _frame_event(
                    pattern="BF_WHITE",
                    led_gate_names=("led_red",),
                    mcu_time_us=10_000,
                    led_timing=payload,
                )
            )

        payload["hardware_outputs_enabled"] = True
        with self.assertRaisesRegex(LedTimingError, "hardware outputs disabled"):
            DisabledOutputLedTimingContract.from_json_dict(payload)

    def test_rejects_physical_pin_names_in_protocol_timing_contract(self):
        payload = build_disabled_output_led_timing_contract(
            LogicalLedTimingModel().plan_frame(
                pattern="BF_WHITE",
                frame_start_us=10_000,
                exposure_start_us=10_100,
                exposure_us=500,
                gate_pulse_us=200,
            )
        ).to_json_dict()
        payload["logical_channel_names"] = ["PB13"]

        with self.assertRaisesRegex(LedTimingError, "logical alias"):
            validate_frame_event_led_timing_contract(
                _frame_event(
                    pattern="BF_WHITE",
                    led_gate_names=("PB13",),
                    mcu_time_us=10_000,
                    led_timing=payload,
                )
            )


def _frame_event(
    *,
    pattern: str,
    led_gate_names: tuple[str, ...],
    mcu_time_us: int,
    led_timing: dict,
) -> FrameEventRecord:
    return FrameEventRecord(
        protocol_version="1.0.0",
        scan_id="led-contract-fixture",
        stripe_id=4,
        frame_id=300,
        stripe_frame_index=0,
        pattern=pattern,
        led_gate_names=led_gate_names,
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
