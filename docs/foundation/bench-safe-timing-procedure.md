# Bench-Safe Timing Procedure Draft

Status: draft, not approved for execution.

This procedure defines the evidence needed before selecting a firmware base for
position-indexed scanner events. It does not approve motor motion, GPIO output,
camera triggering, LED strobing or firmware flashing.

## Scope

Use this procedure to compare:

- Klipper-based scanner event extension;
- grblHAL plugin or extension;
- external RP2040 sync-board fallback.

The procedure exists because the firmware base must be selected from measured
behavior and maintainability evidence, not convenience alone.

## Required Architecture Checks

Every candidate must show:

- frame events are position-indexed;
- frame identity and coordinates are not inferred from Linux wall-clock time;
- `FRAME_EVENT` metadata includes frame ID, stripe frame index, position,
  coordinate source, LED pattern and Z state or scheduled Z state;
- camera frame arrival may start processing but does not define frame identity;
- future encoder coordinate sources are not blocked;
- homing state is available as a scan precondition;
- hardware outputs fail inactive on stop/fault.

## Phase 0: Dry-Run Fixture

Approved to run in the repository simulator only.

Inputs:

- synthetic Klipper-like commanded position samples;
- synthetic grblHAL-like planner snapshots;
- synthetic external sync-board STEP/DIR pulse samples.

Required checks:

- common scheduler receives `PositionSample` records;
- generated `FRAME_EVENT` records have strictly increasing `frame_id`;
- stripe frame index resets per stripe;
- LED pattern metadata follows the recipe;
- `hardware_outputs_enabled=false`;
- stop/fault prevents further event emission.

Expected artifact:

- test command and result;
- short note linking candidate stream fixture to the relevant issue or PR.

## Phase 1: No-Motion Electrical Review

Not approved by this document. Requires explicit issue comment approval before
execution.

Preconditions:

- controller board and wiring photographed;
- board revision, MCU and current firmware recorded;
- output candidate pins named from documentation and active config;
- camera, LEDs and external trigger loads disconnected;
- common ground or isolation strategy reviewed;
- logic analyzer or oscilloscope input impedance and voltage range confirmed;
- emergency power-off method identified.

Allowed evidence after approval:

- idle voltage level on candidate diagnostic outputs;
- inactive state polarity;
- whether the signal is safe for a Pi, logic analyzer or isolator input.

Disallowed in this phase:

- motor motion;
- homing;
- firmware flashing;
- camera trigger output into a camera;
- LED strobe output into LEDs;
- changing microsteps, current/Vref or pin mappings.

## Phase 2: No-Load Timing Capture

Not approved by this document. Requires a separate reviewed procedure.

Allowed candidate setups after approval:

- synthetic STEP/DIR source into an external sync-board input;
- firmware simulator or bench controller with no motors connected;
- logic-analyzer capture of diagnostic outputs with camera and LEDs
  disconnected.

Required capture channels, where applicable:

- position source: STEP and DIR, or equivalent position tick;
- diagnostic frame output;
- camera-trigger-equivalent output;
- LED-white-equivalent output;
- LED-red-equivalent output;
- LED-green-equivalent output;
- stop/fault indicator if available.

Required measurements:

- trigger edge position error in counts;
- trigger edge jitter over repeated frames;
- LED gate timing relative to trigger edge;
- one-to-one mapping between trigger-equivalent output and `FRAME_EVENT`;
- safe stop latency to outputs inactive;
- behavior when a pulse, frame event or stop is intentionally missing in the
  synthetic fixture.

## Phase 3: One-Axis Low-Speed Timing Capture

Not approved by this document. Requires explicit approval with exact command,
operator, physical setup and emergency stop method.

Preconditions:

- `boards/kingroon_mono_v2/safe-test-plan.md` first-axis requirements are met;
- X-only low-speed motion has been approved;
- no slide or objective contact risk exists;
- the controller remains in the known-good Klipper configuration;
- no LED, camera or spare GPIO output test is combined with first motion unless
  separately approved.

Initial envelope:

- X axis only;
- relative jog from a temporary origin;
- feed rate 30 mm/min or slower;
- move magnitude 0.2 mm or less;
- total first-session travel 1.0 mm or less unless explicitly expanded.

Stop conditions:

- unexpected direction;
- stall, grinding or skipped steps;
- cable strain;
- motion toward a mechanical limit or unsafe area;
- Klipper disconnect or inconsistent state;
- operator uncertainty.

## Result Template

Record one result per candidate and phase:

```yaml
candidate: klipper | grblhal | external-rp2040-sync-board
phase: dry_run | no_motion_electrical_review | no_load_timing | one_axis_timing
date:
operator:
hardware_connected:
firmware_revision:
config_revision:
commands_or_fixture:
outputs_enabled: false
motors_enabled: false
camera_connected: false
leds_connected: false
measurements:
  frame_events:
  trigger_equivalent_edges:
  missed_events:
  jitter:
  stop_latency:
result: pass | fail | blocked
notes:
```

If any field is unknown, record it as `unknown`; do not fill guessed values.

## Recommendation Gate

Do not recommend a firmware base until:

- Phase 0 passes for all candidates that remain under consideration;
- at least one candidate has reviewed timing evidence from Phase 2 or Phase 3;
- firmware maintenance cost is documented;
- homing and coordinate-source metadata paths are documented;
- failures and blocked tests are recorded in the issue trail.

