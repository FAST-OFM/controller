# Parallel Firmware Component Workstreams

Status: software-only development plan. This document does not approve live
firmware flashing, GPIO toggling, motor motion, camera triggering, LED driving
or hardware tests.

## Purpose

Scanner firmware work is split into isolated components so configuration,
math, frame identity, illumination timing, coordinate fusion, focus,
calibration, predictive Z and controller integration can advance in parallel
without coupling to live hardware.

Hidden chat memory is not source of truth. Interfaces, assumptions, tests and
known limits belong in this repository.

## Shared Rules

- MCU remains the timing master.
- Acquisition events are position-indexed, not Linux-time-indexed.
- Frame identity and coordinates come from MCU `FRAME_EVENT` metadata.
- Autofocus uses RAW Bayer or linear image data, not JPEG/preview frames.
- Predictive Z corrections are scheduled into the future by frame or position.
- Do not implement `move_z_now` as the autofocus correction path.
- Do not write a full motion planner from scratch.
- Unknown hardware values remain unknown.
- Components are software-only until a reviewed hardware boundary promotes
  them.
- Code and documentation work follows
  `docs/foundation/code-architecture-standards.md`.

## Agent Delegation Rules

- Parallel work is allowed only on disjoint ownership scopes.
- A worker may spawn child agents for bounded software-only subtasks in its
  assigned scope.
- Default child-agent limit per worker is two unless the lead agent assigns a
  larger limit for that specific scope.
- Child agents inherit the same constraints: no firmware flashing, GPIO
  toggling, motor motion, camera triggering, LED driving, serial control,
  network control or hardware tests.
- Workers may install local project dependencies or prepare local repos needed
  for their software-only task.
- Workers must report changed files, tests run and remaining assumptions.
- Workers must not revert or overwrite changes outside their assigned scope.
- Workers and child agents must not open, approve, merge, force-push or
  direct-push PRs unless the lead agent explicitly delegates that operation for
  one named PR.
- Cross-cutting interface changes are owned by the lead agent or an explicitly
  assigned architecture worker.
- The lead agent closes completed workers after taking their result, whether
  the result is integrated, superseded or rejected.

## Interface Layer

Shared protocols live in:

- `src/firmware_components/interfaces.py`
- `src/controller_adapter/interfaces.py`

The interface layer owns common value objects for:

- stripe geometry;
- focus frame inputs and focus estimates;
- axis calibration observations and estimates;
- predictive Z correction samples and planned corrections.

The interface layer must not import Klipper, open serial ports, send commands,
toggle outputs, command motors, trigger cameras, drive LEDs or flash firmware.

Controller adapter protocols live under `src/controller_adapter/` and define
`MotionPositionProvider`, `ScannerCommandPort`, `ProtocolEventSink`,
`OutputBackend`, `PassiveMetadataEventSource` and `ControllerCapabilities`.
Klipper, grblHAL and RP2040 are future adapters behind those protocols.
Scheduler and planner modules consume the abstract boundary and must not import
adapter packages directly. Hardware outputs default to disabled; dry-run
backends reject attempts to enable them. Passive `live_metadata` adapters may
expose already captured controller-neutral metadata, but they must not submit
commands, open serial, toggle outputs or imply live scanner-sync approval.

## Workstreams

### Architecture

Ownership:

- `src/firmware_components/`
- docs under `docs/foundation/`

Responsibilities:

- define software-only interfaces;
- keep components replaceable behind protocols;
- preserve safety boundaries and source-of-truth docs;
- prevent hidden constants from leaking into implementations.

### Platform, Camera And Readiness Config

Ownership:

- `src/camera_config/`
- `src/platform_config/`
- `src/readiness/`
- `tests/simulator/test_camera_config_model.py`
- `tests/simulator/test_platform_config_loader.py`
- `tests/simulator/test_platform_config_model.py`
- `tests/simulator/test_startup_readiness_model.py`

Responsibilities:

- validate camera mode, exposure, frame period, crop and binning metadata;
- keep camera crop/binning as configuration, not a timing source;
- aggregate platform profile, motion, IO, camera and scan recipe domains;
- produce preflight inputs from validated domain objects;
- keep startup readiness states explicit: blocked, safe-disabled or ready.

