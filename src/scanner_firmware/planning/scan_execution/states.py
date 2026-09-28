"""Scan execution state value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.planning.readiness.types import StartupReadinessDecision
from scanner_firmware.planning.scan_preflight.decisions import ScanPreflightDecision


ScanExecutionState = Literal[
    "BOOT",
    "CONFIG_REQUIRED",
    "IDLE_SAFE_DISABLED",
    "READY",
    "SCAN_PREPARE",
    "SCANNING",
    "STOPPING",
    "COMPLETE",
    "FAULT",
]
TerminalReason = Literal[
    "DRY_RUN_COMPLETE",
    "SCAN_COMPLETE",
    "STOPPED",
    "FAULT_DETECTED",
]


class ScanExecutionError(ValueError):
    """Raised when a scan execution transition is not allowed."""


@dataclass(frozen=True)
class ScanExecutionInput:
    """Decision data supplied to the execution state machine."""

    readiness: StartupReadinessDecision
    preflight: ScanPreflightDecision
    dry_run: bool
    hardware_outputs_armed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.dry_run, bool):
            raise ScanExecutionError("dry_run must be a boolean")
        if not isinstance(self.hardware_outputs_armed, bool):
            raise ScanExecutionError("hardware_outputs_armed must be a boolean")
        if self.dry_run and self.hardware_outputs_armed:
            raise ScanExecutionError(
                "dry-run scan execution requires hardware outputs to remain disabled"
            )


@dataclass(frozen=True)
class ScanExecutionSnapshot:
    state: ScanExecutionState
    terminal_reason: TerminalReason | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def terminal(self) -> bool:
        return self.state in ("COMPLETE", "FAULT")
