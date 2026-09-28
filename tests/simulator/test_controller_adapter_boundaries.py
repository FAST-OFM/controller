from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from scanner_firmware.adapters.controller_adapter.dry_run import (  # noqa: E402
    HARDWARE_OUTPUT_DISABLED_REASON,
    DryRunMotionPositionProvider,
    DryRunOutputBackend,
    DryRunScannerCommandPort,
    PassiveLiveMetadataAdapter,
)
from scanner_firmware.adapters.controller_adapter.interfaces import (  # noqa: E402
    ControllerCapabilities,
    ControllerSnapshot,
    MotionPositionSample,
    OutputRequest,
    PassiveMetadataEventSource,
    ProtocolEvent,
    ProtocolEventSink,
    ScannerCommand,
)


class ControllerAdapterBoundaryTests(unittest.TestCase):
    def test_capabilities_and_snapshots_default_to_software_only_outputs(self):
        capabilities = ControllerCapabilities(controller_kind="simulator")
        snapshot = ControllerSnapshot(adapter_name="dry-run", capabilities=capabilities)

        self.assertFalse(capabilities.hardware_outputs_enabled)
        self.assertFalse(capabilities.supports_output_backend)
        self.assertFalse(snapshot.connected)
        self.assertFalse(snapshot.serial_open)

    def test_adapters_expose_snapshots_without_opening_serial(self):
        adapter = DryRunScannerCommandPort(
            adapter_name="future-klipper",
            advertised_capabilities=ControllerCapabilities(
                controller_kind="klipper",
                protocol_version=1,
                supports_position_snapshots=True,
                supports_frame_events=True,
            ),
        )

        snapshot = adapter.snapshot()
        result = adapter.submit(ScannerCommand(name="start_scan", payload=(("scan_id", "s1"),)))

        self.assertEqual(snapshot.adapter_name, "future-klipper")
        self.assertFalse(snapshot.serial_open)
        self.assertTrue(result.accepted)
        self.assertEqual(adapter.commands, (ScannerCommand(name="start_scan", payload=(("scan_id", "s1"),)),))
        self.assertEqual(adapter.snapshots, (snapshot,))

    def test_dry_run_adapter_negotiates_capability_snapshot_without_outputs(self):
        adapter = DryRunScannerCommandPort(
            adapter_name="negotiated-klipper",
            advertised_capabilities=ControllerCapabilities(
                controller_kind="klipper",
                protocol_version=1,
                supports_position_snapshots=True,
                supports_frame_events=False,
                supports_z_schedule=True,
                supports_output_backend=True,
            ),
            requested_capabilities=ControllerCapabilities(
                controller_kind="klipper",
                protocol_version=2,
                supports_position_snapshots=True,
                supports_frame_events=True,
                supports_z_schedule=True,
                supports_output_backend=True,
                hardware_outputs_enabled=True,
            ),
        )

        snapshot = adapter.snapshot()

        self.assertEqual(snapshot.capabilities.controller_kind, "klipper")
        self.assertEqual(snapshot.capabilities.protocol_version, 1)
        self.assertTrue(snapshot.capabilities.supports_position_snapshots)
        self.assertFalse(snapshot.capabilities.supports_frame_events)
        self.assertTrue(snapshot.capabilities.supports_z_schedule)
        self.assertTrue(snapshot.capabilities.supports_output_backend)
        self.assertFalse(snapshot.capabilities.supports_passive_event_ingest)
        self.assertFalse(snapshot.capabilities.hardware_outputs_enabled)

    def test_snapshot_rejects_serial_or_hardware_enabled_state(self):
        with self.assertRaisesRegex(ValueError, "serial"):
            ControllerSnapshot(
                adapter_name="bad-adapter",
                capabilities=ControllerCapabilities(controller_kind="klipper"),
                serial_open=True,
            )
        with self.assertRaisesRegex(ValueError, "hardware outputs disabled"):
            ControllerSnapshot(
                adapter_name="bad-adapter",
                capabilities=ControllerCapabilities(
                    controller_kind="klipper",
                    hardware_outputs_enabled=True,
                ),
            )

    def test_dry_run_output_backend_rejects_hardware_enable(self):
        backend = DryRunOutputBackend()

        accepted = backend.apply(OutputRequest(channel="frame_gate", active=True))

        self.assertTrue(accepted.accepted)
        self.assertFalse(accepted.hardware_outputs_enabled)
        self.assertEqual(backend.requests, (OutputRequest(channel="frame_gate", active=True),))

        rejected = backend.apply(
            OutputRequest(
                channel="frame_gate",
                active=True,
                hardware_outputs_enabled=True,
            )
        )

        self.assertFalse(rejected.accepted)
        self.assertFalse(rejected.hardware_outputs_enabled)
        self.assertEqual(rejected.reason, HARDWARE_OUTPUT_DISABLED_REASON)

    def test_dry_run_command_port_rejects_hardware_output_commands(self):
        adapter = DryRunScannerCommandPort()

        result = adapter.submit(ScannerCommand(name="arm_outputs"))
        payload_result = adapter.submit(
            ScannerCommand(
                name="start_scan",
                payload=(("scan_id", "s1"), ("hardware_outputs_enabled", True)),
            )
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, HARDWARE_OUTPUT_DISABLED_REASON)
        self.assertFalse(payload_result.accepted)
        self.assertEqual(payload_result.reason, HARDWARE_OUTPUT_DISABLED_REASON)
        self.assertEqual(adapter.commands, ())
        self.assertEqual(adapter.rejections, (result, payload_result))

    def test_simple_providers_record_identical_abstract_position_samples(self):
        samples = (
            MotionPositionSample(0, 5, mcu_time_us=0, sequence=0),
            MotionPositionSample(20, 5, mcu_time_us=1000, sequence=1),
            MotionPositionSample(40, 5, mcu_time_us=2000, sequence=2),
        )
        providers = (
            DryRunMotionPositionProvider(
                samples,
                advertised_capabilities=ControllerCapabilities(
                    controller_kind="klipper",
                    supports_position_snapshots=True,
                ),
            ),
            DryRunMotionPositionProvider(
                samples,
                advertised_capabilities=ControllerCapabilities(
                    controller_kind="grblhal",
                    supports_position_snapshots=True,
                ),
            ),
            DryRunMotionPositionProvider(
                samples,
                advertised_capabilities=ControllerCapabilities(
                    controller_kind="rp2040",
                    supports_position_snapshots=True,
                ),
            ),
        )

        observed = [provider.samples() for provider in providers]

        self.assertEqual(observed, [samples, samples, samples])
        for provider in providers:
            self.assertEqual(provider.read_count, 1)
            self.assertFalse(provider.capabilities.hardware_outputs_enabled)

    def test_position_provider_exposes_negotiated_capability_snapshot(self):
        provider = DryRunMotionPositionProvider(
            (MotionPositionSample(0, 0),),
            adapter_name="dry-position",
            advertised_capabilities=ControllerCapabilities(
                controller_kind="rp2040",
                supports_position_snapshots=True,
                supports_frame_events=False,
            ),
            requested_capabilities=ControllerCapabilities(
                controller_kind="rp2040",
                supports_position_snapshots=True,
                supports_frame_events=True,
                hardware_outputs_enabled=True,
            ),
        )

        snapshot = provider.snapshot()

        self.assertEqual(snapshot.adapter_name, "dry-position")
        self.assertEqual(snapshot.capabilities.controller_kind, "rp2040")
        self.assertTrue(snapshot.capabilities.supports_position_snapshots)
        self.assertFalse(snapshot.capabilities.supports_frame_events)
        self.assertFalse(snapshot.capabilities.hardware_outputs_enabled)
        self.assertEqual(provider.snapshots, (snapshot,))

    def test_protocol_event_sink_records_controller_neutral_events(self):
        sink = RecordingProtocolEventSink()
        event = ProtocolEvent(kind="controller_snapshot", payload=(("adapter", "sim"),))

        sink.emit(event)

        self.assertEqual(sink.events, (event,))

    def test_passive_live_metadata_adapter_has_no_command_or_output_authority(self):
        requested = ControllerCapabilities(
            controller_kind="klipper",
            supports_frame_events=True,
            supports_z_schedule=True,
            supports_output_backend=True,
            supports_passive_event_ingest=True,
            hardware_outputs_enabled=True,
        )
        adapter: PassiveMetadataEventSource = PassiveLiveMetadataAdapter(
            connected=True,
            requested_capabilities=requested,
        )
        event = ProtocolEvent(kind="frame_event", payload=(("frame_id", 10),))

        snapshot = adapter.snapshot()
        assert isinstance(adapter, PassiveLiveMetadataAdapter)
        adapter.ingest(event)

        self.assertEqual(snapshot.adapter_mode, "live_metadata")
        self.assertTrue(snapshot.connected)
        self.assertFalse(snapshot.serial_open)
        self.assertEqual(snapshot.capabilities.controller_kind, "klipper")
        self.assertTrue(snapshot.capabilities.supports_frame_events)
        self.assertTrue(snapshot.capabilities.supports_z_schedule)
        self.assertFalse(snapshot.capabilities.supports_output_backend)
        self.assertTrue(snapshot.capabilities.supports_passive_event_ingest)
        self.assertFalse(snapshot.capabilities.hardware_outputs_enabled)
        self.assertEqual(adapter.events, (event,))
        self.assertFalse(hasattr(adapter, "submit"))
        self.assertFalse(hasattr(adapter, "apply"))

    def test_passive_metadata_adapter_rejects_ingest_without_capability(self):
        adapter = PassiveLiveMetadataAdapter(
            requested_capabilities=ControllerCapabilities(
                controller_kind="klipper",
                supports_passive_event_ingest=False,
            )
        )

        with self.assertRaisesRegex(ValueError, "passive event ingest"):
            adapter.ingest(ProtocolEvent(kind="frame_event"))

    def test_scheduler_and_planner_modules_do_not_import_adapter_packages(self):
        violations = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            if not _is_scheduler_or_planner_path(path):
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if _imports_adapter_package(alias.name):
                            violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    if _imports_adapter_package(node.module):
                        violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

        self.assertEqual(violations, [])


@dataclass
class RecordingProtocolEventSink(ProtocolEventSink):
    _events: list[ProtocolEvent] | None = None

    @property
    def events(self) -> tuple[ProtocolEvent, ...]:
        return tuple(self._events or ())

    def emit(self, event: ProtocolEvent) -> None:
        if self._events is None:
            self._events = []
        self._events.append(event)


def _is_scheduler_or_planner_path(path: Path) -> bool:
    parts = path.relative_to(SRC_ROOT).parts
    path_text = "/".join(parts)
    return (
        "scheduler" in path_text
        or "planner" in path_text
        or path_text.startswith("scanner_sync/dry_run_service.py")
    )


def _imports_adapter_package(module_name: str) -> bool:
    return module_name.startswith("scanner_firmware.adapters.") or module_name.startswith(
        "klipper_adapter"
    )


if __name__ == "__main__":
    unittest.main()