### Scan Math

Ownership:

- `src/scan_math/`
- `tests/simulator/test_scan_math_geometry.py`

Responsibilities:

- stripe geometry;
- event position sequences;
- bounds and overshoot math;
- screw pitch, motor-step and microstep conversions.

### Scan Planning

Ownership:

- `src/scan_planning/`
- `tests/simulator/test_scan_planning_model.py`

Responsibilities:

- compile software-only ROI and stripe recipes into `ScanPlan`,
  `StripePlan` and `FramePlan` metadata;
- assign frame ids, scan-axis positions, fixed stripe positions, logical LED
  pattern ids, scan mode and coordinate mode;
- validate dry-run state, disabled hardware outputs, soft limits and logical
  LED pattern resolution;
- delegate stripe event geometry to `scan_math`.

### Focus Metric

Ownership:

- `src/focus_metric/`
- `tests/simulator/test_focus_metric_model.py`

Responsibilities:

- RAW/linear image input validation;
- red/green or two-color oblique focus metrics;
- focus error direction and confidence;
- rejection of JPEG, preview or nonlinear image inputs.

### Autofocus Control

Ownership:

- `src/autofocus_control/`
- `tests/simulator/test_autofocus_control_loop.py`

Responsibilities:

- consume focus estimates plus matched MCU `FRAME_EVENT` metadata;
- reject low-confidence, deadband, unmatched or stale observations;
- keep focus correction requests in public micrometer units;
- coalesce repeated future `schedule_z` requests for the same target;
- enforce max correction rate by future frame or future position lookahead;
- reject immediate/current-frame `move_z_now` behavior.

### Calibration

Status: active software-only workstream.

Ownership:

- `src/calibration/`
- `tests/simulator/test_calibration_model.py`

Responsibilities:

- steps-per-mm estimates from measured travel;
- backlash estimates from forward/reverse observations;
- repeatability statistics;
- LED current calibration lookup and interpolation from measured samples.
- process only already-captured observations; live ADC reads, motion, LED power
  and serial control stay behind reviewed hardware gates.

### Predictive Z

Ownership:

- `src/z_scheduler/predictive.py`
- `tests/simulator/test_z_predictive_planner.py`

Responsibilities:

- convert focus-error samples into future absolute Z target requests;
- keep correction delta and absolute Z target semantics separate;
- enforce lead frames or lead position counts;
- clamp corrections to configured limits;
- reject immediate or past corrections.

### Frame Event Matching

Ownership:

- `src/frame_counter/`
- `tests/simulator/test_frame_event_matching.py`

Responsibilities:

- match host image-arrival records to MCU `FRAME_EVENT` records by frame id;
- never infer identity or coordinates from Linux wall-clock arrival time;
- report duplicate, missing, unmatched and terminal stream states;
- keep camera acquisition IO outside the matcher.

### Scan Execution

Ownership:

- `src/scan_execution/`
- `tests/simulator/test_scan_execution_state_machine.py`

Responsibilities:

- model BOOT through terminal scan execution states as software-only data;
- consume readiness and preflight decisions instead of performing live checks;
- require explicit hardware-output arming before entering `SCANNING`;
- keep dry-run execution free of hardware outputs and terminal reasons explicit.

### LED Timing

Ownership:

- `src/led_scheduler/`
- `tests/simulator/test_led_timing_model.py`

Responsibilities:

- resolve logical LED pattern names;
- keep brightness setpoints separate from frame-synchronous gate windows;
- validate exposure containment, settle time and polarity metadata;
- use logical aliases only, not physical GPIO names.

### Coordinate Fusion

Ownership:

- `src/coordinate_source/`
- `tests/simulator/test_coordinate_source_fusion.py`

Responsibilities:

- keep `step_indexed`, `encoder_indexed` and `hybrid` modes explicit;
- preserve commanded step counts as the current coordinate source;
- report missing, stale, unhealthy or disagreeing encoder observations;
- leave unknown encoder state as unknown rather than guessing.

## Integration Boundary

Integration into scanner-sync or Klipper is a later step. A component is not
approved for live use merely because its simulator tests pass.

Before any live Stage B or later action, the relevant docs under `docs/klipper/`
must still pass their review gates.
