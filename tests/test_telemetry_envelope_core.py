from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pytest

import scanner_core.telemetry.names as telemetry_names
from scanner_core.telemetry import (
    CANONICAL_TELEMETRY_EVENT_NAMES,
    OBSERVABILITY_CONTRACT_EVENT_NAMES,
    OBSERVABILITY_TELEMETRY_CONTRACT_ID,
    FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID,
    FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_ID,
    TELEMETRY_EVENT_SCHEMA_VERSION,
    TelemetryEnvelopeError,
    make_telemetry_envelope,
    normalize_telemetry_envelope,
    project_firmware_telemetry_report_events,
    telemetry_canonical_sha256,
    validate_firmware_telemetry_reports,
    validate_telemetry_event_name,
    validate_telemetry_envelope,
    validate_telemetry_records,
)


FIXTURE = Path("tests/fixtures/telemetry/software_only_telemetry_v1.jsonl")
EXPECTED = Path("tests/fixtures/telemetry/telemetry_replay_expected_v1.json")
FIRMWARE_REPORT_VALUES = Path("tests/fixtures/telemetry/firmware_telemetry_report_values_v1.json")


def _event(**overrides):
    event = {
        "schema_id": TELEMETRY_EVENT_SCHEMA_ID,
        "schema_version": TELEMETRY_EVENT_SCHEMA_VERSION,
        "event_name": "acquisition_run_started",
        "source_component": "scanner-pi.acquisition.runner",
        "severity": "info",
        "hardware_outputs_enabled": False,
        "live_hardware_access_used": False,
        "payload": {"dry_run": True},
    }
    event.update(overrides)
    return event


def _records() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _firmware_report_values() -> dict:
    return json.loads(FIRMWARE_REPORT_VALUES.read_text(encoding="utf-8"))


def test_pi_telemetry_fixture_replays_to_experiments_expected_projection() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    replay = validate_telemetry_records(_records())

    assert replay.is_valid
    assert replay.errors == ()
    assert replay.as_dict()["event_names"] == expected["event_names"]
    assert replay.as_dict()["event_counts"] == expected["event_counts"]
    assert replay.as_dict()["run_ids"] == expected["run_ids"]
    assert replay.as_dict()["scan_ids"] == expected["scan_ids"]
    assert replay.as_dict()["frame_ids"] == expected["frame_ids"]
    assert replay.as_dict()["summary"] == expected["summary"]
    assert _sha256(FIXTURE) == expected["source_fixture_sha256"]
    assert expected["contract_id"] == OBSERVABILITY_TELEMETRY_CONTRACT_ID


def test_firmware_telemetry_report_values_project_to_shared_replay_contract() -> None:
    fixture = _firmware_report_values()
    before = {name for name in sys.modules if name == "scanner_firmware" or name.startswith("scanner_firmware.")}

    replay = validate_firmware_telemetry_reports(fixture["reports"])
    projected = project_firmware_telemetry_report_events(fixture["reports"][2])

    after = {name for name in sys.modules if name == "scanner_firmware" or name.startswith("scanner_firmware.")}

    assert replay.is_valid
    assert replay.errors == ()
    assert replay.as_dict()["event_names"] == [
        "controller_event_decoded",
        "readiness_check_result",
        "readiness_check_result",
        "frame_event_received",
        "frame_event_received",
        "z_scheduler_terminal",
        "z_command_enqueued",
        "z_command_accepted",
        "z_command_rejected",
        "z_command_applied",
    ]
    assert replay.as_dict()["event_counts"] == {
        "controller_event_decoded": 1,
        "frame_event_received": 2,
        "readiness_check_result": 2,
        "z_command_accepted": 1,
        "z_command_applied": 1,
        "z_command_enqueued": 1,
        "z_command_rejected": 1,
        "z_scheduler_terminal": 1,
    }
    assert replay.as_dict()["run_ids"] == ["run-fixture-telemetry"]
    assert replay.as_dict()["scan_ids"] == ["scan-telemetry"]
    assert replay.as_dict()["frame_ids"] == [40, 41, 44]
    assert replay.as_dict()["summary"] == {
        "record_count": 10,
        "invalid_record_count": 0,
        "hardware_output_enabled_count": 0,
        "live_hardware_access_count": 0,
        "unsafe_payload_field_count": 0,
        "diagnostic_identity_source_count": 0,
        "unknown_event_name_count": 0,
    }
    assert len(projected) == 7
    assert projected[0]["schema_id"] == TELEMETRY_EVENT_SCHEMA_ID
    assert projected[0]["payload"] == {"report_kind": "dry_run_scheduler_outcome"}
    assert {report["schema_id"] for report in fixture["reports"]} == {FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID}
    assert {
        event["schema_id"]
        for report in fixture["reports"]
        for event in report["events"]
    } == {FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID}
    assert before == after
    assert fixture["contract_id"] == OBSERVABILITY_TELEMETRY_CONTRACT_ID
    assert fixture["source_fixture_sha256"] == {
        "firmware_telemetry_controller_decode_report_v1.json": (
            "5101a076c2ecca8e10a9424958720a5212d39bd251f25d1d0e51747a8b117a94"
        ),
        "firmware_telemetry_readiness_report_v1.json": (
            "5458bf833ccf6e495d4695991315c6a564bc949e2747e772e334b94263dba40d"
        ),
        "firmware_telemetry_dry_run_scheduler_report_v1.json": (
            "2c3d07763a08250a1105df9bbed2d5218044655656b5623e4544a548dc055f1e"
        ),
    }


