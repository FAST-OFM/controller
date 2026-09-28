import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.dry_run_pipeline.runner import run_dry_run_pipeline  # noqa: E402
from scanner_firmware.planning.dry_run_pipeline.types import DryRunPipelineConfig  # noqa: E402
from scanner_firmware.planning.frame_counter.publishing.errors import (  # noqa: E402
    DuplicatePlannedFrameError,
)
from scanner_firmware.planning.frame_counter.publishing.records import (  # noqa: E402
    PlannedFrameTrigger,
)


def planned_trigger(
    *,
    scan_id: str = "dry-run-replay",
    stripe_id: int = 0,
    stripe_frame_index: int = 0,
    event_position: int = 0,
    mcu_time_us: int = 1000,
    led_timing: dict[str, Any] | None = None,
) -> PlannedFrameTrigger:
    return PlannedFrameTrigger(
        scan_id=scan_id,
        stripe_id=stripe_id,
        stripe_frame_index=stripe_frame_index,
        pattern="BF_WHITE",
        led_gate_names=("led_white",),
        coordinate_source_used="step_indexed",
        position_axis="X",
        event_position=event_position,
        sample_position=event_position,
        position_overshoot_count=0,
        x_count=event_position,
        y_count=5,
        z_count=500,
        x_step_commanded=event_position,
        y_step_commanded=5,
        z_step_commanded=500,
        mcu_time_us=mcu_time_us,
        led_timing=led_timing,
        trigger_output_name="dry_run_frame_event",
        dry_run=True,
        hardware_outputs_enabled=False,
    )


class DryRunPipelineTests(unittest.TestCase):
    def test_replays_planned_frame_triggers_as_protocol_records(self):
        result = run_dry_run_pipeline(
            (
                planned_trigger(stripe_frame_index=0, event_position=0),
                planned_trigger(
                    stripe_frame_index=1,
                    event_position=100,
                    mcu_time_us=2000,
                ),
                planned_trigger(stripe_id=1, stripe_frame_index=0, event_position=200),
            ),
            config=DryRunPipelineConfig(protocol_version=3),
            first_frame_id=40,
        )

        self.assertEqual(
            [event.frame_id for event in result.published_events],
            [40, 41, 42],
        )
        self.assertEqual(
            [record.frame_id for record in result.protocol_records],
            [40, 41, 42],
        )
        self.assertEqual(
            [record.protocol_version for record in result.protocol_records],
            [3, 3, 3],
        )

        first = result.frame_results[0]
        self.assertEqual(first.planned_trigger.key, ("dry-run-replay", 0, 0))
        self.assertEqual(first.protocol_record.type, "FRAME_EVENT")
        self.assertEqual(first.protocol_record.event_position, 0)
        self.assertEqual(first.protocol_record.x_count, 0)
        self.assertEqual(first.protocol_record.y_count, 5)
        self.assertEqual(first.protocol_record.z_count, 500)
        self.assertEqual(first.protocol_record.pattern, "BF_WHITE")
        self.assertFalse(first.protocol_record.hardware_outputs_enabled)

    def test_replay_preserves_led_timing_metadata(self):
        led_timing = _led_timing_payload(frame_start_us=1000)

        result = run_dry_run_pipeline(
            (planned_trigger(led_timing=led_timing),),
            first_frame_id=40,
        )

        frame = result.frame_results[0]
        self.assertEqual(frame.planned_trigger.led_timing, led_timing)
        self.assertEqual(frame.published_event.led_timing, led_timing)
        self.assertEqual(frame.protocol_record.led_timing, led_timing)
        self.assertEqual(frame.protocol_record.to_json_dict()["led_timing"], led_timing)

    def test_replay_preserves_publisher_duplicate_guardrails(self):
        trigger = planned_trigger()

        with self.assertRaisesRegex(DuplicatePlannedFrameError, "duplicate planned"):
            run_dry_run_pipeline((trigger, trigger))


def _led_timing_payload(*, frame_start_us: int) -> dict[str, Any]:
    return {
        "pattern": "BF_WHITE",
        "frame_use": "brightfield_tile",
        "logical_channel_names": ["led_white"],
        "frame_start_us": frame_start_us,
        "exposure_start_us": frame_start_us + 100,
        "exposure_end_us": frame_start_us + 600,
        "brightness_setpoints": [{"gate_name": "led_white", "brightness": 0.5}],
        "gate_windows": [
            {
                "gate_name": "led_white",
                "start_us": frame_start_us + 120,
                "end_us": frame_start_us + 320,
                "polarity": "active_high",
            }
        ],
        "hardware_outputs_enabled": False,
        "backend": "disabled_output_metadata",
        "contract_id": "led_scheduler_timing_contract_v1",
    }


if __name__ == "__main__":
    unittest.main()
