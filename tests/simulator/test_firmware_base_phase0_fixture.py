from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.firmware_base.dry_run_adapters import (  # noqa: E402
    GrblHalPlannerSnapshot,
    KlipperCommandedPositionSample,
    StepDirPulse,
    grblhal_planner_snapshots_to_samples,
    klipper_commanded_positions_to_samples,
    step_dir_pulses_to_samples,
)
from scanner_firmware.foundation.protocol.events import scheduler_event_to_protocol_record  # noqa: E402
from scanner_firmware.planning.trigger_scheduler.scheduler import (  # noqa: E402
    DryRunPositionEventScheduler,
)
from scanner_firmware.planning.trigger_scheduler.types import (  # noqa: E402
    PositionSample,
    StripeSchedule,
)


FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "firmware_base_phase0_expected.json"
)


class FirmwareBasePhase0FixtureTests(unittest.TestCase):
    def test_phase0_fixture_matches_generated_dry_run_events(self):
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(expected["phase"], "dry_run")
        self.assertFalse(expected["hardware_outputs_enabled"])
        self.assertEqual(
            {
                "klipper",
                "grblhal",
                "external-rp2040-sync-board",
            },
            set(expected["candidates"]),
        )
        self.assertEqual(expected["candidates"], _generate_candidate_events())

    def test_klipper_like_fixture_serializes_to_protocol_records(self):
        payloads = [
            scheduler_event_to_protocol_record(event).to_json_dict()
            for event in _run_klipper_like_fixture()
        ]

        self.assertEqual([payload["type"] for payload in payloads], ["FRAME_EVENT", "FRAME_EVENT"])
        self.assertEqual([payload["frame_id"] for payload in payloads], [0, 1])
        self.assertEqual([payload["pattern"] for payload in payloads], ["BF_WHITE", "AF_RED_GREEN"])
        self.assertEqual(
            [payload["led_gate_names"] for payload in payloads],
            [["led_white"], ["led_red", "led_green"]],
        )
        self.assertEqual(
            {payload["trigger_output_name"] for payload in payloads},
            {"camera_or_sync_trigger"},
        )
        self.assertTrue(all(payload["coordinate_source_used"] == "step_indexed" for payload in payloads))
        self.assertTrue(all(payload["hardware_outputs_enabled"] is False for payload in payloads))
        self.assertEqual(
            json.loads(scheduler_event_to_protocol_record(_run_klipper_like_fixture()[0]).to_json())[
                "type"
            ],
            "FRAME_EVENT",
        )


def _generate_candidate_events() -> dict:
    return {
        "klipper": _event_summary(
            _run_klipper_like_fixture(),
        ),
        "grblhal": _event_summary(
            _run_grblhal_like_fixture(),
        ),
        "external-rp2040-sync-board": _event_summary(
            _run_sync_board_like_fixture(),
        ),
    }


def _run_klipper_like_fixture():
    samples = klipper_commanded_positions_to_samples(
        [
            KlipperCommandedPositionSample(0, 0, event_time_s=0.0),
            KlipperCommandedPositionSample(20, 0, event_time_s=0.001),
            KlipperCommandedPositionSample(40, 0, event_time_s=0.002),
        ]
    )
    schedule = StripeSchedule(
        scan_id="phase0-klipper",
        stripe_id=1,
        axis="X",
        start_position=0,
        end_position=40,
        first_event_position=20,
        event_pitch=20,
        event_count=2,
        pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
    )
    return _run_schedule(schedule, samples)


def _run_grblhal_like_fixture():
    samples = grblhal_planner_snapshots_to_samples(
        [
            GrblHalPlannerSnapshot(0, 5, tick_us=0),
            GrblHalPlannerSnapshot(25, 5, tick_us=25),
            GrblHalPlannerSnapshot(50, 5, tick_us=50),
        ]
    )
    schedule = StripeSchedule(
        scan_id="phase0-grblhal",
        stripe_id=1,
        axis="X",
        start_position=0,
        end_position=50,
        first_event_position=25,
        event_pitch=25,
        event_count=2,
        pattern_sequence=("BF_WHITE",),
    )
    return _run_schedule(schedule, samples)


def _run_sync_board_like_fixture():
    samples = step_dir_pulses_to_samples(
        [
            StepDirPulse(axis="X", direction=1, timestamp_us=10, pulse_count=10),
            StepDirPulse(axis="X", direction=1, timestamp_us=20, pulse_count=10),
            StepDirPulse(axis="X", direction=1, timestamp_us=30, pulse_count=10),
        ]
    )
    schedule = StripeSchedule(
        scan_id="phase0-sync-board",
        stripe_id=1,
        axis="X",
        start_position=0,
        end_position=30,
        first_event_position=10,
        event_pitch=10,
        event_count=3,
        pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
    )
    return _run_schedule(schedule, samples)


def _run_schedule(schedule: StripeSchedule, samples: list[PositionSample]):
    return DryRunPositionEventScheduler().run(schedule, samples)


def _event_summary(events) -> list:
    return [
        {
            "frame_id": event.frame_id,
            "stripe_frame_index": event.stripe_frame_index,
            "pattern": event.pattern,
            "led_gate_names": list(event.led_gate_names),
            "trigger_output_name": event.trigger_output_name,
            "coordinate_source_used": event.coordinate_source_used,
            "coordinate_flags": list(event.coordinate_flags),
            "position_axis": event.position_axis,
            "event_position": event.event_position,
            "sample_position": event.sample_position,
            "position_overshoot_count": event.position_overshoot_count,
            "x_count": event.x_count,
            "y_count": event.y_count,
            "z_count": event.z_count,
            "x_step_commanded": event.x_step_commanded,
            "y_step_commanded": event.y_step_commanded,
            "mcu_time_us": event.mcu_time_us,
        }
        for event in events
    ]


if __name__ == "__main__":
    unittest.main()