def test_firmware_telemetry_report_projection_rejects_non_software_only_values() -> None:
    report = copy.deepcopy(_firmware_report_values()["reports"][0])
    report["hardware_outputs_enabled"] = True

    replay = validate_firmware_telemetry_reports([report])

    assert not replay.is_valid
    assert any("$reports[0].hardware_outputs_enabled: expected false" in error for error in replay.errors)
    assert replay.summary["record_count"] == 0

    report = copy.deepcopy(_firmware_report_values()["reports"][0])
    report["events"][0]["live_hardware_access_used"] = True

    replay = validate_firmware_telemetry_reports([report])

    assert not replay.is_valid
    assert any(
        "$reports[0].events[0].live_hardware_access_used: expected false" in error
        for error in replay.errors
    )


def test_firmware_telemetry_report_projection_rejects_shape_drift() -> None:
    report = copy.deepcopy(_firmware_report_values()["reports"][0])
    report["event_count"] = 2

    replay = validate_firmware_telemetry_reports([report])

    assert not replay.is_valid
    assert any("$reports[0].event_count: expected 1, got 2" in error for error in replay.errors)

    report = copy.deepcopy(_firmware_report_values()["reports"][0])
    report["events"][0]["schema_id"] = TELEMETRY_EVENT_SCHEMA_ID

    with pytest.raises(TelemetryEnvelopeError, match="schema_id"):
        project_firmware_telemetry_report_events(report)


def test_observability_contract_event_names_are_accepted() -> None:
    for event_name in OBSERVABILITY_CONTRACT_EVENT_NAMES:
        record = normalize_telemetry_envelope(_event(event_name=event_name))

        assert record["event_name"] == event_name
        assert record["hardware_outputs_enabled"] is False
        assert record["live_hardware_access_used"] is False


def test_preview_event_names_are_observability_contract_events() -> None:
    for event_name in ("preview_frame_published", "preview_frame_dropped"):
        record = normalize_telemetry_envelope(
            _event(
                event_name=event_name,
                source_component="scanner-pi.acquisition.preview",
                severity="debug" if event_name.endswith("published") else "warning",
                payload={"route": "tile", "valid": True},
            )
        )

        assert event_name in OBSERVABILITY_CONTRACT_EVENT_NAMES
        assert record["event_name"] == event_name


def test_canonical_event_name_registry_shape_is_guarded() -> None:
    non_observability_names = {"tile_written", "tile_qa_residual_recorded"}

    assert telemetry_names.CANONICAL_TELEMETRY_EVENT_NAMES is CANONICAL_TELEMETRY_EVENT_NAMES
    assert telemetry_names.OBSERVABILITY_CONTRACT_EVENT_NAMES is OBSERVABILITY_CONTRACT_EVENT_NAMES
    assert telemetry_names.TELEMETRY_EVENT_SCHEMA_ID == TELEMETRY_EVENT_SCHEMA_ID
    assert telemetry_names.TELEMETRY_EVENT_SCHEMA_VERSION == TELEMETRY_EVENT_SCHEMA_VERSION
    assert non_observability_names < CANONICAL_TELEMETRY_EVENT_NAMES
    assert OBSERVABILITY_CONTRACT_EVENT_NAMES == CANONICAL_TELEMETRY_EVENT_NAMES - non_observability_names
    assert all(
        re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", event_name)
        for event_name in CANONICAL_TELEMETRY_EVENT_NAMES
    )


def test_validate_telemetry_event_name_guards_observability_boundary() -> None:
    assert validate_telemetry_event_name("frame_event_received") == "frame_event_received"
    assert (
        validate_telemetry_event_name("tile_written", observability_only=False)
        == "tile_written"
    )

    with pytest.raises(TelemetryEnvelopeError, match="unknown telemetry event_name"):
        validate_telemetry_event_name("tile_written")
    with pytest.raises(TelemetryEnvelopeError, match="non-empty string"):
        validate_telemetry_event_name("")


