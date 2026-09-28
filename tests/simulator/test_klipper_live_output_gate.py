from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.live_output.gate import (  # noqa: E402
    validate_live_output_gate_package,
    validate_live_output_gate_yaml,
)


class KlipperLiveOutputGateTests(unittest.TestCase):
    def test_accepts_complete_fixture(self):
        result = validate_live_output_gate_yaml(
            (REPO_ROOT / "tests" / "fixtures" / "klipper_live_output_gate_complete.yaml")
            .read_text(encoding="utf-8")
        )

        self.assertTrue(result.review_ready)
        self.assertEqual(result.blockers, ())

    def test_incomplete_fixture_preserves_blockers(self):
        result = validate_live_output_gate_yaml(
            (REPO_ROOT / "tests" / "fixtures" / "klipper_live_output_gate_incomplete.yaml")
            .read_text(encoding="utf-8")
        )

        self.assertFalse(result.review_ready)
        self.assertIn("live_pi_hostname_unknown", result.blockers)
        self.assertIn("current_state.mks_serial_path_must_be_present", result.blockers)
        self.assertIn(
            "timed_output_sequence.all_outputs_off_must_be_finite_one_shot",
            result.blockers,
        )

    def test_approval_claiming_fixture_is_rejected(self):
        result = validate_live_output_gate_yaml(
            (
                REPO_ROOT
                / "tests"
                / "fixtures"
                / "klipper_live_output_gate_approval_claiming.yaml"
            ).read_text(encoding="utf-8")
        )

        self.assertFalse(result.review_ready)
        self.assertIn(
            "live_test_gate.approved_must_be_false_in_static_package",
            result.blockers,
        )

    def test_accepts_complete_software_only_live_output_gate_review(self):
        result = validate_live_output_gate_package(_gate_payload())

        self.assertTrue(result.review_ready)
        self.assertEqual(result.blockers, ())
        self.assertTrue(result.software_only)
        self.assertFalse(result.live_hardware_access_used)
        self.assertFalse(result.can_execute_live_output)
        self.assertFalse(result.can_flash_firmware)

    def test_yaml_entrypoint_uses_same_gate(self):
        result = validate_live_output_gate_yaml(
            """
live_output_gate:
  gate_id: stationary-af-timed-output-live-output-gate-v1
  review_issue_or_pr: scanner-firmware#220
  live_pi_hostname: pi5
  mks_flash_gate_ref: scanner-firmware#220/mks_flash_gate
  firmware_artifact:
    commit: 42115ae
    binary_path: captures/mks-live-output/klipper.bin
    dictionary_path: captures/mks-live-output/klipper.dict
    patch_artifact_path: docs/patches/klipper-scanner-sync-timed-output-sequence.patch
  printer_cfg:
    active_printer_cfg_path: captures/mks-live-output/printer.cfg
    baseline_backup_path: captures/mks-live-output/printer.cfg.before
  rollback:
    plan_path: docs/evidence/mks-live-output-rollback.md
    previous_firmware_artifact: captures/mks-live-output/baseline-klipper.bin
    previous_printer_cfg_backup: captures/mks-live-output/printer.cfg.before
  current_state:
    klipper_service_active: true
    mks_serial_path_present: true
    mcu_handshake_restored: true
    identify_response_timeout_observed: false
  current_scanner_sync_config:
    enable: false
    hardware_outputs_enabled: false
    output_pins_configured: false
  proposed_scanner_sync_config:
    mode: timed_output_sequence_bench
    enable: true
    hardware_outputs_enabled: true
    output_pins_configured: true
  no_motion_constraints:
    motors_commanded: false
    homing_commanded: false
    z_motion_commanded: false
    manual_center_required: false
  timed_output_sequence:
    command_fixture: scanner-pi/fixtures/sync/rg_autofocus_hq_xvs_timed_output_sequence_v1.jsonl
    all_outputs_off_fixture: scanner-pi/fixtures/sync/all_outputs_off_timed_output_sequence_v1.jsonl
    status_lifecycle_matches_validators: true
    scanner_sync_stop_guarded_by_active_sequence: true
    all_outputs_off_is_finite_one_shot: true
  safe_state:
    all_outputs_off_command_available: true
    post_stop_safe_state_required: true
  outputs:
    hq_xvs_sync:
      pin: PD6
      connector: E0_STEP
      polarity: active_high
      load_path: 3.3 V MKS logic through reviewed level shifter to HQ XVS
      default_state: off_or_inactive_until_measured
      verified_loaded_behavior: false
      level_shift_reviewed: true
    led_white_gate:
      pin: PB13
      connector: TC1_SCK
      polarity: active_high
      load_path: external current-limited LED driver gate
      default_state: off_or_inactive_until_measured
      verified_loaded_behavior: false
      external_current_limit_reviewed: true
    led_red_gate:
      pin: PA10
      connector: wifi_rxd1
      polarity: active_high
      load_path: external current-limited LED driver gate
      default_state: off_or_inactive_until_measured
      verified_loaded_behavior: false
      external_current_limit_reviewed: true
    led_green_gate:
      pin: PA9
      connector: wifi_txd1
      polarity: active_high
      load_path: external current-limited LED driver gate
      default_state: off_or_inactive_until_measured
      verified_loaded_behavior: false
      external_current_limit_reviewed: true
  stop_conditions:
    - unexpected_output_state
    - unexpected_current_or_heating
    - camera_trigger_mismatch
    - communication_fault
    - operator_uncertainty
  stop_conditions_reviewed: true
  expected_observation: finite no-motion timed-output sequence with scoped XVS/LED gate waveforms
  live_test_gate:
    required: true
    approved: false
    executed: false
"""
        )

        self.assertTrue(result.review_ready)
        self.assertEqual(result.blockers, ())

    def test_requires_artifacts_and_rejects_unknowns(self):
        payload = _gate_payload()
        payload["live_output_gate"]["firmware_artifact"]["binary_path"] = "UNKNOWN"
        del payload["live_output_gate"]["rollback"]["previous_printer_cfg_backup"]

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn("firmware_artifact.binary_path_unknown", result.blockers)
        self.assertIn("rollback.previous_printer_cfg_backup_missing", result.blockers)

    def test_blocks_unready_current_state(self):
        payload = _gate_payload()
        payload["live_output_gate"]["current_state"]["mcu_handshake_restored"] = False
        payload["live_output_gate"]["current_state"][
            "identify_response_timeout_observed"
        ] = True

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn("current_state.mcu_handshake_must_be_restored", result.blockers)
        self.assertIn("current_state.identify_response_timeout_unresolved", result.blockers)

    def test_requires_safe_current_config_and_explicit_proposed_live_output_config(self):
        payload = _gate_payload()
        payload["live_output_gate"]["current_scanner_sync_config"]["enable"] = True
        payload["live_output_gate"]["proposed_scanner_sync_config"][
            "hardware_outputs_enabled"
        ] = False

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn(
            "current_scanner_sync_config.enable_must_be_false_before_gate",
            result.blockers,
        )
        self.assertIn(
            "proposed_scanner_sync_config.hardware_outputs_enabled_must_be_true_for_review",
            result.blockers,
        )

    def test_blocks_motion_or_homing_scope(self):
        payload = _gate_payload()
        payload["live_output_gate"]["no_motion_constraints"]["motors_commanded"] = True
        payload["live_output_gate"]["no_motion_constraints"]["homing_commanded"] = True

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn("no_motion_constraints.motors_commanded_must_be_false", result.blockers)
        self.assertIn("no_motion_constraints.homing_commanded_must_be_false", result.blockers)

    def test_requires_lifecycle_and_finite_all_outputs_off_evidence(self):
        payload = _gate_payload()
        payload["live_output_gate"]["timed_output_sequence"][
            "status_lifecycle_matches_validators"
        ] = False
        payload["live_output_gate"]["timed_output_sequence"][
            "all_outputs_off_is_finite_one_shot"
        ] = False

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn(
            "timed_output_sequence.status_lifecycle_must_match_validators",
            result.blockers,
        )
        self.assertIn(
            "timed_output_sequence.all_outputs_off_must_be_finite_one_shot",
            result.blockers,
        )

    def test_requires_output_electrical_review_without_loaded_claims(self):
        payload = _gate_payload()
        payload["live_output_gate"]["outputs"]["led_red_gate"][
            "external_current_limit_reviewed"
        ] = False
        payload["live_output_gate"]["outputs"]["hq_xvs_sync"]["level_shift_reviewed"] = False
        payload["live_output_gate"]["outputs"]["led_green_gate"][
            "verified_loaded_behavior"
        ] = True

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn(
            "outputs.led_red_gate.external_current_limit_reviewed_must_be_true",
            result.blockers,
        )
        self.assertIn(
            "outputs.hq_xvs_sync.level_shift_reviewed_must_be_true",
            result.blockers,
        )
        self.assertIn(
            "outputs.led_green_gate.verified_loaded_behavior_must_be_false",
            result.blockers,
        )

    def test_rejects_static_live_approval_claims(self):
        payload = _gate_payload()
        payload["live_output_gate"]["live_test_gate"]["approved"] = True

        result = validate_live_output_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn(
            "live_test_gate.approved_must_be_false_in_static_package",
            result.blockers,
        )
        self.assertIn(
            "live_output_gate.live_test_gate.approved_must_not_claim_approval",
            result.blockers,
        )
        self.assertFalse(result.can_execute_live_output)


