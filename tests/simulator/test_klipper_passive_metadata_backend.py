import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (  # noqa: E402
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (  # noqa: E402
    EXPECTED_COMMAND_FORMATS,
    EXPECTED_RESPONSE_FORMATS,
    LiveKlipperScannerSyncObservation,
)
from scanner_firmware.adapters.scanner_sync.live_metadata_backend import (  # noqa: E402
    PassiveLiveMetadataBackend,
    PassiveLiveMetadataBackendError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext  # noqa: E402
from scanner_firmware.foundation.protocol.events import FrameEventRecord  # noqa: E402


class KlipperPassiveMetadataBackendTests(unittest.TestCase):
    def test_ready_backend_ingests_and_validates_metadata_sequence(self):
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
            ),
        )

        first = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=10, stripe_frame_index=0, event_position=20),
        )
        second = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=11, stripe_frame_index=1, event_position=40),
        )
        terminal = backend.ingest_response(
            "SCHEDULER_TERMINAL",
            {
                "stripe_id": 1,
                "status": 0,
                "reason": 0,
                "emitted_frame_count": 2,
                "expected_frame_count": 3,
                "last_frame_id": 11,
                "next_frame_id": 12,
                "next_stripe_frame_index": 2,
                "mcu_time_us": 300,
            },
        )
        validation = backend.validate_sequence()

        self.assertEqual(first.type, "FRAME_EVENT")
        self.assertEqual(second.pattern, "AF_RED_GREEN")
        self.assertEqual(terminal.type, "SCHEDULER_TERMINAL")
        self.assertEqual(validation.frame_count, 2)
        self.assertEqual(validation.terminal_count, 1)
        self.assertEqual(backend.status.record_count, 3)
        self.assertEqual(backend.status.last_event_type, "SCHEDULER_TERMINAL")
        self.assertTrue(backend.status.validate_before_forward)
        self.assertFalse(any(record.hardware_outputs_enabled for record in backend.records))

    def test_backend_validates_before_storing_invalid_live_sequence(self):
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            ),
        )
        first = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=10, stripe_frame_index=0, event_position=20),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "frame_id"):
            backend.ingest_response(
                "FRAME_EVENT",
                _frame_params(frame_id=12, stripe_frame_index=1, event_position=40),
            )

        self.assertEqual(backend.records, (first,))
        self.assertEqual(backend.status.record_count, 1)

    def test_backend_rejects_frame_after_terminal_before_forwarding(self):
        sink = []
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            ),
            sink=sink,
        )
        first = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=10, stripe_frame_index=0, event_position=20),
        )
        terminal = backend.ingest_response(
            "SCHEDULER_TERMINAL",
            {
                "stripe_id": 1,
                "status": 0,
                "reason": 0,
                "emitted_frame_count": 1,
                "expected_frame_count": 2,
                "last_frame_id": 10,
                "next_frame_id": 11,
                "next_stripe_frame_index": 1,
                "mcu_time_us": 300,
            },
        )

        with self.assertRaisesRegex(
            ScannerSyncEventStreamError,
            "follows SCHEDULER_TERMINAL",
        ):
            backend.ingest_response(
                "FRAME_EVENT",
                _frame_params(frame_id=11, stripe_frame_index=1, event_position=40),
            )

        self.assertEqual(backend.records, (first, terminal))
        self.assertEqual(sink, [first, terminal])

    def test_backend_rejects_bad_z_ordering_before_forwarding(self):
        sink = []
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            ),
            sink=sink,
        )
        first = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=10, stripe_frame_index=0, event_position=20),
        )
        second = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=11, stripe_frame_index=1, event_position=40),
        )
        scheduled = backend.ingest_response(
            "Z_SCHEDULED",
            {"seq": 7, "stripe_id": 1, "status": 0},
        )

        with self.assertRaisesRegex(
            ScannerSyncEventStreamError,
            "not after Z_SCHEDULED",
        ):
            backend.ingest_response(
                "Z_APPLIED",
                {
                    "seq": 7,
                    "stripe_id": 1,
                    "apply_target_kind": "position",
                    "apply_at_position_count": 30,
                    "position": 30,
                    "frame_id": 12,
                    "z_cmd_count": 123,
                    "status": 0,
                },
            )

        self.assertEqual(backend.records, (first, second, scheduled))
        self.assertEqual(sink, [first, second, scheduled])

    def test_backend_rejects_scan_mismatch_before_forwarding(self):
        sink = []
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            ),
            sink=sink,
        )
        first = backend.ingest_response(
            "FRAME_EVENT",
            _frame_params(frame_id=10, stripe_frame_index=0, event_position=20),
        )
        mismatched = _frame_record(
            scan_id="scan-b",
            frame_id=11,
            stripe_frame_index=1,
            event_position=40,
        )

        with (
            patch(
                "scanner_firmware.adapters.klipper_adapter.event_streaming.dispatch."
                "decode_scanner_sync_response",
                return_value=mismatched,
            ),
            self.assertRaisesRegex(ScannerSyncEventStreamError, "scan_id mismatch"),
        ):
            backend.ingest_response(
                "FRAME_EVENT",
                _frame_params(frame_id=11, stripe_frame_index=1, event_position=40),
            )

        self.assertEqual(backend.records, (first,))
        self.assertEqual(sink, [first])

    def test_backend_rejects_hardware_output_record_before_forwarding(self):
        sink = []
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            ),
            sink=sink,
        )
        hardware_record = _frame_record(
            scan_id="scan-a",
            frame_id=10,
            stripe_frame_index=0,
            event_position=20,
            hardware_outputs_enabled=True,
        )

        with (
            patch(
                "scanner_firmware.adapters.klipper_adapter.event_streaming.dispatch."
                "decode_scanner_sync_response",
                return_value=hardware_record,
            ),
            self.assertRaisesRegex(ScannerSyncEventStreamError, "hardware outputs"),
        ):
            backend.ingest_response(
                "FRAME_EVENT",
                _frame_params(frame_id=10, stripe_frame_index=0, event_position=20),
            )

        self.assertEqual(backend.records, ())
        self.assertEqual(sink, [])

    def test_backend_rejects_non_ready_live_observation(self):
        with self.assertRaisesRegex(PassiveLiveMetadataBackendError, "ready"):
            PassiveLiveMetadataBackend(
                observation=LiveKlipperScannerSyncObservation(
                    host_extra_present=True,
                    config_section_present=True,
                    config_enable=False,
                    mcu_connected=True,
                ),
                context=ScannerSyncDecodeContext(scan_id="scan-a"),
            )

    def test_backend_has_no_command_or_hardware_control_surface(self):
        backend = PassiveLiveMetadataBackend(
            observation=_ready_observation(),
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
        )

        for forbidden_name in (
            "send",
            "send_wait_ack",
            "start_stripe",
            "start_stripe_from_source",
            "toggle_gpio",
            "flash",
        ):
            self.assertFalse(hasattr(backend, forbidden_name), forbidden_name)


