import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_core.predictive_z.types import (  # noqa: E402
    StripeContext,
    ZCommand,
    ZSchedulerConfig,
)
from scanner_core.telemetry import validate_telemetry_event_name  # noqa: E402
from scanner_firmware.foundation.protocol.events import (  # noqa: E402
    FrameEventRecord,
    SchedulerTerminalRecord,
)
from scanner_firmware.planning.readiness.result import (  # noqa: E402
    PlatformReadinessCheck,
    PlatformReadinessResult,
)
from scanner_firmware.planning.trigger_scheduler.scheduler import (  # noqa: E402
    DryRunPositionEventScheduler,
)
from scanner_firmware.planning.trigger_scheduler.types import (  # noqa: E402
    PositionSample,
    StripeSchedule,
)
from scanner_firmware.planning.z_scheduler.scheduler import (  # noqa: E402
    PredictiveZSchedulerSimulator,
)
from scanner_firmware.telemetry.report.producers import (  # noqa: E402
    TelemetryEvent,
    build_controller_decode_telemetry_report,
    build_dry_run_scheduler_telemetry_report,
    build_readiness_check_telemetry_report,
)


FIXTURE_GENERATED_AT = "2026-07-02T00:00:00Z"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
CONTROLLER_FIXTURE = FIXTURES / "firmware_telemetry_controller_decode_report_v1.json"
READINESS_FIXTURE = FIXTURES / "firmware_telemetry_readiness_report_v1.json"
DRY_RUN_FIXTURE = FIXTURES / "firmware_telemetry_dry_run_scheduler_report_v1.json"

REQUIRED_EVENT_KEYS = {
    "schema_id",
    "schema_version",
    "event_name",
    "source_component",
    "severity",
    "hardware_outputs_enabled",
    "live_hardware_access_used",
    "payload",
}


class FirmwareTelemetryReportProducerTests(unittest.TestCase):
    def test_controller_decode_report_fixture_is_deterministic(self):
        report = build_controller_decode_telemetry_report(
            _controller_records(),
            report_id="controller-decode-telemetry-v1",
            generated_at=FIXTURE_GENERATED_AT,
            run_id="run-fixture-telemetry",
        ).to_json_dict()

        self.assertEqual(report, _load(CONTROLLER_FIXTURE))
        self.assertEqual(report["event_names"], ["controller_event_decoded"])
        self.assert_no_hardware_or_live_access(report)

    def test_readiness_check_report_fixture_is_deterministic(self):
        report = build_readiness_check_telemetry_report(
            _readiness_result(),
            report_id="readiness-telemetry-v1",
            generated_at=FIXTURE_GENERATED_AT,
            run_id="run-fixture-telemetry",
        ).to_json_dict()

        self.assertEqual(report, _load(READINESS_FIXTURE))
        self.assertEqual(
            report["event_names"],
            ["readiness_check_result", "readiness_check_result"],
        )
        self.assert_no_hardware_or_live_access(report)
        self.assertEqual([event["severity"] for event in report["events"]], ["info", "warning"])

    def test_dry_run_scheduler_report_fixture_is_deterministic(self):
        report = build_dry_run_scheduler_telemetry_report(
            _dry_run_scheduler_outcomes(),
            report_id="dry-run-scheduler-telemetry-v1",
            generated_at=FIXTURE_GENERATED_AT,
            run_id="run-fixture-telemetry",
        ).to_json_dict()

        self.assertEqual(report, _load(DRY_RUN_FIXTURE))
        self.assertEqual(
            report["event_names"],
            [
                "frame_event_received",
                "frame_event_received",
                "z_scheduler_terminal",
                "z_command_enqueued",
                "z_command_accepted",
                "z_command_rejected",
                "z_command_applied",
            ],
        )
        self.assert_no_hardware_or_live_access(report)

    def test_fixture_event_names_are_canonical_in_scanner_core_contract(self):
        names = set()
        for fixture in (CONTROLLER_FIXTURE, READINESS_FIXTURE, DRY_RUN_FIXTURE):
            names.update(_load(fixture)["event_names"])

        for event_name in sorted(names):
            self.assertEqual(validate_telemetry_event_name(event_name), event_name)

    def test_event_model_rejects_non_software_only_flags(self):
        with self.assertRaisesRegex(ValueError, "hardware_outputs_enabled"):
            TelemetryEvent(
                event_name="readiness_check_result",
                source_component="scanner-firmware.test",
                severity="info",
                payload={"check": "unit"},
                hardware_outputs_enabled=True,
            )

        with self.assertRaisesRegex(ValueError, "live_hardware_access_used"):
            TelemetryEvent(
                event_name="readiness_check_result",
                source_component="scanner-firmware.test",
                severity="info",
                payload={"check": "unit"},
                live_hardware_access_used=True,
            )

    def assert_no_hardware_or_live_access(self, report):
        self.assertFalse(report["hardware_outputs_enabled"])
        self.assertFalse(report["live_hardware_access_used"])
        for event in report["events"]:
            self.assertTrue(REQUIRED_EVENT_KEYS <= set(event))
            self.assertFalse(event["hardware_outputs_enabled"])
            self.assertFalse(event["live_hardware_access_used"])


