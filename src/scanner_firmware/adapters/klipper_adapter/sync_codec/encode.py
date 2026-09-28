"""Encoding helpers for host-to-MCU scanner-sync commands."""

from __future__ import annotations

from zlib import crc32

from scanner_firmware.adapters.klipper_adapter.sync_codec.tables import (
    AXIS_CODES,
    TARGET_KIND_CODES,
    TERMINAL_REASON_CODES,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (
    EncodedKlipperCommand,
    ScannerSyncCodecError,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    SCANNER_SYNC_ARM_AF_WINDOW_COMMAND,
    SCANNER_SYNC_FIRE_AF_WINDOW_NOW_COMMAND,
    SCANNER_SYNC_RUN_STATIONARY_AF_TEST_COMMAND,
    SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
    SCANNER_SYNC_START_COMMAND,
    SCANNER_SYNC_STOP_COMMAND,
    SCANNER_SYNC_SCHEDULE_Z_COMMAND,
)
from scanner_core.scan_units import micrometers_to_nanometers
from scanner_firmware.foundation.protocol.events import (
    ARM_AF_WINDOW_COMMAND,
    FIRE_AF_WINDOW_NOW_COMMAND,
    RUN_STATIONARY_AF_TEST_COMMAND,
    RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
    SCHEDULE_Z_COMMAND,
    START_COMMAND,
    STOP_COMMAND,
    ArmAfWindowCommand,
    FireAfWindowNowCommand,
    RunStationaryAfTestCommand,
    RunTimedOutputSequenceCommand,
    ScannerSyncCommand,
    ScannerSyncStartCommand,
    ScannerSyncStopCommand,
    ScheduleZCommand,
    TimedOutputSequenceStep,
)


TERMINAL_REASON_WIRE_CODES = {
    reason: code
    for code, reason in TERMINAL_REASON_CODES.items()
    if isinstance(code, int)
}
TIMED_OUTPUT_SEQUENCE_MODE_WIRE_CODES = {
    "diagnostic_immediate": 0,
    "position_armed": 1,
}
TIMED_OUTPUT_SEQUENCE_START_CONDITION_WIRE_CODES = {
    "immediate": 0,
    "position_count": 1,
}


def encode_scanner_sync_command(
    *,
    oid: int,
    command: ScannerSyncCommand,
) -> EncodedKlipperCommand:
    """Encode a typed scanner-sync command without sending it."""

    if isinstance(command, ScannerSyncStartCommand):
        return encode_start_command(oid=oid, command=command)
    if isinstance(command, ScannerSyncStopCommand):
        return encode_stop_command(oid=oid, command=command)
    if isinstance(command, ScheduleZCommand):
        return encode_schedule_z_command(oid=oid, command=command)
    if isinstance(command, ArmAfWindowCommand):
        return encode_arm_af_window_command(oid=oid, command=command)
    if isinstance(command, FireAfWindowNowCommand):
        return encode_fire_af_window_now_command(oid=oid, command=command)
    if isinstance(command, RunStationaryAfTestCommand):
        return encode_run_stationary_af_test_command(oid=oid, command=command)
    if isinstance(command, RunTimedOutputSequenceCommand):
        return encode_run_timed_output_sequence_command(oid=oid, command=command)
    raise ScannerSyncCodecError("unsupported scanner-sync command DTO")


def encode_start_command(
    *,
    oid: int,
    command: ScannerSyncStartCommand,
) -> EncodedKlipperCommand:
    """Encode a project ``scanner_sync_start`` command for the local binding."""

    return EncodedKlipperCommand(
        name=START_COMMAND,
        msgformat=SCANNER_SYNC_START_COMMAND,
        args=(oid, command.next_frame_id),
    )


def encode_stop_command(
    *,
    oid: int,
    command: ScannerSyncStopCommand,
) -> EncodedKlipperCommand:
    """Encode a project ``scanner_sync_stop`` command for the local binding."""

    try:
        reason_code = TERMINAL_REASON_WIRE_CODES[command.reason]
    except KeyError as exc:
        raise ScannerSyncCodecError(
            f"unsupported scanner_sync_stop reason: {command.reason!r}"
        ) from exc
    return EncodedKlipperCommand(
        name=STOP_COMMAND,
        msgformat=SCANNER_SYNC_STOP_COMMAND,
        args=(oid, reason_code),
    )


def encode_schedule_z_command(
    *,
    oid: int,
    command: ScheduleZCommand,
) -> EncodedKlipperCommand:
    """Encode a project ``scanner_sync_schedule_z`` command for the local binding."""

    if (
        (
            command.apply_at_position_count is not None
            or command.apply_at_position_um is not None
        )
        and command.apply_at_frame_id is not None
    ):
        raise ScannerSyncCodecError(
            "scanner_sync_schedule_z command cannot target both frame and position"
        )

    if command.apply_at_position_count is not None:
        target_kind = TARGET_KIND_CODES["position"]
        target_value = command.apply_at_position_count
    elif command.apply_at_frame_id is not None:
        target_kind = TARGET_KIND_CODES["frame"]
        target_value = command.apply_at_frame_id
    else:
        raise ScannerSyncCodecError("scanner_sync_schedule_z command has no target")

    z_target_nm = micrometers_to_nanometers(command.z_target_um, name="z_target_um")
    return EncodedKlipperCommand(
        name=SCHEDULE_Z_COMMAND,
        msgformat=SCANNER_SYNC_SCHEDULE_Z_COMMAND,
        args=(
            oid,
            command.seq,
            command.stripe_id,
            target_kind,
            target_value,
            z_target_nm,
        ),
    )


def encode_arm_af_window_command(
    *,
    oid: int,
    command: ArmAfWindowCommand,
) -> EncodedKlipperCommand:
    """Encode a position-indexed autofocus window arm command."""

    return EncodedKlipperCommand(
        name=ARM_AF_WINDOW_COMMAND,
        msgformat=SCANNER_SYNC_ARM_AF_WINDOW_COMMAND,
        args=(
            oid,
            command.seq,
            command.stripe_id,
            command.frame_id,
            command.stripe_frame_index,
            _axis_wire_code(command.position_axis),
            command.trigger_position_count,
            command.pattern_id,
            command.settle_us,
            command.xvs_trigger_pulse_us,
            command.exposure_hold_us,
        ),
    )


def encode_fire_af_window_now_command(
    *,
    oid: int,
    command: FireAfWindowNowCommand,
) -> EncodedKlipperCommand:
    """Encode a diagnostic immediate autofocus window command."""

    if not command.diagnostic_only:
        raise ScannerSyncCodecError(
            "scanner_sync_fire_af_window_now is diagnostic-only"
        )
    return EncodedKlipperCommand(
        name=FIRE_AF_WINDOW_NOW_COMMAND,
        msgformat=SCANNER_SYNC_FIRE_AF_WINDOW_NOW_COMMAND,
        args=(
            oid,
            command.seq,
            command.stripe_id,
            command.frame_id,
            command.stripe_frame_index,
            _axis_wire_code(command.position_axis),
            command.event_position_count,
            command.pattern_id,
            command.settle_us,
            command.xvs_trigger_pulse_us,
            command.exposure_hold_us,
        ),
    )


def encode_run_stationary_af_test_command(
    *,
    oid: int,
    command: RunStationaryAfTestCommand,
) -> EncodedKlipperCommand:
    """Encode a diagnostic stationary AF timing test command."""

    if not command.diagnostic_only:
        raise ScannerSyncCodecError(
            "scanner_sync_run_stationary_af_test is diagnostic-only"
        )
    return EncodedKlipperCommand(
        name=RUN_STATIONARY_AF_TEST_COMMAND,
        msgformat=SCANNER_SYNC_RUN_STATIONARY_AF_TEST_COMMAND,
        args=(
            oid,
            command.seq,
            command.stripe_id,
            command.first_frame_id,
            command.frame_count,
            command.frame_period_us,
            _axis_wire_code(command.position_axis),
            command.event_position_count,
            command.pattern_id,
            command.settle_us,
            command.xvs_trigger_pulse_us,
            command.exposure_hold_us,
        ),
    )


def encode_run_timed_output_sequence_command(
    *,
    oid: int,
    command: RunTimedOutputSequenceCommand,
) -> EncodedKlipperCommand:
    """Encode a compact generic timed output sequence without sending it."""

    if not command.diagnostic_only:
        raise ScannerSyncCodecError(
            "scanner_sync_run_timed_output_sequence is diagnostic-only"
        )
    encoded_steps = encode_timed_output_sequence_steps(command.steps)
    return EncodedKlipperCommand(
        name=RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
        msgformat=SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
        args=(
            oid,
            command.seq,
            command.stripe_id,
            command.seq_id,
            _timed_output_sequence_mode_wire_code(command.mode),
            _timed_output_sequence_start_condition_wire_code(command.start_condition),
            _optional_count_wire_value(command.start_position_count),
            command.repeat_count,
            _optional_count_wire_value(command.frame_id_base),
            command.pattern_id,
            command.safe_output_mask,
            command.safe_output_values,
            command.idle_output_mask,
            command.idle_output_values,
            len(command.steps),
            crc32(encoded_steps) & 0xFFFFFFFF,
            encoded_steps,
        ),
    )


def encode_timed_output_sequence_steps(
    steps: tuple[TimedOutputSequenceStep, ...],
) -> bytes:
    """Encode sequence steps as 8-byte little-endian MCU payload records."""

    payload = bytearray()
    for step in steps:
        payload.append(step.output_mask)
        payload.append(step.output_values)
        payload.extend(step.delay_us.to_bytes(4, byteorder="little", signed=False))
        payload.extend(step.event_flags.to_bytes(2, byteorder="little", signed=False))
    return bytes(payload)


def _timed_output_sequence_mode_wire_code(mode: str) -> int:
    try:
        return TIMED_OUTPUT_SEQUENCE_MODE_WIRE_CODES[mode]
    except KeyError as exc:
        raise ScannerSyncCodecError(f"unsupported timed output sequence mode: {mode!r}") from exc


def _timed_output_sequence_start_condition_wire_code(start_condition: str) -> int:
    try:
        return TIMED_OUTPUT_SEQUENCE_START_CONDITION_WIRE_CODES[start_condition]
    except KeyError as exc:
        raise ScannerSyncCodecError(
            f"unsupported timed output sequence start_condition: {start_condition!r}"
        ) from exc


def _optional_count_wire_value(value: int | None) -> int:
    return -1 if value is None else value


def _axis_wire_code(axis: str) -> str:
    try:
        encoded = AXIS_CODES[axis]
    except KeyError as exc:
        raise ScannerSyncCodecError(f"unsupported position_axis: {axis!r}") from exc
    if not isinstance(encoded, str):
        raise ScannerSyncCodecError(f"unsupported position_axis wire code: {encoded!r}")
    return encoded
