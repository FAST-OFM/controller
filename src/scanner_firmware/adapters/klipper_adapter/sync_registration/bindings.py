"""Scanner-sync Klipper command and response bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProtocolEventType = Literal[
    "FRAME_EVENT",
    "SCHEDULER_TERMINAL",
    "Z_SCHEDULED",
    "Z_APPLIED",
    "Z_REJECTED",
    "TIMED_OUTPUT_SEQUENCE_STATUS",
]

SCANNER_SYNC_CONFIG_COMMAND = (
    "config_scanner_sync oid={oid} protocol_version={version} "
    "hardware_outputs_enabled={hardware_outputs_enabled}"
)
SCANNER_SYNC_CONFIG_FORMAT = (
    "config_scanner_sync oid=%c protocol_version=%c hardware_outputs_enabled=%c"
)
SUPPORTED_PROTOCOL_VERSIONS = (1,)

SCANNER_SYNC_START_COMMAND = "scanner_sync_start oid=%c next_frame_id=%u"
SCANNER_SYNC_STOP_COMMAND = "scanner_sync_stop oid=%c reason=%c"
SCANNER_SYNC_SCHEDULE_Z_COMMAND = (
    "scanner_sync_schedule_z oid=%c seq=%u stripe_id=%u target_kind=%c "
    "target_value=%i z_target_nm=%i"
)
SCANNER_SYNC_ARM_AF_WINDOW_COMMAND = (
    "scanner_sync_arm_af_window oid=%c seq=%u stripe_id=%u frame_id=%u "
    "stripe_frame_index=%u position_axis=%c trigger_position_count=%i "
    "pattern_id=%u settle_us=%u xvs_trigger_pulse_us=%u exposure_hold_us=%u"
)
SCANNER_SYNC_FIRE_AF_WINDOW_NOW_COMMAND = (
    "scanner_sync_fire_af_window_now oid=%c seq=%u stripe_id=%u frame_id=%u "
    "stripe_frame_index=%u position_axis=%c event_position_count=%i "
    "pattern_id=%u settle_us=%u xvs_trigger_pulse_us=%u exposure_hold_us=%u"
)
SCANNER_SYNC_RUN_STATIONARY_AF_TEST_COMMAND = (
    "scanner_sync_run_stationary_af_test oid=%c seq=%u stripe_id=%u "
    "first_frame_id=%u frame_count=%u frame_period_us=%u position_axis=%c "
    "event_position_count=%i pattern_id=%u settle_us=%u "
    "xvs_trigger_pulse_us=%u exposure_hold_us=%u"
)
SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND = (
    "scanner_sync_run_timed_output_sequence oid=%c seq=%u stripe_id=%u seq_id=%u "
    "mode=%c start_condition=%c start_position_count=%i repeat_count=%u "
    "frame_id_base=%i pattern_id=%u safe_output_mask=%c safe_output_values=%c "
    "idle_output_mask=%c idle_output_values=%c step_count=%u steps_crc32=%u "
    "encoded_steps=%*s"
)

SCANNER_SYNC_FRAME_EVENT_RESPONSE = (
    "scanner_sync_frame_event oid=%c frame_id=%u stripe_id=%u stripe_frame_index=%u "
    "pattern_id=%u position_axis=%c event_position=%i x_count=%i y_count=%i "
    "z_count=%i mcu_time_us=%u status=%c flags=%u"
)
SCANNER_SYNC_SCHEDULER_TERMINAL_RESPONSE = (
    "scanner_sync_scheduler_terminal oid=%c stripe_id=%u status=%c reason=%c "
    "emitted_frame_count=%u expected_frame_count=%u last_frame_id=%i "
    "next_frame_id=%u next_stripe_frame_index=%u mcu_time_us=%u"
)
SCANNER_SYNC_Z_SCHEDULED_RESPONSE = (
    "scanner_sync_z_scheduled oid=%c seq=%u stripe_id=%u status=%c"
)
SCANNER_SYNC_Z_APPLIED_RESPONSE = (
    "scanner_sync_z_applied oid=%c seq=%u frame_id=%u z_cmd_count=%i status=%c"
)
SCANNER_SYNC_Z_REJECTED_RESPONSE = (
    "scanner_sync_z_rejected oid=%c seq=%u reason=%c status=%c"
)
SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE_STATUS_RESPONSE = (
    "scanner_sync_timed_output_sequence_status oid=%c seq=%u stripe_id=%u "
    "seq_id=%u status=%c reason=%c repeat_index=%u step_index=%u mcu_time_us=%u"
)


@dataclass(frozen=True)
class ScannerSyncCommandBinding:
    name: str
    msgformat: str
    required: bool = True


@dataclass(frozen=True)
class ScannerSyncResponseBinding:
    protocol_event_type: ProtocolEventType
    msgformat: str


@dataclass(frozen=True)
class ScannerSyncRegistrationSnapshot:
    oid: int
    protocol_version: int
    hardware_outputs_enabled: bool
    timed_output_sequence_enabled: bool
    config_command: str
    command_bindings: tuple[ScannerSyncCommandBinding, ...]
    response_bindings: tuple[ScannerSyncResponseBinding, ...]


COMMAND_BINDINGS: tuple[ScannerSyncCommandBinding, ...] = (
    ScannerSyncCommandBinding("start", SCANNER_SYNC_START_COMMAND),
    ScannerSyncCommandBinding("stop", SCANNER_SYNC_STOP_COMMAND),
    ScannerSyncCommandBinding("schedule_z", SCANNER_SYNC_SCHEDULE_Z_COMMAND),
    ScannerSyncCommandBinding("arm_af_window", SCANNER_SYNC_ARM_AF_WINDOW_COMMAND),
    ScannerSyncCommandBinding(
        "fire_af_window_now",
        SCANNER_SYNC_FIRE_AF_WINDOW_NOW_COMMAND,
    ),
    ScannerSyncCommandBinding(
        "run_stationary_af_test",
        SCANNER_SYNC_RUN_STATIONARY_AF_TEST_COMMAND,
    ),
)

EXPERIMENTAL_COMMAND_BINDINGS: tuple[ScannerSyncCommandBinding, ...] = (
    ScannerSyncCommandBinding(
        "run_timed_output_sequence",
        SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
        required=False,
    ),
)

EXPERIMENTAL_RESPONSE_BINDINGS: tuple[ScannerSyncResponseBinding, ...] = (
    ScannerSyncResponseBinding(
        "TIMED_OUTPUT_SEQUENCE_STATUS",
        SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE_STATUS_RESPONSE,
    ),
)

RESPONSE_BINDINGS: tuple[ScannerSyncResponseBinding, ...] = (
    ScannerSyncResponseBinding("FRAME_EVENT", SCANNER_SYNC_FRAME_EVENT_RESPONSE),
    ScannerSyncResponseBinding(
        "SCHEDULER_TERMINAL",
        SCANNER_SYNC_SCHEDULER_TERMINAL_RESPONSE,
    ),
    ScannerSyncResponseBinding("Z_SCHEDULED", SCANNER_SYNC_Z_SCHEDULED_RESPONSE),
    ScannerSyncResponseBinding("Z_APPLIED", SCANNER_SYNC_Z_APPLIED_RESPONSE),
    ScannerSyncResponseBinding("Z_REJECTED", SCANNER_SYNC_Z_REJECTED_RESPONSE),
)

RESPONSE_EVENT_BY_MSGFORMAT = {
    binding.msgformat: binding.protocol_event_type for binding in RESPONSE_BINDINGS
}
