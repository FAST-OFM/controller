"""Scanner-sync Klipper registration lifecycle."""

from __future__ import annotations

from typing import Callable

from scanner_firmware.adapters.klipper_adapter.model import (
    KlipperCommand,
    KlipperCommandQueue,
    KlipperMcu,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (
    COMMAND_BINDINGS,
    EXPERIMENTAL_COMMAND_BINDINGS,
    EXPERIMENTAL_RESPONSE_BINDINGS,
    RESPONSE_BINDINGS,
    SCANNER_SYNC_CONFIG_COMMAND,
    SUPPORTED_PROTOCOL_VERSIONS,
    ProtocolEventType,
    ScannerSyncCommandBinding,
    ScannerSyncRegistrationSnapshot,
)


ScannerSyncResponseHandler = Callable[[ProtocolEventType, dict[str, object]], None]


class ScannerSyncKlipperRegistration:
    """Register scanner-sync command and response shapes against a Klipper-like MCU.

    The object mirrors the future Klipper extra lifecycle: allocate resources
    during construction, then bind config commands and message formats inside
    Klipper's config callback phase.
    """

    def __init__(
        self,
        mcu: KlipperMcu,
        *,
        protocol_version: int = 1,
        hardware_outputs_enabled: bool = False,
        enable_timed_output_sequence: bool = False,
        response_handler: ScannerSyncResponseHandler | None = None,
    ):
        if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ValueError(f"unsupported protocol_version: {protocol_version}")
        if hardware_outputs_enabled:
            raise ValueError(
                "hardware_outputs_enabled is not supported by the metadata-only "
                "dry-run registration"
            )
        self._mcu = mcu
        self._response_handler = response_handler
        self.protocol_version = protocol_version
        self.hardware_outputs_enabled = hardware_outputs_enabled
        self.enable_timed_output_sequence = enable_timed_output_sequence
        self.oid = mcu.create_oid()
        self.command_queue = mcu.alloc_command_queue()
        self.commands: dict[str, KlipperCommand] = {}
        mcu.register_config_callback(self._build_config)

    @property
    def snapshot(self) -> ScannerSyncRegistrationSnapshot:
        command_bindings = COMMAND_BINDINGS
        response_bindings = RESPONSE_BINDINGS
        if self.enable_timed_output_sequence:
            command_bindings = command_bindings + EXPERIMENTAL_COMMAND_BINDINGS
            response_bindings = response_bindings + EXPERIMENTAL_RESPONSE_BINDINGS
        return ScannerSyncRegistrationSnapshot(
            oid=self.oid,
            protocol_version=self.protocol_version,
            hardware_outputs_enabled=self.hardware_outputs_enabled,
            timed_output_sequence_enabled=self.enable_timed_output_sequence,
            config_command=SCANNER_SYNC_CONFIG_COMMAND.format(
                oid=self.oid,
                version=self.protocol_version,
                hardware_outputs_enabled=int(self.hardware_outputs_enabled),
            ),
            command_bindings=command_bindings,
            response_bindings=response_bindings,
        )

    def _build_config(self) -> None:
        snapshot = self.snapshot
        self._mcu.add_config_cmd(snapshot.config_command, is_init=True)
        for binding in snapshot.command_bindings:
            self.commands[binding.name] = self._lookup_required_command(
                binding,
                self.command_queue,
            )
        for binding in snapshot.response_bindings:
            self._mcu.register_serial_response(
                self._make_response_callback(binding.protocol_event_type),
                binding.msgformat,
                self.oid,
            )

    def _lookup_required_command(
        self,
        binding: ScannerSyncCommandBinding,
        queue: KlipperCommandQueue,
    ) -> KlipperCommand:
        return self._mcu.lookup_command(binding.msgformat, cq=queue)

    def _make_response_callback(
        self,
        event_type: ProtocolEventType,
    ) -> Callable[[dict[str, object]], None]:
        def _handle(params: dict[str, object]) -> None:
            self._handle_scanner_response(event_type, params)

        return _handle

    def _handle_scanner_response(
        self,
        event_type: ProtocolEventType,
        params: dict[str, object],
    ) -> None:
        if self._response_handler is not None:
            self._response_handler(event_type, params)
            return
        raise RuntimeError(
            "scanner-sync response dispatch is not implemented in the dry-run "
            f"registration plan: {event_type}"
        )
