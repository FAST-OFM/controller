# Klipper Scanner-Sync Patch Proposal

Status: design proposal only. This document does not approve edits to the live
Pi Klipper checkout, Klipper service restarts, firmware flashing, motor motion,
GPIO toggling, camera triggering or LED output.

## Purpose

This proposal describes the minimal Klipper host/MCU extension shape needed to
evaluate Klipper as a scanner firmware base while preserving the project
architecture:

- MCU is the timing master.
- Acquisition events are position-indexed, not Linux-time-indexed.
- Frame identity and coordinates come from MCU `FRAME_EVENT` metadata.
- The Pi may start image processing when a camera frame arrives, but it must
  not infer frame identity or coordinates from camera arrival time.
- Future autofocus corrections use scheduled `schedule_z` commands by future
  frame or position, not immediate scan-time `move_z_now`.
- Per-frame G-code round trips are not an acceptable scanner timing path.

## Current Evidence

Read-only inspection of the current Pi checkout is recorded in
`docs/evidence/klipper-readonly-inspection.md`.

Local, hardware-free foundation already exists in this repository:

- `src/klipper_adapter/model.py`: small Klipper MCU API contract;
- `src/klipper_adapter/fake.py`: dry-run fake MCU registration surface;
- `src/klipper_adapter/scanner_sync.py`: scanner-sync command/response names;
- `src/klipper_adapter/codec.py`: local event/command conversion contract;
- `src/klipper_adapter/dry_run_harness.py`: in-memory integration harness.

This foundation is not a live Klipper patch and not a selected binary wire
format. It exists to keep names, units and safety boundaries testable before
touching Klipper.

## Proposed Klipper Components

### Host Extra

Candidate file:

- `klippy/extras/scanner_sync.py`

Responsibilities:

- parse a `[scanner_sync]` config section;
- bind named MCU pins only after config review;
- allocate one scanner-sync MCU object id;
- register scanner-sync MCU config commands;
- look up scanner-sync host-to-MCU commands;
- register scanner-sync MCU-to-host responses;
- expose decoded scanner events to a local host transport for the Pi
  acquisition process;
- reject operation unless scanner-sync is explicitly enabled in config.

The host extra must not implement per-frame scanner timing in Python. Python
may configure a scan, send future `schedule_z` commands and receive events.
Position-indexed event decisions belong on the MCU side.

### MCU Object

Candidate MCU files to inspect and patch after review:

- `src/basecmd.c` or equivalent command registration area;
- `src/command.c` / message dispatch helpers;
- stepper or timer-related files that can access scheduled position progress;
- board-independent GPIO scheduling helpers if available.

The exact files must be confirmed against the target Klipper commit before
implementation. Do not guess or patch live Klipper from this proposal alone.

Responsibilities:

- own the scanner-sync state machine;
- reject start unless required configuration is complete;
- schedule events by commanded step position for the initial implementation;
- keep the interface compatible with future encoder-indexed coordinates;
- produce one `FRAME_EVENT` for every physical camera trigger when hardware
  output is enabled;
- support metadata-only dry-run events without physical output;
- accept `schedule_z` only for future frame/position targets;
- emit `Z_SCHEDULED`, `Z_APPLIED` or `Z_REJECTED` for every `schedule_z`;
- emit `SCHEDULER_TERMINAL` only when host stop or fault prevents the
  remaining planned `FRAME_EVENT` records; clean completion emits no terminal
  record;
- drive configured outputs safe on stop/fault.

## Proposed Config Shape

Illustrative only:

```ini
[scanner_sync]
enable: false
protocol_version: 1
coordinate_source: commanded_steps
mode: dry_run
camera_trigger_pin: none
led_white_pin: none
led_red_pin: none
led_green_pin: none
frame_event_transport: host_response
```

Config rules:

- `enable` must default to `false`.
- Hardware pins must default to `none`.
- `mode: dry_run` must not toggle GPIO.
- `mode: hardware_output` must require a separate reviewed bench-safe issue.
- Pin names must come from the documented controller worksheet, not guesses.
- Homing requirements must be explicit before any scan mode can run.

