"""Dry-run controller adapter implementations.

These adapters satisfy the controller boundary protocols without importing
Klipper, opening serial ports, sending commands, toggling GPIO, moving motors,
triggering cameras, driving LEDs or enabling hardware outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scanner_firmware.adapters.controller_adapter.interfaces import (
    ControllerCapabilities,
    ControllerKind,
    ControllerSnapshot,
    MotionPositionSample,
    OutputRequest,
    OutputResult,
    ProtocolEvent,
    ScannerCommand,
    ScannerCommandResult,
    payload_dict,
)


HARDWARE_OUTPUT_DISABLED_REASON = "hardware outputs disabled"


def negotiate_capabilities(
    *,
    advertised: ControllerCapabilities,
    requested: ControllerCapabilities | None = None,
) -> ControllerCapabilities:
    """Return a passive dry-run capability snapshot.

    Capability booleans are intersected when a request is supplied. Hardware
    output enablement is always forced off at this dry-run boundary, even when
    the caller requests or the advertised backend reports output support.
    """

    if requested is None:
        return ControllerCapabilities(
            controller_kind=advertised.controller_kind,
            protocol_version=advertised.protocol_version,
            supports_position_snapshots=advertised.supports_position_snapshots,
            supports_frame_events=advertised.supports_frame_events,
            supports_z_schedule=advertised.supports_z_schedule,
            supports_output_backend=advertised.supports_output_backend,
            supports_passive_event_ingest=advertised.supports_passive_event_ingest,
            hardware_outputs_enabled=False,
        )

    return ControllerCapabilities(
        controller_kind=_negotiate_controller_kind(
            requested.controller_kind,
            advertised.controller_kind,
        ),
        protocol_version=_negotiate_protocol_version(
            requested.protocol_version,
            advertised.protocol_version,
        ),
        supports_position_snapshots=(
            requested.supports_position_snapshots and advertised.supports_position_snapshots
        ),
        supports_frame_events=requested.supports_frame_events
        and advertised.supports_frame_events,
        supports_z_schedule=requested.supports_z_schedule
        and advertised.supports_z_schedule,
        supports_output_backend=requested.supports_output_backend
        and advertised.supports_output_backend,
        supports_passive_event_ingest=requested.supports_passive_event_ingest
        and advertised.supports_passive_event_ingest,
        hardware_outputs_enabled=False,
    )


@dataclass
class DryRunScannerCommandPort:
    """In-memory scanner command port for software-only boundary tests."""

    adapter_name: str = "controller-dry-run"
    advertised_capabilities: ControllerCapabilities = ControllerCapabilities(
        controller_kind="simulator",
        supports_position_snapshots=True,
        supports_frame_events=True,
        supports_z_schedule=True,
        supports_output_backend=True,
    )
    requested_capabilities: ControllerCapabilities | None = None
    _commands: list[ScannerCommand] = field(default_factory=list, init=False)
    _snapshots: list[ControllerSnapshot] = field(default_factory=list, init=False)
    _rejections: list[ScannerCommandResult] = field(default_factory=list, init=False)

    @property
    def capabilities(self) -> ControllerCapabilities:
        return negotiate_capabilities(
            advertised=self.advertised_capabilities,
            requested=self.requested_capabilities,
        )

    @property
    def commands(self) -> tuple[ScannerCommand, ...]:
        return tuple(self._commands)

    @property
    def snapshots(self) -> tuple[ControllerSnapshot, ...]:
        return tuple(self._snapshots)

    @property
    def rejections(self) -> tuple[ScannerCommandResult, ...]:
        return tuple(self._rejections)

    def snapshot(self) -> ControllerSnapshot:
        snapshot = ControllerSnapshot(
            adapter_name=self.adapter_name,
            capabilities=self.capabilities,
            adapter_mode="dry_run",
            detail="dry-run capability negotiation",
        )
        self._snapshots.append(snapshot)
        return snapshot

    def submit(self, command: ScannerCommand) -> ScannerCommandResult:
        if _requests_hardware_outputs(command):
            result = ScannerCommandResult(
                accepted=False,
                reason=HARDWARE_OUTPUT_DISABLED_REASON,
                records=(("command", command.name),),
            )
            self._rejections.append(result)
            return result

        self._commands.append(command)
        return ScannerCommandResult(
            accepted=True,
            records=(("command", command.name), ("dry_run", True)),
        )


@dataclass
class DryRunMotionPositionProvider:
    """Finite commanded-position provider for simulator/controller conformance."""

    _samples: tuple[MotionPositionSample, ...]
    adapter_name: str = "controller-position-dry-run"
    advertised_capabilities: ControllerCapabilities = ControllerCapabilities(
        controller_kind="simulator",
        supports_position_snapshots=True,
    )
    requested_capabilities: ControllerCapabilities | None = None
    read_count: int = 0
    _snapshots: list[ControllerSnapshot] = field(default_factory=list, init=False)

    @property
    def capabilities(self) -> ControllerCapabilities:
        return negotiate_capabilities(
            advertised=self.advertised_capabilities,
            requested=self.requested_capabilities,
        )

    @property
    def snapshots(self) -> tuple[ControllerSnapshot, ...]:
        return tuple(self._snapshots)

    def snapshot(self) -> ControllerSnapshot:
        snapshot = ControllerSnapshot(
            adapter_name=self.adapter_name,
            capabilities=self.capabilities,
            adapter_mode="dry_run",
            detail="dry-run position capability negotiation",
        )
        self._snapshots.append(snapshot)
        return snapshot

    def samples(self) -> tuple[MotionPositionSample, ...]:
        self.read_count += 1
        return self._samples


@dataclass
class DryRunOutputBackend:
    """In-memory output backend that refuses hardware-affecting state."""

    capabilities: ControllerCapabilities = ControllerCapabilities(
        controller_kind="simulator",
        supports_output_backend=True,
    )
    _requests: list[OutputRequest] = field(default_factory=list, init=False)

    @property
    def requests(self) -> tuple[OutputRequest, ...]:
        return tuple(self._requests)

    def apply(self, request: OutputRequest) -> OutputResult:
        if request.hardware_outputs_enabled:
            return OutputResult(
                accepted=False,
                reason=HARDWARE_OUTPUT_DISABLED_REASON,
            )
        self._requests.append(request)
        return OutputResult(accepted=True)


@dataclass
class PassiveLiveMetadataAdapter:
    """In-memory passive metadata adapter for live-capture boundary tests.

    This adapter records already-decoded controller-neutral metadata events. It
    cannot submit commands, open serial, toggle outputs or claim hardware
    approval.
    """

    adapter_name: str = "passive-live-metadata"
    advertised_capabilities: ControllerCapabilities = ControllerCapabilities(
        controller_kind="klipper",
        supports_frame_events=True,
        supports_z_schedule=True,
        supports_passive_event_ingest=True,
    )
    requested_capabilities: ControllerCapabilities | None = None
    connected: bool = False
    _events: list[ProtocolEvent] = field(default_factory=list, init=False)
    _snapshots: list[ControllerSnapshot] = field(default_factory=list, init=False)

    @property
    def capabilities(self) -> ControllerCapabilities:
        return negotiate_capabilities(
            advertised=self.advertised_capabilities,
            requested=self.requested_capabilities,
        )

    @property
    def events(self) -> tuple[ProtocolEvent, ...]:
        return tuple(self._events)

    @property
    def snapshots(self) -> tuple[ControllerSnapshot, ...]:
        return tuple(self._snapshots)

    def snapshot(self) -> ControllerSnapshot:
        snapshot = ControllerSnapshot(
            adapter_name=self.adapter_name,
            capabilities=self.capabilities,
            adapter_mode="live_metadata",
            connected=self.connected,
            serial_open=False,
            detail="passive live metadata boundary",
        )
        self._snapshots.append(snapshot)
        return snapshot

    def ingest(self, event: ProtocolEvent) -> None:
        if not self.capabilities.supports_passive_event_ingest:
            raise ValueError("passive event ingest capability is not available")
        self._events.append(event)


def _requests_hardware_outputs(command: ScannerCommand) -> bool:
    if command.name == "arm_outputs":
        return True
    payload = payload_dict(command.payload)
    return payload.get("hardware_outputs_enabled") is True


def _negotiate_controller_kind(
    requested: ControllerKind,
    advertised: ControllerKind,
) -> ControllerKind:
    if requested == advertised:
        return requested
    if requested == "unknown":
        return advertised
    if advertised == "unknown":
        return requested
    return "unknown"


def _negotiate_protocol_version(
    requested: int | None,
    advertised: int | None,
) -> int | None:
    if requested is None:
        return advertised
    if advertised is None:
        return requested
    return min(requested, advertised)
