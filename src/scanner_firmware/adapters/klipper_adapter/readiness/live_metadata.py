"""Live Klipper metadata readiness model.

This module models whether a live Klipper setup is ready for scanner-sync
metadata integration. It is deliberately passive: it does not import Klipper,
open serial ports, send commands, toggle pins, command motion, trigger cameras,
drive LEDs or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    COMMAND_BINDINGS,
    RESPONSE_BINDINGS,
    SUPPORTED_PROTOCOL_VERSIONS,
)


LiveMetadataStage = Literal[
    "not_installed",
    "host_extra_loaded_disabled",
    "host_extra_enabled_without_mcu",
    "host_extra_enabled_without_responses",
    "unsafe_hardware_outputs",
    "unsupported_protocol",
    "ready_to_enable",
]
ReadinessStatus = Literal["blocked", "safe_disabled", "ready"]


@dataclass(frozen=True)
class LiveKlipperScannerSyncObservation:
    """Observed live Klipper state for scanner-sync readiness evaluation."""

    host_extra_present: bool
    config_section_present: bool
    config_enable: bool
    mcu_connected: bool
    mcu_config_format_present: bool = True
    mcu_command_formats: frozenset[str] = frozenset()
    registered_response_formats: frozenset[str] = frozenset()
    protocol_version: int = 1
    metadata_only_mode: bool = True
    hardware_outputs_enabled: bool = False
    config_safety_fields_present: bool = True
    configured_output_keys: tuple[str, ...] = ()
    response_dispatch_available: bool = False

    def __post_init__(self) -> None:
        if self.protocol_version < 1:
            raise ValueError("protocol_version must be >= 1")


@dataclass(frozen=True)
class LiveMetadataReadiness:
    """Computed readiness result for live scanner-sync metadata work."""

    stage: LiveMetadataStage
    status: ReadinessStatus
    blockers: tuple[str, ...]
    missing_command_formats: tuple[str, ...]
    missing_response_formats: tuple[str, ...]

    @property
    def can_enable_scanner_sync(self) -> bool:
        """Return whether `[scanner_sync] enable: true` is software-ready."""

        return self.status == "ready"


EXPECTED_COMMAND_FORMATS = tuple(binding.msgformat for binding in COMMAND_BINDINGS)
EXPECTED_RESPONSE_FORMATS = tuple(binding.msgformat for binding in RESPONSE_BINDINGS)
def evaluate_live_metadata_readiness(
    observation: LiveKlipperScannerSyncObservation,
) -> LiveMetadataReadiness:
    """Evaluate a passive live Klipper scanner-sync observation."""

    missing_commands = tuple(
        msgformat
        for msgformat in EXPECTED_COMMAND_FORMATS
        if msgformat not in observation.mcu_command_formats
    )
    missing_responses = tuple(
        msgformat
        for msgformat in EXPECTED_RESPONSE_FORMATS
        if msgformat not in observation.registered_response_formats
    )
    blockers: list[str] = []

    if not observation.mcu_connected:
        blockers.append("mcu_not_connected")
    if not observation.host_extra_present:
        blockers.append("host_extra_missing")
    if not observation.config_section_present:
        blockers.append("config_section_missing")

    if blockers:
        return LiveMetadataReadiness(
            stage="not_installed",
            status="blocked",
            blockers=tuple(blockers),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if observation.protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        return LiveMetadataReadiness(
            stage="unsupported_protocol",
            status="blocked",
            blockers=("unsupported_protocol_version",),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if not observation.config_enable:
        return LiveMetadataReadiness(
            stage="host_extra_loaded_disabled",
            status="safe_disabled",
            blockers=(),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if not observation.config_safety_fields_present:
        return LiveMetadataReadiness(
            stage="unsafe_hardware_outputs",
            status="blocked",
            blockers=("scanner_sync_safety_fields_missing",),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if observation.hardware_outputs_enabled or not observation.metadata_only_mode:
        return LiveMetadataReadiness(
            stage="unsafe_hardware_outputs",
            status="blocked",
            blockers=("metadata_only_mode_required", "hardware_outputs_must_be_disabled"),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if observation.configured_output_keys:
        return LiveMetadataReadiness(
            stage="unsafe_hardware_outputs",
            status="blocked",
            blockers=("scanner_sync_output_pins_configured",),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if not observation.mcu_config_format_present:
        return LiveMetadataReadiness(
            stage="host_extra_enabled_without_mcu",
            status="blocked",
            blockers=("scanner_sync_mcu_config_format_missing",),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if missing_commands:
        return LiveMetadataReadiness(
            stage="host_extra_enabled_without_mcu",
            status="blocked",
            blockers=("scanner_sync_mcu_commands_missing",),
            missing_command_formats=missing_commands,
            missing_response_formats=missing_responses,
        )

    if missing_responses or not observation.response_dispatch_available:
        blockers = []
        if missing_responses:
            blockers.append("scanner_sync_response_formats_missing")
        if not observation.response_dispatch_available:
            blockers.append("scanner_sync_response_dispatch_missing")
        return LiveMetadataReadiness(
            stage="host_extra_enabled_without_responses",
            status="blocked",
            blockers=tuple(blockers),
            missing_command_formats=(),
            missing_response_formats=missing_responses,
        )

    return LiveMetadataReadiness(
        stage="ready_to_enable",
        status="ready",
        blockers=(),
        missing_command_formats=(),
        missing_response_formats=missing_responses,
    )
