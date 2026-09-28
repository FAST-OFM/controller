from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.dry_run_pipeline.scan_geometry_fixture import (  # noqa: E402
    build_scan_geometry_dry_run_fixture_records,
)
from scanner_core.scan_geometry import StripeGeometry  # noqa: E402


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "scan_geometry_dry_run_protocol_v1.jsonl"
FRAME_EVENT_SCHEMA_PATH = REPO_ROOT / "specifications" / "frame-event-schema.yaml"


class ScanGeometryDryRunFixtureTests(unittest.TestCase):
    def test_checked_in_fixture_matches_deterministic_builder(self):
        self.assertEqual(
            _load_jsonl(FIXTURE_PATH),
            list(build_scan_geometry_dry_run_fixture_records()),
        )

    def test_fixture_preserves_contract_geometry_and_reverse_stripe_order(self):
        records = _load_jsonl(FIXTURE_PATH)

        self.assertEqual(len(records), 6)
        self.assertTrue(all(record["hardware_outputs_enabled"] is False for record in records))
        self.assertTrue(all(record["dry_run"] is True for record in records))
        self.assertEqual(
            {record["fixture_id"] for record in records},
            {"fixture_firmware_scan_geometry_dry_run_v1"},
        )
        self.assertEqual(
            {record["validation_id"] for record in records},
            {"static_firmware_scan_geometry_dry_run_check"},
        )
        self.assertEqual(
            {record["scan_id"] for record in records},
            {"tissue-map-synthetic-file-v1:dry-run"},
        )
        self.assertEqual({record["roi_id"] for record in records}, {"roi_tissue_001"})
        self.assertEqual(
            {record["rounding_mode"] for record in records},
            {"round_half_away_from_zero"},
        )
        self.assertEqual(
            {record["coordinate_source_requested"] for record in records},
            {"step_count"},
        )
        self.assertEqual({record["coordinate_source_used"] for record in records}, {"step_indexed"})

        self.assertEqual(
            [(record["stripe_id"], record["stripe_frame_index"]) for record in records],
            [
                ("stripe_roi_tissue_001_y0", 0),
                ("stripe_roi_tissue_001_y0", 1),
                ("stripe_roi_tissue_001_y0", 2),
                ("stripe_roi_tissue_001_y1", 0),
                ("stripe_roi_tissue_001_y1", 1),
                ("stripe_roi_tissue_001_y1", 2),
            ],
        )
        self.assertEqual(
            [record["planned_event_axis_um"] for record in records],
            [1550.0, 4575.0, 7600.0, 7600.0, 4575.0, 1550.0],
        )
        self.assertEqual(
            [record["event_position"] for record in records],
            [1550, 4575, 7600, 7600, 4575, 1550],
        )
        self.assertEqual(
            [(record["scan_direction"], record["axis_sign"]) for record in records],
            [
                ("positive", 1),
                ("positive", 1),
                ("positive", 1),
                ("negative", -1),
                ("negative", -1),
                ("negative", -1),
            ],
        )
        self.assertEqual(
            [record["cross_axis_center_um"] for record in records],
            [2825.0, 2825.0, 2825.0, 4825.0, 4825.0, 4825.0],
        )
        self.assertEqual([record["tile_col"] for record in records], [0, 1, 2, 2, 1, 0])
        self.assertEqual([record["tile_row"] for record in records], [0, 0, 0, 1, 1, 1])
        self.assertEqual(
            [record["is_bf_tile_candidate"] for record in records],
            [True, False, True, True, False, True],
        )

    def test_fixture_event_positions_match_scanner_core_geometry_samples(self):
        records = _load_jsonl(FIXTURE_PATH)

        self.assertEqual(StripeGeometry.__module__, "scanner_core.scan_geometry")
        for stripe_id in {record["stripe_id"] for record in records}:
            stripe_records = [record for record in records if record["stripe_id"] == stripe_id]
            first_record = stripe_records[0]
            geometry = StripeGeometry(
                axis=first_record["scan_axis"],
                start_position=first_record["event_position"],
                end_position=stripe_records[-1]["event_position"],
                first_event_position=first_record["event_position"],
                event_pitch=(
                    first_record["axis_sign"] * int(first_record["frame_pitch_um"])
                ),
                event_count=first_record["expected_frame_count"],
            )

            self.assertEqual(
                [
                    (
                        sample.event_index,
                        sample.axis,
                        sample.position_count,
                    )
                    for sample in geometry.position_samples
                ],
                [
                    (
                        record["stripe_frame_index"],
                        record["frame_event"]["position_axis"],
                        record["event_position"],
                    )
                    for record in stripe_records
                ],
            )

    def test_nested_frame_events_match_docs_schema_surface(self):
        records = _load_jsonl(FIXTURE_PATH)
        schema = yaml.safe_load(FRAME_EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))

        for index, record in enumerate(records):
            with self.subTest(row=index):
                frame_event = record["frame_event"]
                _assert_schema_surface(self, frame_event, schema)
                self.assertEqual(frame_event["type"], "FRAME_EVENT")
                self.assertEqual(frame_event["protocol_version"], "1.0.0")
                self.assertEqual(frame_event["event_position"], record["event_position"])
                self.assertEqual(frame_event["sample_position"], record["sample_position"])
                self.assertEqual(
                    frame_event["position_overshoot_count"],
                    record["position_overshoot_count"],
                )
                self.assertEqual(frame_event["frame_id"], record["frame_id"])
                self.assertEqual(
                    frame_event["stripe_frame_index"],
                    record["stripe_frame_index"],
                )
                self.assertEqual(frame_event["status"], "OK")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_schema_surface(
    test_case: unittest.TestCase,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    properties = schema["properties"]
    test_case.assertEqual(set(payload) - set(properties), set())
    test_case.assertEqual(set(schema["required"]) - set(payload), set())

    for name, property_schema in properties.items():
        if name not in payload:
            continue
        value = payload[name]
        if "const" in property_schema:
            test_case.assertEqual(value, property_schema["const"])
        if "enum" in property_schema:
            test_case.assertIn(value, property_schema["enum"])
        if "oneOf" in property_schema:
            test_case.assertTrue(
                any(
                    _matches_json_type(value, option["type"])
                    for option in property_schema["oneOf"]
                )
            )
        elif "type" in property_schema:
            test_case.assertTrue(
                _matches_json_type(value, property_schema["type"]),
                f"{name}={value!r} does not match {property_schema['type']!r}",
            )


def _matches_json_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_json_type(value, item) for item in expected_type)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "null":
        return value is None
    return False


if __name__ == "__main__":
    unittest.main()
