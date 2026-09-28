"""Local Klipper-facing adapter contracts.

This module intentionally does not import Klipper.  It captures only the small
MCU API surface a future scanner-sync adapter is expected to use while building
configuration in Klipper's host process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


ConfigCallback = Callable[[], None]
SerialResponseCallback = Callable[[dict[str, Any]], None]


class KlipperCommandQueue(Protocol):
    """Opaque Klipper command queue handle."""


class KlipperCommand(Protocol):
    """Opaque Klipper command handle returned by lookup_command."""

    def send(self, data: Any = (), minclock: int = 0, reqclock: int = 0) -> None:
        """Send a command to the MCU."""

    def send_wait_ack(self, data: Any = (), minclock: int = 0, reqclock: int = 0) -> None:
        """Send a command and wait for an MCU ack."""

    def get_command_tag(self) -> int:
        """Return Klipper's numeric command tag."""


class KlipperMcu(Protocol):
    """Read-only local contract for the Klipper MCU object used by adapters."""

    def create_oid(self) -> int:
        """Allocate an MCU object id for config construction."""

    def register_config_callback(self, callback: ConfigCallback) -> None:
        """Register a callback invoked when Klipper builds MCU config."""

    def add_config_cmd(
        self,
        cmd: str,
        is_init: bool = False,
        on_restart: bool = False,
    ) -> None:
        """Add a config command to Klipper's pending MCU config."""

    def lookup_command(
        self,
        msgformat: str,
        cq: KlipperCommandQueue | None = None,
    ) -> KlipperCommand:
        """Look up a required MCU command by Klipper message format."""

    def try_lookup_command(self, msgformat: str) -> bool:
        """Return whether an optional MCU command exists."""

    def register_serial_response(
        self,
        callback: SerialResponseCallback,
        msgformat: str,
        oid: int | None = None,
    ) -> None:
        """Register a decoded MCU response callback."""

    def alloc_command_queue(self) -> KlipperCommandQueue:
        """Allocate a Klipper command queue for related adapter commands."""


@dataclass(frozen=True)
class KlipperConfigCommandRecord:
    cmd: str
    is_init: bool = False
    on_restart: bool = False


@dataclass(frozen=True)
class KlipperCommandLookupRecord:
    msgformat: str
    queue_id: int | None
    required: bool
    available: bool
    command_tag: int | None = None


@dataclass(frozen=True)
class KlipperSerialResponseRecord:
    msgformat: str
    oid: int | None
    callback_name: str


@dataclass(frozen=True)
class KlipperApiCallRecord:
    name: str
    phase: str
    detail: str
