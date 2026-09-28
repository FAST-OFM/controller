# Firmware Contracts

Status: software-only architecture contract. This document does not approve
live firmware flashing, GPIO toggling, motion, camera triggering, LED driving,
serial control, network control or hardware tests.

## Purpose

Development agents must use this document as the shared contract for firmware
naming, state machines, event records, scan math and package interfaces. When
a new convention is needed, update this document and the enforcing tests or
guardrails in the same PR.

Parallel workers must treat this file and `code-architecture-standards.md` as
their input contract. Work on focus calculation, calibration math, predictive Z,
scan execution, protocol events or adapters should start from these shared
interfaces so independently developed components meet at typed boundaries
instead of through ad hoc facades.

## Naming

- Events use uppercase protocol names for host-visible records:
  `FRAME_EVENT`, `SCHEDULER_TERMINAL`, `Z_SCHEDULED`, `Z_APPLIED`,
  `Z_REJECTED`.
- Commands use lower snake case verbs at the protocol boundary, such as
  `schedule_z`. Python command value objects use explicit names ending in
  `Command`.
- Records are immutable data returned across boundaries and end in `Record`
  when the name would otherwise be ambiguous.
- Adapters are hardware, firmware-base, process, filesystem or protocol
  boundary implementations and end in `Adapter` when exposed as a class.
- Ports are neutral ownership interfaces. Use `Port` for host/domain-facing
  capabilities and `Protocol` only for structural typing contracts.
- Simulators and dry-run implementations must be named `Simulator`,
  `DryRun...` or `Fake...` and must keep `hardware_outputs_enabled=false`.
- DTOs are serialization-only boundary objects. Use `Dto` only when an object
  exists to match an external payload shape; prefer domain records otherwise.
- Config values name units and domain explicitly, for example
  `trigger_pulse_us`, `event_pitch_count`, `z_target_um`,
  `hardware_outputs_enabled`.

## State Machines

- States describe durable controller or planner conditions: `IDLE`,
  `HOMING`, `READY`, `SCAN_STRIPE`, `PAUSED`, `FAULT`.
- Decisions are validation outcomes, not states. Use `accepted` or `rejected`
  for command/schedule decisions and include a reason for rejection.
- Readiness uses `ReadinessReason` records for parent-facing explanations.
  Reason domains are `board`, `scanner_sync` and `live_test_gate`. Board and
  scanner-sync reasons must preserve unknown hardware facts as unknowns; they
  must not infer live board, homing or scanner-sync approval from static
  software evidence.
- Terminal records are records, not states. Use `SCHEDULER_TERMINAL` with
  `status: stopped | fault` when a stripe cannot emit its remaining planned
  `FRAME_EVENT` records.
- Use `fault` for runtime failures, unsafe inconsistencies or synchronization
  loss. Use `stopped` for requested host stops. Use `rejected` for commands
  that were not admitted. Use `accepted` only after the scheduler has enough
  validated data to execute later.
- Simulators, dry-run paths and metadata-only paths must set
  `hardware_outputs_enabled=false` and must not imply camera, LED, GPIO, motor
  or live controller execution.
- Logical IO aliases are metadata records, not output authority. Candidate
  aliases must not be treated as active outputs, and superseded or rejected
  pins cannot become active aliases without explicit re-review evidence.
- Software-only readiness results may report `ready_for_dry_run`, but they must
  still carry a `live_test_gate` reason when live test approval has not been
  granted. That reason is not a dry-run blocker; it prevents dry-run readiness
  from being interpreted as approval to flash firmware or command hardware.
- Passive `live_metadata` adapters may expose already-captured
  controller-neutral protocol events. They are not command/control adapters and
  must not open serial, submit scanner commands, toggle outputs or authorize
  live scanner-sync execution.

## Event Contract

- The MCU is the timing master. Linux wall-clock time is diagnostic only and
  must not identify frames or derive coordinates.
- `FRAME_EVENT` is the source of frame identity, scan coordinates, LED pattern
  metadata and Z state. A camera frame without a matching event is invalid
  scan data.
- Frame events are position-indexed. Initial coordinates use commanded step
  counts; schemas must remain ready for future encoder-indexed or hybrid
  coordinates.
- Each `FRAME_EVENT` identifies `scan_id`, `stripe_id`, global `frame_id`,
  `stripe_frame_index`, `position_axis`, `event_position`,
  resolved `x_count`, `y_count`, `z_count`, coordinate source, optional
  encoder counts, MCU timestamp and hardware-output state.
- `event_position` is the scheduled position. `sample_position` is the sampled
  position that crossed it. `position_overshoot_count` is signed as
  `sample_position - event_position`.
