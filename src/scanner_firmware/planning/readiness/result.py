"""Platform readiness result v1 emitter.

The emitter is software-only. It does not probe Klipper, serial ports, GPIO,
motion, LEDs, cameras or firmware flashing paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from scanner_firmware.planning.readiness.reasons import derive_startup_readiness_reasons
from scanner_firmware.planning.readiness.types import StartupSelfCheckInput
from scanner_firmware.planning.readiness.types import ReadinessReason


SCHEMA_ID = "platform_readiness_result_v1"
SCHEMA_VERSION = "1.1.0"
OWNER_REPO = "scanner-firmware"

ReadinessState = Literal[
    "config_invalid",
    "interface_unbound",
    "safe_disabled",
    "ready_for_dry_run",
    "ready_for_live_test",
    "faulted",
]
CheckStatus = Literal["pass", "fail", "blocked", "skipped"]
CheckScope = Literal[
    "config",
    "interface_binding",
    "protocol",
    "calibration",
    "homing",
    "controller_discovery",
    "live_test_gate",
]
BlockerSeverity = Literal["p0", "p1", "p2"]


@dataclass(frozen=True)
class PlatformReadinessCheck:
    id: str
    status: CheckStatus
    scope: CheckScope
    evidence: str | None
    message: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string("id", self.id)
        _require_member("status", self.status, ("pass", "fail", "blocked", "skipped"))
        _require_member(
            "scope",
            self.scope,
            (
                "config",
                "interface_binding",
                "protocol",
                "calibration",
                "homing",
                "controller_discovery",
                "live_test_gate",
            ),
        )
        if self.status != "skipped" and self.evidence is None:
            raise ValueError("evidence is required unless status is skipped")
        if self.evidence is not None:
            _require_non_empty_string("evidence", self.evidence)
        if self.message is not None:
            _require_non_empty_string("message", self.message)

    def to_json_dict(self) -> dict[str, str | None]:
        payload = {
            "id": self.id,
            "status": self.status,
            "scope": self.scope,
            "evidence": self.evidence,
        }
        if self.message is not None:
            payload["message"] = self.message
        return payload


@dataclass(frozen=True)
class PlatformReadinessUnknown:
    field: str
    reason: str

    def __post_init__(self) -> None:
        _require_non_empty_string("field", self.field)
        _require_non_empty_string("reason", self.reason)

    def to_json_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason}


@dataclass(frozen=True)
class PlatformReadinessBlocker:
    id: str
    severity: BlockerSeverity
    message: str

    def __post_init__(self) -> None:
        _require_non_empty_string("id", self.id)
        _require_member("severity", self.severity, ("p0", "p1", "p2"))
        _require_non_empty_string("message", self.message)

    def to_json_dict(self) -> dict[str, str]:
        return {"id": self.id, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class LiveTestApproval:
    required: bool
    approved: bool = False
    issue_or_pr: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise ValueError("live_test_approval.required must be a boolean")
        if self.approved is not False:
            raise ValueError("software-only readiness records cannot approve live tests")
        if self.issue_or_pr is not None:
            _require_non_empty_string("live_test_approval.issue_or_pr", self.issue_or_pr)

    def to_json_dict(self) -> dict[str, bool | str | None]:
        return {
            "required": self.required,
            "approved": self.approved,
            "issue_or_pr": self.issue_or_pr,
        }


@dataclass(frozen=True)
class PlatformReadinessResult:
    generated_at: str
    target: str
    readiness_state: ReadinessState
    checks: tuple[PlatformReadinessCheck, ...]
    unknowns: tuple[PlatformReadinessUnknown, ...]
    blockers: tuple[PlatformReadinessBlocker, ...]
    reasons: tuple[ReadinessReason, ...] = ()
    hardware_outputs_enabled: bool = False
    live_test_approval: LiveTestApproval = LiveTestApproval(required=False)
    owner_repo: str = OWNER_REPO
    schema_id: str = SCHEMA_ID
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_id != SCHEMA_ID:
            raise ValueError(f"schema_id must be {SCHEMA_ID}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if self.owner_repo != OWNER_REPO:
            raise ValueError(f"owner_repo must be {OWNER_REPO}")
        _require_non_empty_string("generated_at", self.generated_at)
        _require_non_empty_string("target", self.target)
        _require_member(
            "readiness_state",
            self.readiness_state,
            (
                "config_invalid",
                "interface_unbound",
                "safe_disabled",
                "ready_for_dry_run",
                "ready_for_live_test",
                "faulted",
            ),
        )
        if self.readiness_state == "ready_for_live_test":
            raise ValueError("firmware software-only readiness cannot promote to ready_for_live_test")
        if self.hardware_outputs_enabled is not False:
            raise ValueError("hardware_outputs_enabled must be false")
        if not self.checks:
            raise ValueError("checks must not be empty")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "owner_repo": self.owner_repo,
            "target": self.target,
            "readiness_state": self.readiness_state,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_test_approval": self.live_test_approval.to_json_dict(),
            "reasons": [reason.to_json_dict() for reason in self.reasons],
            "checks": [check.to_json_dict() for check in self.checks],
            "unknowns": [unknown.to_json_dict() for unknown in self.unknowns],
            "blockers": [blocker.to_json_dict() for blocker in self.blockers],
        }


def emit_firmware_platform_readiness_result(
    selfcheck: StartupSelfCheckInput,
    *,
    generated_at: str,
    target: str,
    config_evidence: str = "tests/fixtures/firmware_config_split_valid.json",
    platform_profile_evidence: str = "tests/fixtures/board_profile_kinematics_fixture.yaml",
    protocol_evidence: str = "tests/fixtures/frame_event_replay_protocol_v1.jsonl",
) -> PlatformReadinessResult:
    """Emit the scanner-firmware platform readiness result v1 record."""

    checks = [
        _check(
            "firmware_config_schema",
            selfcheck.config_schema_valid,
            "config",
            config_evidence,
            "Firmware config schema accepted.",
        ),
        _check(
            "platform_profile",
            selfcheck.platform_profile_valid,
            "config",
            platform_profile_evidence,
            "Platform profile accepted by software-only validation.",
        ),
        _check(
            "printer_config_present",
            selfcheck.printer_config_present,
            "config",
            config_evidence,
            "Controller/printer configuration is present.",
        ),
        _check(
            "safe_defaults_declared",
            selfcheck.safe_defaults_declared,
            "config",
            config_evidence,
            "Output safe defaults are declared.",
        ),
        _check(
            "inactive_outputs_declared",
            selfcheck.inactive_outputs_declared,
            "config",
            config_evidence,
            "Inactive output state is declared.",
        ),
        _check(
            "output_ownership_unambiguous",
            selfcheck.output_ownership_unambiguous,
            "interface_binding",
            config_evidence,
            "Output ownership is unambiguous.",
        ),
        _check(
            "camera_mode_config",
            selfcheck.camera_mode_valid,
            "config",
            config_evidence,
            "Referenced camera mode config is accepted by startup inputs.",
        ),
        _check(
            "camera_crop_config",
            selfcheck.camera_crop_valid,
            "config",
            config_evidence,
            "Referenced camera crop config is accepted by startup inputs.",
        ),
        _check(
            "scanner_sync_metadata",
            selfcheck.scanner_sync_metadata_ready,
            "protocol",
            protocol_evidence,
            "Scanner-sync metadata path is software-ready.",
        ),
        _check(
            "scan_preflight",
            selfcheck.scan_preflight_accepted,
            "protocol",
            protocol_evidence,
            "Scan preflight accepted the dry-run plan.",
        ),
        _check(
            "homing_status",
            selfcheck.homing_complete
            and selfcheck.homing_feasibility_status == "implemented",
            "homing",
            "software-only startup self-check input",
            "Homing is complete and feasibility is implemented.",
        ),
        _check(
            "hardware_outputs_disabled",
            not selfcheck.hardware_outputs_armed,
            "live_test_gate",
            "software-only startup self-check input",
            "Hardware outputs remain disabled.",
        ),
        PlatformReadinessCheck(
            id="live_test_approval_gate",
            status="pass",
            scope="live_test_gate",
            evidence="scanner-docs/governance/live-test-approval-gate.md",
            message="No live test is approved or executed by this software-only record.",
        ),
    ]

    unknowns = _unknowns_for(selfcheck)
    blockers = _blockers_for(selfcheck)
    reasons = derive_startup_readiness_reasons(
        selfcheck,
        config_evidence=config_evidence,
        platform_profile_evidence=platform_profile_evidence,
        protocol_evidence=protocol_evidence,
    )
    return PlatformReadinessResult(
        generated_at=generated_at,
        target=target,
        readiness_state=_readiness_state_for(selfcheck, blockers),
        checks=tuple(checks),
        unknowns=tuple(unknowns),
        blockers=tuple(blockers),
        reasons=reasons,
    )


def _check(
    id: str,
    passed: bool,
    scope: CheckScope,
    evidence: str,
    pass_message: str,
) -> PlatformReadinessCheck:
    return PlatformReadinessCheck(
        id=id,
        status="pass" if passed else "blocked",
        scope=scope,
        evidence=evidence,
        message=pass_message if passed else f"{id} is not satisfied.",
    )


def _unknowns_for(selfcheck: StartupSelfCheckInput) -> tuple[PlatformReadinessUnknown, ...]:
    unknowns: list[PlatformReadinessUnknown] = []
    if not selfcheck.homing_complete:
        unknowns.append(
            PlatformReadinessUnknown(
                field="homing.completion",
                reason=(
                    "Homing is incomplete or unverified; software-only readiness does not "
                    "command motion or home axes."
                ),
            )
        )
    if selfcheck.homing_feasibility_status == "unknown":
        unknowns.append(
            PlatformReadinessUnknown(
                field="homing.feasibility_status",
                reason=(
                    "Live homing feasibility is unknown because no controller, switch or "
                    "motion probing is performed."
                ),
            )
        )
    if not selfcheck.scanner_sync_metadata_ready:
        unknowns.append(
            PlatformReadinessUnknown(
                field="scanner_sync.live_metadata_binding",
                reason=(
                    "Scanner-sync live metadata readiness is not proven without live Klipper "
                    "or controller discovery."
                ),
            )
        )
    return tuple(unknowns)


def _blockers_for(selfcheck: StartupSelfCheckInput) -> tuple[PlatformReadinessBlocker, ...]:
    blockers: list[PlatformReadinessBlocker] = []
    for id, passed in (
        ("firmware_config_schema_invalid", selfcheck.config_schema_valid),
        ("platform_profile_invalid", selfcheck.platform_profile_valid),
        ("printer_config_missing", selfcheck.printer_config_present),
        ("safe_defaults_missing", selfcheck.safe_defaults_declared),
        ("inactive_outputs_missing", selfcheck.inactive_outputs_declared),
        ("output_ownership_ambiguous", selfcheck.output_ownership_unambiguous),
    ):
        if not passed:
            blockers.append(
                PlatformReadinessBlocker(
                    id=id,
                    severity="p0",
                    message=f"{id} blocks firmware startup readiness.",
                )
            )
    for id, passed in (
        ("camera_mode_invalid", selfcheck.camera_mode_valid),
        ("camera_crop_invalid", selfcheck.camera_crop_valid),
        ("scan_preflight_not_accepted", selfcheck.scan_preflight_accepted),
    ):
        if not passed:
            blockers.append(
                PlatformReadinessBlocker(
                    id=id,
                    severity="p1",
                    message=f"{id} blocks dry-run promotion.",
                )
            )
    if not selfcheck.scanner_sync_metadata_ready:
        blockers.append(
            PlatformReadinessBlocker(
                id="scanner_sync_metadata_not_ready",
                severity="p0",
                message=(
                    "Scanner-sync metadata readiness is not proven; live controller probing "
                    "is outside this software-only result."
                ),
            )
        )
    if not selfcheck.homing_complete:
        blockers.append(
            PlatformReadinessBlocker(
                id="homing_incomplete",
                severity="p0",
                message=(
                    "Homing remains incomplete or unverified and must not be assumed by "
                    "firmware readiness."
                ),
            )
        )
    if selfcheck.homing_feasibility_status == "unknown":
        blockers.append(
            PlatformReadinessBlocker(
                id="homing_feasibility_unknown",
                severity="p0",
                message="Homing feasibility is unknown without live hardware validation.",
            )
        )
    if selfcheck.homing_feasibility_status == "not_implemented":
        blockers.append(
            PlatformReadinessBlocker(
                id="homing_not_implemented",
                severity="p0",
                message="Homing is not implemented and scan workflows must remain blocked.",
            )
        )
    if selfcheck.hardware_outputs_armed:
        blockers.append(
            PlatformReadinessBlocker(
                id="hardware_outputs_armed",
                severity="p0",
                message="Software-only readiness requires hardware outputs to remain disabled.",
            )
        )
    return tuple(blockers)


def _readiness_state_for(
    selfcheck: StartupSelfCheckInput,
    blockers: tuple[PlatformReadinessBlocker, ...],
) -> ReadinessState:
    if selfcheck.hardware_outputs_armed:
        return "faulted"
    if not all(
        (
            selfcheck.config_schema_valid,
            selfcheck.platform_profile_valid,
            selfcheck.printer_config_present,
            selfcheck.safe_defaults_declared,
            selfcheck.inactive_outputs_declared,
            selfcheck.output_ownership_unambiguous,
        )
    ):
        return "config_invalid"
    if blockers:
        return "safe_disabled"
    return "ready_for_dry_run"


def _require_non_empty_string(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _require_member(name: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        allowed_values = ", ".join(allowed)
        raise ValueError(f"{name} must be one of: {allowed_values}")
