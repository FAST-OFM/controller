# Custom Firmware Control Document

Status: design-control gate. This document must be reviewed before writing or
deploying custom scanner firmware beyond dry-run simulations and disposable
patch sketches.

## Purpose

The scanner firmware controls motion-adjacent timing, camera trigger metadata,
illumination timing and future Z correction scheduling. A custom firmware path
therefore needs a written control document before implementation work crosses
from local simulation into live controller behavior.

This document records the required architecture, interfaces, safety gates and
test strategy. It is not a firmware-base selection decision and not an approval
to flash or run hardware.

## Non-Negotiable Architecture

- MCU is the timing master.
- Acquisition events are position-indexed, not Linux-time-indexed.
- Initial coordinate source is commanded step count.
- Future coordinate source must support linear encoders.
- Homing is mandatory before scan execution.
- Initial Z is stepper-only.
- Future fine-Z actuator must be supported.
- Prescan camera produces tissue map and scan planning inputs.
- Prescan camera is not the real-time timing source.
- Camera frame arrival may start processing.
- MCU `FRAME_EVENT` supplies frame identity, coordinates, LED pattern and Z
  state.
- Frame identity or coordinates must not be inferred from Linux wall-clock
  time.
- Red/green or generic two-color oblique autofocus uses RAW Bayer or other
  linear unsqueezed image data.
- JPEG or preview frames must not be used for autofocus estimation.
- Scan execution mode must be configurable.
- Continuous scanning is a target, not an assumption.
- Predictive Z corrections must be scheduled into the future by position or
  frame.
- Autofocus must not be implemented as immediate scan-time `move_z_now`.
- Coordinate tiling plus overlap QA is the target.
- Heavy feature stitching is not the core pipeline.
- Do not write a full motion planner from scratch unless Klipper, grblHAL and
  external sync-board fallback are explicitly rejected with evidence.
- GitHub docs, ADRs, issues and handoff files are the source of truth.
- Hidden chat memory is not source of truth.
- Do not make clinical, diagnostic, regulatory or patient-safety claims.

## Current Hardware Baseline

Current documented baseline:

- Controller: MKS Robin Mini V2.0, PCB code `M-M-B-A-00526`.
- MCU class: STM32F103 family from current Klipper deployment evidence.
- Motion bring-up: X/Y/Z under Klipper on Raspberry Pi 5.
- Motors: NEMA 11.
- XY screw pitch: 2 mm per revolution.
- Z screw pitch: 0.5 mm per revolution.
- Stepper drivers: A4988.
- Observed E connector / auxiliary mappings are discovery results, not a
  general board definition.
- Current candidate signal assignments must remain tagged as candidate or
  locally verified according to the controller worksheet.

Mechanics and electronics must be represented in machine configuration. Screw
pitch, motor steps, microstepping, trigger pitch, exposure timing and LED timing
must not be hard-coded in firmware logic.

## Firmware Base Options

### Klipper Patch

Use when:

- the project can preserve Klipper motion planning;
- scanner timing can be implemented as a maintainable host/MCU extension;
- `FRAME_EVENT` and `schedule_z` can be carried without per-frame G-code round
  trips;
- safe stop and shutdown semantics remain clear.

Current status:

- dry-run adapter foundation exists in this repository;
- disposable Phase 1 scanner-sync stub has been built under host simulator;
- disabled live host-extra Stage A passed on the Pi after MKS USB serial
  recovery with `[scanner_sync] enable: false`;
- live MKS firmware does not contain scanner-sync MCU commands yet;
- position-coupled timing hook is not implemented.

The architecture gate remains unchanged: MCU timing master, position-indexed
`FRAME_EVENT`, no Linux-time metadata, no per-frame G-code timing path and no
immediate scan-time `move_z_now` autofocus path.

### grblHAL Plugin

Use when:

- HAL/plugin architecture gives a cleaner scanner event hook;
- target controller and pinout are known;
- timing evidence is better than Klipper with lower maintenance risk.

Current status:

- no target deployment has been validated for the current MKS board.

### External RP2040 Sync Board

Use when:

- motion firmware remains mostly unchanged;
- scanner timing can be derived from STEP/DIR or future encoder signals;
- external board can emit trigger, LED gates and `FRAME_EVENT` metadata
  deterministically.

Current status:

- remains a supported fallback and may become primary if Klipper patching is too
  invasive.

### Standalone Custom Motion Firmware

Use only if:

- Klipper, grblHAL and external sync-board approaches fail with documented
  evidence;
- the team explicitly accepts the cost of maintaining planner, homing, safety,
  acceleration, configuration and diagnostics;
- the design is reviewed as a separate architecture decision.

Standalone custom motion firmware is not the default path.

## Configuration Model

All hardware-dependent values must come from machine configuration:

- axis steps per revolution;
- screw pitch;
- microstepping;
- travel limits;
- soft limits;
- acceleration and velocity limits;
- homing mode and inputs;
- coordinate source mode;
- encoder scaling if present;
- camera trigger output;
- LED gate outputs;
- output polarity;
- boot and shutdown output states;
- LED current-control backend;
- scan execution mode;
- frame pitch and overlap;
- Z limits and scheduling lead time.

Configuration must support at least these profiles:

- current MKS/Klipper bring-up;
- dry-run simulator;
- future RP2040 sync-board;
- future encoder-indexed coordinate source.

