"""Latency helpers for predictive-Z planning."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite

from .count_space import round_apply_position_count_coordinate


@dataclass(frozen=True)
class PredictiveZBudget:
    exposure_to_frame_ready_ms: float
    frame_matching_ms: float
    af_compute_ms: float
    pi_to_mcu_ms: float
    mcu_queue_ms: float
    z_response_or_settle_ms: float
    safety_margin_ms: float = 0.0

    @property
    def total_latency_s(self) -> float:
        return (
            self.exposure_to_frame_ready_ms
            + self.frame_matching_ms
            + self.af_compute_ms
            + self.pi_to_mcu_ms
            + self.mcu_queue_ms
            + self.z_response_or_settle_ms
            + self.safety_margin_ms
        ) / 1000.0


def compute_apply_position_um(
    measurement_position_um: float,
    scan_velocity_um_s: float,
    budget: PredictiveZBudget,
    ahead_offset_um: float = 0.0,
) -> float:
    """Return the future coordinate where a Z correction should apply."""

    return measurement_position_um + ahead_offset_um + scan_velocity_um_s * budget.total_latency_s


def compute_apply_frame_id(
    measured_frame_id: int,
    frame_rate_hz: float,
    budget: PredictiveZBudget,
    safety_frames: int = 0,
) -> int:
    if frame_rate_hz <= 0:
        raise ValueError("frame_rate_hz must be positive")
    latency_frames = ceil(budget.total_latency_s * frame_rate_hz)
    return measured_frame_id + latency_frames + safety_frames


def round_apply_position_count(
    raw_count_coordinate: float,
    scan_direction_count: int,
) -> int:
    """Round a fractional scheduler count without moving the target earlier."""

    if not isinstance(raw_count_coordinate, int | float) or isinstance(
        raw_count_coordinate, bool
    ):
        raise ValueError("raw_count_coordinate must be numeric")
    if not isfinite(float(raw_count_coordinate)):
        raise ValueError("raw_count_coordinate must be finite")
    if not isinstance(scan_direction_count, int) or isinstance(scan_direction_count, bool):
        raise ValueError("scan_direction_count must be an integer")
    if scan_direction_count > 0:
        return round_apply_position_count_coordinate(
            raw_count_coordinate,
            scan_direction_count=1,
        )
    if scan_direction_count < 0:
        return round_apply_position_count_coordinate(
            raw_count_coordinate,
            scan_direction_count=-1,
        )
    raise ValueError("scan_direction_count must be non-zero")
