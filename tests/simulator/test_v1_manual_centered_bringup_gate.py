from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.manual_center_bringup.evaluator import (  # noqa: E402
    evaluate_v1_manual_centered_bringup,
)
from scanner_firmware.planning.manual_center_bringup.types import (  # noqa: E402
    PlannedPosition,
    V1ManualCenteredBringupError,
    V1ManualCenteredBringupInput,
    XYEnvelope,
    ZFocusEnvelope,
)


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "v1_manual_centered_bringup_gate_v1.json"


def input_from_fixture(path: Path = FIXTURE_PATH) -> V1ManualCenteredBringupInput:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["software_only"] is True
    assert payload["contains_hardware_commands"] is False
    assert payload["may_move_stage"] is False
    bringup = payload["bringup"]
    xy = bringup["xy_envelope"]
    z = bringup["z_focus_envelope"]
    return V1ManualCenteredBringupInput(
        procedure_reviewed=bringup["procedure_reviewed"],
        operator_manual_center_confirmed=bringup["operator_manual_center_confirmed"],
        live_test_approval_id=bringup["live_test_approval_id"],
        emergency_stop_available=bringup["emergency_stop_available"],
        stop_conditions_reviewed=bringup["stop_conditions_reviewed"],
        homing_commands_requested=bringup["homing_commands_requested"],
        scan_workflow_requested=bringup["scan_workflow_requested"],
        z_motion_enabled=bringup["z_motion_enabled"],
        predictive_z_commands_enabled=bringup["predictive_z_commands_enabled"],
        xy_envelope=XYEnvelope(
            center_x_mm=xy["center_x_mm"],
            center_y_mm=xy["center_y_mm"],
            radius_x_mm=xy["radius_x_mm"],
            radius_y_mm=xy["radius_y_mm"],
        ),
        z_focus_envelope=ZFocusEnvelope(
            manual_focus_z_um=z["manual_focus_z_um"],
            min_delta_um=z["min_delta_um"],
            max_delta_um=z["max_delta_um"],
        ),
        planned_positions=tuple(
            PlannedPosition(
                label=position["label"],
                x_mm=position["x_mm"],
                y_mm=position["y_mm"],
                z_um=position.get("z_um"),
            )
            for position in bringup["planned_positions"]
        ),
    )


def replace_input(
    base: V1ManualCenteredBringupInput,
    **overrides,
) -> V1ManualCenteredBringupInput:
    values = {
        "procedure_reviewed": base.procedure_reviewed,
        "operator_manual_center_confirmed": base.operator_manual_center_confirmed,
        "live_test_approval_id": base.live_test_approval_id,
        "emergency_stop_available": base.emergency_stop_available,
        "stop_conditions_reviewed": base.stop_conditions_reviewed,
        "homing_commands_requested": base.homing_commands_requested,
        "scan_workflow_requested": base.scan_workflow_requested,
        "xy_envelope": base.xy_envelope,
        "z_focus_envelope": base.z_focus_envelope,
        "planned_positions": base.planned_positions,
        "z_motion_enabled": base.z_motion_enabled,
        "predictive_z_commands_enabled": base.predictive_z_commands_enabled,
    }
    values.update(overrides)
    return V1ManualCenteredBringupInput(**values)


class V1ManualCenteredBringupGateTests(unittest.TestCase):
    def test_accepts_reviewed_manual_centered_bounded_fixture(self) -> None:
        decision = evaluate_v1_manual_centered_bringup(input_from_fixture())

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.checked_positions, 3)
        self.assertEqual(decision.errors, ())
        self.assertEqual(
            decision.warnings,
            ("predictive-Z/autofocus estimates may be observed but must not command Z",),
        )

    def test_rejects_missing_review_or_operator_approval(self) -> None:
        decision = evaluate_v1_manual_centered_bringup(
            replace_input(
                input_from_fixture(),
                procedure_reviewed=False,
                operator_manual_center_confirmed=False,
                live_test_approval_id=None,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertIn("reviewed live-test procedure is required", decision.errors)
        self.assertIn("operator manual center confirmation is required", decision.errors)
        self.assertIn("live-test approval id is required", decision.errors)

    def test_rejects_homing_or_scan_workflow_requests(self) -> None:
        decision = evaluate_v1_manual_centered_bringup(
            replace_input(
                input_from_fixture(),
                homing_commands_requested=True,
                scan_workflow_requested=True,
            )
        )

        self.assertFalse(decision.accepted)
        self.assertIn(
            "homing commands are forbidden in V1 manual-centered bring-up",
            decision.errors,
        )
        self.assertIn(
            "scan workflow commands are forbidden in V1 manual-centered bring-up",
            decision.errors,
        )

    def test_rejects_xy_position_outside_configured_envelope(self) -> None:
        base = input_from_fixture()
        decision = evaluate_v1_manual_centered_bringup(
            replace_input(
                base,
                planned_positions=base.planned_positions
                + (PlannedPosition("x-overrun", 10.01, 0.0, 0.0),),
            )
        )

        self.assertFalse(decision.accepted)
        self.assertTrue(any("x-overrun" in error for error in decision.errors))
        self.assertTrue(any("outside manual-center envelope" in error for error in decision.errors))

    def test_rejects_missing_or_unbounded_z_focus_envelope(self) -> None:
        decision = evaluate_v1_manual_centered_bringup(
            replace_input(input_from_fixture(), z_focus_envelope=None)
        )

        self.assertFalse(decision.accepted)
        self.assertIn("numeric Z focus envelope must be configured", decision.errors)
        with self.assertRaises(V1ManualCenteredBringupError):
            evaluate_v1_manual_centered_bringup(
                replace_input(
                    input_from_fixture(),
                    z_focus_envelope=ZFocusEnvelope(
                        manual_focus_z_um=0.0,
                        min_delta_um=0.0,
                        max_delta_um=80.0,
                    ),
                )
            )

    def test_rejects_z_target_outside_configured_focus_envelope(self) -> None:
        base = input_from_fixture()
        decision = evaluate_v1_manual_centered_bringup(
            replace_input(
                base,
                planned_positions=base.planned_positions
                + (PlannedPosition("z-overrun", 0.0, 0.0, 81.0),),
            )
        )

        self.assertFalse(decision.accepted)
        self.assertTrue(any("z-overrun" in error for error in decision.errors))
        self.assertTrue(any("manual-focus envelope" in error for error in decision.errors))

    def test_rejects_predictive_z_command_output_for_v1(self) -> None:
        decision = evaluate_v1_manual_centered_bringup(
            replace_input(input_from_fixture(), predictive_z_commands_enabled=True)
        )

        self.assertFalse(decision.accepted)
        self.assertIn(
            "predictive-Z command output is forbidden in V1 manual-centered bring-up",
            decision.errors,
        )


if __name__ == "__main__":
    unittest.main()
