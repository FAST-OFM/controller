import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.event_streaming.dispatch import ScannerSyncProtocolDispatcher  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (  # noqa: E402
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.testing.fake import DryRunKlipperMcu  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext  # noqa: E402
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (  # noqa: E402
    COMMAND_BINDINGS,
    SCANNER_SYNC_FRAME_EVENT_RESPONSE,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.registration import (  # noqa: E402
    ScannerSyncKlipperRegistration,
)


class KlipperProtocolDispatcherTests(unittest.TestCase):
    def test_dispatcher_decodes_callback_payloads_to_protocol_records(self):
        dispatcher = ScannerSyncProtocolDispatcher(
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE", "AF_RED_GREEN"),
                trigger_output_name="mks_pd6",
            )
        )

        record = dispatcher.handle_response(
            "FRAME_EVENT",
            {
                "frame_id": 12,
                "stripe_id": 7,
                "stripe_frame_index": 2,
                "pattern_id": 1,
                "position_axis": 0,
                "event_position": 200,
                "sample_position": 203,
                "position_overshoot_count": 3,
                "x_count": 1203,
                "y_count": 412,
                "z_count": 5,
                "x_step_commanded": 203,
                "y_step_commanded": 12,
                "z_step_commanded": 6,
                "x_encoder_count": 1203,
                "y_encoder_count": 412,
                "coordinate_flags": ["sample_overshot_event_position"],
                "mcu_time_us": 4000,
                "status": 0,
                "flags": 0,
            },
        )

        self.assertEqual(record.type, "FRAME_EVENT")
        self.assertEqual(record.scan_id, "scan-a")
        self.assertEqual(record.pattern, "AF_RED_GREEN")
        self.assertEqual(record.trigger_output_name, "mks_pd6")
        self.assertEqual(record.sample_position, 203)
        self.assertEqual(record.position_overshoot_count, 3)
        self.assertEqual(record.x_count, 1203)
        self.assertEqual(record.x_step_commanded, 203)
        self.assertEqual(record.x_encoder_count, 1203)
        self.assertEqual(record.coordinate_flags, ("sample_overshot_event_position",))
        self.assertFalse(record.hardware_outputs_enabled)
        self.assertEqual(dispatcher.records, (record,))
        self.assertEqual(dispatcher.stats.record_count, 1)
        self.assertEqual(dispatcher.stats.last_event_type, "FRAME_EVENT")

    def test_dispatcher_can_be_registered_with_dry_run_klipper_callbacks(self):
        dispatcher = ScannerSyncProtocolDispatcher(
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            )
        )
        mcu = DryRunKlipperMcu(
            available_commands=[binding.msgformat for binding in COMMAND_BINDINGS]
        )
        registration = ScannerSyncKlipperRegistration(
            mcu,
            response_handler=dispatcher.handle_response,
        )
        mcu.run_config_callbacks()

        mcu.emit_serial_response(
            SCANNER_SYNC_FRAME_EVENT_RESPONSE,
            {
                "frame_id": 1,
                "stripe_id": 0,
                "stripe_frame_index": 0,
                "pattern_id": 0,
                "position_axis": 0,
                "event_position": 100,
                "x_count": 100,
                "y_count": 0,
                "z_count": 0,
                "mcu_time_us": 1000,
                "status": 0,
                "flags": 0,
            },
            oid=registration.oid,
        )

        self.assertEqual(len(dispatcher.records), 1)
        self.assertEqual(dispatcher.records[0].type, "FRAME_EVENT")
        self.assertEqual(dispatcher.records[0].frame_id, 1)

    def test_dispatcher_forwards_records_to_optional_sink(self):
        sink = []
        dispatcher = ScannerSyncProtocolDispatcher(
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
            sink=sink,
        )

        record = dispatcher.handle_response(
            "Z_SCHEDULED",
            {"seq": 10, "stripe_id": 7, "status": 0},
        )

        self.assertEqual(sink, [record])

    def test_dispatcher_can_validate_before_forwarding_to_sink(self):
        sink = []
        dispatcher = ScannerSyncProtocolDispatcher(
            context=ScannerSyncDecodeContext(scan_id="scan-a"),
            sink=sink,
            validate_before_sink=True,
        )
        first = dispatcher.handle_response(
            "FRAME_EVENT",
            _frame_event_params(frame_id=1, stripe_frame_index=0),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "frame_id"):
            dispatcher.handle_response(
                "FRAME_EVENT",
                _frame_event_params(frame_id=3, stripe_frame_index=1),
            )

        self.assertEqual(sink, [first])
        self.assertEqual(dispatcher.records, (first,))

    def test_dispatcher_validates_decoded_sequence(self):
        dispatcher = ScannerSyncProtocolDispatcher(
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            )
        )
        dispatcher.handle_response(
            "FRAME_EVENT",
            _frame_event_params(frame_id=1, stripe_frame_index=0),
        )
        dispatcher.handle_response(
            "FRAME_EVENT",
            _frame_event_params(frame_id=2, stripe_frame_index=1),
        )
        dispatcher.handle_response(
            "SCHEDULER_TERMINAL",
            {
                "status": 0,
                "reason": 0,
                "emitted_frame_count": 2,
                "expected_frame_count": 3,
                "last_frame_id": 2,
                "next_frame_id": 3,
                "next_stripe_frame_index": 2,
                "mcu_time_us": 3000,
            },
        )

        validation = dispatcher.validate_sequence()

        self.assertEqual(validation.frame_count, 2)
        self.assertEqual(validation.terminal_count, 1)
        self.assertEqual(validation.last_frame_id, 2)

    def test_dispatcher_validation_rejects_invalid_decoded_sequence(self):
        dispatcher = ScannerSyncProtocolDispatcher(
            context=ScannerSyncDecodeContext(
                scan_id="scan-a",
                pattern_names=("BF_WHITE",),
            )
        )
        dispatcher.handle_response(
            "FRAME_EVENT",
            _frame_event_params(frame_id=1, stripe_frame_index=0),
        )
        dispatcher.handle_response(
            "FRAME_EVENT",
            _frame_event_params(frame_id=3, stripe_frame_index=1),
        )

        with self.assertRaisesRegex(ScannerSyncEventStreamError, "frame_id"):
            dispatcher.validate_sequence()


def _frame_event_params(*, frame_id: int, stripe_frame_index: int):
    return {
        "frame_id": frame_id,
        "stripe_id": 0,
        "stripe_frame_index": stripe_frame_index,
        "pattern_id": 0,
        "position_axis": 0,
        "event_position": frame_id * 100,
        "x_count": frame_id * 100,
        "y_count": 0,
        "z_count": 0,
        "mcu_time_us": frame_id * 1000,
        "status": 0,
        "flags": 0,
    }


if __name__ == "__main__":
    unittest.main()
