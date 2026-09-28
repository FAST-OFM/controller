"""Passive Klipper scanner-sync readiness evidence report.

This module composes already-captured scanner-sync evidence. It never runs
Klipper, opens serial or network transports, enables scanner-sync, toggles
GPIO/LED/camera outputs, commands motion or flashes firmware.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.parsing import (
    decode_scanner_sync_json_lines,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (
    build_scanner_sync_capture_report,
)
from scanner_firmware.adapters.klipper_adapter.readiness.config_parser import (
    ScannerSyncConfigError,
    ScannerSyncConfigObservation,
    parse_scanner_sync_config,
)
from scanner_firmware.adapters.klipper_adapter.readiness.dictionary import (
    ScannerSyncDictionaryCapabilities,
    observation_from_dictionary,
    scan_scanner_sync_dictionary,
)
from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (
    LiveMetadataReadiness,
    evaluate_live_metadata_readiness,
)
from scanner_firmware.adapters.klipper_adapter.readiness.stage_b_review import (
    StageBReviewPackageError,
    StageBReviewReadinessSummary,
    summarize_stage_b_review_yaml,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (
    ScannerSyncDecodeContext,
)


PASSIVE_KLIPPER_READINESS_REPORT_SCHEMA_ID = "passive_klipper_scanner_sync_readiness_v1"
PASSIVE_KLIPPER_READINESS_REPORT_SCHEMA_VERSION = "1.0.0"
PASSIVE_KLIPPER_READINESS_REPORT_GENERATED_AT = "2026-07-02T00:00:00Z"


@dataclass(frozen=True)
class PassiveKlipperReadinessReport:
    """One deterministic software-only readiness report from saved evidence."""

    report_id: str
    generated_at: str
    dictionary_capabilities: ScannerSyncDictionaryCapabilities
    config_observation: ScannerSyncConfigObservation | None
    live_metadata_readiness: LiveMetadataReadiness | None
    stage_b_review: StageBReviewReadinessSummary | None
    capture_report: dict[str, Any] | None
    blockers: tuple[str, ...]
    inputs: dict[str, str]
    software_only: bool = True
    hardware_outputs_enabled: bool = False
    live_hardware_access_used: bool = False
    scanner_sync_enabled_by_report: bool = False

    @property
    def ready_for_passive_metadata(self) -> bool:
        return not self.blockers

    @property
    def ready_for_live_hardware(self) -> bool:
        return False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PASSIVE_KLIPPER_READINESS_REPORT_SCHEMA_ID,
            "schema_version": PASSIVE_KLIPPER_READINESS_REPORT_SCHEMA_VERSION,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "software_only": self.software_only,
            "hardware_outputs_enabled": self.hardware_outputs_enabled,
            "live_hardware_access_used": self.live_hardware_access_used,
            "scanner_sync_enabled_by_report": self.scanner_sync_enabled_by_report,
            "ready_for_passive_metadata": self.ready_for_passive_metadata,
            "ready_for_live_hardware": self.ready_for_live_hardware,
            "blockers": list(self.blockers),
            "inputs": dict(self.inputs),
            "dictionary": _dictionary_dict(self.dictionary_capabilities),
            "config": (
                _config_observation_dict(self.config_observation)
                if self.config_observation is not None
                else None
            ),
            "live_metadata_readiness": (
                _live_metadata_readiness_dict(self.live_metadata_readiness)
                if self.live_metadata_readiness is not None
                else None
            ),
            "stage_b_review": (
                _stage_b_review_dict(self.stage_b_review)
                if self.stage_b_review is not None
                else None
            ),
            "event_stream": self.capture_report,
        }

    def write_json(self, output_path: str | Path) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json_dict(), indent=2) + "\n", encoding="utf-8")


def build_passive_klipper_readiness_report_from_paths(
    *,
    dictionary_path: str | Path,
    scanner_sync_config_path: str | Path,
    stage_b_review_path: str | Path,
    capture_jsonl_path: str | Path,
    decode_context: ScannerSyncDecodeContext,
    response_dispatch_available: bool,
    report_id: str = "passive-klipper-scanner-sync-readiness-v1",
    generated_at: str = PASSIVE_KLIPPER_READINESS_REPORT_GENERATED_AT,
) -> PassiveKlipperReadinessReport:
    """Build a passive readiness report from saved files only."""

    # Reports are replay artifacts, so record portable input identities rather
    # than leaking the machine-specific absolute directory used for replay.
    paths = {
        "dictionary_path": Path(dictionary_path).name,
        "scanner_sync_config_path": Path(scanner_sync_config_path).name,
        "stage_b_review_path": Path(stage_b_review_path).name,
        "capture_jsonl_path": Path(capture_jsonl_path).name,
    }
    return build_passive_klipper_readiness_report(
        dictionary_text=Path(dictionary_path).read_text(encoding="utf-8"),
        scanner_sync_config_text=Path(scanner_sync_config_path).read_text(encoding="utf-8"),
        stage_b_review_text=Path(stage_b_review_path).read_text(encoding="utf-8"),
        capture_jsonl_text=Path(capture_jsonl_path).read_text(encoding="utf-8"),
        decode_context=decode_context,
        response_dispatch_available=response_dispatch_available,
        report_id=report_id,
        generated_at=generated_at,
        inputs=paths,
    )


def build_passive_klipper_readiness_report(
    *,
    dictionary_text: str,
    scanner_sync_config_text: str,
    stage_b_review_text: str,
    capture_jsonl_text: str,
    decode_context: ScannerSyncDecodeContext,
    response_dispatch_available: bool,
    report_id: str = "passive-klipper-scanner-sync-readiness-v1",
    generated_at: str = PASSIVE_KLIPPER_READINESS_REPORT_GENERATED_AT,
    inputs: dict[str, str] | None = None,
) -> PassiveKlipperReadinessReport:
    """Build a passive readiness report from already-captured evidence text."""

    blockers: list[str] = []
    dictionary = scan_scanner_sync_dictionary(dictionary_text)

    config = _parse_config(scanner_sync_config_text, blockers)
    stage_b = _summarize_stage_b(stage_b_review_text, blockers)
    capture = _capture_report(capture_jsonl_text, decode_context, blockers)
    live_readiness = None
    if config is not None:
        live_readiness = evaluate_live_metadata_readiness(
            observation_from_dictionary(
                dictionary_text,
                host_extra_present=True,
                config_section_present=config.section_present,
                config_enable=config.enable,
                mcu_connected=True,
                response_dispatch_available=response_dispatch_available,
                metadata_only_mode=config.metadata_only_mode,
                hardware_outputs_enabled=config.hardware_outputs_enabled,
                config_safety_fields_present=config.safety_fields_present,
                configured_output_keys=config.configured_output_keys,
                protocol_version=config.protocol_version,
            )
        )
        blockers.extend(f"live_metadata:{blocker}" for blocker in live_readiness.blockers)
        if live_readiness.status != "ready":
            blockers.append(f"live_metadata_status:{live_readiness.status}")

    if stage_b is not None:
        blockers.extend(f"stage_b:{blocker}" for blocker in stage_b.blockers)
        if stage_b.readiness_state != "passive_observation_ready":
            blockers.append(f"stage_b_state:{stage_b.readiness_state}")
        observation = stage_b.observation
        if observation is not None:
            if not observation.metadata_only_mode:
                blockers.append("stage_b:metadata_only_mode_required")
            if observation.hardware_outputs_enabled:
                blockers.append("stage_b:hardware_outputs_must_be_disabled")
            if observation.output_pins_configured:
                blockers.append("stage_b:output_pins_must_not_be_configured")

    if capture is not None and not capture.get("accepted"):
        blockers.append("event_stream:not_accepted")

    if not response_dispatch_available:
        blockers.append("scanner_sync_response_dispatch_missing")

    return PassiveKlipperReadinessReport(
        report_id=report_id,
        generated_at=generated_at,
        dictionary_capabilities=dictionary,
        config_observation=config,
        live_metadata_readiness=live_readiness,
        stage_b_review=stage_b,
        capture_report=capture,
        blockers=tuple(_dedupe(blockers)),
        inputs={} if inputs is None else dict(inputs),
    )


def _parse_config(
    text: str,
    blockers: list[str],
) -> ScannerSyncConfigObservation | None:
    try:
        return parse_scanner_sync_config(text)
    except ScannerSyncConfigError as exc:
        blockers.append(f"config_parse_error:{exc}")
        return None


def _summarize_stage_b(
    text: str,
    blockers: list[str],
) -> StageBReviewReadinessSummary | None:
    try:
        return summarize_stage_b_review_yaml(text)
    except StageBReviewPackageError as exc:
        blockers.append(f"stage_b_parse_error:{exc}")
        return None


def _capture_report(
    text: str,
    context: ScannerSyncDecodeContext,
    blockers: list[str],
) -> dict[str, Any] | None:
    try:
        records = decode_scanner_sync_json_lines(
            text.splitlines(),
            context=context,
            require_event_type=True,
        )
        return build_scanner_sync_capture_report(records).to_json_dict()
    except ScannerSyncEventStreamError as exc:
        blockers.append(f"event_stream_error:{exc}")
        return None


def _dictionary_dict(capabilities: ScannerSyncDictionaryCapabilities) -> dict[str, Any]:
    return {
        "config_format_present": capabilities.config_format_present,
        "has_all_required_commands": capabilities.has_all_required_commands,
        "has_all_required_responses": capabilities.has_all_required_responses,
        "command_formats": sorted(capabilities.command_formats),
        "response_formats": sorted(capabilities.response_formats),
        "missing_command_formats": list(capabilities.missing_command_formats),
        "missing_response_formats": list(capabilities.missing_response_formats),
    }


def _config_observation_dict(observation: ScannerSyncConfigObservation) -> dict[str, Any]:
    return {
        "section_present": observation.section_present,
        "enable": observation.enable,
        "protocol_version": observation.protocol_version,
        "metadata_only_mode": observation.metadata_only_mode,
        "safety_fields_present": observation.safety_fields_present,
        "hardware_outputs_enabled": observation.hardware_outputs_enabled,
        "configured_output_keys": list(observation.configured_output_keys),
        "output_pins_configured": observation.output_pins_configured,
    }


def _live_metadata_readiness_dict(readiness: LiveMetadataReadiness) -> dict[str, Any]:
    return {
        "stage": readiness.stage,
        "status": readiness.status,
        "can_enable_scanner_sync": readiness.can_enable_scanner_sync,
        "blockers": list(readiness.blockers),
        "missing_command_formats": list(readiness.missing_command_formats),
        "missing_response_formats": list(readiness.missing_response_formats),
    }


def _stage_b_review_dict(summary: StageBReviewReadinessSummary) -> dict[str, Any]:
    observation = asdict(summary.observation) if summary.observation is not None else None
    if observation is not None:
        observation["expected_stripes_seen"] = list(observation["expected_stripes_seen"])
    return {
        "readiness_state": summary.readiness_state,
        "review_accepted": summary.review_accepted,
        "blockers": list(summary.blockers),
        "static_simulator_only": summary.static_simulator_only,
        "live_testing_approved": summary.live_testing_approved,
        "can_execute_live_stage_b": summary.can_execute_live_stage_b,
        "can_enable_scanner_sync": summary.can_enable_scanner_sync,
        "observation": observation,
    }


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)
