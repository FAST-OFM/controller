"""Interfaces for scanner-sync service substitution points.

These protocols keep simulator and future live adapters behind explicit
boundaries. They do not import Klipper, open serial ports, command motion,
toggle GPIO, trigger cameras or drive LEDs.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from scanner_firmware.foundation.protocol.events import ProtocolRecord
from scanner_firmware.planning.scan_preflight.decisions import (
    ScanPreflightDecision,
    ScanPreflightInput,
)
from scanner_firmware.planning.trigger_scheduler.types import PositionSample

__all__ = [
    "LoadedScanPlan",
    "PositionSampleSource",
    "ScanExecutionBackend",
    "ScanPreflightDecision",
    "ScanPreflightInput",
]


@dataclass(frozen=True)
class LoadedScanPlan:
    scan_id: str
    stripe_count: int


class PositionSampleSource(Protocol):
    """Provide position samples for one stripe execution."""

    def samples_for_stripe(self, stripe_index: int) -> Iterable[PositionSample]:
        """Return commanded/observed position samples for a stripe."""


class ScanExecutionBackend(Protocol):
    """Run scanner-sync workflow operations behind a replaceable backend."""

    def load_scan_recipe(self, scan_recipe: Mapping[str, Any]) -> LoadedScanPlan:
        """Load a scan recipe into the backend."""

    def run_preflight(self, preflight: ScanPreflightInput) -> ScanPreflightDecision:
        """Evaluate and store scan preflight state."""

    def start_stripe_from_source(
        self,
        stripe_index: int,
        source: PositionSampleSource,
        *,
        stop_after_events: int | None = None,
        fault_after_events: int | None = None,
        fault_message: str = "simulated scheduler fault",
    ) -> list[ProtocolRecord]:
        """Execute one stripe using an injected position sample source."""
