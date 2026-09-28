"""Canonical firmware scan execution mode names."""

from __future__ import annotations

from typing import Literal


ScanMode = Literal[
    "stop_and_capture",
    "micro_stop",
    "segmented_fly_scan",
    "fly_scan_open_loop",
    "fly_scan_predictive_z",
]

ALL_SCAN_MODES: frozenset[ScanMode] = frozenset(
    (
        "stop_and_capture",
        "micro_stop",
        "segmented_fly_scan",
        "fly_scan_open_loop",
        "fly_scan_predictive_z",
    )
)

