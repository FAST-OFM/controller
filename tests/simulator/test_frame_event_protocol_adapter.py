import json
import sys
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.frame_counter.protocol.adapter import (  # noqa: E402
    FrameCounterProtocolAdapterError,
    frame_counter_event_to_protocol_record,
    frame_publisher_terminal_to_protocol_record,
    published_frame_event_to_protocol_record,
)
from scanner_firmware.planning.frame_counter.publishing.allocator import (  # noqa: E402
    FrameIdAllocator,
)
from scanner_firmware.planning.frame_counter.publishing.publisher import (  # noqa: E402
    FrameEventPublisher,
)
from scanner_firmware.planning.frame_counter.publishing.records import (  # noqa: E402
    FramePublisherTerminal,
    PlannedFrameTrigger,
)
from scanner_firmware.foundation.protocol.events import FrameEventRecord, SchedulerTerminalRecord  # noqa: E402


def planned_trigger(
    *,
    scan_id: str = "scan-a",
    stripe_id: int = 3,
    stripe_frame_index: int = 0,
    led_timing: dict[str, Any] | None = None,
) -> PlannedFrameTrigger:
    return PlannedFrameTrigger(
        scan_id=scan_id,
        stripe_id=stripe_id,
        stripe_frame_index=stripe_frame_index,
        pattern="AF_RED_GREEN",
        led_gate_names=("led_red", "led_green"),
        trigger_output_name="camera_or_sync_trigger",
        coordinate_source_used="hybrid",
        position_axis="X",
        event_position=120,
        sample_position=125,
        position_overshoot_count=5,
        x_count=120,
        y_count=9,
        z_count=2,
        x_step_commanded=125,
        y_step_commanded=9,
        z_step_commanded=2,
        x_encoder_count=118,
        y_encoder_count=10,
        coordinate_flags=("sample_overshot_event_position",),
        led_timing=led_timing,
        mcu_time_us=1010,
    )