def test_make_envelope_uses_software_only_defaults() -> None:
    event = make_telemetry_envelope(
        "frame_match_decision",
        source_component="scanner-pi.acquisition.frames.matcher",
        payload={"accepted": True, "reason_code": "frame_id_match"},
        scan_id="scan-a",
        frame_id=9,
    )

    assert event.event_name == "frame_match_decision"
    assert event.hardware_outputs_enabled is False
    assert event.live_hardware_access_used is False
    assert event.as_dict()["frame_id"] == 9


@pytest.mark.parametrize(
    "field",
    [
        "schema_id",
        "schema_version",
        "event_name",
        "source_component",
        "severity",
        "hardware_outputs_enabled",
        "live_hardware_access_used",
        "payload",
    ],
)
def test_envelope_requires_core_fields(field: str) -> None:
    payload = _event()
    del payload[field]

    validation = validate_telemetry_envelope(payload)

    assert not validation.is_valid
    assert any(field in error for error in validation.errors)


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"schema_id": "scanner.telemetry"}, "schema_id"),
        ({"schema_version": "2.0.0"}, "schema_version"),
        ({"event_name": "camera_frame"}, "unknown telemetry event_name"),
        ({"event_name": "tile_written"}, "unknown telemetry event_name"),
        ({"severity": "notice"}, "invalid telemetry severity"),
        ({"payload": ["not", "object"]}, "payload: expected object"),
        ({"payload": {"bad": object()}}, "must be JSON serializable"),
        ({"payload": {"bad": math.nan}}, "must be JSON serializable"),
        ({"hardware_outputs_enabled": True}, "hardware_outputs_enabled"),
        ({"live_hardware_access_used": True}, "live_hardware_access_used"),
        ({"camera_sequence": -1}, "camera_sequence"),
        ({"unknown_field": "nope"}, "unknown telemetry envelope fields"),
    ],
)
def test_envelope_rejects_contract_violations(overrides: dict, match: str) -> None:
    with pytest.raises(TelemetryEnvelopeError, match=match):
        normalize_telemetry_envelope(_event(**overrides))


def test_replay_summary_counts_unsafe_payload_alias_keys_and_values() -> None:
    records = _records()
    records[1]["payload"]["collectorPath"] = "/dev/ttyUSB0"
    records[2]["payload"]["network_url"] = "http://scanner-pi.local:7125"
    records[3]["payload"]["notes"] = ["offline note", "run avrdude now"]

    replay = validate_telemetry_records(records)

    assert not replay.is_valid
    assert any("collectorPath: forbidden telemetry payload field" in error for error in replay.errors)
    assert any("network_url: forbidden telemetry payload field" in error for error in replay.errors)
    assert any("notes[1]: forbidden live hardware/control value" in error for error in replay.errors)
    assert replay.summary["unsafe_payload_field_count"] == 5
    assert replay.summary["invalid_record_count"] == 3


def test_replay_summary_counts_hardware_flags() -> None:
    records = _records()
    records[0]["hardware_outputs_enabled"] = True
    records[1]["live_hardware_access_used"] = True

    replay = validate_telemetry_records(records)

    assert replay.summary["hardware_output_enabled_count"] == 1
    assert replay.summary["live_hardware_access_count"] == 1
    assert replay.summary["invalid_record_count"] == 2


@pytest.mark.parametrize(
    "identity_source",
    [
        "camera_sequence",
        "camera_sensor_timestamp_ns",
        "camera_metadata",
        "host_monotonic_ns",
        "host_wall_time_iso8601",
        "host_clock",
    ],
)
def test_envelope_rejects_identity_inference_from_diagnostic_fields(identity_source: str) -> None:
    payload = _event(
        event_name="camera_frame_received",
        camera_sequence=17,
        camera_sensor_timestamp_ns=1000,
        payload={"frame_identity_source": identity_source},
    )

    validation = validate_telemetry_envelope(payload)

    assert not validation.is_valid
    assert validation.summary["diagnostic_identity_source_count"] == 1
    assert any("diagnostic clock/camera" in error for error in validation.errors)


def test_envelope_allows_diagnostic_camera_fields_when_identity_is_explicit() -> None:
    record = normalize_telemetry_envelope(
        _event(
            event_name="camera_frame_received",
            frame_id=17,
            stripe_id=2,
            stripe_frame_index=4,
            camera_sequence=99,
            camera_sensor_timestamp_ns=100020003000,
            payload={"frame_identity_source": "mcu_frame_event"},
        )
    )

    assert record["frame_id"] == 17
    assert record["camera_sequence"] == 99
    assert record["payload"]["frame_identity_source"] == "mcu_frame_event"


def test_canonical_hash_is_deterministic_for_replay_projection() -> None:
    replay = validate_telemetry_records(_records())
    shuffled = copy.deepcopy(replay.as_dict())
    shuffled["summary"] = dict(reversed(list(shuffled["summary"].items())))

    assert telemetry_canonical_sha256(replay.as_dict()) == telemetry_canonical_sha256(shuffled)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
