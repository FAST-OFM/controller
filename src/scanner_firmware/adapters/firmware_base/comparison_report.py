"""Offline comparison report for firmware-base dry-run candidates.

This module reads already-generated dry-run metadata only. It never imports or
contacts Klipper, grblHAL, GPIO, serial, camera, LED, motor or flashing APIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


FIRMWARE_BASE_PHASE0_COMPARISON_SCHEMA_ID = "firmware_base_phase0_comparison_v1"
FIRMWARE_BASE_PHASE0_COMPARISON_SCHEMA_VERSION = "1.0.0"
FIRMWARE_BASE_PHASE0_COMPARISON_GENERATED_AT = "2026-07-02T00:00:00Z"

EXPECTED_CANDIDATES = (
    "klipper",
    "grblhal",
    "external-rp2040-sync-board",
)

COMMON_DRY_RUN_GATES = (
    "phase0_fixture_present",
    "hardware_outputs_disabled",
    "all_candidates_feed_common_scheduler",
    "position_indexed_frame_events_present",
    "frame_ids_are_contiguous_per_candidate",
    "stripe_frame_indices_are_contiguous_per_candidate",
    "coordinate_source_recorded",
    "trigger_and_led_metadata_recorded",
)

REMAINING_SPIKE_GATES = (
    "bench_safe_or_no_hardware_timing_result",
    "position_indexed_output_jitter_measurement",
    "safe_stop_or_fault_terminal_behavior_per_candidate",
    "scheduled_z_bidirectional_ack_path",
    "homing_state_and_coordinate_source_integration",
    "future_encoder_coordinate_source_path",
    "fork_or_plugin_maintenance_cost",
    "approved_live_hardware_procedure_before_outputs",
)


class FirmwareBaseComparisonError(ValueError):
    """Raised when the offline firmware-base comparison input is invalid."""


@dataclass(frozen=True)
class CandidateDryRunSummary:
    """Phase-0 dry-run signal extracted for one firmware-base candidate."""

    candidate: str
    event_count: int
    first_frame_id: int | None
    last_frame_id: int | None
    frame_ids_contiguous: bool
    stripe_frame_indices_contiguous: bool
    position_axis_values: tuple[str, ...]
    coordinate_sources: tuple[str, ...]
    patterns_seen: tuple[str, ...]
    led_gate_sets_seen: tuple[tuple[str, ...], ...]
    trigger_output_names: tuple[str, ...]
    event_positions: tuple[int, ...]
    sample_positions: tuple[int, ...]
    mcu_time_us_values: tuple[int, ...]
    max_position_overshoot_count: int
    dry_run_adapter_signal: str = "common_scheduler_fixture_passed"
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False

    @property
    def passed_phase0_metadata_gate(self) -> bool:
        return (
            self.event_count > 0
            and self.frame_ids_contiguous
            and self.stripe_frame_indices_contiguous
            and self.coordinate_sources
            and self.patterns_seen
            and self.trigger_output_names
            and self.max_position_overshoot_count == 0
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "event_count": self.event_count,
            "first_frame_id": self.first_frame_id,
            "last_frame_id": self.last_frame_id,
            "frame_ids_contiguous": self.frame_ids_contiguous,
            "stripe_frame_indices_contiguous": self.stripe_frame_indices_contiguous,
            "position_axis_values": list(self.position_axis_values),
            "coordinate_sources": list(self.coordinate_sources),
            "patterns_seen": list(self.patterns_seen),
            "led_gate_sets_seen": [list(gates) for gates in self.led_gate_sets_seen],
            "trigger_output_names": list(self.trigger_output_names),
            "event_positions": list(self.event_positions),
            "sample_positions": list(self.sample_positions),
            "mcu_time_us_values": list(self.mcu_time_us_values),
            "max_position_overshoot_count": self.max_position_overshoot_count,
            "dry_run_adapter_signal": self.dry_run_adapter_signal,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "passed_phase0_metadata_gate": self.passed_phase0_metadata_gate,
        }


@dataclass(frozen=True)
class FirmwareBasePhase0ComparisonReport:
    """Software-only comparison report for the current phase-0 fixture."""

    report_id: str
    generated_at: str
    candidates: tuple[CandidateDryRunSummary, ...]
    source_fixture: str
    common_dry_run_gates: tuple[str, ...] = COMMON_DRY_RUN_GATES
    remaining_spike_gates: tuple[str, ...] = REMAINING_SPIKE_GATES
    recommendation_state: str = "not_ready_for_final_selection"
    software_only: bool = True
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False
    final_firmware_base_selected: bool = False

    @property
    def phase0_metadata_gate_passed(self) -> bool:
        return all(candidate.passed_phase0_metadata_gate for candidate in self.candidates)

    @property
    def candidate_names(self) -> tuple[str, ...]:
        return tuple(candidate.candidate for candidate in self.candidates)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_id": FIRMWARE_BASE_PHASE0_COMPARISON_SCHEMA_ID,
            "schema_version": FIRMWARE_BASE_PHASE0_COMPARISON_SCHEMA_VERSION,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "source_fixture": self.source_fixture,
            "software_only": self.software_only,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "final_firmware_base_selected": self.final_firmware_base_selected,
            "recommendation_state": self.recommendation_state,
            "candidate_names": list(self.candidate_names),
            "phase0_metadata_gate_passed": self.phase0_metadata_gate_passed,
            "common_dry_run_gates": list(self.common_dry_run_gates),
            "remaining_spike_gates": list(self.remaining_spike_gates),
            "candidates": [
                candidate.to_json_dict()
                for candidate in sorted(self.candidates, key=lambda item: item.candidate)
            ],
        }

    def write_json(self, output_path: str | Path) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json_dict(), indent=2) + "\n", encoding="utf-8")


def build_firmware_base_phase0_comparison_report_from_path(
    fixture_path: str | Path,
    *,
    report_id: str = "firmware-base-phase0-comparison-v1",
    generated_at: str = FIRMWARE_BASE_PHASE0_COMPARISON_GENERATED_AT,
) -> FirmwareBasePhase0ComparisonReport:
    """Build a deterministic comparison report from a checked-in fixture."""

    path = Path(fixture_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return build_firmware_base_phase0_comparison_report(
        payload,
        source_fixture=str(path),
        report_id=report_id,
        generated_at=generated_at,
    )


def build_firmware_base_phase0_comparison_report(
    payload: Mapping[str, Any],
    *,
    source_fixture: str,
    report_id: str = "firmware-base-phase0-comparison-v1",
    generated_at: str = FIRMWARE_BASE_PHASE0_COMPARISON_GENERATED_AT,
) -> FirmwareBasePhase0ComparisonReport:
    """Build a comparison report from phase-0 dry-run fixture data."""

    _validate_payload_header(payload)
    candidates_payload = payload["candidates"]
    if not isinstance(candidates_payload, Mapping):
        raise FirmwareBaseComparisonError("candidates must be a mapping")

    actual_candidates = tuple(candidates_payload)
    if set(actual_candidates) != set(EXPECTED_CANDIDATES):
        raise FirmwareBaseComparisonError(
            "candidates must cover exactly: " + ", ".join(EXPECTED_CANDIDATES)
        )

    summaries = tuple(
        _summarize_candidate(candidate, candidates_payload[candidate])
        for candidate in EXPECTED_CANDIDATES
    )
    return FirmwareBasePhase0ComparisonReport(
        report_id=report_id,
        generated_at=generated_at,
        candidates=summaries,
        source_fixture=source_fixture,
    )


def _validate_payload_header(payload: Mapping[str, Any]) -> None:
    if payload.get("phase") != "dry_run":
        raise FirmwareBaseComparisonError("phase must be dry_run")
    if payload.get("hardware_outputs_enabled") is not False:
        raise FirmwareBaseComparisonError("hardware_outputs_enabled must be false")


def _summarize_candidate(candidate: str, events: Any) -> CandidateDryRunSummary:
    if not isinstance(events, list):
        raise FirmwareBaseComparisonError(f"{candidate} events must be a list")
    if not events:
        raise FirmwareBaseComparisonError(f"{candidate} must contain at least one event")
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise FirmwareBaseComparisonError(f"{candidate} event {index} must be a mapping")

    frame_ids = _required_ints(candidate, events, "frame_id")
    stripe_indices = _required_ints(candidate, events, "stripe_frame_index")
    overshoots = _required_ints(candidate, events, "position_overshoot_count")

    return CandidateDryRunSummary(
        candidate=candidate,
        event_count=len(events),
        first_frame_id=frame_ids[0],
        last_frame_id=frame_ids[-1],
        frame_ids_contiguous=_is_contiguous_from_zero(frame_ids),
        stripe_frame_indices_contiguous=_is_contiguous_from_zero(stripe_indices),
        position_axis_values=_unique_strings(candidate, events, "position_axis"),
        coordinate_sources=_unique_strings(candidate, events, "coordinate_source_used"),
        patterns_seen=_unique_strings(candidate, events, "pattern"),
        led_gate_sets_seen=_unique_string_tuples(candidate, events, "led_gate_names"),
        trigger_output_names=_unique_strings(candidate, events, "trigger_output_name"),
        event_positions=tuple(_required_ints(candidate, events, "event_position")),
        sample_positions=tuple(_required_ints(candidate, events, "sample_position")),
        mcu_time_us_values=tuple(_required_ints(candidate, events, "mcu_time_us")),
        max_position_overshoot_count=max(overshoots),
    )


def _required_ints(candidate: str, events: list[Mapping[str, Any]], key: str) -> list[int]:
    values: list[int] = []
    for index, event in enumerate(events):
        value = event.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise FirmwareBaseComparisonError(f"{candidate} event {index} {key} must be an int")
        values.append(value)
    return values


def _unique_strings(candidate: str, events: list[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, event in enumerate(events):
        value = event.get(key)
        if not isinstance(value, str) or not value:
            raise FirmwareBaseComparisonError(f"{candidate} event {index} {key} must be a string")
        if value not in values:
            values.append(value)
    return tuple(values)


def _unique_string_tuples(
    candidate: str,
    events: list[Mapping[str, Any]],
    key: str,
) -> tuple[tuple[str, ...], ...]:
    values: list[tuple[str, ...]] = []
    for index, event in enumerate(events):
        raw_value = event.get(key)
        if not isinstance(raw_value, list) or not raw_value:
            raise FirmwareBaseComparisonError(f"{candidate} event {index} {key} must be a list")
        value = tuple(raw_value)
        if not all(isinstance(item, str) and item for item in value):
            raise FirmwareBaseComparisonError(
                f"{candidate} event {index} {key} must contain strings"
            )
        if value not in values:
            values.append(value)
    return tuple(values)


def _is_contiguous_from_zero(values: list[int]) -> bool:
    return values == list(range(len(values)))
