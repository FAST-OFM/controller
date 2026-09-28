"""Telemetry envelope field groups used by validation and projection."""

from __future__ import annotations


TELEMETRY_SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})

REQUIRED_ENVELOPE_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "event_name",
        "source_component",
        "severity",
        "hardware_outputs_enabled",
        "live_hardware_access_used",
        "payload",
    }
)
IDENTITY_FIELDS = frozenset(
    {
        "run_id",
        "scan_id",
        "frame_id",
        "stripe_id",
        "stripe_frame_index",
        "command_id",
        "calibration_id",
    }
)
DIAGNOSTIC_FIELDS = frozenset(
    {
        "host_monotonic_ns",
        "host_wall_time_iso8601",
        "mcu_time_us",
        "camera_sensor_timestamp_ns",
        "camera_sequence",
    }
)
TELEMETRY_REPLAY_SUMMARY_KEYS = (
    "record_count",
    "invalid_record_count",
    "hardware_output_enabled_count",
    "live_hardware_access_count",
    "unsafe_payload_field_count",
    "diagnostic_identity_source_count",
    "unknown_event_name_count",
)

REQUIRED_FIRMWARE_REPORT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "report_id",
        "generated_at",
        "source_component",
        "hardware_outputs_enabled",
        "live_hardware_access_used",
        "event_count",
        "event_names",
        "events",
    }
)

NON_NEGATIVE_INT_FIELDS = frozenset(
    {
        "frame_id",
        "stripe_id",
        "stripe_frame_index",
        "host_monotonic_ns",
        "mcu_time_us",
        "camera_sensor_timestamp_ns",
        "camera_sequence",
    }
)
STRING_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "event_name",
        "source_component",
        "severity",
        "run_id",
        "scan_id",
        "command_id",
        "calibration_id",
        "host_wall_time_iso8601",
    }
)
DIAGNOSTIC_IDENTITY_SOURCES = DIAGNOSTIC_FIELDS | {
    "clock",
    "host_clock",
    "host_time",
    "wall_time",
    "camera_metadata",
    "camera_timestamp",
}
IDENTITY_SOURCE_FIELDS = frozenset(
    {
        "identity_source",
        "frame_identity_source",
        "scan_identity_source",
        "coordinate_identity_source",
    }
)
FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "device_path",
        "firmware_flash",
        "gcode",
        "gpio",
        "gpio_pin",
        "hardware_command",
        "led_output",
        "move_z_now",
        "network_endpoint",
        "serial_port",
    }
)
FORBIDDEN_PAYLOAD_TOKENS = frozenset(
    {
        "avrdude",
        "bossac",
        "command",
        "device",
        "dfu",
        "endpoint",
        "firmware",
        "flash",
        "gcode",
        "gpio",
        "klipper",
        "led",
        "motor",
        "motion",
        "network",
        "openocd",
        "path",
        "picotool",
        "serial",
        "socket",
        "tty",
    }
)
UNSAFE_PAYLOAD_BOOLEAN_FIELDS = frozenset(
    {
        "contains_hardware_commands",
        "hardware_outputs_enabled",
        "live_hardware_access_used",
        "may_access_gpio",
        "may_command_motion",
        "may_emit_led_output",
        "may_flash_firmware",
        "may_move_stage",
        "may_open_camera",
        "may_open_network",
        "may_open_serial_port",
    }
)
