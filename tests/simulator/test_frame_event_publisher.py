import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.frame_counter.publishing.allocator import (  # noqa: E402
    FrameIdAllocator,
)
from scanner_firmware.planning.frame_counter.publishing.errors import (  # noqa: E402
    DuplicatePlannedFrameError,
    FrameEventPublishError,
    FramePublishTerminalError,
)
from scanner_firmware.planning.frame_counter.publishing.publisher import (  # noqa: E402
    FrameEventPublisher,
)
from scanner_firmware.planning.frame_counter.publishing.records import (  # noqa: E402
    PlannedFrameTrigger,
)


def planned_trigger(
    *,
    scan_id: str = "scan-a",
    stripe_id: int = 1,
    stripe_frame_index: int = 0,
    event_position: int = 100,
    mcu_time_us: int = 10,
    hardware_outputs_enabled: bool = False,
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
        z_count=0,
        x_step_commanded=event_position,
        y_step_commanded=5,
        z_step_commanded=0,
        mcu_time_us=mcu_time_us,
        led_timing=led_timing,
        hardware_outputs_enabled=hardware_outputs_enabled,
    )


class FrameEventPublisherTests(unittest.TestCase):
    def test_frame_ids_are_monotonic_across_stripes(self):
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=40))

        first = publisher.publish_planned(
            planned_trigger(stripe_id=1, stripe_frame_index=0)
        )
        second = publisher.publish_planned(
            planned_trigger(stripe_id=1, stripe_frame_index=1, event_position=200)
        )
        third = publisher.publish_planned(
            planned_trigger(stripe_id=2, stripe_frame_index=0, event_position=300)
        )

        self.assertEqual([first.frame_id, second.frame_id, third.frame_id], [40, 41, 42])
        self.assertEqual(
            [
                first.stripe_frame_index,
                second.stripe_frame_index,
                third.stripe_frame_index,
            ],
            [0, 1, 0],
        )
        self.assertEqual(publisher.next_frame_id, 43)

    def test_duplicate_planned_frame_is_rejected_without_allocating_id(self):
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=10))
        trigger = planned_trigger(stripe_id=1, stripe_frame_index=0)

        event = publisher.publish_planned(trigger)
        with self.assertRaisesRegex(DuplicatePlannedFrameError, "duplicate planned"):
            publisher.publish_planned(trigger)

        self.assertEqual(event.frame_id, 10)
        self.assertEqual(publisher.next_frame_id, 11)

    def test_terminal_summary_reports_expected_and_emitted_counts(self):
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=7))
        publisher.publish_planned(planned_trigger(stripe_id=3, stripe_frame_index=0))
        publisher.publish_planned(
            planned_trigger(stripe_id=3, stripe_frame_index=1, event_position=125)
        )

        terminal = publisher.terminal_summary(
            scan_id="scan-a",
            stripe_id=3,
            expected_frame_count=4,
            mcu_time_us=500,
            status="stopped",
            reason_code="host_stop",
            message="stop requested",
        )

        self.assertEqual(terminal.type, "SCHEDULER_TERMINAL")
        self.assertEqual(terminal.emitted_frame_count, 2)
        self.assertEqual(terminal.expected_frame_count, 4)
        self.assertEqual(terminal.last_frame_id, 8)
        self.assertEqual(terminal.next_frame_id, 9)
        self.assertEqual(terminal.next_stripe_frame_index, 2)
        self.assertFalse(terminal.hardware_outputs_enabled)

    def test_terminal_rejects_expected_count_below_emitted_count(self):
        publisher = FrameEventPublisher()
        publisher.publish_planned(planned_trigger(stripe_frame_index=0))

        with self.assertRaisesRegex(FramePublishTerminalError, "less than emitted"):
            publisher.terminal_summary(
                scan_id="scan-a",
                stripe_id=1,
                expected_frame_count=0,
                mcu_time_us=100,
            )

    def test_metadata_dry_run_outputs_keep_hardware_outputs_disabled(self):
        publisher = FrameEventPublisher()
        event = publisher.publish_planned(planned_trigger())
        terminal = publisher.terminal_summary(
            scan_id="scan-a",
            stripe_id=1,
            expected_frame_count=2,
            mcu_time_us=20,
        )

        self.assertFalse(event.hardware_outputs_enabled)
        self.assertFalse(terminal.hardware_outputs_enabled)

        with self.assertRaisesRegex(FrameEventPublishError, "hardware_outputs_enabled"):
            planned_trigger(hardware_outputs_enabled=True)

    def test_publish_planned_preserves_led_timing_metadata(self):
        led_timing = _led_timing_payload()
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=40))

        event = publisher.publish_planned(planned_trigger(led_timing=led_timing))
        payload = event.to_protocol_record().to_json_dict()

        self.assertEqual(event.led_timing, led_timing)
        self.assertEqual(payload["led_timing"], led_timing)
        self.assertFalse(payload["led_timing"]["hardware_outputs_enabled"])

    def test_publish_planned_rejects_unsafe_led_timing_metadata(self):
        led_timing = _led_timing_payload()
        led_timing["hardware_outputs_enabled"] = True

        with self.assertRaisesRegex(FrameEventPublishError, "led_timing"):
            planned_trigger(led_timing=led_timing)

    def test_publish_planned_rejects_mismatched_led_timing_metadata(self):
        led_timing = _led_timing_payload()
        led_timing["frame_start_us"] = 11

        with self.assertRaisesRegex(FrameEventPublishError, "frame_start_us"):
            planned_trigger(led_timing=led_timing)

    def test_clean_completion_does_not_emit_terminal_summary(self):
        publisher = FrameEventPublisher()
        publisher.publish_planned(planned_trigger())

        with self.assertRaisesRegex(FramePublishTerminalError, "clean completion"):
            publisher.terminal_summary(
                scan_id="scan-a",
                stripe_id=1,
                expected_frame_count=1,
                mcu_time_us=20,
            )


def _led_timing_payload() -> dict[str, Any]:
    return {
        "pattern": "BF_WHITE",
        "frame_use": "brightfield_tile",
        "logical_channel_names": ["led_white"],
        "frame_start_us": 10,
        "exposure_start_us": 20,
        "exposure_end_us": 120,
        "brightness_setpoints": [{"gate_name": "led_white", "brightness": 0.5}],
        "gate_windows": [
            {
                "gate_name": "led_white",
                "start_us": 25,
                "end_us": 75,
                "polarity": "active_high",
            }
        ],
        "hardware_outputs_enabled": False,
        "backend": "disabled_output_metadata",
        "contract_id": "led_scheduler_timing_contract_v1",
    }


if __name__ == "__main__":
    unittest.main()