- `SCHEDULER_TERMINAL` is emitted for host stop, scheduler fault or exhausted
  position sample stream and reports emitted count, expected count, last
  emitted frame, next frame id, reason and `hardware_outputs_enabled=false` for
  simulator paths.
- Predictive Z events are explicit: `Z_SCHEDULED` means accepted for future
  execution, `Z_APPLIED` means applied at the reported future frame or
  position, and `Z_REJECTED` means the correction will not be applied.

## Math

- The frozen firmware math contract is
  `firmware_math_units_sign_rounding_v1`, represented in
  `scanner_firmware.domain.scan_math.contracts`. Tests must fail if these
  names or constants drift without a reviewed contract update.
- Position counts are scheduler coordinates. Physical units are domain
  quantities. Names must carry units (`*_count`, `*_um`, `*_us`) and conversion
  must happen at explicit calibration or adapter boundaries.
- Controller counts are unitless integer scheduler coordinates. Millimeters and
  micrometers are physical distances. Microseconds are timing durations and
  must not be mixed with frame ids or position counts. `1 mm = 1000 um` and
  `1 um = 1000 nm`.
- Physical-unit conversions to integer nanometers or controller steps use
  deterministic half-away-from-zero rounding, never implicit banker rounding.
- Derived motion constants, including steps-per-mm, counts-per-um, exposure
  lead, settle distance and Z correction bounds, must come from recipe,
  calibration or platform config/domain objects. Do not hardcode scanner
  mechanics in planner code.
- Direction is signed. Positive and negative stripes use the same record
  fields, but comparisons and pitch advancement must honor the signed scan
  direction.
- Stripe-relative progress is measured from the stripe's planned movement
  bounds, while acquisition progress is measured from event positions.
  `start_position` is not automatically the first acquisition event.
- Overshoot is signed as `sample_position - event_position` and retained. Do
  not silently replace scheduled event coordinates with an overshot sample
  position.
- Lead, settle and lookahead windows are explicit recipe or config values.
  Predictive Z must be scheduled into a future frame or future position far
  enough ahead for motion limits and settle policy.
- `z_target_*` values are absolute commanded Z targets unless a field is
  explicitly named `z_delta_*`, `z_error_*` or `z_correction_*`. Focus error
  samples and correction deltas must not be serialized as absolute targets
  without conversion at the owning planner boundary.
- No-correction windows are valid policy. Inside them, planners must reject,
  defer or coalesce corrections rather than issue immediate current-frame Z
  movement.
- Calibration lookup must be deterministic, bounded and documented at the
  lookup boundary. Missing, out-of-range or ambiguous calibration data is a
  rejection or fault according to the owning state machine; it is not guessed.
- Math boundary failures reject commands before scheduling when the request can
  be tied to a command (`invalid_target`, `insufficient_lookahead`,
  `z_limit_exceeded`, `target_outside_stripe`, `no_correction_window`). Runtime
  coordinate-source or stream consistency failures are scheduler faults, not
  inferred coordinates.
- Focus metrics for autofocus consume RAW Bayer or explicitly linear image
  data. JPEG, preview or nonlinear frames are invalid focus inputs.

## Interfaces

- Implementation modules are imported directly from responsibility-specific
  modules. Do not add package `__init__.py` re-export facades.
- Package initializers are namespace markers. They may name subpackages for
  discoverability, but they must not import and re-export implementation
  classes, functions or constants.
- `model.py` is allowed only when it owns concrete data models or local
  contracts. Do not use `model.py` as a compatibility facade for unrelated
  implementation modules.
- Component packages must not accumulate large flat lists of unrelated modules.
  Split into subpackages by responsibility once a directory becomes a dumping
  ground.
- Architecture tests and guardrails must enforce facade and flat-structure
  rules. Allowlists are permitted only for documented migration exceptions,
  with the exception named in the test.
- Current documented exceptions are:
  `src/scanner_firmware/domain/calibration/__init__.py` as a migration
  initializer; `src/scanner_firmware/adapters/klipper_adapter/model.py`,
  `src/scanner_firmware/adapters/klipper_adapter/event_streaming/model.py`,
  `src/scanner_firmware/domain/platform_config/model.py` as cohesive model or
  local contract modules; and `src/scanner_firmware/domain/calibration` as a
  flat package while its LED and axis calibration responsibilities remain
  intentionally grouped.

## Agent And PR Rules

- Add new contracts here first or in the same PR that introduces them.
- Update tests or architecture guardrails in the same PR as any new naming,
  event, state-machine, math or interface convention.
- Keep changes software-only unless a separate reviewed hardware-affecting
  procedure explicitly approves live hardware execution.
- Do not make clinical or regulatory claims in firmware docs or comments.
