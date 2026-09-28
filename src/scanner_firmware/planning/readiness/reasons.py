"""Typed readiness reasons for board, scanner-sync and live-test gates."""

from __future__ import annotations

from scanner_firmware.planning.readiness.types import (
    ReadinessReason,
    ReadinessReasonCode,
    StartupSelfCheckInput,
)


SOFTWARE_ONLY_INPUT_EVIDENCE = "software-only startup self-check input"
LIVE_TEST_GATE_EVIDENCE = "scanner-docs/governance/live-test-approval-gate.md"


def derive_startup_readiness_reasons(
    selfcheck: StartupSelfCheckInput,
    *,
    config_evidence: str = "tests/fixtures/firmware_config_split_valid.json",
    platform_profile_evidence: str = "tests/fixtures/board_profile_kinematics_fixture.yaml",
    protocol_evidence: str = "tests/fixtures/frame_event_replay_protocol_v1.jsonl",
) -> tuple[ReadinessReason, ...]:
    """Return the explicit software-only reasons behind readiness state.

    The reason model is intentionally passive. Unknown hardware facts remain
    unknown, and the live-test gate is always represented separately from
    dry-run readiness so software readiness cannot be mistaken for live
    approval.
    """

    reasons: list[ReadinessReason] = []
    _append_if_false(
        reasons,
        passed=selfcheck.config_schema_valid,
        code="board_config_schema_invalid",
        evidence=config_evidence,
        message="Firmware board config schema has not been accepted.",
    )
    _append_if_false(
        reasons,
        passed=selfcheck.platform_profile_valid,
        code="board_profile_invalid",
        evidence=platform_profile_evidence,
        message="Firmware board profile has not been accepted.",
    )
    _append_if_false(
        reasons,
        passed=selfcheck.printer_config_present,
        code="board_printer_config_missing",
        evidence=config_evidence,
        message="Controller/printer config is missing from software readiness input.",
    )
    _append_if_false(
        reasons,
        passed=selfcheck.safe_defaults_declared,
        code="board_safe_defaults_missing",
        evidence=config_evidence,
        message="Board output safe defaults are not declared.",
    )
    _append_if_false(
        reasons,
        passed=selfcheck.inactive_outputs_declared,
        code="board_inactive_outputs_missing",
        evidence=config_evidence,
        message="Inactive board output states are not declared.",
    )
    _append_if_false(
        reasons,
        passed=selfcheck.output_ownership_unambiguous,
        code="board_output_ownership_ambiguous",
        evidence=config_evidence,
        message="Board output ownership is ambiguous.",
    )
    if not selfcheck.homing_complete:
        reasons.append(
            ReadinessReason(
                code="board_homing_incomplete",
                domain="board",
                category="unknown",
                severity="p0",
                evidence=SOFTWARE_ONLY_INPUT_EVIDENCE,
                message=(
                    "Homing is incomplete or unverified; firmware readiness must not "
                    "infer physical board readiness."
                ),
            )
        )
    if selfcheck.homing_feasibility_status == "unknown":
        reasons.append(
            ReadinessReason(
                code="board_homing_feasibility_unknown",
                domain="board",
                category="unknown",
                severity="p0",
                evidence=SOFTWARE_ONLY_INPUT_EVIDENCE,
                message=(
                    "Live homing feasibility is unknown without verified controller, "
                    "switch and motion evidence."
                ),
            )
        )
    if selfcheck.homing_feasibility_status == "not_implemented":
        reasons.append(
            ReadinessReason(
                code="board_homing_not_implemented",
                domain="board",
                category="blocker",
                severity="p0",
                evidence=SOFTWARE_ONLY_INPUT_EVIDENCE,
                message="Homing is not implemented for the board readiness path.",
            )
        )
    if not selfcheck.scanner_sync_metadata_ready:
        reasons.append(
            ReadinessReason(
                code="scanner_sync_metadata_not_ready",
                domain="scanner_sync",
                category="unknown",
                severity="p0",
                evidence=protocol_evidence,
                message=(
                    "Scanner-sync metadata readiness is not proven by passive software "
                    "evidence."
                ),
            )
        )
    if not selfcheck.scan_preflight_accepted:
        reasons.append(
            ReadinessReason(
                code="scanner_sync_preflight_not_accepted",
                domain="scanner_sync",
                category="blocker",
                severity="p1",
                evidence=protocol_evidence,
                message="Scanner-sync dry-run preflight has not accepted the scan plan.",
            )
        )
    if selfcheck.hardware_outputs_armed:
        reasons.append(
            ReadinessReason(
                code="live_hardware_outputs_armed",
                domain="live_test_gate",
                category="blocker",
                severity="p0",
                evidence=SOFTWARE_ONLY_INPUT_EVIDENCE,
                message=(
                    "Hardware outputs are armed in input state, which is outside "
                    "software-only readiness."
                ),
            )
        )
    reasons.append(
        ReadinessReason(
            code="live_test_approval_not_granted",
            domain="live_test_gate",
            category="safety_gate",
            severity="p0",
            evidence=LIVE_TEST_GATE_EVIDENCE,
            message=(
                "This firmware readiness result does not approve firmware flashing, "
                "GPIO, motion, LEDs, camera triggers or live controller commands."
            ),
        )
    )
    return tuple(reasons)


def _append_if_false(
    reasons: list[ReadinessReason],
    *,
    passed: bool,
    code: ReadinessReasonCode,
    evidence: str,
    message: str,
) -> None:
    if passed:
        return
    reasons.append(
        ReadinessReason(
            code=code,
            domain="board",
            category="blocker",
            severity="p0",
            evidence=evidence,
            message=message,
        )
    )
