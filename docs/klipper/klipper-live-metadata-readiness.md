# Klipper Live Metadata Readiness

Status: software-only readiness model. This document does not approve firmware
flashing, enabling scanner-sync, GPIO toggling, motor motion, camera triggering
or LED output.

## Purpose

The live Pi 5 now proves a narrow Stage A boundary:

- the MKS USB serial path is restored;
- Klipper can connect to the MKS MCU;
- the scanner-sync host extra can be installed;
- `[scanner_sync] enable: false` can be present in `printer.cfg`;
- Klipper can restart and configure the MCU with scanner-sync disabled.

This is not evidence that scanner-sync is ready to run. The live MKS firmware
does not contain scanner-sync MCU commands yet.

Disabled preflight and enabled metadata-only readiness are separate states.
`enable: false` may be safe-disabled when the host extra and config are present
and scanner-sync does not command outputs. That disabled preflight state is not
blocked by missing MCU scanner-sync dictionary formats or missing response
dispatch, because scanner-sync is not enabled. It also does not approve changing
to `enable: true`.

## Readiness States

The local readiness model is implemented in
`src/klipper_adapter/live_metadata.py`.

| Stage | Meaning | Enable allowed |
|---|---|---|
| `not_installed` | Host extra, config section or MCU connection is missing | No |
| `host_extra_loaded_disabled` | Disabled preflight: host extra and config are present, but `enable: false`; safe-disabled only, not enabled readiness | No |
| `host_extra_enabled_without_mcu` | Config requests enable, but required MCU command formats are missing | No |
| `host_extra_enabled_without_responses` | MCU commands exist, but response formats or dispatch are missing | No |
| `unsafe_hardware_outputs` | Metadata-only mode is not enforced or hardware outputs are enabled | No |
| `unsupported_protocol` | Config requests a protocol version unsupported by this contract | No |
| `ready_to_enable` | Enabled metadata-only readiness: explicit reviewed config, dictionary command/response formats, response dispatch and no output pins are present | Software-ready only |

The current live MKS state is expected to evaluate as:

```text
stage: host_extra_loaded_disabled
status: safe_disabled
can_enable_scanner_sync: false
```

The current state is allowed to remain installed as disabled preflight. It must
not be described as enabled metadata-only readiness.

## Enabled Metadata-Only Readiness Gate

`ready_to_enable` requires all of these reviewed inputs at the same time:

- captured `[scanner_sync]` config explicitly requests `enable: true`,
  `mode: metadata_only` and `hardware_outputs_enabled: false`;
- scanner-sync output pins are absent, unset or `none`;
- the reviewed MCU dictionary contains every required scanner-sync command
  format and response format;
- host response dispatch is reviewed and available for every expected
  scanner-sync response;
- protocol version is supported by this contract.

If any item is missing or ambiguous, readiness must remain blocked. Missing
enabled-safety fields are unknown values, not safe defaults.

## Required Command Formats

The readiness model uses the same command names as the dry-run registration
plan:

- `scanner_sync_start`
- `scanner_sync_stop`
- `scanner_sync_schedule_z`
- `scanner_sync_arm_af_window`
- `scanner_sync_fire_af_window_now`

If any of these command formats are missing from the live MCU dictionary,
`[scanner_sync] enable: true` must remain blocked.

`scanner_sync_arm_af_window` is required for the position-indexed scan path.
`scanner_sync_fire_af_window_now` is required only for local no-motion bench
diagnostics and does not authorize production scan timing from host time.

## Required Response Formats And Dispatch

Readiness also requires:

- every expected scanner-sync response format is registered;
- dispatch preserves the exact project event type for each response;
- status fields are decoded per event type;
- `FRAME_EVENT flags` are either `0` or explicitly documented before use.

Missing response formats or missing response dispatch block readiness even if
all command formats are present.

## Required Event Names

The event names remain uniform across firmware, Pi code and docs:

- `scanner_sync_frame_event` -> `FRAME_EVENT`
- `scanner_sync_scheduler_terminal` -> `SCHEDULER_TERMINAL`
- `scanner_sync_z_scheduled` -> `Z_SCHEDULED`
- `scanner_sync_z_applied` -> `Z_APPLIED`
- `scanner_sync_z_rejected` -> `Z_REJECTED`

`FRAME_EVENT` is still the source of frame identity, coordinates, LED pattern
and Z state. The Pi must not infer frame identity or coordinates from Linux
wall-clock time or camera frame arrival time.

## Current Boundary

Allowed without hardware:

- run local readiness tests;
- compare expected command/response names against a Klipper dictionary dump;
- prepare a reviewed firmware patch in a disposable Klipper checkout;
- document rollback and stop conditions.

The dictionary comparison is implemented in
`src/klipper_adapter/dictionary.py`. It can consume already-captured
`out/klipper.dict` text or log excerpts and produce the command/response format
sets used by the readiness model. This is a passive check only; it does not open
serial ports or enable scanner-sync.

