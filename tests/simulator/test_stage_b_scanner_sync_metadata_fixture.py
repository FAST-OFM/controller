from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.event_streaming.cli import main  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.event_streaming.parsing import (  # noqa: E402
    decode_scanner_sync_json_lines,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (  # noqa: E402
    build_scanner_sync_capture_report,
)
from scanner_firmware.adapters.klipper_adapter.harness.payloads import (  # noqa: E402
    synthetic_callback_payload,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (  # noqa: E402
    ScannerSyncDecodeContext,
)
from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    ZAppliedRecord,
    ZRejectedRecord,
    ZScheduledRecord,
)


FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "scanner_sync_stage_b_metadata_capture_v1.jsonl"
)
EXPECTED_SUMMARY_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "scanner_sync_stage_b_metadata_capture_expected_summary_v1.json"
)
SCAN_ID = "stage-b-synthetic-scanner-sync-metadata-capture"
PATTERNS = ("BF_WHITE", "AF_RED_GREEN")
RAW_CAPTURE_TOP_LEVEL_KEYS = frozenset(
    (
        "capture_stage",
        "event_type",
        "fixture_id",
        "hardware_outputs_enabled",
        "params",
        "synthetic",
    )
)
RAW_CAPTURE_PARAM_KEYS_BY_EVENT_TYPE = {
    "FRAME_EVENT": frozenset(
        (
            "event_position",
            "flags",
            "frame_id",
            "mcu_time_us",
            "pattern_id",
            "position_axis",
            "status",
            "stripe_frame_index",
            "stripe_id",
            "x_count",
            "y_count",
            "z_count",
        )
    ),
    "Z_SCHEDULED": frozenset(("command_id", "seq", "status", "stripe_id")),
    "Z_APPLIED": frozenset(("frame_id", "seq", "status", "z_cmd_count")),
    "Z_REJECTED": frozenset(("command_id", "reason", "seq", "status", "stripe_id")),
    "SCHEDULER_TERMINAL": frozenset(
        (
            "emitted_frame_count",
            "expected_frame_count",
            "last_frame_id",
            "mcu_time_us",
            "message",
            "next_frame_id",
            "next_stripe_frame_index",
            "reason",
            "status",
            "stripe_id",
        )
    ),
}


class StageBScannerSyncMetadataFixtureTests(unittest.TestCase):
    def test_stage_b_capture_fixture_is_synthetic_raw_scanner_sync_metadata(self):
        payloads = _load_raw_payloads()

        self.assertEqual(
            [payload["event_type"] for payload in payloads],
            [
                "FRAME_EVENT",
                "Z_SCHEDULED",
                "FRAME_EVENT",
                "Z_APPLIED",
                "FRAME_EVENT",
                "Z_REJECTED",
                "SCHEDULER_TERMINAL",
            ],
        )
        self.assertTrue(all(payload["capture_stage"] == "stage_b" for payload in payloads))
        self.assertTrue(all(payload["synthetic"] is True for payload in payloads))
        self.assertTrue(
            all(payload["hardware_outputs_enabled"] is False for payload in payloads)
        )
        self.assertTrue(all("params" in payload and "type" not in payload for payload in payloads))
        for payload in payloads:
            payload_text = json.dumps(payload, sort_keys=True).lower()
            for forbidden in (
                "serial",
                "gpio",
                "camera",
                "klipper",
                "dictionary",
                "live_pi",
                "pi_host",
                "led_gate_names",
                "trigger_output_name",
                "motion_output",
            ):
                self.assertNotIn(forbidden, payload_text)

    def test_stage_b_capture_fixture_uses_declared_raw_callback_schema(self):
        for payload in _load_raw_payloads():
            with self.subTest(event_type=payload["event_type"]):
                self.assertEqual(frozenset(payload), RAW_CAPTURE_TOP_LEVEL_KEYS)
                self.assertEqual(
                    payload["fixture_id"],
                    "scanner_sync_stage_b_metadata_capture_v1",
                )
                self.assertEqual(
                    frozenset(payload["params"]),
                    RAW_CAPTURE_PARAM_KEYS_BY_EVENT_TYPE[payload["event_type"]],
                )

    def test_stage_b_capture_fixture_decodes_to_expected_summary(self):
        decoded_records = decode_scanner_sync_json_lines(
            FIXTURE_PATH.read_text(encoding="utf-8").splitlines(),
            context=_decode_context(),
            require_event_type=True,
        )

        summary = build_scanner_sync_capture_report(decoded_records).to_json_dict()

        self.assertEqual(summary, _load_expected_summary())

    def test_cli_validates_stage_b_capture_fixture_to_expected_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "stage-b-summary.json"

            code = main(
                [
                    str(FIXTURE_PATH),
                    "--scan-id",
                    SCAN_ID,
                    "--pattern",
                    PATTERNS[0],
                    "--pattern",
                    PATTERNS[1],
                    "--summary-json",
                    "--output",
                    str(output_path),
                    "--expect-record-count",
                    "7",
                    "--expect-frame-count",
                    "3",
                    "--expect-terminal-count",
                    "1",
                    "--expect-first-frame-id",
                    "1360",
                    "--expect-last-frame-id",
                    "1362",
                    "--expect-stripes-seen",
                    "6",
                ]
            )

            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")),
                _load_expected_summary(),
            )

    def test_synthetic_callback_payload_preserves_z_metadata(self):
        records = [
            ZScheduledRecord(
                seq=13600,
                scan_id=SCAN_ID,
                stripe_id=6,
                command_id="stage-b-z-frame-1362",
            ),
            ZAppliedRecord(
                seq=13600,
                scan_id=SCAN_ID,
                stripe_id=6,
                command_id="stage-b-z-frame-1362",
                apply_target_kind="frame",
                apply_at_frame_id=1362,
                frame_id=1362,
                position=1400,
                z_target_steps=32,
            ),
            ZRejectedRecord(
                seq=13601,
                scan_id=SCAN_ID,
                stripe_id=6,
                command_id="stage-b-z-too-late",
                reason="insufficient_lookahead",
            ),
        ]

        payloads = [synthetic_callback_payload(record) for record in records]

        self.assertEqual(payloads[0]["params"]["command_id"], "stage-b-z-frame-1362")
        self.assertEqual(payloads[1]["params"]["apply_target_kind"], 0)
        self.assertEqual(payloads[1]["params"]["apply_at_frame_id"], 1362)
        self.assertEqual(payloads[1]["params"]["position"], 1400)
        self.assertEqual(payloads[1]["params"]["z_target_steps"], 32)
        self.assertEqual(payloads[2]["params"]["reason"], 3)
        self.assertEqual(payloads[2]["params"]["command_id"], "stage-b-z-too-late")


def _decode_context() -> ScannerSyncDecodeContext:
    return ScannerSyncDecodeContext(
        scan_id=SCAN_ID,
        pattern_names=PATTERNS,
    )


def _load_raw_payloads() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_expected_summary() -> dict[str, object]:
    return json.loads(EXPECTED_SUMMARY_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