def _gate_payload() -> dict:
    return copy.deepcopy(
        {
            "live_output_gate": {
                "gate_id": "stationary-af-timed-output-live-output-gate-v1",
                "review_issue_or_pr": "scanner-firmware#220",
                "live_pi_hostname": "pi5",
                "mks_flash_gate_ref": "scanner-firmware#220/mks_flash_gate",
                "firmware_artifact": {
                    "commit": "42115ae",
                    "binary_path": "captures/mks-live-output/klipper.bin",
                    "dictionary_path": "captures/mks-live-output/klipper.dict",
                    "patch_artifact_path": (
                        "docs/patches/klipper-scanner-sync-timed-output-sequence.patch"
                    ),
                },
                "printer_cfg": {
                    "active_printer_cfg_path": "captures/mks-live-output/printer.cfg",
                    "baseline_backup_path": "captures/mks-live-output/printer.cfg.before",
                },
                "rollback": {
                    "plan_path": "docs/evidence/mks-live-output-rollback.md",
                    "previous_firmware_artifact": (
                        "captures/mks-live-output/baseline-klipper.bin"
                    ),
                    "previous_printer_cfg_backup": (
                        "captures/mks-live-output/printer.cfg.before"
                    ),
                },
                "current_state": {
                    "klipper_service_active": True,
                    "mks_serial_path_present": True,
                    "mcu_handshake_restored": True,
                    "identify_response_timeout_observed": False,
                },
                "current_scanner_sync_config": {
                    "enable": False,
                    "hardware_outputs_enabled": False,
                    "output_pins_configured": False,
                },
                "proposed_scanner_sync_config": {
                    "mode": "timed_output_sequence_bench",
                    "enable": True,
                    "hardware_outputs_enabled": True,
                    "output_pins_configured": True,
                },
                "no_motion_constraints": {
                    "motors_commanded": False,
                    "homing_commanded": False,
                    "z_motion_commanded": False,
                    "manual_center_required": False,
                },
                "timed_output_sequence": {
                    "command_fixture": (
                        "scanner-pi/fixtures/sync/"
                        "rg_autofocus_hq_xvs_timed_output_sequence_v1.jsonl"
                    ),
                    "all_outputs_off_fixture": (
                        "scanner-pi/fixtures/sync/"
                        "all_outputs_off_timed_output_sequence_v1.jsonl"
                    ),
                    "status_lifecycle_matches_validators": True,
                    "scanner_sync_stop_guarded_by_active_sequence": True,
                    "all_outputs_off_is_finite_one_shot": True,
                },
                "safe_state": {
                    "all_outputs_off_command_available": True,
                    "post_stop_safe_state_required": True,
                },
                "outputs": {
                    "hq_xvs_sync": {
                        "pin": "PD6",
                        "connector": "E0_STEP",
                        "polarity": "active_high",
                        "load_path": (
                            "3.3 V MKS logic through reviewed level shifter to HQ XVS"
                        ),
                        "default_state": "off_or_inactive_until_measured",
                        "verified_loaded_behavior": False,
                        "level_shift_reviewed": True,
                    },
                    "led_white_gate": {
                        "pin": "PB13",
                        "connector": "TC1_SCK",
                        "polarity": "active_high",
                        "load_path": "external current-limited LED driver gate",
                        "default_state": "off_or_inactive_until_measured",
                        "verified_loaded_behavior": False,
                        "external_current_limit_reviewed": True,
                    },
                    "led_red_gate": {
                        "pin": "PA10",
                        "connector": "wifi_rxd1",
                        "polarity": "active_high",
                        "load_path": "external current-limited LED driver gate",
                        "default_state": "off_or_inactive_until_measured",
                        "verified_loaded_behavior": False,
                        "external_current_limit_reviewed": True,
                    },
                    "led_green_gate": {
                        "pin": "PA9",
                        "connector": "wifi_txd1",
                        "polarity": "active_high",
                        "load_path": "external current-limited LED driver gate",
                        "default_state": "off_or_inactive_until_measured",
                        "verified_loaded_behavior": False,
                        "external_current_limit_reviewed": True,
                    },
                },
                "stop_conditions": [
                    "unexpected_output_state",
                    "unexpected_current_or_heating",
                    "camera_trigger_mismatch",
                    "communication_fault",
                    "operator_uncertainty",
                ],
                "stop_conditions_reviewed": True,
                "expected_observation": (
                    "finite no-motion timed-output sequence with scoped XVS/LED "
                    "gate waveforms"
                ),
                "live_test_gate": {
                    "required": True,
                    "approved": False,
                    "executed": False,
                },
            }
        }
    )


if __name__ == "__main__":
    unittest.main()