## Command And Event Names

The local dry-run registration plan uses these host-to-MCU command names:

- `scanner_sync_start`
- `scanner_sync_stop`
- `scanner_sync_schedule_z`
- `scanner_sync_arm_af_window`
- `scanner_sync_fire_af_window_now`

`scanner_sync_arm_af_window` is the scan path and must be armed by position
count. `scanner_sync_fire_af_window_now` is a diagnostic bench command for
no-motion tests and must not become the normal scan timing source.

It maps MCU-to-host response names to project protocol event names:

- `scanner_sync_frame_event` -> `FRAME_EVENT`
- `scanner_sync_scheduler_terminal` -> `SCHEDULER_TERMINAL`
- `scanner_sync_z_scheduled` -> `Z_SCHEDULED`
- `scanner_sync_z_applied` -> `Z_APPLIED`
- `scanner_sync_z_rejected` -> `Z_REJECTED`

These names should remain uniform across firmware, Pi code, docs and issues.

## Data Path

### Dry-Run Path

```text
scan recipe
  -> scanner_sync host extra
  -> scanner_sync MCU state machine in metadata-only mode
  -> scanner_sync_frame_event responses
  -> Pi event receiver
  -> frame matcher test fixtures
```

No GPIO, camera trigger, LED output or motor command is allowed in this path.

### Hardware-Output Path

```text
scan recipe
  -> scanner_sync host extra
  -> scanner_sync MCU state machine
  -> position-indexed trigger/LED output
  -> scanner_sync_frame_event response with matching frame id
  -> Pi event receiver
  -> frame matcher
```

This path is not approved by this proposal. It requires a separate bench-safe
plan, reviewed wiring, reviewed pin mapping and explicit approval.

## Implementation Phases

### Phase 0: Local Proposal And Harness

Already implemented in this repository:

- fake Klipper API surface;
- scanner-sync registration plan;
- local codec;
- in-memory dry-run harness.

No live Klipper edit.

### Phase 1: Patch Sketch Outside Live Pi

Allowed next design step:

- clone or copy the target Klipper commit into a disposable workspace;
- draft `scanner_sync.py` host extra and MCU command stubs;
- compile or run Klipper unit/build checks if available;
- do not install the patch into the live Pi checkout;
- do not restart Klipper;
- do not flash the MCU;
- do not connect outputs.

Output: patch review PR or patchset notes, still not applied to the scanner.

Phase 1 output is recorded in
`docs/evidence/klipper-scanner-sync-phase1-stub-report.md`, with the disposable patch
artifact in `docs/patches/klipper-scanner-sync-phase1-stub.patch`.

### Phase 2A: Disabled Live Host-Extra Load

Completed on July 1, 2026 after MKS USB serial recovery:

- backup live Klipper config;
- install the scanner-sync host extra on Pi;
- keep scanner-sync `enable: false`;
- verify Klipper starts and reconnects to the MKS MCU;
- do not enable scanner-sync MCU commands;
- do not flash firmware;
- do not send G-code;
- do not toggle GPIO;
- do not move motors;
- do not trigger the camera;
- do not drive LEDs.

Output: host-extra import/config proof only. No event transport proof was
performed.

The Stage A attempts and successful retry are recorded in
`docs/evidence/klipper-live-metadata-stage-a-attempt.md`. Current readiness state is
recorded in `docs/klipper/klipper-live-metadata-readiness.md`.

Current live state:

- `~/klipper/klippy/extras/scanner_sync.py` is present as an untracked live
  host extra;
- `printer.cfg` contains `[scanner_sync] enable: false`;
- the live MKS firmware lacks scanner-sync MCU commands;
- `[scanner_sync] enable: true` remains blocked until a reviewed firmware patch
  and flash step are approved.

### Phase 2B: Live Metadata-Only Event Transport Plan

Requires separate approval before execution:

- exact Klipper host and MCU patch diff;
- exact MKS firmware build and flash procedure;
- scanner-sync still defaults to `enable: false`;
- metadata-only mode with `hardware_outputs_enabled=false`;
- no configured GPIO outputs;
- no motor motion;
- no camera trigger;
- no LED output;
- expected `FRAME_EVENT`, `SCHEDULER_TERMINAL`, `Z_SCHEDULED`, `Z_APPLIED` and
  `Z_REJECTED` records;
- rollback plan and stop conditions.

Output: event transport proof only. This phase is not approved by this
proposal.

A disposable Phase 2 metadata-only sketch for review is recorded in
`docs/evidence/klipper-scanner-sync-phase2-metadata-only-report.md`, with the patch
artifact in `docs/patches/klipper-scanner-sync-phase2-metadata-only.patch`.
It removes the Phase 1 `scanner_sync_debug_emit` helper and keeps event
transport independent of GPIO, camera trigger, LED output and motion. It is not
approved for live Pi installation or firmware flashing.

### Phase 3: Stationary AF Live-Output Patch Sketch

A disposable Phase 3 patch sketch is recorded in
`docs/evidence/klipper-scanner-sync-phase3-stationary-af-live-output-report.md`,
with the patch artifact in
`docs/patches/klipper-scanner-sync-phase3-stationary-af-live-output.patch`.

The patch adds `mode: stationary_af_bench` and
`SCANNER_SYNC_RUN_STATIONARY_AF_TEST` for a no-motion LED/XVS timing bench. It
requires explicit pin configuration and `hardware_outputs_enabled: true` before
any hardware output command can be sent.

The Phase 3 artifact was built on the Pi 5 in a disposable checkout against the
current MKS STM32F103 configuration. That build evidence does not approve live
Klipper installation, MKS flashing, GPIO toggling, camera triggering, LED output
or motor motion.

Requires separate approval before live execution:

- reviewed dummy output or disconnected scope-only pin;
- no camera connected to trigger output unless explicitly approved;
- no LED load connected unless explicitly approved;
- no scan motion unless explicitly approved;
- oscilloscope capture plan with stop conditions.

Output: timing/jitter evidence.

### Phase 4: Motion-Coupled Scanner Test

Not in scope for this proposal.

This phase requires complete controller discovery, homing strategy, safe motion
procedure and reviewed pin/output wiring.

## Open Design Decisions

- Whether the live Klipper proof should be a downstream patch, a maintained
  fork, or an external sync-board fallback.
- Exact MCU-side source files and scheduler hook point for position-indexed
  event generation.
- Binary response payload layout and size limits.
- Event buffering and backpressure behavior if the Pi does not read events
  quickly enough.
- How scanner-sync state interacts with Klipper emergency stop and shutdown.
- How homing state is represented in `FRAME_EVENT`.
- How future encoder-indexed coordinates enter the same event schema.
- Whether camera trigger and event response are ordered trigger-first,
  event-first or same-cycle with documented latency.
- Minimum viable `schedule_z` units: nanometers, steps or a calibrated fixed
  point representation.

## Rejection Criteria

Klipper should remain unselected or move behind the RP2040 sync-board fallback
if the patch requires any of the following:

- per-frame G-code round trips;
- Linux wall-clock timing for frame identity or coordinates;
- large invasive changes to Klipper motion planning without a maintainable
  upstream/fork strategy;
- inability to emit `FRAME_EVENT` metadata reliably at scan rate;
- inability to reject unsafe or late `schedule_z` commands deterministically;
- inability to preserve safe stop behavior.

## Required Review Before Any Live Work

Before any live Pi/Klipper change, create a reviewed issue or PR containing:

- exact Klipper commit and local patch diff;
- exact config changes;
- exact controller pins and wiring state;
- confirmation that scanner-sync defaults disabled;
- rollback instructions;
- commands to run;
- expected logs/events;
- stop conditions;
- statement that no clinical, diagnostic, regulatory or patient-safety claims
  are being made.

The broader firmware design-control gate is recorded in
`docs/foundation/custom-firmware-control-document.md`.
