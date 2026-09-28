from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.mks_flash_gate import (  # noqa: E402
    validate_mks_flash_gate_package,
    validate_mks_flash_gate_yaml,
)


class KlipperMksFlashGateTests(unittest.TestCase):
    def test_accepts_complete_software_only_flash_gate_review(self):
        result = validate_mks_flash_gate_package(_gate_payload())

        self.assertTrue(result.review_ready)
        self.assertEqual(result.blockers, ())
        self.assertTrue(result.software_only)
        self.assertFalse(result.live_hardware_access_used)
        self.assertFalse(result.can_execute_flash)

    def test_yaml_entrypoint_uses_same_gate(self):
        result = validate_mks_flash_gate_yaml(
            """
mks_flash_gate:
  live_pi_hostname: pi5
  klipper_commit: c707dd19214709dc23684b254a68e3bf69e4cfb3
  captured_artifacts:
    klipper_config_path: captures/mks-flash/.config
    klipper_dictionary_path: captures/mks-flash/klipper.dict
    klipper_binary_path: captures/mks-flash/klipper.bin
    active_printer_cfg_path: captures/mks-flash/printer.cfg
  serial_paths:
    mks_by_path: /dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0
    mks_by_id: none observed for MKS CH341
  connectivity:
    klipper_service_active: true
    mks_serial_path_present: true
    mcu_handshake_restored: true
    identify_response_timeout_observed: false
  firmware_flash:
    bootloader_or_flash_method: STM32F103 USART3 bootloader reviewed for this MKS board
    exact_command_or_ui_steps: human-executed reviewed bootloader copy step at the machine
  rollback:
    plan_path: docs/evidence/mks-flash-rollback.md
    previous_klipper_ref: c707dd19214709dc23684b254a68e3bf69e4cfb3
    previous_firmware_artifact: captures/mks-flash/baseline-klipper.bin
    printer_cfg_backup_path: captures/mks-flash/printer.cfg.before
  scanner_sync_config:
    enable: false
    metadata_only_mode: true
    hardware_outputs_enabled: false
    output_pins_configured: false
"""
        )

        self.assertTrue(result.review_ready)
        self.assertEqual(result.blockers, ())

    def test_blocks_unresolved_identify_response_timeout_or_missing_handshake(self):
        payload = _gate_payload()
        payload["mks_flash_gate"]["connectivity"]["mcu_handshake_restored"] = False
        payload["mks_flash_gate"]["connectivity"]["identify_response_timeout_observed"] = True

        result = validate_mks_flash_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn("connectivity.mcu_handshake_must_be_restored", result.blockers)
        self.assertIn("connectivity.identify_response_timeout_unresolved", result.blockers)
        self.assertFalse(result.can_execute_flash)

    def test_requires_captured_artifacts_and_rollback_plan(self):
        payload = _gate_payload()
        payload["mks_flash_gate"]["captured_artifacts"]["klipper_binary_path"] = "UNKNOWN"
        del payload["mks_flash_gate"]["rollback"]["printer_cfg_backup_path"]

        result = validate_mks_flash_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn("captured_artifacts.klipper_binary_path_unknown", result.blockers)
        self.assertIn("rollback.printer_cfg_backup_path_missing", result.blockers)

    def test_blocks_scanner_sync_enable_or_hardware_outputs_before_flash(self):
        payload = _gate_payload()
        payload["mks_flash_gate"]["scanner_sync_config"]["enable"] = True
        payload["mks_flash_gate"]["scanner_sync_config"]["hardware_outputs_enabled"] = True
        payload["mks_flash_gate"]["scanner_sync_config"]["output_pins_configured"] = True

        result = validate_mks_flash_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn(
            "scanner_sync_config.enable_must_remain_false_before_flash",
            result.blockers,
        )
        self.assertIn(
            "scanner_sync_config.hardware_outputs_enabled_must_be_false",
            result.blockers,
        )
        self.assertIn(
            "scanner_sync_config.output_pins_configured_must_be_false",
            result.blockers,
        )

    def test_rejects_flash_approval_claims(self):
        payload = _gate_payload()
        payload["mks_flash_gate"]["approved_for_flash"] = True

        result = validate_mks_flash_gate_package(payload)

        self.assertFalse(result.review_ready)
        self.assertIn("mks_flash_gate.approved_for_flash_must_not_claim_approval", result.blockers)
        self.assertFalse(result.can_execute_flash)


def _gate_payload() -> dict:
    return copy.deepcopy(
        {
            "mks_flash_gate": {
                "live_pi_hostname": "pi5",
                "klipper_commit": "c707dd19214709dc23684b254a68e3bf69e4cfb3",
                "captured_artifacts": {
                    "klipper_config_path": "captures/mks-flash/.config",
                    "klipper_dictionary_path": "captures/mks-flash/klipper.dict",
                    "klipper_binary_path": "captures/mks-flash/klipper.bin",
                    "active_printer_cfg_path": "captures/mks-flash/printer.cfg",
                },
                "serial_paths": {
                    "mks_by_path": (
                        "/dev/serial/by-path/"
                        "platform-xhci-hcd.0-usb-0:1:1.0-port0"
                    ),
                    "mks_by_id": "none observed for MKS CH341",
                },
                "connectivity": {
                    "klipper_service_active": True,
                    "mks_serial_path_present": True,
                    "mcu_handshake_restored": True,
                    "identify_response_timeout_observed": False,
                },
                "firmware_flash": {
                    "bootloader_or_flash_method": (
                        "STM32F103 USART3 bootloader reviewed for this MKS board"
                    ),
                    "exact_command_or_ui_steps": (
                        "human-executed reviewed bootloader copy step at the machine"
                    ),
                },
                "rollback": {
                    "plan_path": "docs/evidence/mks-flash-rollback.md",
                    "previous_klipper_ref": "c707dd19214709dc23684b254a68e3bf69e4cfb3",
                    "previous_firmware_artifact": "captures/mks-flash/baseline-klipper.bin",
                    "printer_cfg_backup_path": "captures/mks-flash/printer.cfg.before",
                },
                "scanner_sync_config": {
                    "enable": False,
                    "metadata_only_mode": True,
                    "hardware_outputs_enabled": False,
                    "output_pins_configured": False,
                },
            }
        }
    )


if __name__ == "__main__":
    unittest.main()
