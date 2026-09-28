"""Firmware scan-geometry dry-run fixture records.

The fixture builder is software-only. It serializes deterministic planning
metadata and nested FRAME_EVENT payloads; it does not access controllers,
serial ports, GPIO, motion, LEDs, cameras or firmware flashing tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Literal

from scanner_core.scan_geometry import StripeGeometry
from scanner_core.scan_units import round_half_away_from_zero


CONTRACT_ID = "scan_geometry_contract_v1"
FIXTURE_ID = "fixture_firmware_scan_geometry_dry_run_v1"
VALIDATION_ID = "static_firmware_scan_geometry_dry_run_check"
SCAN_ID = "tissue-map-synthetic-file-v1:dry-run"
ROI_ID = "roi_tissue_001"
STAGE_COORDINATE_FRAME = "stage_um_v1"
ROUNDING_MODE = "round_half_away_from_zero"
COORDINATE_SOURCE_REQUESTED = "step_count"
COORDINATE_SOURCE_USED = "step_indexed"
PROTOCOL_VERSION = "1.0.0"

ROI_BOUNDS_UM = {
    "x_min_um": 1550.0,
    "x_max_um": 7600.0,
    "y_min_um": 2300.0,
    "y_max_um": 5450.0,
}
TILE_GEOMETRY_UM = {
    "tile_size_x_um": 3275.0,
    "tile_size_y_um": 2250.0,
    "tile_pitch_x_um": 3025.0,
    "tile_pitch_y_um": 2000.0,
    "overlap_x_um": 250.0,
    "overlap_y_um": 250.0,
    "qa_overlap_margin_um": 250.0,
}
STRIPE_WIDTH_UM = 2250.0
FRAME_PITCH_UM = 3025.0
EXPECTED_FRAME_COUNT = 3
Z_COUNT = 0
SYNTHETIC_FRAME_PERIOD_US = 1000


JsonDict = Dict[str, Any]
ScanDirection = Literal["positive", "negative"]


@dataclass(frozen=True)
class FixtureStripe:
    stripe_id: str
    scan_direction: ScanDirection
    axis_sign: int
    start_um: float
    end_um: float
    cross_axis_center_um: float
    first_frame_axis_um: float
    frame_pitch_um: float
    expected_frame_count: int
    tile_row: int


STRIPES = (
    FixtureStripe(
        stripe_id="stripe_roi_tissue_001_y0",
        scan_direction="positive",
        axis_sign=1,
        start_um=1550.0,
        end_um=7600.0,
        cross_axis_center_um=2825.0,
        first_frame_axis_um=1550.0,
        frame_pitch_um=FRAME_PITCH_UM,
        expected_frame_count=EXPECTED_FRAME_COUNT,
        tile_row=0,
    ),
    FixtureStripe(
        stripe_id="stripe_roi_tissue_001_y1",
        scan_direction="negative",
        axis_sign=-1,
        start_um=7600.0,
        end_um=1550.0,
        cross_axis_center_um=4825.0,
        first_frame_axis_um=7600.0,
        frame_pitch_um=-FRAME_PITCH_UM,
        expected_frame_count=EXPECTED_FRAME_COUNT,
        tile_row=1,
    ),
)


def build_scan_geometry_dry_run_fixture_records() -> tuple[JsonDict, ...]:
    """Build deterministic firmware dry-run fixture rows."""

    records: list[JsonDict] = []
    frame_id = 20
    for stripe in STRIPES:
        geometry = _stripe_geometry(stripe)
        for position_sample in geometry.position_samples:
            stripe_frame_index = _require_event_index(position_sample.event_index)
            planned_axis_um = float(position_sample.position_count)
            pattern = _pattern_for_index(stripe_frame_index)
            event_position = position_sample.position_count
            cross_axis_count = _um_to_count(stripe.cross_axis_center_um)
            tile_col = int(
                (planned_axis_um - ROI_BOUNDS_UM["x_min_um"])
                / TILE_GEOMETRY_UM["tile_pitch_x_um"]
            )
            records.append(
                _fixture_record(
                    stripe=stripe,
                    frame_id=frame_id,
                    stripe_frame_index=stripe_frame_index,
                    pattern=pattern,
                    planned_axis_um=planned_axis_um,
                    event_position=event_position,
                    cross_axis_count=cross_axis_count,
                    tile_col=tile_col,
                )
            )
            frame_id += 1
    return tuple(records)


def scan_geometry_dry_run_fixture_jsonl() -> str:
    """Serialize deterministic fixture rows as canonical newline-delimited JSON."""

    return "\n".join(
        json.dumps(record, sort_keys=False, separators=(",", ":"))
        for record in build_scan_geometry_dry_run_fixture_records()
    )


def _fixture_record(
    *,
    stripe: FixtureStripe,
    frame_id: int,
    stripe_frame_index: int,
    pattern: str,
    planned_axis_um: float,
    event_position: int,
    cross_axis_count: int,
    tile_col: int,
) -> JsonDict:
    frame_event = {
        "type": "FRAME_EVENT",
        "protocol_version": PROTOCOL_VERSION,
        "scan_id": SCAN_ID,
        "stripe_id": stripe.stripe_id,
        "frame_id": frame_id,
        "stripe_frame_index": stripe_frame_index,
        "pattern": pattern,
        "coordinate_source_used": COORDINATE_SOURCE_USED,
        "position_axis": "X",
        "event_position": event_position,
        "sample_position": event_position,
        "position_overshoot_count": 0,
        "x_count": event_position,
        "y_count": cross_axis_count,
        "z_count": Z_COUNT,
        "x_step_commanded": event_position,
        "y_step_commanded": cross_axis_count,
        "z_step_commanded": Z_COUNT,
        "x_encoder_count": None,
        "y_encoder_count": None,
        "z_encoder_count": None,
        "z_state": "not_requested",
        "z_command_seq": None,
        "coordinate_flags": [],
        "mcu_time_us": (frame_id + 1) * SYNTHETIC_FRAME_PERIOD_US,
        "trigger_pulse_us": None,
        "led_pattern_id": pattern.lower(),
        "led_pulse_us": None,
        "expected_camera_frame": None,
        "status": "OK",
    }
    return {
        "type": "FIRMWARE_SCAN_GEOMETRY_DRY_RUN_FRAME",
        "contract_id": CONTRACT_ID,
        "fixture_id": FIXTURE_ID,
        "validation_id": VALIDATION_ID,
        "dry_run": True,
        "hardware_outputs_enabled": False,
        "scan_id": SCAN_ID,
        "roi_id": ROI_ID,
        "roi_bounds_um": dict(ROI_BOUNDS_UM),
        "stage_coordinate_frame": STAGE_COORDINATE_FRAME,
        "scan_axis": "x",
        "scan_direction": stripe.scan_direction,
        "axis_sign": stripe.axis_sign,
        "coordinate_source_requested": COORDINATE_SOURCE_REQUESTED,
        "coordinate_source_used": COORDINATE_SOURCE_USED,
        "rounding_mode": ROUNDING_MODE,
        "stripe_id": stripe.stripe_id,
        "start_um": stripe.start_um,
        "end_um": stripe.end_um,
        "cross_axis_center_um": stripe.cross_axis_center_um,
        "stripe_width_um": STRIPE_WIDTH_UM,
        "first_frame_axis_um": stripe.first_frame_axis_um,
        "frame_pitch_um": FRAME_PITCH_UM,
        "expected_frame_count": stripe.expected_frame_count,
        "frame_id": frame_id,
        "stripe_frame_index": stripe_frame_index,
        "pattern": pattern,
        "planned_event_axis_um": planned_axis_um,
        "event_position": event_position,
        "sample_position": event_position,
        "position_overshoot_count": 0,
        "tile_origin_x_um": planned_axis_um,
        "tile_origin_y_um": stripe.cross_axis_center_um,
        "tile_row": stripe.tile_row,
        "tile_col": tile_col,
        "is_bf_tile_candidate": pattern == "BF_WHITE",
        **TILE_GEOMETRY_UM,
        "frame_event": frame_event,
    }


def _pattern_for_index(stripe_frame_index: int) -> str:
    return ("BF_WHITE", "AF_RED_GREEN", "BF_WHITE")[stripe_frame_index]


def _stripe_geometry(stripe: FixtureStripe) -> StripeGeometry:
    return StripeGeometry(
        axis="X",
        start_position=_um_to_count(stripe.start_um),
        end_position=_um_to_count(stripe.end_um),
        first_event_position=_um_to_count(stripe.first_frame_axis_um),
        event_pitch=_um_to_count(stripe.frame_pitch_um),
        event_count=stripe.expected_frame_count,
    )


def _require_event_index(event_index: int | None) -> int:
    if event_index is None:
        raise ValueError("scanner-core fixture position samples must include event_index")
    return event_index


def _um_to_count(value_um: float) -> int:
    return round_half_away_from_zero(value_um, name="fixture_um")
