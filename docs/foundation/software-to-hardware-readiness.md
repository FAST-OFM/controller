# Software To Hardware Readiness

Status: software-only readiness audit. This document does not approve SSH to a
Pi, firmware flashing, serial/GPIO access, motor motion, homing, camera
triggering, LED output, or hardware runtime changes.

## Scope

This audit covers the first V1 hardware test path across `scanner-pi`,
`scanner-firmware` and `scanner-core` for a manual-centered, bounded,
non-scan bring-up without homing.

The requested test shape is intentionally narrower than a scan workflow:

- operator manually centers the stage before any commanded motion;
- no homing commands are issued;
- no hard-stop approaches are allowed;
- X/Y motion is bounded to a small envelope around the declared manual center;
- Z motion is limited to a minimal focus-search range after manual focus setup;
- HQ camera XVS work is treated as a sync-sink/electrical-readiness question,
  not as a replacement for MCU `FRAME_EVENT` identity;
- MKS scanner-sync live metadata must remain metadata-only until reviewed;
- Arduino LED brightness setpoints and MKS LED gate timing remain separate.

Normal scan workflows still require homing for X, Y and Z.

## Current Software Evidence

### scanner-pi

Ready for software-only replay:

- `fixtures/config/pi_runtime_config_split_v1.json` uses `dummy_replay`,
  `dry_run_replay`, `replay_jsonl`, `require_frame_event: true` and
  `coordinate_source: mcu_frame_event`.
- `tests/test_acquisition_runtime_readiness.py` verifies that Pi readiness is
  `ready_for_dry_run` only, with `hardware_outputs_enabled: false`.
- `scanner/illumination/brightness.py` keeps Arduino control behind
  `BrightnessController` for slow brightness/VREF setpoints only. It is not a
  frame-synchronous LED gate, camera trigger, frame identity, or coordinate
  source.
- The Pi hardware evidence placeholder keeps controller pins, rails, current
  limits, homing/travel, LED load behavior, camera trigger behavior and boot
  reset state unknown.

Not live-ready:

- no Pi-side artifact currently proves a live HQ camera XVS electrical mode,
  polarity, voltage compatibility, or timing relationship;
- no Pi runtime fixture may open camera, serial, GPIO, network, motion, LED or
  firmware resources during this audit;
- `camera_baseline` and `camera_stage` calibration contracts are static
  software evidence and must not be used as implicit hardware approval.

### scanner-firmware

Ready for software-only planning and replay:

- `src/scanner_firmware/adapters/homing/readiness.py` blocks current MKS/A4988
  homing readiness because the present override only sets position and does not
  physically home X/Y/Z.
- `src/scanner_firmware/planning/scan_preflight/evaluator.py` accepts missing
  homing only for dry-run mode with `hardware_outputs_enabled: false`.
- `docs/scheduling/position-event-scheduler-spec.md` keeps physical trigger,
  LED strobe and GPIO backends disabled until explicit hardware review.
- `docs/klipper/klipper-live-metadata-readiness.md` defines the current
  scanner-sync boundary as safe-disabled unless all metadata-only command and
  response formats, response dispatch, safety fields and no-output config are
  reviewed.
- `docs/scheduling/led-scheduler-and-drive-modes.md` records the current MKS
  no-load LED gate candidates and keeps loaded LED strobe output, camera trigger
  validation and driver capability unexercised.

Not live-ready:

- firmware readiness records cannot promote to `ready_for_live_test`;
- current MKS homing is incomplete and must not be treated as scan-start
  readiness;
- scanner-sync live metadata is not a substitute for camera trigger and LED
  output validation;
- LED gate aliases are not loaded-current evidence.

### scanner-core

No V1 hardware runtime responsibility is present in `scanner-core`.

The package is pure Python and must stay hardware-free. Its relevant value for
this test is offline validation of shared telemetry, predictive-Z and replay
helpers. No new `scanner-core` shared behavior is required for the first bounded
hardware test unless at least two implementation repos consume it and
`scanner-docs` records the shared-logic ledger entry.

## V1 Hardware Test Gate

All items in this section must be explicitly true before the first bounded live
hardware test. Until then, the readiness state is blocked for live hardware.

### Test Definition

- A reviewed issue, PR or procedure names the exact test as a manual-centered
  bounded non-scan test.
- The procedure states that it is not homing acceptance and not scan workflow
  acceptance.
- The procedure lists the exact software revision, config files, operator
  starting state and stop conditions.
- SSH, serial, GPIO, camera, LED and motion access are prohibited unless the
  reviewed procedure explicitly approves that exact action.

### Manual Center And Motion Bounds

- Operator manually centers the sample/stage and records that center as the
  temporary origin for this test only.
