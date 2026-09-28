"""Startup readiness evaluation."""

from __future__ import annotations

from scanner_firmware.planning.readiness.reasons import derive_startup_readiness_reasons
from scanner_firmware.planning.readiness.types import (
    StartupReadinessDecision,
    StartupSelfCheckInput,
)


def evaluate_startup_readiness(
    selfcheck: StartupSelfCheckInput,
) -> StartupReadinessDecision:
    """Aggregate passive startup/self-check status into one decision."""

    reasons = derive_startup_readiness_reasons(selfcheck)
    blockers: list[str] = []
    for name, value in (
        ("config_schema_valid", selfcheck.config_schema_valid),
        ("platform_profile_valid", selfcheck.platform_profile_valid),
        ("printer_config_present", selfcheck.printer_config_present),
        ("safe_defaults_declared", selfcheck.safe_defaults_declared),
        ("inactive_outputs_declared", selfcheck.inactive_outputs_declared),
        ("output_ownership_unambiguous", selfcheck.output_ownership_unambiguous),
    ):
        if not value:
            blockers.append(name)
    if blockers:
        return StartupReadinessDecision(
            stage="CONFIG_REQUIRED",
            status="blocked",
            blockers=tuple(blockers),
            reasons=reasons,
        )

    idle_blockers = []
    if not selfcheck.camera_mode_valid:
        idle_blockers.append("camera_mode_valid")
    if not selfcheck.camera_crop_valid:
        idle_blockers.append("camera_crop_valid")
    if idle_blockers:
        return StartupReadinessDecision(
            stage="IDLE_SAFE_DISABLED",
            status="blocked",
            blockers=tuple(idle_blockers),
            reasons=reasons,
        )

    warnings: list[str] = []
    if not selfcheck.homing_complete:
        warnings.append("homing_incomplete")
    if selfcheck.homing_feasibility_status == "unknown":
        warnings.append("homing_feasibility_unknown")
    if selfcheck.homing_feasibility_status == "not_implemented":
        warnings.append("homing_not_implemented")
    if not selfcheck.scanner_sync_metadata_ready:
        warnings.append("scanner_sync_metadata_not_ready")
    if not selfcheck.scan_preflight_accepted:
        warnings.append("scan_preflight_not_accepted")

    if selfcheck.hardware_outputs_armed:
        return StartupReadinessDecision(
            stage="IDLE_SAFE_DISABLED",
            status="blocked",
            blockers=("hardware_outputs_armed",),
            warnings=tuple(warnings),
            reasons=reasons,
        )

    if warnings:
        return StartupReadinessDecision(
            stage="IDLE_SAFE_DISABLED",
            status="safe_disabled",
            blockers=(),
            warnings=tuple(warnings),
            reasons=reasons,
        )

    if not selfcheck.hardware_outputs_armed:
        return StartupReadinessDecision(
            stage="READY",
            status="safe_disabled",
            blockers=(),
            warnings=("hardware_outputs_not_armed",),
            reasons=reasons,
        )

    raise RuntimeError("software-only readiness cannot enter SCAN_PREPARE")
