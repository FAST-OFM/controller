"""Software-only replay evidence for remaining firmware-base spike gates.

This module consumes checked protocol JSONL fixtures only. It does not import
or contact Klipper, grblHAL, GPIO, serial, camera, LED, motor or flashing APIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scanner_firmware.adapters.firmware_base.comparison_report import REMAINING_SPIKE_GATES
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (
    build_scanner_sync_capture_report,
)
from scanner_firmware.foundation.protocol.events import (
    SchedulerTerminalRecord,
)
from scanner_firmware.foundation.protocol.parsing import decode_protocol_json_lines


FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_SCHEMA_ID = "firmware_base_gate_replay_evidence_v1"
FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_SCHEMA_VERSION = "1.0.0"
FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_GENERATED_AT = "2026-07-02T00:00:00Z"

ADVANCED_SPIKE_GATES = (
    "safe_stop_or_fault_terminal_behavior_per_candidate",
    "scheduled_z_bidirectional_ack_path",
)


@dataclass(frozen=True)
class ReplayFixtureEvidence:
    """Acceptance summary for one checked scanner-sync protocol fixture."""

    fixture: str
    record_count: int
    event_types: tuple[str, ...]
    frame_count: int
    terminal_count: int
    terminal_statuses: tuple[str, ...]
    terminal_reason_codes: tuple[str, ...]
    z_scheduled_count: int
    z_applied_count: int
    z_rejected_count: int
    z_outcomes: tuple[dict[str, Any], ...]
    hardware_outputs_enabled: bool = False
    accepted: bool = True

    @property
    def has_stop_terminal(self) -> bool:
        return "stopped" in self.terminal_statuses

    @property
    def has_fault_terminal(self) -> bool:
        return "fault" in self.terminal_statuses

    @property
    def has_clean_completion_policy(self) -> bool:
        return self.frame_count > 0 and self.terminal_count == 0

    @property
    def has_scheduled_z_applied_pair(self) -> bool:
        return self.z_scheduled_count > 0 and self.z_applied_count > 0

    @property
    def has_z_rejection_path(self) -> bool:
        return self.z_rejected_count > 0

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture,
            "accepted": self.accepted,
            "record_count": self.record_count,
            "event_types": list(self.event_types),
            "frame_count": self.frame_count,
            "terminal_count": self.terminal_count,
            "terminal_statuses": list(self.terminal_statuses),
            "terminal_reason_codes": list(self.terminal_reason_codes),
            "z_scheduled_count": self.z_scheduled_count,
            "z_applied_count": self.z_applied_count,
            "z_rejected_count": self.z_rejected_count,
            "z_outcomes": list(self.z_outcomes),
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
        }


@dataclass(frozen=True)
class FirmwareBaseGateReplayEvidence:
    """Bounded software replay evidence for selected remaining spike gates."""

    report_id: str
    generated_at: str
    source_fixtures: tuple[str, ...]
    fixtures: tuple[ReplayFixtureEvidence, ...]
    advanced_spike_gates: tuple[str, ...] = ADVANCED_SPIKE_GATES
    remaining_spike_gates_before_close: tuple[str, ...] = REMAINING_SPIKE_GATES
    candidate_coverage: str = "common_protocol_fixture_only"
    live_readiness_claimed: bool = False
    final_firmware_base_selected: bool = False
    software_only: bool = True
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False

    @property
    def safe_stop_fault_terminal_check_passed(self) -> bool:
        return (
            any(fixture.has_stop_terminal for fixture in self.fixtures)
            and any(fixture.has_fault_terminal for fixture in self.fixtures)
            and any(fixture.has_clean_completion_policy for fixture in self.fixtures)
            and all(not fixture.hardware_outputs_enabled for fixture in self.fixtures)
        )

    @property
    def scheduled_z_ack_path_check_passed(self) -> bool:
        return any(fixture.has_scheduled_z_applied_pair for fixture in self.fixtures) and all(
            not fixture.hardware_outputs_enabled for fixture in self.fixtures
        )

    @property
    def z_rejection_path_observed(self) -> bool:
        return any(fixture.has_z_rejection_path for fixture in self.fixtures)

    @property
    def software_replay_evidence_passed(self) -> bool:
        return (
            self.safe_stop_fault_terminal_check_passed
            and self.scheduled_z_ack_path_check_passed
            and self.software_only
            and not self.hardware_outputs_enabled
            and not self.live_hardware_access_used
            and not self.live_readiness_claimed
            and not self.final_firmware_base_selected
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_id": FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_SCHEMA_ID,
            "schema_version": FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_SCHEMA_VERSION,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "source_fixtures": list(self.source_fixtures),
            "software_only": self.software_only,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "live_readiness_claimed": self.live_readiness_claimed,
            "final_firmware_base_selected": self.final_firmware_base_selected,
            "candidate_coverage": self.candidate_coverage,
            "advanced_spike_gates": list(self.advanced_spike_gates),
            "safe_stop_fault_terminal_check_passed": (
                self.safe_stop_fault_terminal_check_passed
            ),
            "scheduled_z_ack_path_check_passed": self.scheduled_z_ack_path_check_passed,
            "z_rejection_path_observed": self.z_rejection_path_observed,
            "software_replay_evidence_passed": self.software_replay_evidence_passed,
            "remaining_spike_gates_before_close": list(
                self.remaining_spike_gates_before_close
            ),
            "fixtures": [fixture.to_json_dict() for fixture in self.fixtures],
        }

    def write_json(self, output_path: str | Path) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json_dict(), indent=2) + "\n", encoding="utf-8")


def build_firmware_base_gate_replay_evidence_from_paths(
    fixture_paths: Iterable[str | Path],
    *,
    report_id: str = "firmware-base-gate-replay-evidence-v1",
    generated_at: str = FIRMWARE_BASE_GATE_REPLAY_EVIDENCE_GENERATED_AT,
) -> FirmwareBaseGateReplayEvidence:
    """Build deterministic gate evidence from checked protocol JSONL fixtures."""

    fixture_evidence = tuple(
        _summarize_protocol_fixture(Path(path)) for path in fixture_paths
    )
    return FirmwareBaseGateReplayEvidence(
        report_id=report_id,
        generated_at=generated_at,
        source_fixtures=tuple(fixture.fixture for fixture in fixture_evidence),
        fixtures=fixture_evidence,
    )


def _summarize_protocol_fixture(path: Path) -> ReplayFixtureEvidence:
    records = decode_protocol_json_lines(path.read_text(encoding="utf-8").splitlines())
    if not records:
        raise FirmwareBaseGateReplayEvidenceError(f"{path}: fixture must contain records")
    if any(record.hardware_outputs_enabled for record in records):
        raise FirmwareBaseGateReplayEvidenceError(
            f"{path}: hardware_outputs_enabled must remain false"
        )

    report = build_scanner_sync_capture_report(records).to_json_dict()
    terminal_records = tuple(
        record for record in records if isinstance(record, SchedulerTerminalRecord)
    )
    return ReplayFixtureEvidence(
        fixture=str(path),
        record_count=report["record_count"],
        event_types=tuple(report["event_types"]),
        frame_count=report["frame_count"],
        terminal_count=report["terminal_count"],
        terminal_statuses=_unique_strings(record.status for record in terminal_records),
        terminal_reason_codes=_unique_strings(
            record.reason_code for record in terminal_records
        ),
        z_scheduled_count=report["z_scheduled_count"],
        z_applied_count=report["z_applied_count"],
        z_rejected_count=report["z_rejected_count"],
        z_outcomes=tuple(report["z_outcomes"]),
        hardware_outputs_enabled=any(record.hardware_outputs_enabled for record in records),
    )


def _unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return tuple(seen)


class FirmwareBaseGateReplayEvidenceError(ValueError):
    """Raised when firmware-base replay evidence cannot be built."""
