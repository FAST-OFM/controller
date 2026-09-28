"""Canonical telemetry event names and schema identifiers."""

from __future__ import annotations


OBSERVABILITY_TELEMETRY_CONTRACT_ID = "observability_telemetry_event_v1"
TELEMETRY_EVENT_SCHEMA_ID = "scanner_pi.telemetry_event"
TELEMETRY_EVENT_SCHEMA_VERSION = "1.0.0"
FIRMWARE_TELEMETRY_EVENT_SCHEMA_ID = "firmware_telemetry_event_v1"
FIRMWARE_TELEMETRY_REPORT_SCHEMA_ID = "firmware_telemetry_report_v1"

CANONICAL_TELEMETRY_EVENT_NAMES = frozenset(
    {
        "acquisition_run_started",
        "acquisition_run_stopped",
        "controller_event_decoded",
        "camera_frame_received",
        "frame_event_received",
        "frame_match_decision",
        "frame_route_decision",
        "queue_backpressure",
        "tile_written",
        "tile_qa_residual_recorded",
        "calibration_bundle_resolved",
        "calibration_check_failed",
        "autofocus_sample_validated",
        "autofocus_metric_computed",
        "tissue_mask_decision",
        "predictive_z_prediction",
        "preview_frame_published",
        "preview_frame_dropped",
        "z_command_enqueued",
        "z_command_accepted",
        "z_command_rejected",
        "z_command_applied",
        "z_scheduler_terminal",
        "brightness_setpoint_requested",
        "brightness_setpoint_applied",
        "led_gate_metadata_recorded",
        "illumination_safety_blocked",
        "readiness_check_result",
        "safety_gate_blocked",
        "operator_approval_recorded",
        "experiment_artifact_recorded",
        "evidence_ledger_written",
    }
)
OBSERVABILITY_CONTRACT_EVENT_NAMES = frozenset(
    name
    for name in CANONICAL_TELEMETRY_EVENT_NAMES
    if name not in {"tile_written", "tile_qa_residual_recorded"}
)


def _validate_telemetry_event_name(
    event_name: object,
    *,
    observability_only: bool = True,
) -> str:
    """Return a canonical telemetry event name, otherwise raise ValueError."""

    if not isinstance(event_name, str) or not event_name:
        raise ValueError("telemetry event_name must be a non-empty string")
    allowed_names = (
        OBSERVABILITY_CONTRACT_EVENT_NAMES
        if observability_only
        else CANONICAL_TELEMETRY_EVENT_NAMES
    )
    if event_name not in allowed_names:
        raise ValueError(f"unknown telemetry event_name: {event_name!r}")
    return event_name
