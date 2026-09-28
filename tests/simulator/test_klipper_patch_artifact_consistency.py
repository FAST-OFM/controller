import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.adapters.klipper_adapter.readiness.patch_audit import (  # noqa: E402
    audit_klipper_patch_boundary,
)
from scanner_firmware.adapters.klipper_adapter.sync_registration.bindings import (  # noqa: E402
    COMMAND_BINDINGS,
    RESPONSE_BINDINGS,
    SCANNER_SYNC_CONFIG_COMMAND,
    SCANNER_SYNC_CONFIG_FORMAT,
    SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
    SCANNER_SYNC_Z_APPLIED_RESPONSE,
)


PATCH_ARTIFACT = (
    REPO_ROOT / "docs" / "patches" / "klipper-scanner-sync-phase1-stub.patch"
)
PHASE2_PATCH_ARTIFACT = (
    REPO_ROOT / "docs" / "patches" / "klipper-scanner-sync-phase2-metadata-only.patch"
)
PHASE3_PATCH_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "patches"
    / "klipper-scanner-sync-phase3-stationary-af-live-output.patch"
)
TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "patches"
    / "klipper-scanner-sync-timed-output-sequence.patch"
)
STAGE_B_CHECKLIST = "docs/klipper/klipper-live-metadata-stage-b-review-checklist.md"
STAGE_B_CAPTURE_SCRIPT = "scripts/capture-klipper-stage-b-evidence.sh"
FORBIDDEN_HARDWARE_SNIPPETS = (
    "gpio_out_setup",
    "gpio_out_write",
    "gpio_out_toggle",
    "queue_digital_out",
    "queue_pwm_out",
    "stepper_stop_on_trigger",
    "command_queue_step",
)
FORBIDDEN_LIVE_SCRIPT_SNIPPETS = (
    "systemctl restart",
    "systemctl stop",
    "systemctl start",
    "service klipper",
    "make flash",
    "flash_usb",
    "avrdude",
    "stm32flash",
    "dfu-util",
    "SET_PIN",
    "G28",
    "FORCE_MOVE",
)
FORBIDDEN_PHASE3_MOTION_OR_FLASH_SNIPPETS = (
    "command_queue_step",
    "stepper_stop_on_trigger",
    "endstop_home",
    "queue_step oid=",
    "G28",
    "FORCE_MOVE",
    "make flash",
    "flash_usb",
    "avrdude",
    "stm32flash",
    "dfu-util",
)
FORBIDDEN_TIMED_OUTPUT_SEQUENCE_MOTION_HOMING_OR_FLASH_SNIPPETS = (
    "command_queue_step",
    "stepper_stop_on_trigger",
    "endstop_home",
    "homing_state",
    "home_start",
    "home_finalize",
    "queue_step oid=",
    "G28",
    "FORCE_MOVE",
    "make flash",
    "flash_usb",
    "avrdude",
    "stm32flash",
    "dfu-util",
)