def _ready_observation() -> LiveKlipperScannerSyncObservation:
    return LiveKlipperScannerSyncObservation(
        host_extra_present=True,
        config_section_present=True,
        config_enable=True,
        mcu_connected=True,
        mcu_command_formats=frozenset(EXPECTED_COMMAND_FORMATS),
        registered_response_formats=frozenset(EXPECTED_RESPONSE_FORMATS),
        response_dispatch_available=True,
        metadata_only_mode=True,
        hardware_outputs_enabled=False,
    )


def _frame_params(
    *,
    frame_id: int,
    stripe_frame_index: int,
    event_position: int,
) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "stripe_id": 1,
        "stripe_frame_index": stripe_frame_index,
        "pattern_id": stripe_frame_index,
        "position_axis": 0,
        "event_position": event_position,
        "x_count": event_position,
        "y_count": 5,
        "z_count": 0,
        "mcu_time_us": 100 * (stripe_frame_index + 1),
        "status": 0,
        "flags": 0,
    }


def _frame_record(
    *,
    scan_id: str,
    frame_id: int,
    stripe_frame_index: int,
    event_position: int,
    hardware_outputs_enabled: bool = False,
) -> FrameEventRecord:
    return FrameEventRecord(
        protocol_version=1,
        scan_id=scan_id,
        stripe_id=1,
        frame_id=frame_id,
        stripe_frame_index=stripe_frame_index,
        pattern="BF_WHITE",
        coordinate_source_used="step_indexed",
        position_axis="X",
        event_position=event_position,
        sample_position=event_position,
        position_overshoot_count=0,
        x_count=event_position,
        y_count=5,
        z_count=0,
        x_step_commanded=event_position,
        y_step_commanded=5,
        z_step_commanded=0,
        mcu_time_us=100 * (stripe_frame_index + 1),
        hardware_outputs_enabled=hardware_outputs_enabled,
    )


if __name__ == "__main__":
    unittest.main()
