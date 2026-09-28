"""Software-only controller adapter boundary.

This module defines the controller-facing contracts used by scheduler, planner
and simulator code. It does not import Klipper, grblHAL, RP2040 SDK modules,
open serial ports, send controller commands, toggle outputs, trigger cameras,
drive LEDs, move motors or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


ControllerKind = Literal["klipper", "grblhal", "rp2040", "simulator", "unknown"]
ControllerAdapterMode = Literal["dry_run", "live_metadata", "unknown"]
ControllerCommandName = Literal["start_scan", "stop_scan", "schedule_z", "arm_outputs"]
ProtocolEventKind = Literal[
    "frame_event",
    "scheduler_terminal",
    "z_scheduled",
    "z_rejected",
    "z_applied",
    "controller_snapshot",
]


@dataclass(frozen=True)
class ControllerCapabilities:
    """Passive capability snapshot for a controller adapter.

    Hardware outputs are disabled by default. A future live adapter may report
    discovered capabilities here, but this value object does not authorize
    hardware-affecting behavior by itself.
    """

    controller_kind: ControllerKind = "unknown"
    protocol_version: int | None = None
    supports_position_snapshots: bool = False
    supports_frame_events: bool = False
    supports_z_schedule: bool = False
    supports_output_backend: bool = False
    supports_passive_event_ingest: bool = False
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        if self.controller_kind not in ("klipper", "grblhal", "rp2040", "simulator", "unknown"):
            raise ValueError("unsupported controller_kind")
        if self.protocol_version is not None:
            _require_non_negative_int("protocol_version", self.protocol_version)
        _require_bool("supports_position_snapshots", self.supports_position_snapshots)
        _require_bool("supports_frame_events", self.supports_frame_events)
        _require_bool("supports_z_schedule", self.supports_z_schedule)
        _require_bool("supports_output_backend", self.supports_output_backend)
        _require_bool("supports_passive_event_ingest", self.supports_passive_event_ingest)
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)


@dataclass(frozen=True)
class ControllerSnapshot:
    """Adapter status captured without opening serial or touching hardware."""

    adapter_name: str
    capabilities: ControllerCapabilities
    adapter_mode: ControllerAdapterMode = "unknown"
    connected: bool = False
    serial_open: bool = False
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("adapter_name", self.adapter_name)
        if self.adapter_mode not in ("dry_run", "live_metadata", "unknown"):
            raise ValueError("unsupported controller adapter_mode")
        _require_bool("connected", self.connected)
        _require_bool("serial_open", self.serial_open)
        if self.serial_open:
            raise ValueError("controller snapshots must not open serial")
        if self.capabilities.hardware_outputs_enabled:
            raise ValueError("controller snapshots must keep hardware outputs disabled")
        if self.detail is not None:
            _require_non_empty("detail", self.detail)


@dataclass(frozen=True)
class MotionPositionSample:
    """Abstract commanded-position sample shared by all controller adapters."""

    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int = 0
    mcu_time_us: int = 0
    sequence: int | None = None

    def __post_init__(self) -> None:
        _require_int("x_step_commanded", self.x_step_commanded)
        _require_int("y_step_commanded", self.y_step_commanded)
        _require_int("z_step_commanded", self.z_step_commanded)
        _require_non_negative_int("mcu_time_us", self.mcu_time_us)
        if self.sequence is not None:
            _require_non_negative_int("sequence", self.sequence)


@dataclass(frozen=True)
class ScannerCommand:
    """Software command intent before a controller-specific adapter encodes it."""

    name: ControllerCommandName
    payload: tuple[tuple[str, int | float | str | bool | None], ...] = ()
    dry_run: bool = True

    def __post_init__(self) -> None:
        if self.name not in ("start_scan", "stop_scan", "schedule_z", "arm_outputs"):
            raise ValueError("unsupported scanner command")
        _require_bool("dry_run", self.dry_run)
        if not self.dry_run:
            raise ValueError("scanner commands are software-only and must be dry_run")
        for key, _value in self.payload:
            _require_non_empty("payload key", key)


@dataclass(frozen=True)
class ScannerCommandResult:
    """Software-only command result returned by a command port."""

    accepted: bool
    reason: str | None = None
    records: tuple[tuple[str, int | float | str | bool | None], ...] = ()

    def __post_init__(self) -> None:
        _require_bool("accepted", self.accepted)
        if self.reason is not None:
            _require_non_empty("reason", self.reason)
        for key, _value in self.records:
            _require_non_empty("record key", key)


@dataclass(frozen=True)
class ProtocolEvent:
    """Controller-neutral protocol event emitted by adapter backends."""

    kind: ProtocolEventKind
    payload: tuple[tuple[str, int | float | str | bool | None], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in (
            "frame_event",
            "scheduler_terminal",
            "z_scheduled",
            "z_rejected",
            "z_applied",
            "controller_snapshot",
        ):
            raise ValueError("unsupported protocol event kind")
        for key, _value in self.payload:
            _require_non_empty("payload key", key)


@dataclass(frozen=True)
class OutputRequest:
    """Logical output request before an output backend applies policy."""

    channel: str
    active: bool
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("channel", self.channel)
        _require_bool("active", self.active)
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)


@dataclass(frozen=True)
class OutputResult:
    accepted: bool
    hardware_outputs_enabled: bool = False
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_bool("accepted", self.accepted)
        _require_bool("hardware_outputs_enabled", self.hardware_outputs_enabled)
        if self.hardware_outputs_enabled:
            raise ValueError("controller adapter output results must default hardware outputs off")
        if self.reason is not None:
            _require_non_empty("reason", self.reason)


class MotionPositionProvider(Protocol):
    """Provide abstract commanded-position samples without controller coupling."""

    capabilities: ControllerCapabilities

    def samples(self) -> tuple[MotionPositionSample, ...]:
        """Return a finite software-only snapshot of commanded positions."""


class ScannerCommandPort(Protocol):
    """Accept scanner command intents behind controller-specific adapters."""

    capabilities: ControllerCapabilities

    def snapshot(self) -> ControllerSnapshot:
        """Return passive adapter status without opening serial."""

    def submit(self, command: ScannerCommand) -> ScannerCommandResult:
        """Submit a software-only command intent."""


class PassiveMetadataEventSource(Protocol):
    """Expose already-captured metadata without command or hardware authority."""

    capabilities: ControllerCapabilities

    def snapshot(self) -> ControllerSnapshot:
        """Return passive metadata adapter status without opening serial."""

    @property
    def events(self) -> tuple[ProtocolEvent, ...]:
        """Return controller-neutral metadata events already ingested."""


class ProtocolEventSink(Protocol):
    """Receive controller-neutral protocol events from an adapter."""

    def emit(self, event: ProtocolEvent) -> None:
        """Record or dispatch one protocol event."""


class OutputBackend(Protocol):
    """Apply logical output requests behind an explicit software safety gate."""

    capabilities: ControllerCapabilities

    def apply(self, request: OutputRequest) -> OutputResult:
        """Apply a logical output request or reject hardware-affecting state."""


def _require_bool(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a bool")


def _require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")


def _require_non_negative_int(name: str, value: object) -> None:
    _require_int(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def payload_dict(payload: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
    """Convert a validated tuple payload to a dictionary for tests/adapters."""

    return dict(payload)