class KlipperPatchArtifactConsistencyTests(unittest.TestCase):
    def test_phase1_patch_contains_local_registration_command_names(self):
        patch_text = PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn(
            "config_scanner_sync oid=%d protocol_version=%d",
            added_source,
        )
        for binding in COMMAND_BINDINGS:
            self.assertIn(binding.msgformat, added_source)
        for binding in RESPONSE_BINDINGS:
            self.assertIn(binding.msgformat, added_source)

    def test_phase1_patch_keeps_hardware_outputs_out_of_stub(self):
        patch_text = PATCH_ARTIFACT.read_text()

        for snippet in FORBIDDEN_HARDWARE_SNIPPETS:
            self.assertNotIn(snippet, patch_text)

    def test_phase1_patch_declares_no_live_scan_mode(self):
        patch_text = PATCH_ARTIFACT.read_text()

        self.assertIn("Phase 1 sketch only", patch_text)
        self.assertIn("does not schedule motion", patch_text)
        self.assertIn("does not schedule scanner timing", patch_text)

    def test_phase1_z_applied_response_contract_has_no_stripe_id(self):
        self.assertIn("seq=%u", SCANNER_SYNC_Z_APPLIED_RESPONSE)
        self.assertIn("frame_id=%u", SCANNER_SYNC_Z_APPLIED_RESPONSE)
        self.assertNotIn("stripe_id", SCANNER_SYNC_Z_APPLIED_RESPONSE)

    def test_phase2_patch_is_metadata_only_and_removes_debug_emit(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn("mode: metadata_only", patch_text)
        self.assertIn("hardware_outputs_enabled: false", patch_text)
        self.assertIn("maxval=1", patch_text)
        self.assertIn("hardware_outputs_enabled=0", added_source)
        self.assertIn("self.callback_events = []", patch_text)
        self.assertIn(
            "event = {'event_type': event_type, 'params': dict(params)}",
            patch_text,
        )
        self.assertIn("self.callback_events.append(event)", patch_text)
        self.assertIn("'callback_events': list(self.callback_events)", patch_text)
        self.assertIn("self.last_event = event", patch_text)
        self.assertNotIn("self.last_event['type']", patch_text)
        self.assertIn(
            SCANNER_SYNC_CONFIG_COMMAND.format(
                oid="%d",
                version="%d",
                hardware_outputs_enabled=0,
            ),
            added_source,
        )
        self.assertIn(
            SCANNER_SYNC_CONFIG_FORMAT,
            added_source,
        )
        self.assertIn("scanner_sync_frame_event", added_source)
        self.assertIn("scanner_sync_scheduler_terminal", added_source)
        self.assertNotIn("scanner_sync_debug_emit", patch_text)
        for snippet in FORBIDDEN_HARDWARE_SNIPPETS:
            self.assertNotIn(snippet, patch_text)

    def test_phase2_patch_passes_static_boundary_audit(self):
        audit = audit_klipper_patch_boundary(PHASE2_PATCH_ARTIFACT.read_text())

        self.assertTrue(audit.passed)
        self.assertTrue(audit.disabled_by_default)
        self.assertTrue(audit.metadata_only_mode_enforced)
        self.assertTrue(audit.hardware_outputs_forced_disabled)
        self.assertTrue(audit.patch_config_metadata_only)
        self.assertTrue(audit.patch_config_hardware_outputs_disabled)
        self.assertTrue(audit.patch_config_safety_fields_present)
        self.assertTrue(audit.config_format_present)
        self.assertEqual(audit.missing_command_formats, ())
        self.assertEqual(audit.missing_response_formats, ())
        self.assertEqual(audit.configured_output_keys, ())
        self.assertEqual(audit.forbidden_hardware_snippets, ())

    def test_phase3_patch_is_stationary_af_bench_only(self):
        patch_text = PHASE3_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn("Phase 3 stationary AF bench support", patch_text)
        self.assertIn("stationary_af_bench", patch_text)
        self.assertIn("hardware outputs require stationary_af_bench", patch_text)
        self.assertIn("xvs_trigger_pin", patch_text)
        self.assertIn("led_white_pin", patch_text)
        self.assertIn("led_red_pin", patch_text)
        self.assertIn("led_green_pin", patch_text)
        self.assertIn("config_scanner_sync_output", added_source)
        self.assertIn("scanner_sync_run_stationary_af_test", added_source)
        self.assertIn("scanner_sync_outputs_safe", added_source)
        self.assertIn("scanner_sync_emit_frame_event(ss->oid, ss)", added_source)
        self.assertIn(
            "scanner_sync_schedule(ss, SSP_XVS_HIGH, ss->next_frame_clock)",
            added_source,
        )
        self.assertNotIn("scanner_sync_emit_frame_event(0, ss)", added_source)
        self.assertNotIn("scanner_sync_schedule(ss, SSP_PREPARE_AF, now)", added_source)

    def test_phase3_patch_does_not_add_motion_or_flash_paths(self):
        patch_text = PHASE3_PATCH_ARTIFACT.read_text()

        for snippet in FORBIDDEN_PHASE3_MOTION_OR_FLASH_SNIPPETS:
            self.assertNotIn(snippet, patch_text)

    def test_timed_output_sequence_patch_declares_experimental_command_binding(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn(
            SCANNER_SYNC_RUN_TIMED_OUTPUT_SEQUENCE_COMMAND,
            added_source,
        )
        self.assertIn("run_timed_output_sequence", added_source)
        self.assertIn(
            "scanner_sync_run_timed_output_sequence oid=%c seq=%u stripe_id=%u",
            added_source,
        )
        self.assertIn("seq_id=%u mode=%c start_condition=%c", added_source)
        self.assertIn("uint32_t stripe_id = args[2]", added_source)
        self.assertIn("ss->stripe_id = stripe_id", added_source)

    def test_timed_output_sequence_patch_defines_mks_logical_output_map(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        expected_mappings = (
            "SCANNER_SYNC_OUTPUT_LED_WHITE = 0x01",
            "SCANNER_SYNC_OUTPUT_LED_RED = 0x02",
            "SCANNER_SYNC_OUTPUT_LED_GREEN = 0x04",
            "SCANNER_SYNC_OUTPUT_HQ_XVS_SYNC = 0x08",
            "SS_OUTPUT_LED_WHITE = 0x01",
            "SS_OUTPUT_LED_RED = 0x02",
            "SS_OUTPUT_LED_GREEN = 0x04",
            "SS_OUTPUT_HQ_XVS_SYNC = 0x08",
            "hq_xvs_sync_pin",
        )
        for snippet in expected_mappings:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, patch_text)

        host_order = (
            added_source.index("SCANNER_SYNC_OUTPUT_LED_WHITE = 0x01"),
            added_source.index("SCANNER_SYNC_OUTPUT_LED_RED = 0x02"),
            added_source.index("SCANNER_SYNC_OUTPUT_LED_GREEN = 0x04"),
            added_source.index("SCANNER_SYNC_OUTPUT_HQ_XVS_SYNC = 0x08"),
        )
        mcu_order = (
            added_source.index("SS_OUTPUT_LED_WHITE = 0x01"),
            added_source.index("SS_OUTPUT_LED_RED = 0x02"),
            added_source.index("SS_OUTPUT_LED_GREEN = 0x04"),
            added_source.index("SS_OUTPUT_HQ_XVS_SYNC = 0x08"),
        )
        self.assertEqual(tuple(sorted(host_order)), host_order)
        self.assertEqual(tuple(sorted(mcu_order)), mcu_order)
        self.assertIn("case SS_OUTPUT_LED_WHITE:return SSO_LED_WHITE;", added_source)
        self.assertIn("case SS_OUTPUT_LED_RED:return SSO_LED_RED;", added_source)
        self.assertIn("case SS_OUTPUT_LED_GREEN:return SSO_LED_GREEN;", added_source)
        self.assertIn("case SS_OUTPUT_HQ_XVS_SYNC:return SSO_HQ_XVS_SYNC;", added_source)

    def test_timed_output_sequence_patch_uses_hq_xvs_sync_not_old_trigger_output(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn("hq_xvs_sync_pin", added_source)
        self.assertIn("SSO_HQ_XVS_SYNC", added_source)
        self.assertIn("SS_OUTPUT_HQ_XVS_SYNC", added_source)
        forbidden_added_snippets = (
            "xvs_trigger_pin",
            "OUTPUT_TRIGGER",
            "SSO_TRIGGER",
            "SS_OUTPUT_TRIGGER",
            "camera_trigger_pin",
        )
        for snippet in forbidden_added_snippets:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet, added_source)

    def test_timed_output_sequence_patch_parses_steps_and_validates_crc(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()

        expected_parser_snippets = (
            "SS_STEP_BYTES = 8",
            "encoded_steps_len != step_count * SS_STEP_BYTES",
            "scanner_sync_decode_timed_output_step",
            "step->output_mask = encoded[0]",
            "step->output_values = encoded[1]",
            "scanner_sync_read_u32_le(encoded + 2)",
            "scanner_sync_read_u16_le(encoded + 6)",
            "scanner_sync_crc32(encoded_steps, encoded_steps_len) != steps_crc32",
        )
        for snippet in expected_parser_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, patch_text)

    def test_timed_output_sequence_patch_latches_outputs_and_supports_pauses(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()

        self.assertIn(
            "ss->latched_outputs = (ss->latched_outputs & ~output_mask)",
            patch_text,
        )
        self.assertIn("| (output_values & output_mask)", patch_text)
        self.assertIn("A pause step has output_mask=0", patch_text)
        self.assertIn("if (step->output_mask)", patch_text)
        self.assertIn("ss->timer.waketime += step->delay_ticks", patch_text)

    def test_timed_output_sequence_patch_handles_repeat_count(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()

        self.assertIn("uint32_t repeat_count = args[7]", patch_text)
        self.assertIn("ss->repeat_count = repeat_count", patch_text)
        self.assertIn("repeat_count=0 repeats until explicit stop", patch_text)
        self.assertIn("ss->repeat_count && ss->repeat_index >= ss->repeat_count", patch_text)
        self.assertIn("scanner_sync_apply_output_state(ss, ss->idle_output_mask", patch_text)
        self.assertIn("ss->sequence_active = 0", patch_text)
        self.assertIn("ss->active = 0", patch_text)
        self.assertIn("ss->timer_active = 0", patch_text)
        self.assertIn("return SF_DONE", patch_text)
        self.assertIn("return SF_RESCHEDULE", patch_text)

    def test_timed_output_sequence_patch_applies_safe_state_on_stop_shutdown_and_fault(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn("scanner_sync_timed_sequence_safe_stop(ss)", patch_text)
        self.assertIn("scanner_sync_timed_sequence_fault(ss)", patch_text)
        self.assertIn("scanner_sync_outputs_safe(ss)", patch_text)
        self.assertIn(
            "scanner_sync_apply_output_state(ss, ss->safe_output_mask,"
            "ss->safe_output_values)",
            added_source.replace("\n", ""),
        )
        self.assertIn("command_scanner_sync_stop", patch_text)
        self.assertIn("scanner_sync_shutdown", patch_text)
        self.assertIn("if (ss->timer_active)", patch_text)
        self.assertIn("sched_del_timer(&ss->timer)", patch_text)
        self.assertIn("ss->safe_output_mask = SS_KNOWN_OUTPUT_MASK", patch_text)
        self.assertIn("ss->safe_output_values = 0", patch_text)
        self.assertIn(
            "+    uint8_t timed_sequence_active = ss->sequence_active;\n"
            "+    scanner_sync_timed_sequence_safe_stop(ss);\n"
            "+    if (timed_sequence_active)\n"
            "+        scanner_sync_emit_timed_sequence_status(\n"
            "+            oid, ss, SS_STATUS_STOPPED, SS_REASON_HOST_STOP);\n"
            "     scanner_sync_emit_terminal(oid, ss, reason);",
            patch_text,
        )
        self.assertNotIn(
            "+    scanner_sync_outputs_safe(ss);\n"
            "     scanner_sync_emit_terminal(oid, ss, reason);",
            patch_text,
        )
        self.assertIn(
            "+        scanner_sync_timed_sequence_safe_stop(ss);\n"
            "     }\n"
            " }\n"
            " DECL_SHUTDOWN(scanner_sync_shutdown);",
            patch_text,
        )

    def test_timed_output_sequence_patch_emits_status_metadata(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn("scanner_sync_timed_output_sequence_status", added_source)
        self.assertIn("scanner_sync_emit_timed_sequence_status", added_source)
        self.assertIn("scanner_sync_emit_timed_sequence_rejected", added_source)
        for snippet in (
            "SS_STATUS_ACCEPTED = 0",
            "SS_STATUS_REJECTED = 1",
            "SS_STATUS_STARTED = 2",
            "SS_STATUS_COMPLETED = 3",
            "SS_STATUS_STOPPED = 4",
            "SS_STATUS_FAULT = 5",
            "SS_REASON_INVALID_COMMAND = 1",
            "SS_REASON_STARTED = 2",
            "SS_REASON_FINITE_COMPLETION = 3",
            "SS_REASON_HOST_STOP = 4",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, added_source)
        self.assertIn("SS_STATUS_ACCEPTED, SS_REASON_ACCEPTED", added_source)
        self.assertIn("SS_STATUS_STARTED, SS_REASON_STARTED", added_source)
        self.assertIn("SS_STATUS_COMPLETED, SS_REASON_FINITE_COMPLETION", added_source)
        self.assertIn("SS_STATUS_STOPPED, SS_REASON_HOST_STOP", added_source)
        self.assertIn("SS_STATUS_FAULT, SS_REASON_FAULT", added_source)

    def test_timed_output_sequence_patch_carries_step_flags_into_frame_event(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()
        added_source = _joined_added_source(patch_text)

        self.assertIn("SS_KNOWN_EVENT_FLAGS", added_source)
        self.assertIn("step->event_flags & ~SS_KNOWN_EVENT_FLAGS", added_source)
        self.assertIn("scanner_sync_emit_timed_sequence_frame_event", added_source)
        self.assertIn("uint16_t event_flags", added_source)
        self.assertIn("flags=%u", added_source)
        self.assertIn("event_flags);", patch_text)
        self.assertIn(
            "scanner_sync_emit_timed_sequence_frame_event(ss->oid, ss, step->event_flags)",
            added_source,
        )

    def test_timed_output_sequence_patch_does_not_add_motion_or_flash_paths(self):
        patch_text = TIMED_OUTPUT_SEQUENCE_PATCH_ARTIFACT.read_text()

        for snippet in FORBIDDEN_TIMED_OUTPUT_SEQUENCE_MOTION_HOMING_OR_FLASH_SNIPPETS:
            self.assertNotIn(snippet, patch_text)

    def test_static_boundary_audit_blocks_enabled_by_default_patch(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text().replace(
            "config.getboolean('enable', False)",
            "config.getboolean('enable', True)",
        )
        audit = audit_klipper_patch_boundary(patch_text)

        self.assertFalse(audit.passed)
        self.assertIn("scanner_sync_enable_default_not_false", audit.blockers)

    def test_static_boundary_audit_blocks_missing_hardware_output_guard(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text().replace(
            "+        if self.hardware_outputs_enabled:\n"
            "+            raise config.error(\n"
            "+                \"scanner_sync hardware outputs are not supported\")\n",
            "",
        )
        audit = audit_klipper_patch_boundary(patch_text)

        self.assertFalse(audit.passed)
        self.assertIn("hardware_outputs_not_forced_disabled", audit.blockers)

    def test_static_boundary_audit_blocks_hardware_enabled_patch_config(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text().replace(
            "hardware_outputs_enabled: false\n",
            "hardware_outputs_enabled: true\n",
        )
        audit = audit_klipper_patch_boundary(patch_text)

        self.assertFalse(audit.passed)
        self.assertFalse(audit.patch_config_hardware_outputs_disabled)
        self.assertIn("scanner_sync_config_hardware_outputs_enabled", audit.blockers)

    def test_static_boundary_audit_blocks_missing_command_format(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text().replace(
            "scanner_sync_stop oid=%c reason=%c",
            "scanner_sync_stop oid=%c",
        )
        audit = audit_klipper_patch_boundary(patch_text)

        self.assertFalse(audit.passed)
        self.assertIn("scanner_sync_mcu_commands_missing", audit.blockers)
        self.assertIn(
            "scanner_sync_stop oid=%c reason=%c",
            audit.missing_command_formats,
        )

    def test_static_boundary_audit_blocks_missing_response_format(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text().replace(
            "scanner_sync_z_rejected oid=%c seq=%u reason=%c status=%c",
            "scanner_sync_z_rejected oid=%c seq=%u status=%c",
        )
        audit = audit_klipper_patch_boundary(patch_text)

        self.assertFalse(audit.passed)
        self.assertIn("scanner_sync_response_formats_missing", audit.blockers)
        self.assertIn(
            "scanner_sync_z_rejected oid=%c seq=%u reason=%c status=%c",
            audit.missing_response_formats,
        )

    def test_static_boundary_audit_blocks_configured_output_pin(self):
        patch_text = PHASE2_PATCH_ARTIFACT.read_text().replace(
            "hardware_outputs_enabled: false\n",
            "hardware_outputs_enabled: false\n+camera_trigger_pin: PA1\n",
        )
        audit = audit_klipper_patch_boundary(patch_text)

        self.assertFalse(audit.passed)
        self.assertEqual(audit.configured_output_keys, ("camera_trigger_pin",))
        self.assertIn("scanner_sync_output_pins_configured", audit.blockers)

    def test_stage_b_docs_require_review_checklist_before_live_execution(self):
        plan_text = (
            REPO_ROOT / "docs" / "klipper" / "klipper-live-metadata-stage-b-plan.md"
        ).read_text()
        protocol_text = (
            REPO_ROOT / "docs" / "klipper" / "klipper-scanner-sync-live-protocol-contract.md"
        ).read_text()
        patch_proposal_text = (
            REPO_ROOT / "docs" / "klipper" / "klipper-scanner-sync-patch-proposal.md"
        ).read_text()
        readiness_text = (
            REPO_ROOT / "docs" / "klipper" / "klipper-live-metadata-readiness.md"
        ).read_text()
        checklist_text = (REPO_ROOT / STAGE_B_CHECKLIST).read_text()

        self.assertIn(STAGE_B_CHECKLIST, plan_text)
        self.assertIn(STAGE_B_CHECKLIST, readiness_text)
        self.assertIn("Status: planning and review artifact only", checklist_text)
        self.assertIn("hardware_outputs_enabled: false", checklist_text)
        self.assertIn("clean completion emits no terminal", plan_text)
        self.assertIn("clean stripe completion", protocol_text)
        self.assertIn("clean completion emits no terminal", patch_proposal_text)
        self.assertNotIn("stop/fault/completion", plan_text)
        self.assertNotIn("stop, completion or fault", patch_proposal_text)
        self.assertIn('"expected_frame_count":2', checklist_text)
        self.assertNotIn('"expected_frame_count":1,"last_frame_id":1', checklist_text)

    def test_stage_b_capture_script_remains_read_only(self):
        script_text = (REPO_ROOT / STAGE_B_CAPTURE_SCRIPT).read_text()

        self.assertIn("Read-only Stage B evidence capture", script_text)
        self.assertIn("systemctl is-active klipper", script_text)
        self.assertIn("tail -120", script_text)
        for snippet in FORBIDDEN_LIVE_SCRIPT_SNIPPETS:
            self.assertNotIn(snippet, script_text)


def _joined_added_source(patch_text: str) -> str:
    """Join added patch lines so split C/Python string literals are searchable."""

    added_lines = [
        line[1:].strip()
        for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "".join(added_lines).replace('"', "").replace("'", "")


if __name__ == "__main__":
    unittest.main()
