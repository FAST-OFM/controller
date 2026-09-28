"""Software-only scan execution state machine."""

from __future__ import annotations

from scanner_firmware.planning.readiness.types import StartupReadinessDecision
from scanner_firmware.planning.scan_execution.states import (
    ScanExecutionError,
    ScanExecutionInput,
    ScanExecutionSnapshot,
)


def initial_scan_execution_state() -> ScanExecutionSnapshot:
    return ScanExecutionSnapshot(state="BOOT")


def apply_startup_decision(
    current: ScanExecutionSnapshot,
    readiness: StartupReadinessDecision,
) -> ScanExecutionSnapshot:
    """Move BOOT or idle startup states to the passive readiness stage."""

    _require_nonterminal(current)
    if current.state not in ("BOOT", "CONFIG_REQUIRED", "IDLE_SAFE_DISABLED", "READY"):
        raise ScanExecutionError(
            f"startup decision cannot be applied from {current.state}"
        )

    if readiness.stage == "CONFIG_REQUIRED":
        return ScanExecutionSnapshot(
            state="CONFIG_REQUIRED",
            warnings=readiness.warnings,
            errors=readiness.blockers,
        )
    if readiness.stage == "IDLE_SAFE_DISABLED":
        return ScanExecutionSnapshot(
            state="IDLE_SAFE_DISABLED",
            warnings=readiness.warnings,
            errors=readiness.blockers,
        )
    if readiness.stage in ("READY", "SCAN_PREPARE"):
        return ScanExecutionSnapshot(
            state="READY",
            warnings=readiness.warnings,
            errors=readiness.blockers,
        )

    raise ScanExecutionError(f"unsupported readiness stage: {readiness.stage}")


def prepare_scan(
    current: ScanExecutionSnapshot,
    inputs: ScanExecutionInput,
) -> ScanExecutionSnapshot:
    """Validate the scan-start gate and enter SCAN_PREPARE."""

    _require_nonterminal(current)
    if current.state not in ("READY", "IDLE_SAFE_DISABLED"):
        raise ScanExecutionError(f"scan cannot be prepared from {current.state}")
    if not inputs.preflight.accepted:
        raise ScanExecutionError(
            "scan preflight decision must be accepted before scan preparation"
        )

    if inputs.dry_run:
        if inputs.readiness.status == "blocked" or inputs.readiness.blockers:
            raise ScanExecutionError(
                "dry-run preparation cannot bypass readiness blockers"
            )
        return ScanExecutionSnapshot(
            state="SCAN_PREPARE",
            warnings=inputs.preflight.warnings + inputs.readiness.warnings,
        )

    if not inputs.readiness.can_prepare_scan:
        raise ScanExecutionError(
            "scan preparation requires a ready startup decision"
        )
    if not inputs.hardware_outputs_armed:
        raise ScanExecutionError(
            "scan preparation requires explicit hardware output arm"
        )
    if inputs.preflight.missing_axes:
        missing_text = ", ".join(inputs.preflight.missing_axes)
        raise ScanExecutionError(
            f"scan preparation requires homing for axes: {missing_text}"
        )

    return ScanExecutionSnapshot(state="SCAN_PREPARE")


def begin_scanning(
    current: ScanExecutionSnapshot,
    inputs: ScanExecutionInput,
) -> ScanExecutionSnapshot:
    """Enter SCANNING only when readiness, preflight and arm gates are true."""

    _require_nonterminal(current)
    if current.state != "SCAN_PREPARE":
        raise ScanExecutionError(f"scanning cannot begin from {current.state}")

    if inputs.dry_run:
        return ScanExecutionSnapshot(
            state="COMPLETE",
            terminal_reason="DRY_RUN_COMPLETE",
            warnings=inputs.preflight.warnings + inputs.readiness.warnings,
        )
    if not inputs.readiness.can_prepare_scan:
        raise ScanExecutionError("SCANNING requires a ready startup decision")
    if not inputs.preflight.accepted:
        raise ScanExecutionError("SCANNING requires an accepted preflight decision")
    if not inputs.hardware_outputs_armed:
        raise ScanExecutionError("SCANNING requires explicit hardware output arm")
    if inputs.preflight.missing_axes:
        missing_text = ", ".join(inputs.preflight.missing_axes)
        raise ScanExecutionError(f"SCANNING requires homing for axes: {missing_text}")

    return ScanExecutionSnapshot(state="SCANNING")


def complete_scan(current: ScanExecutionSnapshot) -> ScanExecutionSnapshot:
    _require_nonterminal(current)
    if current.state != "SCANNING":
        raise ScanExecutionError(f"scan cannot complete from {current.state}")
    return ScanExecutionSnapshot(state="COMPLETE", terminal_reason="SCAN_COMPLETE")


def request_stop(current: ScanExecutionSnapshot) -> ScanExecutionSnapshot:
    _require_nonterminal(current)
    if current.state not in ("SCAN_PREPARE", "SCANNING"):
        raise ScanExecutionError(f"stop cannot be requested from {current.state}")
    return ScanExecutionSnapshot(state="STOPPING")


def complete_stop(current: ScanExecutionSnapshot) -> ScanExecutionSnapshot:
    _require_nonterminal(current)
    if current.state != "STOPPING":
        raise ScanExecutionError(f"stop cannot complete from {current.state}")
    return ScanExecutionSnapshot(state="COMPLETE", terminal_reason="STOPPED")


def enter_fault(current: ScanExecutionSnapshot) -> ScanExecutionSnapshot:
    _require_nonterminal(current)
    return ScanExecutionSnapshot(state="FAULT", terminal_reason="FAULT_DETECTED")


def _require_nonterminal(current: ScanExecutionSnapshot) -> None:
    if current.terminal:
        raise ScanExecutionError(
            f"terminal state {current.state} cannot transition"
        )