Use the CLI entry point for local checks:

```bash
scanner-klipper-readiness out/klipper.dict \
  --host-extra-present \
  --config-section-present \
  --config-enable \
  --mcu-connected \
  --response-dispatch-available \
  --require-ready
```

For one-off checks without installing the package entry point:

```bash
PYTHONPATH=src python -m klipper_adapter.cli out/klipper.dict \
  --host-extra-present \
  --config-section-present \
  --config-enable \
  --mcu-connected \
  --response-dispatch-available
```

Prefer captured `printer.cfg` input over manual config flags when checking live
readiness:

```bash
scanner-klipper-readiness out/klipper.dict \
  --config-file printer.cfg \
  --host-extra-present \
  --mcu-connected \
  --response-dispatch-available
```

The config parser reads only `[scanner_sync]`. It does not connect to Klipper,
restart services or modify the live configuration.

Dictionary presence alone is not enough to run live scanner-sync. Readiness
still requires:

- MCU dictionary format
  `config_scanner_sync oid=%c protocol_version=%c hardware_outputs_enabled=%c`;
- reviewed host response dispatch;
- reviewed response formats for every expected scanner-sync event;
- reviewed config showing no scanner-sync output pins;
- live metadata ingest uses validate-before-forward behavior, so records that
  fail sequence validation are not forwarded to downstream consumers;
- explicit `mode: metadata_only` in captured `[scanner_sync]`;
- explicit `hardware_outputs_enabled: false` in captured `[scanner_sync]`;
- no configured scanner-sync output, pin, trigger, strobe or LED mapping keys
  except values explicitly set to `none`/`unset`/disabled;
- completed passive MKS flash/connectivity gate, checked with
  `validate_mks_flash_gate_yaml`, including captured `.config`, dictionary,
  binary, active `printer.cfg`, serial paths, rollback plan and no unresolved
  `identify_response` timeout;
- live config review;
- explicit firmware flash and rollback plan.

If `[scanner_sync] enable: true` is present but `mode` or
`hardware_outputs_enabled` is missing, readiness must remain blocked. Missing
safety fields are treated as unknown, not as safe defaults.

When response callbacks are available, captured JSONL callback payloads can be
decoded offline into project protocol records:

```bash
scanner-klipper-decode-events captured-scanner-sync-events.jsonl \
  --scan-id scan_001 \
  --trigger-output-name mks_z_plus \
  --pattern BF_WHITE \
  --pattern AF_RED_GREEN
```

Each input line is a captured host callback wrapper:

```json
{"event_type":"FRAME_EVENT","params":{"frame_id":1,"stripe_id":0,"stripe_frame_index":0,"pattern_id":0,"position_axis":0,"event_position":1000,"x_count":1000,"y_count":0,"z_count":0,"mcu_time_us":5000,"status":0,"flags":0}}
```

The decoder remains passive. It validates uniform event names and emits protocol
JSONL records, but it does not communicate with Klipper or hardware.

Use stream validation for captured event sequences before trusting live metadata
tests:

```bash
scanner-klipper-decode-events captured-scanner-sync-events.jsonl \
  --scan-id scan_001 \
  --pattern BF_WHITE \
  --pattern AF_RED_GREEN \
  --validate-stream
```

This checks that decoded `FRAME_EVENT` records are contiguous by `frame_id` and
`stripe_frame_index`, and that terminal counters match decoded frame records.
It also checks Z acknowledgement ordering: `Z_APPLIED` must follow a prior
`Z_SCHEDULED` for the same `seq`, and rejected `seq` values must not later be
reported as applied. It is still an offline check over captured text only.

For a compact acceptance artifact, emit a summary JSON object instead of the
decoded records:

```bash
scanner-klipper-decode-events captured-scanner-sync-events.jsonl \
  --scan-id scan_001 \
  --pattern BF_WHITE \
  --pattern AF_RED_GREEN \
  --summary-json
```

The summary includes `accepted`, `record_count`, event types, frame counts,
terminal counts, first/last frame ids, next frame id and stripes seen. It is an
offline acceptance report for captured metadata text only; it does not prove
camera exposure, LED timing, motion timing or hardware output behavior.

The simulator can produce synthetic callback JSONL fixtures for this same path.
Those fixtures are for codec/replay testing only; they are not evidence that
the live MKS firmware emits scanner-sync events.

Before any Stage B live metadata attempt, complete
`docs/klipper/klipper-live-metadata-stage-b-review-checklist.md` in a reviewed issue or
PR. The checklist must include the exact Klipper commit, host-extra diff, MCU
patch diff, firmware build and flash procedure, rollback path, config diff,
expected capture JSONL and expected summary JSON.

Not allowed by this readiness model:

- firmware flashing;
- setting `[scanner_sync] enable: true` on the live Pi;
- sending scanner-sync commands;
- toggling GPIO;
- moving axes;
- triggering the camera;
- driving LEDs.
