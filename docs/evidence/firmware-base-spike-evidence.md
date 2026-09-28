# Firmware Base Spike Evidence

Status: no-hardware evidence plus V1 path decision. Klipper scanner-sync live
metadata is the selected V1 implementation path. This does not approve live
hardware outputs, MKS flashing, motor motion, homing, camera triggering or LED
strobing.

This document records evidence available for issue `003: Firmware base spike:
Klipper vs grblHAL vs sync-board`. It separates the bounded V1 implementation
decision from tests still needed before making broader hardware-readiness or
long-term firmware-base claims.

## Architecture Requirements

The selected firmware base must preserve these requirements:

- MCU is the timing master for acquisition events.
- Acquisition events are position-indexed, not Linux-time-indexed.
- Initial coordinates may use commanded step count.
- Future coordinate sources must support linear encoders.
- Homing is mandatory before scanning.
- Frame identity and coordinates must come from MCU `FRAME_EVENT` metadata.
- Camera frame arrival may start processing, but must not define frame identity.
- Autofocus estimation must use RAW Bayer or other linear unsqueezed image
  data, not JPEG or preview frames.
- Scan execution mode must remain configurable.
- Predictive Z corrections must be scheduled into the future by position or
  frame.
- The project must not implement a full motion planner from scratch unless the
  evaluated bases fail and the decision is explicitly revisited.

## Verified Evidence

| Area | Evidence | Limitation |
|---|---|---|
| Current controller | MKS Robin Mini V2.0 identified from board photos and active Klipper deployment | Board identity does not select the long-term firmware base |
| Current firmware path | Pi 5 is running Klipper and controls X/Y/Z in the existing bring-up | Existing usage covers motion bring-up and current `PD6` / E0_STEP trigger/sync signaling; `PC4` / Z+ is legacy only |
| Klipper host patterns | Read-only inspection of the current Pi checkout identified `output_pin`, `motion_report`, `pulse_counter` and `mcu.py` APIs that can inform a future scanner extension | Source inspection plus disabled host-extra load only; no scanner-sync MCU command or timing measurement has been executed |
| Klipper live metadata Stage A | Disabled `[scanner_sync] enable: false` host extra loaded on the live Pi 5 after MKS USB serial recovery; Klipper reconnected to the MKS MCU | This proves only host-extra import/config safety with scanner-sync disabled; no firmware patch, scanner-sync MCU command, GPIO, motion, camera trigger or LED output was tested |
| Trigger model | Dry-run scheduler emits `FRAME_EVENT` records from commanded position samples | Host-side simulator only; it does not toggle pins or prove timing jitter |
| Candidate adapters | Dry-run adapters can map synthetic Klipper-like positions, grblHAL-like planner snapshots and external sync-board STEP/DIR pulses into common scheduler samples | These adapters are not real firmware integrations |
| Phase 0 fixture | `tests/fixtures/firmware_base_phase0_expected.json` records expected dry-run event streams for all three candidates | Fixture evidence does not prove physical timing or maintainability |
| Phase 0 comparison | `tests/fixtures/firmware_base_phase0_comparison_report_v1.json` and `docs/evidence/firmware-base-phase0-comparison-report.md` summarize common dry-run metadata gates across all three candidates | Comparison is offline metadata evidence only and keeps final firmware-base selection open |
| Coordinate model | Simulator supports `step_indexed`, `encoder_indexed` and `hybrid` coordinate-source modes | Encoder hardware path is not wired or validated |
| Homing model | Simulator covers physical-switch, sensorless and encoder-index homing state paths | Current MKS setup has no verified physical homing implementation |
| Safety state | No firmware flashing, motor motion, LED strobe, camera trigger or GPIO-output test is part of this evidence | Hardware-output timing remains untested |

## Candidate Evidence Gaps

### Klipper

Known:

- Already deployed on the Pi 5 and current MKS Robin Mini V2.0 bring-up.
- Existing config has been used for X/Y/Z motion and current `PD6` / E0_STEP
  trigger/sync signaling. `PC4` / Z+ is a legacy/config artifact, not the
  current trigger path.
- Read-only source inspection is recorded in
  `docs/evidence/klipper-readonly-inspection.md`.
