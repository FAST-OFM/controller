import sys
import unittest
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.readiness.types import StartupReadinessDecision  # noqa: E402
from scanner_firmware.planning.scan_execution.state_machine import (  # noqa: E402
    apply_startup_decision,
    begin_scanning,
    complete_scan,
    complete_stop,
    enter_fault,
    initial_scan_execution_state,
    prepare_scan,
    request_stop,
)
from scanner_firmware.planning.scan_execution.states import (  # noqa: E402
    ScanExecutionError,
    ScanExecutionInput,
)
from scanner_firmware.planning.scan_execution.plan import (  # noqa: E402
    ExecutionFramePlan,
    ExecutionScanPlan,
    ExecutionStripePlan,
)
from scanner_firmware.planning.scan_execution.traces import (  # noqa: E402
    FLY_SCAN_OPEN_LOOP_FRAME_STEPS,
    FLY_SCAN_PREDICTIVE_Z_FRAME_STEPS,
    MICRO_STOP_STEPS,
    SEGMENTED_FLY_SCAN_FRAME_STEPS,
    STOP_AND_CAPTURE_STEPS,
    build_simulator_scan_execution_trace,
)
from scanner_firmware.planning.scan_preflight.decisions import ScanPreflightDecision  # noqa: E402


def readiness(**overrides) -> StartupReadinessDecision:
    values = dict(
        stage="SCAN_PREPARE",
        status="ready",
        blockers=(),
        warnings=(),
    )
    values.update(overrides)
    return StartupReadinessDecision(**values)


def preflight(**overrides) -> ScanPreflightDecision:
    values = dict(
        accepted=True,
        missing_axes=(),
        warnings=(),
        errors=(),
    )
    values.update(overrides)
    return ScanPreflightDecision(**values)


def execution_input(**overrides) -> ScanExecutionInput:
    values = dict(
        readiness=readiness(),
        preflight=preflight(),
        dry_run=False,
        hardware_outputs_armed=True,
    )
    values.update(overrides)
    return ScanExecutionInput(**values)


def scan_plan(scan_mode):
    scan_id = f"scan-execution-trace-{scan_mode}"
    frames = tuple(
        ExecutionFramePlan(
            scan_id=scan_id,
            stripe_id=0,
            frame_id=index,
            stripe_frame_index=index,
            scan_axis="X",
            scan_axis_position=index * 100,
            scan_mode=scan_mode,
            dry_run=True,
            hardware_outputs_enabled=False,
        )
        for index in range(3)
    )
    return ExecutionScanPlan(
        scan_id=scan_id,
        stripes=(ExecutionStripePlan(stripe_id=0, scan_axis="X", frames=frames),),
        dry_run=True,
        hardware_outputs_enabled=False,
    )


