"""Pytest marker classification for simulator tests."""

from __future__ import annotations

from pathlib import Path

import pytest


SIMULATOR_TEST_ROOT = Path(__file__).resolve().parent


ARCHITECTURE_TESTS = frozenset(
    (
        "test_architecture_guardrails.py",
        "test_component_architecture_boundaries.py",
        "test_controller_adapter_boundaries.py",
        "test_firmware_repo_boundary_guardrail.py",
        "test_klipper_patch_artifact_consistency.py",
        "test_pytest_marker_classification.py",
    )
)
CONTRACT_TESTS = frozenset(
    (
        "test_firmware_component_interfaces.py",
        "test_firmware_config_split.py",
        "test_firmware_telemetry_report_producers.py",
        "test_board_profile_capability_summary.py",
        "test_frame_event_protocol_adapter.py",
        "test_frame_event_replay_fixture.py",
        "test_homing_readiness_contract.py",
        "test_led_timing_protocol_fixture.py",
        "test_klipper_adapter_fake.py",
        "test_klipper_config_parser.py",
        "test_klipper_dictionary_capabilities.py",
        "test_klipper_event_stream.py",
        "test_live_mks_af_window_snapshot.py",
        "test_io_alias_registry.py",
        "test_klipper_live_metadata_readiness.py",
        "test_klipper_live_output_gate.py",
        "test_klipper_mks_flash_gate.py",
        "test_klipper_passive_readiness_report.py",
        "test_klipper_passive_metadata_backend.py",
        "test_klipper_protocol_dispatcher.py",
        "test_klipper_readiness_cli.py",
        "test_klipper_scanner_sync_codec.py",
        "test_klipper_scanner_sync_command_boundary.py",
        "test_klipper_scanner_sync_registration.py",
        "test_klipper_stage_b_review_validator.py",
        "test_platform_readiness_result.py",
        "test_platform_config_loader.py",
        "test_platform_config_model.py",
        "test_protocol_events.py",
        "test_scan_geometry_dry_run_fixture.py",
        "test_scanner_firmware_namespace.py",
        "test_startup_blocker_report.py",
        "test_startup_readiness_model.py",
        "test_software_to_hardware_readiness_doc.py",
        "test_stage_b_scanner_sync_metadata_fixture.py",
        "test_v1_manual_centered_bringup_gate.py",
    )
)
INTEGRATION_TESTS = frozenset(
    (
        "test_firmware_base_comparison_report.py",
        "test_firmware_base_dry_run_adapters.py",
        "test_firmware_base_gate_replay_evidence.py",
        "test_firmware_base_phase0_fixture.py",
        "test_klipper_scanner_sync_dry_run_harness.py",
        "test_dry_run_pipeline.py",
        "test_scanner_sync_backend.py",
        "test_scanner_sync_dry_run_service.py",
        "test_scanner_sync_dry_run_session.py",
    )
)
UNIT_TESTS = frozenset(
    (
        "test_board_profile_kinematics.py",
        "test_board_profile_validator.py",
        "test_atomic_illumination_window.py",
        "test_calibration_model.py",
        "test_coordinate_source_fusion.py",
        "test_coordinate_source_model.py",
        "test_dry_run_scheduler.py",
        "test_frame_event_publisher.py",
        "test_homing_simulator.py",
        "test_led_calibration_workflow.py",
        "test_led_timing_diagnostics.py",
        "test_led_scheduler_model.py",
        "test_led_timing_model.py",
        "test_scan_execution_state_machine.py",
        "test_scan_math_geometry.py",
        "test_scan_plan.py",
        "test_scan_preflight_model.py",
        "test_stationary_af_timing_test.py",
        "test_timed_output_sequence_simulator.py",
        "test_trigger_scheduler_stress_fixtures.py",
        "test_z_predictive_planner.py",
        "test_z_scheduler_model.py",
    )
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath)).resolve()
        if path.parent != SIMULATOR_TEST_ROOT:
            continue
        filename = path.name
        markers = _markers_for_file(filename)
        for marker in markers:
            item.add_marker(getattr(pytest.mark, marker))


def _markers_for_file(filename: str) -> tuple[str, ...]:
    markers: list[str] = []
    if filename in ARCHITECTURE_TESTS:
        markers.append("architecture")
    if filename in CONTRACT_TESTS:
        markers.append("contract")
    if filename in INTEGRATION_TESTS:
        markers.append("integration")
    if filename in UNIT_TESTS:
        markers.append("unit")
    if len(markers) != 1:
        raise ValueError(
            f"{filename} must be classified with exactly one simulator pytest marker; "
            f"got {markers or 'none'}"
        )
    return tuple(markers)