- X and Y commands are limited to `+/-10 mm` from that temporary origin.
- Motion commands are relative to the temporary origin or otherwise checked
  against the same envelope before execution.
- Soft limits reject any command outside the envelope.
- No homing command, endstop seek, hard-stop approach or full-slide scan command
  is present in the test procedure.

### Z Focus Bound

- Manual focus setup happens before any Z test move.
- The test defines a numeric minimal Z search envelope around manual focus.
- Z soft limits reject any command outside that envelope.
- Z motion must stop on timeout, operator stop, unexpected image/contact risk,
  or any controller fault.
- Predictive-Z or autofocus estimates may be observed, but they must not command
  unbounded Z motion.

### HQ XVS Sync-Sink

- The HQ camera XVS electrical role, direction, voltage level and polarity are
  documented before connection.
- XVS is not used as scan identity. MCU `FRAME_EVENT` remains the source of
  frame ID, coordinates, LED pattern and Z state.
- Any XVS observation is treated as timing/electrical evidence only until the
  camera request matcher validates one-to-one association with `FRAME_EVENT`.

### MKS FRAME_EVENT And Live Metadata

- MKS/Klipper scanner-sync is either disabled safe or explicitly reviewed as
  metadata-only with `hardware_outputs_enabled: false`.
- Required scanner-sync command formats, response formats and response dispatch
  are present before any enabled metadata test.
- Captured live metadata is validated offline for contiguous `FRAME_EVENT`
  frame IDs, stripe frame indexes and terminal/Z acknowledgement ordering before
  downstream Pi consumers trust it.
- Metadata-only readiness does not approve camera trigger pulses, LED gates,
  diagnostic GPIO or motion.

### LED Current And Gate Separation

- Arduino is only a slow brightness/VREF controller.
- MKS timing firmware owns frame-synchronous LED gate timing.
- Red, green and white target currents, current limits and sense-resistor
  metadata are reviewed before light emission.
- Red/green current feedback remains unknown until measured with the matching
  LED current path enabled.
- Loaded MKS gate behavior is verified before any LED output is used in a camera
  exposure.
- No scan-time current loop is implemented through USB serial commands.

## Blockers

P0 blockers for the first live hardware test:

- no merged reviewed live-test procedure for the manual-centered bounded
  non-scan path;
- no live-approved artifact proving the `+/-10 mm` X/Y envelope was enforced at
  the hardware command boundary;
- no live-approved Z focus envelope tied to the operator's actual manual focus
  setup;
- no HQ XVS electrical sync-sink evidence;
- no complete MKS scanner-sync enabled metadata-only readiness evidence;
- no loaded LED gate and per-channel current-limit evidence for the planned
  red/green/white paths;
- no hardware evidence schema/result that replaces the current Pi placeholder;
- current homing remains incomplete and cannot be used to justify scan
  workflows.

P1 follow-up blockers before expanding beyond V1:

- homing acceptance for X/Y/Z;
- camera trigger timing and LED pulse placement verified with oscilloscope;
- camera request to `FRAME_EVENT` matching evidence from live capture;
- calibrated red/green autofocus focus curve on raw/linear Bayer frames;
- controller boot/reset output-state evidence.

## Permitted Next Software Work

Allowed without touching hardware:

- add a software-only V1 manual-centered test-plan schema or fixture;
- add static guardrails that reject bounds larger than `+/-10 mm` for the V1
  no-homing path;
- add static guardrails that require a numeric Z focus envelope;
- add offline replay fixtures for `FRAME_EVENT` and camera-request matching;
- add docs/tests that keep Arduino brightness setpoints separate from MKS LED
  gate timing.

Forbidden in this audit:

- changing hardware runtime code;
- opening serial, GPIO, camera, network or SSH connections;
- enabling Klipper/MKS outputs;
- changing camera baseline or camera stage contract files;
- treating dry-run readiness as live-test approval.

## Software Gate Added

`src/scanner_firmware/planning/manual_center_bringup/` now contains a
software-only V1 bring-up gate for the first manual-centered bounded non-scan
test. It is not a scan preflight replacement and it does not command hardware.

The fixture `tests/fixtures/v1_manual_centered_bringup_gate_v1.json` provides
the currently reviewed candidate values:

- explicit reviewed-procedure and operator manual-center approval fields;
- X/Y envelope of `+/-10 mm` around the declared manual center;
- numeric Z focus envelope around manual focus;
- homing and scan workflow commands forbidden;
- predictive-Z/autofocus estimates observable but not allowed to command Z.

This closes the software-only representation of the X/Y and Z bounds. It does
not close the live hardware blockers for HQ XVS electrical evidence, loaded LED
gate/current evidence, or MKS scanner-sync live metadata evidence.