class ScanExecutionStateMachineTests(unittest.TestCase):
    def test_valid_startup_path_reaches_complete(self):
        state = initial_scan_execution_state()

        state = apply_startup_decision(
            state,
            readiness(stage="READY", status="safe_disabled", warnings=("not_armed",)),
        )
        self.assertEqual(state.state, "READY")

        state = prepare_scan(state, execution_input())
        self.assertEqual(state.state, "SCAN_PREPARE")

        state = begin_scanning(state, execution_input())
        self.assertEqual(state.state, "SCANNING")

        state = complete_scan(state)
        self.assertEqual(state.state, "COMPLETE")
        self.assertEqual(state.terminal_reason, "SCAN_COMPLETE")
        self.assertTrue(state.terminal)

    def test_blocks_when_homing_or_readiness_is_missing(self):
        state = apply_startup_decision(
            initial_scan_execution_state(),
            readiness(
                stage="IDLE_SAFE_DISABLED",
                status="safe_disabled",
                warnings=("homing_incomplete",),
            ),
        )
        self.assertEqual(state.state, "IDLE_SAFE_DISABLED")

        with self.assertRaisesRegex(ScanExecutionError, "accepted"):
            prepare_scan(
                state,
                execution_input(
                    readiness=readiness(
                        stage="IDLE_SAFE_DISABLED",
                        status="safe_disabled",
                        warnings=("homing_incomplete",),
                    ),
                    preflight=preflight(
                        accepted=False,
                        missing_axes=("Z",),
                        errors=("homing is missing for required axes: Z",),
                    ),
                    hardware_outputs_armed=False,
                ),
            )

        with self.assertRaisesRegex(ScanExecutionError, "ready startup"):
            prepare_scan(
                state,
                execution_input(
                    readiness=readiness(
                        stage="IDLE_SAFE_DISABLED",
                        status="safe_disabled",
                        warnings=("homing_incomplete",),
                    ),
                    hardware_outputs_armed=True,
                ),
            )

    def test_dry_run_completes_without_hardware_outputs_or_scanning(self):
        state = apply_startup_decision(
            initial_scan_execution_state(),
            readiness(
                stage="IDLE_SAFE_DISABLED",
                status="safe_disabled",
                warnings=("homing_incomplete",),
            ),
        )
        inputs = execution_input(
            readiness=readiness(
                stage="IDLE_SAFE_DISABLED",
                status="safe_disabled",
                warnings=("homing_incomplete",),
            ),
            preflight=preflight(
                accepted=True,
                missing_axes=("Y", "Z"),
                warnings=("dry-run scan accepted with missing homing",),
            ),
            dry_run=True,
            hardware_outputs_armed=False,
        )

        state = prepare_scan(state, inputs)
        self.assertEqual(state.state, "SCAN_PREPARE")

        state = begin_scanning(state, inputs)
        self.assertEqual(state.state, "COMPLETE")
        self.assertEqual(state.terminal_reason, "DRY_RUN_COMPLETE")

    def test_fault_and_stop_reach_terminal_states(self):
        state = prepare_scan(
            apply_startup_decision(initial_scan_execution_state(), readiness()),
            execution_input(),
        )
        scanning = begin_scanning(state, execution_input())

        stopped = complete_stop(request_stop(scanning))
        self.assertEqual(stopped.state, "COMPLETE")
        self.assertEqual(stopped.terminal_reason, "STOPPED")

        faulted = enter_fault(scanning)
        self.assertEqual(faulted.state, "FAULT")
        self.assertEqual(faulted.terminal_reason, "FAULT_DETECTED")

    def test_rejects_invalid_transitions_and_unarmed_scanning(self):
        with self.assertRaisesRegex(ScanExecutionError, "cannot begin"):
            begin_scanning(initial_scan_execution_state(), execution_input())

        prepared = prepare_scan(
            apply_startup_decision(initial_scan_execution_state(), readiness()),
            execution_input(),
        )
        with self.assertRaisesRegex(ScanExecutionError, "hardware output arm"):
            begin_scanning(
                prepared,
                execution_input(hardware_outputs_armed=False),
            )

        terminal = complete_scan(begin_scanning(prepared, execution_input()))
        with self.assertRaisesRegex(ScanExecutionError, "terminal state"):
            complete_scan(terminal)

        with self.assertRaisesRegex(ScanExecutionError, "remain disabled"):
            execution_input(dry_run=True, hardware_outputs_armed=True)

    def test_builds_deterministic_dry_run_execution_traces_for_all_modes(self):
        expected_frame_steps_by_mode = {
            "stop_and_capture": STOP_AND_CAPTURE_STEPS,
            "micro_stop": MICRO_STOP_STEPS,
            "segmented_fly_scan": SEGMENTED_FLY_SCAN_FRAME_STEPS,
            "fly_scan_open_loop": FLY_SCAN_OPEN_LOOP_FRAME_STEPS,
            "fly_scan_predictive_z": FLY_SCAN_PREDICTIVE_Z_FRAME_STEPS,
        }
        expected_mode_steps = {
            "stop_and_capture": ("MOVE_TO_TARGET", "SETTLE_XY", "FRAME_EVENT"),
            "micro_stop": ("MOVE_INCREMENT", "HOLD", "FRAME_EVENT"),
            "segmented_fly_scan": (
                "ACCELERATE",
                "SCAN_SEGMENT_WITH_POSITION_TRIGGER",
                "BOUNDARY_WINDOW",
            ),
            "fly_scan_open_loop": (
                "ACCELERATE",
                "CONSTANT_VELOCITY_POSITION_TRIGGER",
                "DECELERATE",
            ),
            "fly_scan_predictive_z": (
                "PREDICTIVE_Z_QUEUE_CHECK",
                "APPLY_SCHEDULED_Z",
                "FRAME_EVENT",
            ),
        }

        for mode, expected_frame_steps in expected_frame_steps_by_mode.items():
            with self.subTest(mode=mode):
                plan = scan_plan(mode)

                first_trace = build_simulator_scan_execution_trace(plan)
                second_trace = build_simulator_scan_execution_trace(plan)

                self.assertEqual(first_trace, second_trace)
                self.assertEqual(first_trace.mode, mode)
                self.assertEqual(first_trace.terminal_reason, "DRY_RUN_COMPLETE")
                self.assertFalse(first_trace.hardware_outputs_enabled)
                self.assertEqual(first_trace.frame_event_count, len(plan.frames))
                self.assertEqual(first_trace.steps[0], "SCAN_PREPARE")
                self.assertEqual(first_trace.steps[-1], "DRY_RUN_COMPLETE")
                self.assertEqual(
                    [event.sequence for event in first_trace.events],
                    list(range(len(first_trace.events))),
                )
                self.assertFalse(
                    any(event.hardware_outputs_enabled for event in first_trace.events)
                )
                for expected_step in expected_mode_steps[mode]:
                    self.assertIn(expected_step, first_trace.steps)

                first_frame_steps = tuple(
                    event.step
                    for event in first_trace.events
                    if event.frame_id == plan.frames[0].frame_id
                )
                self.assertEqual(first_frame_steps, expected_frame_steps)

    def test_trace_rejects_hardware_outputs_enabled_records(self):
        plan = scan_plan("stop_and_capture")
        bad_frame = replace(plan.frames[0], hardware_outputs_enabled=True)
        bad_stripe = replace(
            plan.stripes[0],
            frames=(bad_frame, *plan.stripes[0].frames[1:]),
        )
        bad_plan = replace(plan, stripes=(bad_stripe,))

        with self.assertRaisesRegex(ScanExecutionError, "hardware_outputs_enabled=false"):
            build_simulator_scan_execution_trace(bad_plan)

        with self.assertRaisesRegex(ScanExecutionError, "hardware_outputs_enabled=false"):
            build_simulator_scan_execution_trace(
                replace(plan, hardware_outputs_enabled=True)
            )

    def test_trace_rejects_legacy_mode_aliases_inside_plans(self):
        plan = scan_plan("stop_and_capture")
        legacy_frame = replace(plan.frames[0], scan_mode="step_stop_capture")
        bad_stripe = replace(
            plan.stripes[0],
            frames=(legacy_frame, *plan.stripes[0].frames[1:]),
        )

        with self.assertRaisesRegex(ScanExecutionError, "not canonical"):
            build_simulator_scan_execution_trace(replace(plan, stripes=(bad_stripe,)))


if __name__ == "__main__":
    unittest.main()
