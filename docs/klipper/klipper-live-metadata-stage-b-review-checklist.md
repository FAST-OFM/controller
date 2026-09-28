# Klipper Live Metadata Stage B Review Checklist

Status: planning and review artifact only. This document does not approve live
execution, firmware flashing, GPIO toggling, motion, camera triggering or LED
driving.

Use this checklist to prepare the reviewed issue or PR required before a Stage B
metadata-only live test. Unknown values must remain `UNKNOWN` until measured or
captured from the live system.

## Scope

Stage B is limited to proving metadata transport:

- scanner-sync host extra loads in metadata-only mode;
- MCU-side scanner-sync command and response formats are present after a
  reviewed firmware patch;
- captured scanner-sync callback payloads decode to project protocol records;
- `FRAME_EVENT` identity and coordinates come from MCU metadata;
- Z acknowledgements use `Z_SCHEDULED`, `Z_APPLIED` and `Z_REJECTED`;
- incomplete host-stop or fault terminal state uses `SCHEDULER_TERMINAL`;
- clean completion is represented by expected contiguous `FRAME_EVENT` records
  and no `SCHEDULER_TERMINAL`;
- all decoded records remain `hardware_outputs_enabled=false`.

Stage B does not prove:

- camera exposure timing;
- LED timing or brightness;
- motor timing accuracy;
- autofocus performance;
- clinical, diagnostic, regulatory or patient-safety behavior.

## Required Review Fields

Every field must be completed in the reviewed issue or PR before live execution:

```yaml
stage_b_review:
  reviewer: UNKNOWN
  review_issue_or_pr: UNKNOWN
  live_pi_hostname: UNKNOWN
  klipper_commit: UNKNOWN
  klipper_worktree_status: UNKNOWN
  scanner_sync_host_extra_diff: UNKNOWN
  scanner_sync_mcu_patch_diff: UNKNOWN
  mks_board_identity:
    board_name: UNKNOWN
    board_revision: UNKNOWN
    mcu_model: UNKNOWN
    bootloader_or_flash_method: UNKNOWN
  firmware_build:
    command: UNKNOWN
    output_artifact: UNKNOWN
    expected_dictionary_path: UNKNOWN
  firmware_flash:
    method: UNKNOWN
    exact_command_or_ui_steps: UNKNOWN
    rollback_method: UNKNOWN
    rollback_artifact: UNKNOWN
  printer_cfg:
    baseline_backup_path: UNKNOWN
    scanner_sync_diff: UNKNOWN
    enable: false
    mode: metadata_only
    hardware_outputs_enabled: false
    output_pins_configured: false
  expected_scanner_sync_formats:
    commands: UNKNOWN
    responses: UNKNOWN
  expected_capture:
    jsonl_path: UNKNOWN
    summary_json_path: UNKNOWN
    expected_record_count: UNKNOWN
    expected_frame_count: UNKNOWN
    expected_terminal_count: UNKNOWN
    expected_first_frame_id: UNKNOWN
    expected_last_frame_id: UNKNOWN
    expected_stripes_seen: UNKNOWN
  stop_conditions_reviewed: false
```

## MKS Flash And Connectivity Gate

Before any MKS firmware flash attempt is reviewed, the issue or PR must also
include a completed passive flash gate package. This gate is software-only: it
checks captured text fields and never opens serial, restarts Klipper, sends
commands or flashes firmware.

Unknown values must stay `UNKNOWN`. The `identify_response` timeout is a hard
blocker until a later captured state proves the MCU handshake is restored.

