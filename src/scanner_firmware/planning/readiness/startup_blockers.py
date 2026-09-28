"""Static startup blocker report for controller, trigger and LED readiness.

This module is software-only. It validates saved evidence records only and does
not probe Klipper, serial devices, GPIO, motors, cameras, LEDs or firmware
flashing paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from scanner_firmware.planning.readiness.result import LiveTestApproval


SCHEMA_ID = "firmware_startup_blocker_report_v1"
SCHEMA_VERSION = "1.0.0"
OWNER_REPO = "scanner-firmware"

StartupBlockerReadinessState = Literal["blocked", "safe_disabled"]
StartupBlockerDomain = Literal["controller", "trigger", "led", "live_output_gate"]
StartupBlockerCheckStatus = Literal["pass", "blocked", "unknown"]
StartupBlockerSeverity = Literal["p0", "p1", "p2"]


@dataclass(frozen=True)
class StartupBlockerCheck:
    id: str
    domain: StartupBlockerDomain
    status: StartupBlockerCheckStatus
    evidence: str
    message: str

    def __post_init__(self) -> None:
        _require_non_empty_string("check.id", self.id)
        _require_member("check.domain", self.domain, _DOMAINS)
        _require_member("check.status", self.status, ("pass", "blocked", "unknown"))
        _require_non_empty_string("check.evidence", self.evidence)
        _require_non_empty_string("check.message", self.message)

    def to_json_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "domain": self.domain,
            "status": self.status,
            "evidence": self.evidence,
            "message": self.message,
        }


@dataclass(frozen=True)
class StartupBlockerUnknown:
    field: str
    domain: StartupBlockerDomain
    reason: str

    def __post_init__(self) -> None:
        _require_non_empty_string("unknown.field", self.field)
        _require_member("unknown.domain", self.domain, _DOMAINS)
        _require_non_empty_string("unknown.reason", self.reason)

    def to_json_dict(self) -> dict[str, str]:
        return {"field": self.field, "domain": self.domain, "reason": self.reason}


@dataclass(frozen=True)
class StartupBlocker:
    id: str
    domain: StartupBlockerDomain
    severity: StartupBlockerSeverity
    message: str

    def __post_init__(self) -> None:
        _require_non_empty_string("blocker.id", self.id)
        _require_member("blocker.domain", self.domain, _DOMAINS)
        _require_member("blocker.severity", self.severity, ("p0", "p1", "p2"))
        _require_non_empty_string("blocker.message", self.message)

    def to_json_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "domain": self.domain,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class FirmwareStartupBlockerReport:
    generated_at: str
    target: str
    issue_id: str
    readiness_state: StartupBlockerReadinessState
    checks: tuple[StartupBlockerCheck, ...]
    unknowns: tuple[StartupBlockerUnknown, ...]
    blockers: tuple[StartupBlocker, ...]
    hardware_outputs_enabled: bool = False
    live_test_approval: LiveTestApproval = LiveTestApproval(required=True)
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
        _require_non_empty_string("issue_id", self.issue_id)
        _require_member("readiness_state", self.readiness_state, ("blocked", "safe_disabled"))
        if self.hardware_outputs_enabled is not False:
            raise ValueError("hardware_outputs_enabled must be false")
        if not self.checks:
            raise ValueError("checks must not be empty")
        if self.readiness_state == "safe_disabled" and self.blockers:
            raise ValueError("safe_disabled report cannot carry startup blockers")
        if self.readiness_state == "blocked" and not self.blockers:
            raise ValueError("blocked report must carry startup blockers")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "owner_repo": self.owner_repo,
            "target": self.target,
            "issue_id": self.issue_id,
            "readiness_state": self.readiness_state,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_test_approval": self.live_test_approval.to_json_dict(),
            "checks": [check.to_json_dict() for check in self.checks],
            "unknowns": [unknown.to_json_dict() for unknown in self.unknowns],
            "blockers": [blocker.to_json_dict() for blocker in self.blockers],
        }


@dataclass(frozen=True)
class StartupBlockerReportValidation:
    accepted: bool
    blockers: tuple[str, ...]


def build_issue_093_startup_blocker_report(
    *,
    generated_at: str,
    target: str,
) -> FirmwareStartupBlockerReport:
    """Build the saved software-only issue 093 startup blocker report."""

    return FirmwareStartupBlockerReport(
        generated_at=generated_at,
        target=target,
        issue_id="093",
        readiness_state="blocked",
        checks=(
            StartupBlockerCheck(
                id="controller_identity_static_only",
                domain="controller",
                status="unknown",
                evidence="boards/kingroon_mono_v2/board.md",
                message=(
                    "Controller identity remains documentation/user-report based; "
                    "no live controller probing is performed."
                ),
            ),
            StartupBlockerCheck(
                id="trigger_output_static_only",
                domain="trigger",
                status="unknown",
                evidence="boards/kingroon_mono_v2/board.md",
                message=(
                    "Current trigger path is documented as a likely physical route, "
                    "not live-approved output behavior."
                ),
            ),
            StartupBlockerCheck(
                id="led_outputs_static_only",
                domain="led",
                status="unknown",
                evidence="boards/kingroon_mono_v2/board.md",
                message=(
                    "LED gate assignments require external drive/current-limit validation; "
                    "no LED output is approved by this report."
                ),
            ),
            StartupBlockerCheck(
                id="live_outputs_disabled",
                domain="live_output_gate",
                status="pass",
                evidence="software-only issue 093 fixture",
                message="The report does not enable or approve live hardware outputs.",
            ),
        ),
        unknowns=(
            StartupBlockerUnknown(
                field="controller.live_identity",
                domain="controller",
                reason=(
                    "Controller identity is not verified from a live board in this "
                    "software-only fixture."
                ),
            ),
            StartupBlockerUnknown(
                field="trigger.electrical_behavior",
                domain="trigger",
                reason=(
                    "Trigger voltage, polarity, load behavior and camera/sync acceptance "
                    "are not measured by static readiness."
                ),
            ),
            StartupBlockerUnknown(
                field="led.driver_current_limit",
                domain="led",
                reason=(
                    "LED drive circuit, current limiting, polarity and load behavior are "
                    "not inferred from candidate pin names."
                ),
            ),
        ),
        blockers=(
            StartupBlocker(
                id="controller_live_identity_unknown",
                domain="controller",
                severity="p0",
                message=(
                    "Startup readiness must remain blocked until controller identity and "
                    "safe connection state are verified outside this fixture."
                ),
            ),
            StartupBlocker(
                id="trigger_live_output_unapproved",
                domain="trigger",
                severity="p0",
                message=(
                    "Trigger output behavior is not live-approved; do not command camera "
                    "or sync trigger output from this report."
                ),
            ),
            StartupBlocker(
                id="led_live_output_unapproved",
                domain="led",
                severity="p0",
                message=(
                    "LED output behavior is not live-approved; do not drive LEDs from "
                    "this report."
                ),
            ),
        ),
    )


def validate_startup_blocker_report(payload: dict[str, Any]) -> StartupBlockerReportValidation:
    """Validate a saved startup blocker report without interpreting live hardware state."""

    validation_blockers: list[str] = []
    if not isinstance(payload, dict):
        return StartupBlockerReportValidation(False, ("startup_blocker_report_must_be_mapping",))

    _validate_required_top_level_keys(payload, validation_blockers)
    if validation_blockers:
        return StartupBlockerReportValidation(False, tuple(validation_blockers))

    try:
        FirmwareStartupBlockerReport(
            generated_at=payload["generated_at"],
            target=payload["target"],
            issue_id=payload["issue_id"],
            readiness_state=payload["readiness_state"],
            hardware_outputs_enabled=payload["hardware_outputs_enabled"],
            live_test_approval=LiveTestApproval(**payload["live_test_approval"]),
            checks=tuple(StartupBlockerCheck(**check) for check in payload["checks"]),
            unknowns=tuple(StartupBlockerUnknown(**unknown) for unknown in payload["unknowns"]),
            blockers=tuple(StartupBlocker(**blocker) for blocker in payload["blockers"]),
            owner_repo=payload["owner_repo"],
            schema_id=payload["schema_id"],
            schema_version=payload["schema_version"],
        )
    except (TypeError, ValueError) as exc:
        validation_blockers.append(str(exc))

    validation_blockers.extend(_validate_issue_093_domains(payload))
    return StartupBlockerReportValidation(
        accepted=not validation_blockers,
        blockers=tuple(validation_blockers),
    )


_DOMAINS = ("controller", "trigger", "led", "live_output_gate")
_REQUIRED_TOP_LEVEL_KEYS = frozenset(
    (
        "schema_id",
        "schema_version",
        "generated_at",
        "owner_repo",
        "target",
        "issue_id",
        "readiness_state",
        "hardware_outputs_enabled",
        "live_test_approval",
        "checks",
        "unknowns",
        "blockers",
    )
)


def _validate_required_top_level_keys(payload: dict[str, Any], blockers: list[str]) -> None:
    missing = sorted(_REQUIRED_TOP_LEVEL_KEYS - set(payload))
    extra = sorted(set(payload) - _REQUIRED_TOP_LEVEL_KEYS)
    blockers.extend(f"{key}_missing" for key in missing)
    blockers.extend(f"{key}_unexpected" for key in extra)


def _validate_issue_093_domains(payload: dict[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    blocker_domains = {
        blocker.get("domain")
        for blocker in payload.get("blockers", ())
        if isinstance(blocker, dict)
    }
    unknown_domains = {
        unknown.get("domain")
        for unknown in payload.get("unknowns", ())
        if isinstance(unknown, dict)
    }
    for domain in ("controller", "trigger", "led"):
        if domain not in blocker_domains:
            blockers.append(f"{domain}_blocker_missing")
        if domain not in unknown_domains:
            blockers.append(f"{domain}_unknown_missing")
    live_approval = payload.get("live_test_approval", {})
    if not isinstance(live_approval, dict) or live_approval.get("approved") is not False:
        blockers.append("live_test_approval_must_not_be_approved")
    if payload.get("hardware_outputs_enabled") is not False:
        blockers.append("hardware_outputs_enabled_must_be_false")
    return tuple(blockers)


def _require_non_empty_string(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _require_member(name: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        allowed_values = ", ".join(allowed)
        raise ValueError(f"{name} must be one of: {allowed_values}")