def _controller_records():
    return (
        FrameEventRecord(
            protocol_version=1,
            scan_id="scan-telemetry",
            stripe_id=3,
            frame_id=40,
            stripe_frame_index=0,
            pattern="BF_WHITE",
            coordinate_source_used="step_indexed",
            position_axis="X",
            event_position=100,
            sample_position=100,
            position_overshoot_count=0,
            x_count=100,
            y_count=5,
            z_count=2,
            x_step_commanded=100,
            y_step_commanded=5,
            z_step_commanded=2,
            mcu_time_us=1000,
            status="ok",
        ),
        SchedulerTerminalRecord(
            protocol_version=1,
            scan_id="scan-telemetry",
            stripe_id=3,
            status="stopped",
            reason_code="host_stop",
            emitted_frame_count=1,
            expected_frame_count=2,
            last_frame_id=40,
            next_frame_id=41,
            next_stripe_frame_index=1,
            mcu_time_us=1100,
            message="fixture stop",
        ),
    )


def _readiness_result():
    return PlatformReadinessResult(
        generated_at=FIXTURE_GENERATED_AT,
        target="scanner-firmware-telemetry-fixture",
        readiness_state="safe_disabled",
        checks=(
            PlatformReadinessCheck(
                id="firmware_config_schema",
                status="pass",
                scope="config",
                evidence="tests/fixtures/firmware_config_split_valid.json",
                message="Firmware config schema accepted.",
            ),
            PlatformReadinessCheck(
                id="live_test_approval_gate",
                status="blocked",
                scope="live_test_gate",
                evidence="scanner-docs/governance/live-test-approval-gate.md",
                message="Live hardware approval is not granted by telemetry.",
            ),
        ),
        unknowns=(),
        blockers=(),
    )


def _dry_run_scheduler_outcomes():
    schedule = StripeSchedule(
        scan_id="scan-telemetry",
        stripe_id=3,
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=20,
        event_pitch=20,
        event_count=3,
        pattern_sequence=("BF_WHITE", "AF_RED_GREEN"),
    )
    position_events = DryRunPositionEventScheduler(first_frame_id=40).run(
        schedule,
        (
            PositionSample(x_step_commanded=20, y_step_commanded=5, mcu_time_us=1000),
            PositionSample(x_step_commanded=40, y_step_commanded=5, mcu_time_us=1100),
        ),
        stop_after_events=2,
    )

    z_scheduler = PredictiveZSchedulerSimulator(
        ZSchedulerConfig(
            min_z_steps=-50,
            max_z_steps=50,
            lead_frames=2,
            settle_frames=1,
        ),
        StripeContext(
            scan_id="scan-telemetry",
            stripe_id=3,
            start_position=0,
            end_position=100,
            current_frame_id=40,
        ),
    )
    z_scheduler.schedule(
        ZCommand(
            command_id="z-ok",
            scan_id="scan-telemetry",
            stripe_id=3,
            apply_at_frame_id=44,
            z_target_steps=12,
        ),
        seq=200,
    )
    z_scheduler.schedule(
        ZCommand(
            command_id="z-too-soon",
            scan_id="scan-telemetry",
            stripe_id=3,
            apply_at_frame_id=41,
            z_target_steps=12,
        ),
        seq=201,
    )
    z_scheduler.advance_to(frame_id=44)

    return tuple(position_events) + z_scheduler.outcomes


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