```yaml
mks_flash_gate:
  live_pi_hostname: UNKNOWN
  klipper_commit: UNKNOWN
  captured_artifacts:
    klipper_config_path: UNKNOWN
    klipper_dictionary_path: UNKNOWN
    klipper_binary_path: UNKNOWN
    active_printer_cfg_path: UNKNOWN
  serial_paths:
    mks_by_path: UNKNOWN
    mks_by_id: UNKNOWN
  connectivity:
    klipper_service_active: false
    mks_serial_path_present: false
    mcu_handshake_restored: false
    identify_response_timeout_observed: true
  firmware_flash:
    bootloader_or_flash_method: UNKNOWN
    exact_command_or_ui_steps: UNKNOWN
  rollback:
    plan_path: UNKNOWN
    previous_klipper_ref: UNKNOWN
    previous_firmware_artifact: UNKNOWN
    printer_cfg_backup_path: UNKNOWN
  scanner_sync_config:
    enable: false
    metadata_only_mode: true
    hardware_outputs_enabled: false
    output_pins_configured: false
```

The package can be checked with
`validate_mks_flash_gate_yaml` from
`scanner_firmware.adapters.klipper_adapter.readiness.mks_flash_gate`. A passing
result means the review package is complete enough for review. It does not
authorize live execution or flashing; the returned `can_execute_flash` value is
always false in this software-only repository.

## Pre-Execution Gates

All gates must pass before any live Stage B action. A disabled preflight and an
enabled metadata-only readiness test have different evidence requirements; do
not use evidence for one state to approve the other.

The reviewed YAML package can be checked as static data with
`validate_stage_b_review_yaml` from
`scanner_firmware.adapters.klipper_adapter.readiness.stage_b_review`. The
validator only parses captured YAML and rejects incomplete packages, `UNKNOWN`
required values, unsafe scanner-sync output pins, hardware outputs, non
metadata-only mode and any live-execution approval claim. Passing this validator
does not approve execution; it only confirms that the review package is complete
enough for human review.

Disabled preflight may be treated as safe-disabled only when:

- Klipper is active before scanner-sync changes.
- MKS serial path is present and stable.
- `printer.cfg` backup path is recorded.
- Existing `[scanner_sync]` state is reviewed and keeps `enable: false`.
- Scanner-sync does not command GPIO, motor, camera or LED outputs.
- Output pins remain unset or `none`.

Safe-disabled preflight does not require scanner-sync MCU command formats,
scanner-sync response formats or host response dispatch to be present. It also
does not authorize enabling scanner-sync.

Enabled metadata-only readiness requires all of the following reviewed evidence
before `enable: true` is used:

- Completed passive MKS flash/connectivity gate with captured `.config`,
  dictionary, binary, active `printer.cfg`, serial paths and rollback plan.
- No unresolved `identify_response` timeout; Klipper must have restored the MKS
  MCU handshake before any flash step is considered.
- Host extra diff is reviewed.
- MCU patch diff is reviewed.
- Firmware build command is reviewed.
- Firmware flash and rollback procedure are reviewed.
- Patch, dictionary, response dispatch and config evidence are accepted.
- Reviewed MCU dictionary contains required scanner-sync command formats.
- Reviewed MCU dictionary contains required scanner-sync response formats.
- Reviewed host response dispatch is available for every expected
  scanner-sync response.
- Reviewed metadata ingest validates each candidate sequence before forwarding
  records to downstream consumers.
- Reviewed `[scanner_sync]` config explicitly contains `enable: true`,
  `mode: metadata_only` and `hardware_outputs_enabled: false`.
- Missing `mode` or `hardware_outputs_enabled` values remain `UNKNOWN`; they
  must not be inferred as safe defaults for an enabled config.
- Scanner-sync output, pin, trigger, strobe and LED mapping keys remain absent
  or explicitly set to `none`/`unset`/disabled.
- Candidate camera and LED pins from board discovery are not configured as
  active outputs for Stage B.

## Passive Readiness Commands

Capture current read-only evidence on the Pi:

```bash
scripts/capture-klipper-stage-b-evidence.sh > stage-b-evidence.md
```

The script only reads files, service state, serial symlinks and logs. It must
not be edited to restart Klipper, flash firmware, send G-code, open serial
devices, toggle GPIO, move axes, trigger the camera or drive LEDs.

These commands are passive file/config checks. They do not open live serial
ports or send Klipper commands when run against captured files:

```bash
scanner-klipper-readiness out/klipper.dict \
  --config-file ~/printer_data/config/printer.cfg \
  --require-ready
```

