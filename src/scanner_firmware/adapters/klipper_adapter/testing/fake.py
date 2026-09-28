"""Dry-run Klipper MCU fake for scanner-sync adapter tests.

The fake models Klipper's registration-time MCU API surface without importing
Klipper or exposing serial/hardware paths.  Command handles are inert and raise
if test code attempts to send through them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from scanner_firmware.adapters.klipper_adapter.model import (
    ConfigCallback,
    KlipperApiCallRecord,
    KlipperCommandLookupRecord,
    KlipperConfigCommandRecord,
    KlipperSerialResponseRecord,
    SerialResponseCallback,
)


class KlipperAdapterError(ValueError):
    """Base error for local Klipper adapter contract violations."""


class KlipperRegistrationOrderError(KlipperAdapterError):
    """Raised when registration-time calls are made out of order."""


class KlipperHardwareAccessError(RuntimeError):
    """Raised when dry-run code attempts serial or hardware access."""


@dataclass(frozen=True)
class DryRunKlipperCommandQueue:
    queue_id: int


@dataclass(frozen=True)
class DryRunKlipperCommand:
    msgformat: str
    queue: DryRunKlipperCommandQueue | None
    command_tag: int

    def send(self, data: Any = (), minclock: int = 0, reqclock: int = 0) -> None:
        raise KlipperHardwareAccessError("dry-run Klipper command send is disabled")

    def send_wait_ack(self, data: Any = (), minclock: int = 0, reqclock: int = 0) -> None:
        raise KlipperHardwareAccessError("dry-run Klipper command send_wait_ack is disabled")

    def get_command_tag(self) -> int:
        return self.command_tag


@dataclass(frozen=True)
class _RegisteredSerialResponse:
    callback: SerialResponseCallback
    msgformat: str
    oid: int | None


class DryRunKlipperMcu:
    """Hardware-free MCU API fake for future Klipper adapter code.

    The fake enforces a conservative scanner-sync registration order:
    allocate object ids and queues, register config callbacks, then run config
    callbacks and perform config commands, command lookups, and serial response
    registration from inside those callbacks.
    """

    def __init__(self, *, available_commands: Iterable[str] | None = None):
        self._available_commands = None
        if available_commands is not None:
            self._available_commands = frozenset(available_commands)
        self._phase = "collecting"
        self._callbacks: list[ConfigCallback] = []
        self._next_oid = 1
        self._next_queue_id = 1
        self._next_command_tag = 1
        self._config_commands: list[KlipperConfigCommandRecord] = []
        self._command_lookups: list[KlipperCommandLookupRecord] = []
        self._serial_responses: list[KlipperSerialResponseRecord] = []
        self._registered_serial_responses: list[_RegisteredSerialResponse] = []
        self._api_calls: list[KlipperApiCallRecord] = []

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def config_commands(self) -> tuple[KlipperConfigCommandRecord, ...]:
        return tuple(self._config_commands)

    @property
    def command_lookups(self) -> tuple[KlipperCommandLookupRecord, ...]:
        return tuple(self._command_lookups)

    @property
    def serial_responses(self) -> tuple[KlipperSerialResponseRecord, ...]:
        return tuple(self._serial_responses)

    @property
    def api_calls(self) -> tuple[KlipperApiCallRecord, ...]:
        return tuple(self._api_calls)

    def create_oid(self) -> int:
        self._require_phase("collecting", "create_oid")
        oid = self._next_oid
        self._next_oid += 1
        self._record("create_oid", str(oid))
        return oid

    def alloc_command_queue(self) -> DryRunKlipperCommandQueue:
        self._require_phase("collecting", "alloc_command_queue")
        queue = DryRunKlipperCommandQueue(self._next_queue_id)
        self._next_queue_id += 1
        self._record("alloc_command_queue", str(queue.queue_id))
        return queue

    def register_config_callback(self, callback: ConfigCallback) -> None:
        self._require_phase("collecting", "register_config_callback")
        if callback in self._callbacks:
            raise KlipperRegistrationOrderError("config callback already registered")
        self._callbacks.append(callback)
        self._record("register_config_callback", self._callback_name(callback))

    def run_config_callbacks(self) -> None:
        self._require_phase("collecting", "run_config_callbacks")
        self._phase = "building_config"
        try:
            for index, callback in enumerate(tuple(self._callbacks)):
                self._record("run_config_callback", f"{index}:{self._callback_name(callback)}")
                callback()
        except Exception:
            self._phase = "failed"
            raise
        self._phase = "configured"

    def add_config_cmd(
        self,
        cmd: str,
        is_init: bool = False,
        on_restart: bool = False,
    ) -> None:
        self._require_phase("building_config", "add_config_cmd")
        if not cmd:
            raise KlipperAdapterError("config command must not be empty")
        self._config_commands.append(KlipperConfigCommandRecord(cmd, is_init, on_restart))
        self._record("add_config_cmd", cmd)

    def lookup_command(
        self,
        msgformat: str,
        cq: DryRunKlipperCommandQueue | None = None,
    ) -> DryRunKlipperCommand:
        self._require_phase("building_config", "lookup_command")
        available = self._is_command_available(msgformat)
        if not available:
            self._command_lookups.append(
                KlipperCommandLookupRecord(msgformat, self._queue_id(cq), True, False)
            )
            raise KlipperAdapterError(f"required Klipper command is unavailable: {msgformat}")

        command = DryRunKlipperCommand(msgformat, cq, self._next_command_tag)
        self._next_command_tag += 1
        self._command_lookups.append(
            KlipperCommandLookupRecord(
                msgformat,
                self._queue_id(cq),
                True,
                True,
                command.command_tag,
            )
        )
        self._record("lookup_command", msgformat)
        return command

    def try_lookup_command(self, msgformat: str) -> bool:
        self._require_phase("building_config", "try_lookup_command")
        available = self._is_command_available(msgformat)
        self._command_lookups.append(
            KlipperCommandLookupRecord(msgformat, None, False, available)
        )
        self._record("try_lookup_command", f"{msgformat}:{available}")
        return available

    def register_serial_response(
        self,
        callback: SerialResponseCallback,
        msgformat: str,
        oid: int | None = None,
    ) -> None:
        self._require_phase("building_config", "register_serial_response")
        if not msgformat:
            raise KlipperAdapterError("serial response format must not be empty")
        self._serial_responses.append(
            KlipperSerialResponseRecord(msgformat, oid, self._callback_name(callback))
        )
        self._registered_serial_responses.append(
            _RegisteredSerialResponse(callback=callback, msgformat=msgformat, oid=oid)
        )
        self._record("register_serial_response", msgformat)

    def emit_serial_response(
        self,
        msgformat: str,
        params: dict[str, Any],
        *,
        oid: int | None = None,
    ) -> None:
        """Inject a decoded serial response into registered dry-run callbacks."""

        if self._phase != "configured":
            raise KlipperRegistrationOrderError(
                "emit_serial_response is only allowed after config callbacks complete"
            )
        for response in self._registered_serial_responses:
            if response.msgformat == msgformat and response.oid == oid:
                response.callback(dict(params))
                self._record("emit_serial_response", msgformat)
                return
        raise KlipperAdapterError(f"serial response is not registered: {msgformat}")

    def get_serial(self) -> None:
        raise KlipperHardwareAccessError("dry-run Klipper fake does not expose serial")

    def raw_send(self, *args: Any, **kwargs: Any) -> None:
        raise KlipperHardwareAccessError("dry-run Klipper fake does not send raw serial data")

    def _is_command_available(self, msgformat: str) -> bool:
        return self._available_commands is None or msgformat in self._available_commands

    def _queue_id(self, queue: DryRunKlipperCommandQueue | None) -> int | None:
        if queue is None:
            return None
        if not isinstance(queue, DryRunKlipperCommandQueue):
            raise KlipperAdapterError("command queue was not allocated by this dry-run fake")
        return queue.queue_id

    def _require_phase(self, expected: str, api_name: str) -> None:
        if self._phase != expected:
            raise KlipperRegistrationOrderError(
                f"{api_name} is only allowed during {expected}; current phase is {self._phase}"
            )

    def _record(self, name: str, detail: str) -> None:
        self._api_calls.append(KlipperApiCallRecord(name, self._phase, detail))

    def _callback_name(self, callback: Any) -> str:
        return getattr(callback, "__qualname__", getattr(callback, "__name__", repr(callback)))
