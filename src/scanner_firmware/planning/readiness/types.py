"""Startup readiness data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StartupStage = Literal["CONFIG_REQUIRED", "IDLE_SAFE_DISABLED", "READY", "SCAN_PREPARE"]
ReadinessStatus = Literal["blocked", "safe_disabled", "ready"]
HomingFeasibilityStatus = Literal["implemented", "not_implemented", "unknown"]
ReadinessReasonDomain = Literal["board", "scanner_sync", "live_test_gate"]
ReadinessReasonCategory = Literal["blocker", "unknown", "safety_gate"]
ReadinessReasonSeverity = Literal["p0", "p1", "p2"]
ReadinessReasonCode = Literal[
    "board_config_schema_invalid",
    "board_profile_invalid",
    "board_printer_config_missing",
    "board_safe_defaults_missing",
    "board_inactive_outputs_missing",
    "board_output_ownership_ambiguous",
    "board_homing_incomplete",
    "board_homing_feasibility_unknown",
    "board_homing_not_implemented",
    "scanner_sync_metadata_not_ready",
    "scanner_sync_preflight_not_accepted",
    "live_hardware_outputs_armed",
    "live_test_approval_not_granted",
]
HOMING_FEASIBILITY_STATUSES: tuple[HomingFeasibilityStatus, ...] = (
    "implemented",
    "not_implemented",
    "unknown",
)
READINESS_REASON_CODES: tuple[ReadinessReasonCode, ...] = (
    "board_config_schema_invalid",
    "board_profile_invalid",
    "board_printer_config_missing",
    "board_safe_defaults_missing",
    "board_inactive_outputs_missing",
    "board_output_ownership_ambiguous",
    "board_homing_incomplete",
    "board_homing_feasibility_unknown",
    "board_homing_not_implemented",
    "scanner_sync_metadata_not_ready",
    "scanner_sync_preflight_not_accepted",
    "live_hardware_outputs_armed",
    "live_test_approval_not_granted",
)


@dataclass(frozen=True)
class ReadinessReason:
    code: ReadinessReasonCode
    domain: ReadinessReasonDomain
    category: ReadinessReasonCategory
    severity: ReadinessReasonSeverity
    evidence: str
    message: str

    def __post_init__(self) -> None:
        if self.code not in READINESS_REASON_CODES:
            raise ValueError("readiness reason code is not recognized")
        if self.domain not in ("board", "scanner_sync", "live_test_gate"):
            raise ValueError("readiness reason domain must be board, scanner_sync or live_test_gate")
        if self.category not in ("blocker", "unknown", "safety_gate"):
            raise ValueError("readiness reason category must be blocker, unknown or safety_gate")
        if self.severity not in ("p0", "p1", "p2"):
            raise ValueError("readiness reason severity must be p0, p1 or p2")
        _require_non_empty_string("readiness reason evidence", self.evidence)
        _require_non_empty_string("readiness reason message", self.message)

    def to_json_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "domain": self.domain,
            "category": self.category,
            "severity": self.severity,
            "evidence": self.evidence,
            "message": self.message,
        }


@dataclass(frozen=True)
class StartupSelfCheckInput:
    config_schema_valid: bool
    platform_profile_valid: bool
    printer_config_present: bool
    safe_defaults_declared: bool
    inactive_outputs_declared: bool
    output_ownership_unambiguous: bool
    camera_mode_valid: bool
    camera_crop_valid: bool
    scan_preflight_accepted: bool
    scanner_sync_metadata_ready: bool
    homing_complete: bool
    hardware_outputs_armed: bool = False
    homing_feasibility_status: HomingFeasibilityStatus = "implemented"

    def __post_init__(self) -> None:
        for name, value in (
            ("config_schema_valid", self.config_schema_valid),
            ("platform_profile_valid", self.platform_profile_valid),
            ("printer_config_present", self.printer_config_present),
            ("safe_defaults_declared", self.safe_defaults_declared),
            ("inactive_outputs_declared", self.inactive_outputs_declared),
            ("output_ownership_unambiguous", self.output_ownership_unambiguous),
            ("camera_mode_valid", self.camera_mode_valid),
            ("camera_crop_valid", self.camera_crop_valid),
            ("scan_preflight_accepted", self.scan_preflight_accepted),
            ("scanner_sync_metadata_ready", self.scanner_sync_metadata_ready),
            ("homing_complete", self.homing_complete),
            ("hardware_outputs_armed", self.hardware_outputs_armed),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
        if self.homing_feasibility_status not in HOMING_FEASIBILITY_STATUSES:
            raise ValueError(
                "homing_feasibility_status must be implemented, "
                "not_implemented or unknown"
            )


@dataclass(frozen=True)
class StartupReadinessDecision:
    stage: StartupStage
    status: ReadinessStatus
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    reasons: tuple[ReadinessReason, ...] = ()

    @property
    def can_prepare_scan(self) -> bool:
        return self.stage == "SCAN_PREPARE" and self.status == "ready"

    @property
    def reason_codes(self) -> tuple[ReadinessReasonCode, ...]:
        return tuple(reason.code for reason in self.reasons)


def _require_non_empty_string(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
