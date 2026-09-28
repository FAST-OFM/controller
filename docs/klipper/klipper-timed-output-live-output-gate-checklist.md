# Klipper Timed-Output Live-Output Gate Checklist

Status: software-only review artifact. This document does not approve firmware
flashing, live controller access, GPIO toggling, camera triggering, LED output,
motor motion or homing.

Use this checklist before any stationary AF or timed-output bench live-output
test. The first acceptable hardware action after this checklist is still a
separately approved, no-motion, one-subsystem-at-a-time test.

## Scope

This gate covers only the reviewed transition from safe-disabled scanner-sync
configuration to a proposed `timed_output_sequence_bench` configuration.

It does not approve:

- firmware flashing;
- motor or Z motion;
- homing;
- camera-side XVS connection or triggering;
- LED power output;
- loaded LED gate validation;
- live Klipper writes or restarts.

## Required Static Package

The owning issue or PR must include a YAML package with this top-level key:

```yaml
live_output_gate:
  gate_id: stationary-af-timed-output-live-output-gate-v1
  review_issue_or_pr: scanner-firmware#220
  live_pi_hostname: UNKNOWN
  mks_flash_gate_ref: UNKNOWN
  firmware_artifact:
    commit: UNKNOWN
    binary_path: UNKNOWN
    dictionary_path: UNKNOWN
    patch_artifact_path: docs/patches/klipper-scanner-sync-timed-output-sequence.patch
  printer_cfg:
    active_printer_cfg_path: UNKNOWN
    baseline_backup_path: UNKNOWN
  rollback:
    plan_path: UNKNOWN
    previous_firmware_artifact: UNKNOWN
    previous_printer_cfg_backup: UNKNOWN
  current_state:
    klipper_service_active: false
    mks_serial_path_present: false
    mcu_handshake_restored: false
    identify_response_timeout_observed: true
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
      pin: UNKNOWN
      connector: UNKNOWN
      polarity: UNKNOWN
      load_path: UNKNOWN
      default_state: UNKNOWN
      verified_loaded_behavior: false
      level_shift_reviewed: false
    led_white_gate:
      pin: UNKNOWN
      connector: UNKNOWN
      polarity: UNKNOWN
      load_path: UNKNOWN
      default_state: UNKNOWN
      verified_loaded_behavior: false
      external_current_limit_reviewed: false
    led_red_gate:
      pin: UNKNOWN
      connector: UNKNOWN
      polarity: UNKNOWN
      load_path: UNKNOWN
      default_state: UNKNOWN
      verified_loaded_behavior: false
      external_current_limit_reviewed: false
    led_green_gate:
      pin: UNKNOWN
      connector: UNKNOWN
      polarity: UNKNOWN
      load_path: UNKNOWN
      default_state: UNKNOWN
      verified_loaded_behavior: false
      external_current_limit_reviewed: false
  stop_conditions:
    - unexpected_output_state
    - unexpected_current_or_heating
    - camera_trigger_mismatch
    - communication_fault
    - operator_uncertainty
  stop_conditions_reviewed: false
  expected_observation: UNKNOWN
  live_test_gate:
    required: true
    approved: false
    executed: false
```

Unknowns must remain `UNKNOWN`. Do not replace them with inferred values.

## Static Validator

Validate the package with
`validate_live_output_gate_yaml` from
`scanner_firmware.adapters.klipper_adapter.readiness.live_output.gate`.

A passing result means only that the review package is complete enough for
human review. It never authorizes live execution. The validator always returns:

- `software_only=true`;
- `live_hardware_access_used=false`;
- `can_execute_live_output=false`;
- `can_flash_firmware=false`.

## Required Before Review

- The MKS flash/connectivity gate is referenced and complete enough for review.
- The current scanner-sync config is still disabled with hardware outputs off.
- The proposed config is explicitly a no-motion `timed_output_sequence_bench`
  review target.
- The timed-output patch artifact matches the cross-repo status lifecycle:
  `accepted -> started -> completed|stopped|fault`; `rejected` is a standalone
  terminal rejection.
- `scanner_sync_stop` emits timed-output `stopped` only for an active
  timed-output sequence.
- All-outputs-off evidence is finite one-shot safe-off evidence.
- The reviewed procedure commands no motors, no homing and no Z motion.
- Every LED output records external current limiting before loaded testing.
- HQ XVS records the reviewed level-shift path before camera-side connection.
- Stop conditions and post-stop safe-state observation are explicit.

## Required Stop Conditions

Stop immediately on:

- unexpected output state or polarity;
- unexpected current, heating, flicker or brightness;
- camera trigger mismatch or extra/missing pulse;
- communication fault;
- any motor or homing activity;
- operator uncertainty.

After a stop, run or verify all outputs off before continuing.
