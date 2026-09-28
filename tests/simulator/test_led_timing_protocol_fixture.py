from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.foundation.protocol.events import FrameEventRecord  # noqa: E402
from scanner_firmware.foundation.protocol.parsing import (  # noqa: E402
    decode_protocol_json_lines,
)
from scanner_firmware.planning.led_scheduler.timing import (  # noqa: E402
    validate_frame_event_led_timing_contract,
)


FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "frame_event_led_timing_protocol_v1.jsonl"
)


class LedTimingProtocolFixtureTests(unittest.TestCase):
    def test_led_timing_fixture_decodes_as_frame_event_protocol_records(self):
        records = _load_fixture_records()
        decoded_records = decode_protocol_json_lines(
            FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        )

        self.assertTrue(
            all(isinstance(record, FrameEventRecord) for record in decoded_records)
        )
        self.assertEqual(
            [record.to_json_dict() for record in decoded_records],
            records,
        )
        self.assertTrue(
            all(record.hardware_outputs_enabled is False for record in decoded_records)
        )

    def test_fixture_carries_disabled_output_led_timing_contracts(self):
        decoded_records = decode_protocol_json_lines(
            FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        )

        contracts = [
            validate_frame_event_led_timing_contract(record)
            for record in decoded_records
        ]

        self.assertEqual(
            [contract.pattern for contract in contracts],
            ["BF_WHITE", "AF_RED_GREEN", "DARK"],
        )
        self.assertEqual(
            [contract.logical_channel_names for contract in contracts],
            [("led_white",), ("led_red", "led_green"), ()],
        )
        self.assertEqual(
            [
                [
                    (window.gate_name, window.start_us, window.end_us)
                    for window in contract.gate_windows
                ]
                for contract in contracts
            ],
            [
                [("led_white", 10120, 10320)],
                [("led_red", 12120, 12320), ("led_green", 12320, 12520)],
                [],
            ],
        )
        self.assertTrue(
            all(contract.backend == "disabled_output_metadata" for contract in contracts)
        )
        self.assertTrue(
            all(contract.hardware_outputs_enabled is False for contract in contracts)
        )

    def test_fixture_led_timing_uses_mcu_time_not_wall_clock_identity(self):
        records = _load_fixture_records()

        for record in records:
            payload = json.dumps(record, sort_keys=True)
            self.assertNotIn("wall_clock", payload)
            self.assertNotIn("linux_time", payload)
            self.assertEqual(record["led_timing"]["frame_start_us"], record["mcu_time_us"])


def _load_fixture_records() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    unittest.main()