class FrameEventProtocolAdapterTests(unittest.TestCase):
    def test_published_frame_event_converts_to_protocol_record_without_wall_clock_identity(self):
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=77))
        event = publisher.publish_planned(planned_trigger())

        record = published_frame_event_to_protocol_record(event)
        payload = record.to_json_dict()

        self.assertIsInstance(record, FrameEventRecord)
        self.assertEqual(payload["type"], "FRAME_EVENT")
        self.assertEqual(payload["scan_id"], "scan-a")
        self.assertEqual(payload["stripe_id"], 3)
        self.assertEqual(payload["frame_id"], 77)
        self.assertEqual(payload["stripe_frame_index"], 0)
        self.assertEqual(payload["pattern"], "AF_RED_GREEN")
        self.assertEqual(payload["led_gate_names"], ["led_red", "led_green"])
        self.assertEqual(payload["trigger_output_name"], "camera_or_sync_trigger")
        self.assertEqual(payload["coordinate_source_used"], "hybrid")
        self.assertEqual(payload["position_axis"], "X")
        self.assertEqual(payload["event_position"], 120)
        self.assertEqual(payload["sample_position"], 125)
        self.assertEqual(payload["position_overshoot_count"], 5)
        self.assertEqual(payload["x_count"], 120)
        self.assertEqual(payload["y_count"], 9)
        self.assertEqual(payload["z_count"], 2)
        self.assertEqual(payload["x_step_commanded"], 125)
        self.assertEqual(payload["y_step_commanded"], 9)
        self.assertEqual(payload["z_step_commanded"], 2)
        self.assertEqual(payload["x_encoder_count"], 118)
        self.assertEqual(payload["y_encoder_count"], 10)
        self.assertEqual(payload["coordinate_flags"], ["sample_overshot_event_position"])
        self.assertEqual(payload["mcu_time_us"], 1010)
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertNotIn("host_wall_clock", payload)
        self.assertEqual(json.loads(record.to_json()), payload)
        self.assertEqual(event.to_protocol_record(), record)

    def test_published_frame_event_preserves_led_timing_contract_metadata(self):
        led_timing = _led_timing_payload()
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=77))
        event = publisher.publish_planned(planned_trigger(led_timing=led_timing))

        record = published_frame_event_to_protocol_record(event)
        payload = record.to_json_dict()

        self.assertEqual(payload["led_timing"], led_timing)
        self.assertEqual(payload["led_timing"]["logical_channel_names"], ["led_red", "led_green"])
        self.assertFalse(payload["led_timing"]["hardware_outputs_enabled"])

    def test_supported_terminal_converts_to_protocol_record_and_roundtrips_json(self):
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=77))
        publisher.publish_planned(planned_trigger())
        terminal = publisher.terminal_summary(
            scan_id="scan-a",
            stripe_id=3,
            expected_frame_count=4,
            mcu_time_us=2000,
            status="stopped",
            reason_code="host_stop",
            message="stop requested",
        )

        record = frame_publisher_terminal_to_protocol_record(terminal)
        payload = record.to_json_dict()

        self.assertIsInstance(record, SchedulerTerminalRecord)
        self.assertEqual(payload["type"], "SCHEDULER_TERMINAL")
        self.assertEqual(payload["status"], "stopped")
        self.assertEqual(payload["reason_code"], "host_stop")
        self.assertEqual(payload["last_frame_id"], 77)
        self.assertEqual(payload["next_frame_id"], 78)
        self.assertEqual(payload["next_stripe_frame_index"], 1)
        self.assertFalse(payload["hardware_outputs_enabled"])
        self.assertEqual(json.loads(record.to_json()), payload)

    def test_dispatches_frame_counter_event_shapes(self):
        publisher = FrameEventPublisher(FrameIdAllocator(first_frame_id=5))
        frame = publisher.publish_planned(planned_trigger())
        terminal = publisher.terminal_summary(
            scan_id="scan-a",
            stripe_id=3,
            expected_frame_count=2,
            mcu_time_us=3000,
            status="stopped",
            reason_code="host_stop",
        )

        self.assertIsInstance(
            frame_counter_event_to_protocol_record(frame), FrameEventRecord
        )
        self.assertIsInstance(
            frame_counter_event_to_protocol_record(terminal), SchedulerTerminalRecord
        )

    def test_rejects_hardware_outputs_enabled_true(self):
        publisher = FrameEventPublisher()
        frame = publisher.publish_planned(planned_trigger())
        terminal = FramePublisherTerminal(
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=3,
            status="stopped",
            reason_code="host_stop",
            emitted_frame_count=0,
            expected_frame_count=1,
            last_frame_id=None,
            next_frame_id=1,
            next_stripe_frame_index=0,
            mcu_time_us=1,
        )

        with self.assertRaisesRegex(
            FrameCounterProtocolAdapterError, "hardware_outputs_enabled"
        ):
            object.__setattr__(frame, "hardware_outputs_enabled", True)
            published_frame_event_to_protocol_record(frame)
        object.__setattr__(terminal, "hardware_outputs_enabled", True)
        with self.assertRaisesRegex(
            FrameCounterProtocolAdapterError, "hardware_outputs_enabled"
        ):
            frame_publisher_terminal_to_protocol_record(terminal)

    def test_rejects_terminal_shape_not_supported_by_protocol_record(self):
        fault_terminal = FramePublisherTerminal(
            protocol_version=1,
            scan_id="scan-a",
            stripe_id=3,
            status="fault",
            reason_code="scheduler_fault",
            emitted_frame_count=0,
            expected_frame_count=1,
            last_frame_id=None,
            next_frame_id=0,
            next_stripe_frame_index=0,
            mcu_time_us=10,
        )
        object.__setattr__(fault_terminal, "reason_code", "publisher_fault")

        with self.assertRaisesRegex(FrameCounterProtocolAdapterError, "reason_code"):
            frame_publisher_terminal_to_protocol_record(fault_terminal)

    def test_source_terminal_rejects_complete_status_and_reason(self):
        with self.assertRaisesRegex(ValueError, "terminal status"):
            FramePublisherTerminal(
                protocol_version=1,
                scan_id="scan-a",
                stripe_id=3,
                status="complete",
                reason_code="host_stop",
                emitted_frame_count=0,
                expected_frame_count=1,
                last_frame_id=None,
                next_frame_id=0,
                next_stripe_frame_index=0,
                mcu_time_us=10,
            )
        with self.assertRaisesRegex(ValueError, "reason_code"):
            FramePublisherTerminal(
                protocol_version=1,
                scan_id="scan-a",
                stripe_id=3,
                status="fault",
                reason_code="complete",
                emitted_frame_count=0,
                expected_frame_count=1,
                last_frame_id=None,
                next_frame_id=0,
                next_stripe_frame_index=0,
                mcu_time_us=10,
            )


def _led_timing_payload() -> dict[str, Any]:
    return {
        "pattern": "AF_RED_GREEN",
        "frame_use": "autofocus",
        "logical_channel_names": ["led_red", "led_green"],
        "frame_start_us": 1010,
        "exposure_start_us": 1110,
        "exposure_end_us": 2110,
        "brightness_setpoints": [
            {"gate_name": "led_red", "brightness": 0.4},
            {"gate_name": "led_green", "brightness": 0.5},
        ],
        "gate_windows": [
            {
                "gate_name": "led_red",
                "start_us": 1160,
                "end_us": 1360,
                "polarity": "active_high",
            },
            {
                "gate_name": "led_green",
                "start_us": 1360,
                "end_us": 1560,
                "polarity": "active_high",
            },
        ],
        "hardware_outputs_enabled": False,
        "backend": "disabled_output_metadata",
        "contract_id": "led_scheduler_timing_contract_v1",
    }


if __name__ == "__main__":
    unittest.main()