## Required Modules

### Motion Adapter

Owns the interface to the selected firmware base. It must not expose Linux-time
frame identity to acquisition.

Required responsibilities:

- report commanded position;
- report motion state;
- expose homing state;
- accept scan-mode configuration;
- provide safe stop integration;
- expose firmware-base capabilities.

### Coordinate Source

Initial implementation:

- commanded step count.

Future implementation:

- encoder-indexed;
- hybrid commanded plus encoder validation.

Interface requirements:

- return X/Y/Z commanded counts;
- return optional encoder counts;
- identify coordinate source used for every frame event;
- set flags when encoder data is missing, stale or inconsistent.

### Trigger Scheduler

Required responsibilities:

- schedule acquisition events by position/frame;
- emit one metadata event per trigger;
- support dry-run metadata-only mode;
- support stop-and-capture, micro-stop, segmented fly-scan, fly-scan open-loop
  and fly-scan predictive-Z modes;
- never depend on Linux wall-clock timing for frame identity.

### Frame Event Publisher

Required fields:

- protocol version;
- scan ID;
- stripe ID;
- global frame ID;
- stripe frame index;
- LED pattern;
- coordinate source used;
- position axis;
- event position;
- X/Y/Z commanded counts;
- optional encoder counts;
- MCU-local timestamp or clock;
- trigger output identity;
- LED gate names or pattern id;
- Z state;
- status;
- hardware-output enabled flag for dry-run separation.

### Z Scheduler

Required responsibilities:

- accept future `schedule_z` commands;
- reject targets that are too late, outside the stripe, outside Z limits, inside
  no-correction windows or inconsistent with current scan state;
- emit `Z_SCHEDULED`, `Z_APPLIED` or `Z_REJECTED`;
- never apply scan-time immediate autofocus corrections to the current frame.

### Homing Controller

Homing is mandatory. The implementation must represent:

- not configured;
- configured but unhomed;
- homing in progress;
- homed;
- homing fault;
- homing invalidated by controller reset, driver fault or configuration change.

Current MKS/A4988 setup does not provide sensorless homing evidence. Any future
Pico/RP2040 sensorless approach must be documented against the actual driver
hardware and validated separately.

### Illumination Controller

Required responsibilities:

- separate timing gate from brightness control;
- represent LED outputs and polarity from configuration;
- support Rev A slow modes;
- support future external constant-current or strobe drivers by configuration;
- require current limiting for every LED channel;
- keep MCU GPIO as logic/control only, not LED current source.

### Safety Controller

Required responsibilities:

- default outputs safe on boot and reset;
- safe stop clears trigger and LED outputs;
- reject scan start without homing;
- reject scan start with unknown required pin mapping;
- reject scan start with hardware outputs enabled in dry-run-only builds;
- report terminal/fault events.

## Protocol Surface

Host-to-MCU:

- `scanner_sync_start`
- `scanner_sync_stop`
- `scanner_sync_schedule_z`

MCU-to-host:

- `FRAME_EVENT`
- `SCHEDULER_TERMINAL`
- `Z_SCHEDULED`
- `Z_APPLIED`
- `Z_REJECTED`

The event names above must stay uniform across firmware, Pi code, docs and
issues.

## Simulation And Test Tiers

### Tier 0: Pure Unit Tests

- no Klipper import;
- no serial;
- no GPIO;
- no hardware;
- validates recipes, scan modes, protocol records and scheduler state.

### Tier 1: Local Firmware-Base Harness

- disposable Klipper or grblHAL checkout;
- host simulator builds only;
- protocol dictionary validation;
- smoke tests that do not send hardware commands.

### Tier 2: Metadata-Only Live Bench

Requires approval.

- patch installed on Pi;
- scanner-sync defaults disabled;
- no configured output pins;
- no motor motion;
- event stream only.

### Tier 3: Single Output Timing Bench

Requires approval.

- scope-only or dummy-load output;
- no camera unless explicitly approved;
- no LEDs unless explicitly approved;
- no scan motion unless explicitly approved.

### Tier 4: Motion-Coupled Bench

Requires approval.

- homing procedure complete;
- soft limits configured;
- wiring reviewed;
- stop conditions rehearsed;
- one-axis low-speed procedure first.

## Release Gates

No firmware build may be used on live scanner hardware until these are true:

- controller identity documented;
- MCU and board revision documented;
- pin mapping documented with verification state;
- electrical levels documented;
- homing strategy documented;
- boot/reset output states documented;
- safe stop behavior documented;
- configuration file reviewed;
- tests for dry-run event sequences pass;
- bench-safe plan approved for the exact test being run;
- rollback procedure documented.

## Required Documentation Before Custom Firmware

Before writing a standalone custom firmware or a deep motion-planner patch,
create or update:

- firmware-base ADR;
- controller worksheet;
- pin map with verification states;
- motion and kinematics configuration;
- homing design;
- scanner protocol schema;
- LED/trigger electrical design;
- Z scheduling design;
- safe test plan;
- rollback plan;
- maintenance plan for fork/upstream divergence.

## Current Decision

The project is not ready to start standalone custom motion firmware.

The current approved path remains:

1. continue dry-run and disposable Klipper patch evidence;
2. preserve RP2040 sync-board fallback;
3. keep grblHAL under evaluation;
4. stop before live hardware until the exact bench plan is reviewed.