The command above is allowed only after `out/klipper.dict` and `printer.cfg`
are captured or reviewed for enabled metadata-only readiness, and after host
response dispatch has been reviewed. If `--require-ready` fails, enabled
readiness remains blocked. A failed enabled-readiness check does not make an
unchanged `enable: false` preflight unsafe by itself.

Decode a captured callback JSONL file:

```bash
scanner-klipper-decode-events captured-scanner-sync-events.jsonl \
  --scan-id scan_001 \
  --pattern BF_WHITE \
  --pattern AF_RED_GREEN \
  --validate-stream
```

Create the required acceptance summary:

```bash
scanner-klipper-decode-events captured-scanner-sync-events.jsonl \
  --scan-id scan_001 \
  --pattern BF_WHITE \
  --pattern AF_RED_GREEN \
  --summary-json \
  --expect-record-count EXPECTED_RECORD_COUNT \
  --expect-frame-count EXPECTED_FRAME_COUNT \
  --expect-terminal-count EXPECTED_TERMINAL_COUNT \
  --expect-first-frame-id EXPECTED_FIRST_FRAME_ID \
  --expect-last-frame-id EXPECTED_LAST_FRAME_ID \
  --expect-stripes-seen EXPECTED_STRIPE_IDS \
  > captured-scanner-sync-summary.json
```

`EXPECTED_STRIPE_IDS` is a comma-separated list such as `0` or `0,1`. These
expected values must come from the reviewed Stage B plan, not from hidden chat
memory.

## Expected Capture JSONL Shape

The reviewed plan must include expected callback payload shapes. Values below
are examples only:

```jsonl
{"event_type":"FRAME_EVENT","params":{"frame_id":1,"stripe_id":0,"stripe_frame_index":0,"pattern_id":0,"position_axis":0,"event_position":1000,"x_count":1000,"y_count":0,"z_count":0,"mcu_time_us":5000,"status":0,"flags":0}}
{"event_type":"SCHEDULER_TERMINAL","params":{"stripe_id":0,"status":0,"reason":0,"emitted_frame_count":1,"expected_frame_count":2,"last_frame_id":1,"next_frame_id":2,"next_stripe_frame_index":1,"mcu_time_us":6000}}
```

Acceptance requires:

- every line is valid JSON;
- every payload has `event_type` and object `params`;
- acceptance commands do not accept `type` as an alias for `event_type`;
- event names use project names exactly;
- `FRAME_EVENT frame_id` values are contiguous;
- each stripe starts at `stripe_frame_index=0`;
- `stripe_frame_index` values are contiguous per stripe;
- no `FRAME_EVENT` for a stripe appears after that stripe's
  `SCHEDULER_TERMINAL`;
- terminal counters match decoded frame records;
- terminal `expected_frame_count` is greater than `emitted_frame_count`;
- Z acknowledgement ordering is valid;
- decoded protocol records set `hardware_outputs_enabled=false`.

## Stop Conditions

Stop immediately and roll back if:

- MKS serial path disappears;
- CH341 or MCU reconnect errors appear;
- Klipper fails to restart cleanly;
- expected scanner-sync command formats are missing after patch evidence;
- expected scanner-sync response formats are missing after patch evidence;
- `config_scanner_sync oid=%c protocol_version=%c hardware_outputs_enabled=%c`
  is missing from the reviewed target dictionary;
- scanner-sync config would enable any physical output;
- any step would drive motors, GPIO, LEDs or camera trigger;
- captured events omit frame identity or coordinates;
- decoded capture summary is not accepted;
- rollback path is unclear.

## Human Hardware Boundary

The following actions require explicit human execution at the machine:

- power-cycling MKS;
- changing wiring;
- pressing boot/reset buttons;
- flashing firmware;
- probing pins;
- connecting oscilloscope or logic analyzer;
- verifying that no motor, LED or camera output occurs.

Record the observed result in the reviewed issue or PR. Do not replace unknown
hardware values with guesses.
