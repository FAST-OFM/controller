# homing

Homing foundation.

This module must make homing a first-class firmware state, not an incidental
G-code macro side effect.

Initial work is documentation and simulator design only. Do not run motors,
change Klipper config or assume unverified switch wiring from this module.

## Current Homing Status

There is no verified homing implementation on the current scanner setup.

The software model keeps this as explicit data. `feasibility.py` exposes a
software-only `HomingFeasibilitySnapshot` with scan preflight status values of
`implemented`, `not_implemented` or `unknown`. `readiness.py` evaluates whether
the available evidence satisfies scan-start homing. The current MKS Robin Mini
V2.0 / A4988 snapshot is `not_implemented`; its per-axis sensorless evidence is
`not_supported`, and unresolved physical-switch or encoder/index evidence
remains `unknown`.

The active Klipper config contains endstop pin assignments, but those are
configuration-level candidates only. They do not mean that physical switches,
sensorless homing, polarity, connector mapping, repeatability or safe homing
behavior have been verified.

The current active Klipper config also contains a `[homing_override]` for
`axes: xyz`, but that override only sets a temporary kinematic position:

```gcode
SET_KINEMATIC_POSITION X=100 Y=100 Z=0
G90
```

This is not physical homing.

In readiness terms, that macro is represented as
`homing_override_sets_position`. It may explain a temporary coordinate value,
but it never counts as a physically homed axis for scan start.

A single `QUERY_ENDSTOPS` readback after explicit test permission returned
inactive/zero states for X, Y and Z while `toolhead.homed_axes` remained empty.
That readback is not proof of connector mapping, switch polarity under
actuation, repeatability or safe homing.

## Current Board Config Candidates

From the active MKS Robin Mini V2.0 Klipper config:

- X endstop: `!PA15`
- Y endstop: `!PA12`
- Z endstop: `!PA11`

The `!` polarity is Klipper syntax from the current config. Treat physical
switch type, connector mapping, debounce behavior and fail state as unverified
until reviewed or measured.

## Future Pico Sensorless Homing Candidate

For a future Pico-based controller, homing may be possible without discrete
endstop switches if the selected stepper drivers expose reliable stall or
load-detection feedback.

Treat this as a candidate approach, not an assumption:

- driver-assisted homing must be validated per axis;
- stall threshold must be configurable and repeatable;
- homing into a hard mechanical stop must be reviewed for force/current risk;
- the method must distinguish real end-of-travel from friction, cable drag,
  acceleration spikes or sample-stage contact;
- Z sensorless homing needs stricter review because it can create
  slide/objective collision risk;
- encoder-ready metadata must still remain supported.

The firmware homing abstraction must support both:

- physical switch homing;
- driver-assisted/sensorless homing;
- future encoder/index homing.

## Required State Machine

```text
IDLE
  -> CHECK_SAFE
  -> PRE_HOME_Z_POLICY
  -> SEEK_FAST
  -> BACKOFF
  -> SEEK_SLOW
  -> SET_MACHINE_ZERO
  -> VERIFY_RELEASE_OR_REPEAT
  -> HOMED
```

Any timeout, impossible switch transition, host stop, overtravel risk or
unexpected state transition must go to `HOMING_FAULT`.

## Safe Behavior

- Homing is required before a real scan unless an explicit simulator mode is
  active.
- Simulator mode may bypass missing homing only while hardware outputs are
  disabled; that result must remain marked safe-disabled and warning-only.
- Hardware outputs unrelated to homing remain inactive: LEDs off, camera
  trigger disabled, diagnostic GPIO disabled.
- Z homing policy must be explicit before any XY homing that could risk the
  objective/slide path.
- Homing must have soft travel limits and timeouts.
- Homing must log commanded counts at switch transitions.
- Homing must not assign scan coordinates until all required axes are homed.

## Coordinate Outputs

After successful homing, firmware may expose:

- machine coordinates in commanded counts;
- machine coordinates in configured units after applying axis scale;
- homing status per axis;
- homing repeatability diagnostics.

Slide, ROI and image coordinates remain higher-level calibrated coordinate
systems and must not be inferred from homing alone.