- The proposed scanner-sync Klipper patch shape is recorded in
  `docs/klipper/klipper-scanner-sync-patch-proposal.md`; it is not approval to patch
  the live Pi checkout.
- A disposable Phase 1 Klipper scanner-sync stub report is recorded in
  `docs/evidence/klipper-scanner-sync-phase1-stub-report.md`; it compiled under
  Klipper host simulator and passed a Klippy smoke test, but it does not prove
  position-indexed hardware timing.
- The first live metadata-only Stage A attempt is recorded in
  `docs/evidence/klipper-live-metadata-stage-a-attempt.md`; it was initially rolled
  back because of an MKS USB serial failure. After physical USB/power recovery,
  the disabled host extra was installed successfully and Klipper reconnected to
  the MKS MCU with `[scanner_sync] enable: false`.
- Current Klipper config does not prove final camera-trigger or LED-strobe
  architecture.

Needed before recommendation:

- Determine whether scanner event generation can be implemented without
  per-frame G-code round trips.
- Determine whether a scanner-specific Klipper host/MCU extension can carry
  both directions of the scanner protocol: MCU-to-host `FRAME_EVENT` /
  `SCHEDULER_TERMINAL` and host-to-MCU `schedule_z`.
- Measure position-indexed output timing and jitter with a reviewed
  bench-safe procedure.
- Document whether a maintainable Klipper host/MCU extension or plugin path is
  realistic.
- Confirm how homing state, commanded coordinates and future encoder metadata
  enter `FRAME_EVENT` records.
- Confirm how `Z_SCHEDULED`, `Z_APPLIED` and `Z_REJECTED` acknowledgements are
  surfaced to the Pi without treating an immediate Z move as valid autofocus
  feedback.

### grblHAL

Known:

- CNC/HAL architecture may be a cleaner fit for scanner-specific motion and
  output plugins.
- No target grblHAL deployment has been tested for this hardware.

Needed before recommendation:

- Run a no-hardware plugin or host-side equivalent that emits scanner
  `FRAME_EVENT` metadata.
- Identify an RP2040 or other target board path that does not require guessing
  pinout, flashing method or electrical levels.
- Measure whether position-indexed events can be generated without host timing
  dependence.
- Document upstream compatibility and maintenance cost.

### External RP2040 Sync Board

Known:

- A sync-board fallback can monitor STEP/DIR or encoder signals and generate
  trigger, LED and metadata events without deeply modifying the motion
  firmware.
- This may be the fastest route to validate scanner acquisition timing.

Needed before recommendation:

- Build a no-motion bench test using synthetic STEP/DIR inputs.
- Verify pulse counting, direction handling, frame metadata, safe stop and
  missed-pulse behavior.
- Complete electrical review before connecting to the motion controller,
  camera trigger, LEDs or Pi inputs.
- Document how future encoder input would replace or augment STEP/DIR
  monitoring.

## Current V1 Decision

Continue V1 implementation on the Klipper scanner-sync live metadata path.

The basis is:

- the current prototype already uses Klipper on the Pi 5 and MKS Robin Mini
  V2.0;
- dry-run scheduler, command codec, event-stream and Stage A disabled
  host-extra work exist;
- atomic illumination-window metadata is modeled in firmware without enabling
  outputs;
- this path avoids writing a full motion planner from scratch.

The decision is bounded:

- no live outputs are approved by this document;
- grblHAL remains a fallback if Klipper integration becomes too invasive;
- external RP2040 sync-board remains the fallback if Klipper cannot provide
  maintainable position-indexed trigger/LED timing and metadata;
- hardware timing, flashing and live-output tests still require separate
  reviewed procedures.

## Next Safe Tests

These tests are safe to run without connected scanner hardware outputs:

1. Run the simulator suite for trigger scheduling, coordinate-source resolution
   and homing state machines.
2. Add candidate-specific adapters only in dry-run mode, with
   `hardware_outputs_enabled=false`.
3. Record `FRAME_EVENT` streams and compare frame IDs, stripe indices, LED
   pattern metadata, coordinate source and stop behavior.
4. Prepare separate reviewed procedures before any motor motion, GPIO output,
   camera trigger, LED strobe or firmware flashing test.
