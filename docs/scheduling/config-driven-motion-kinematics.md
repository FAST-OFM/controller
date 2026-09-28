# Config-Driven Motion Kinematics

Motion resolution is derived from machine configuration. It must not be copied
into firmware, Pi-side planning code or documentation as an independent source
of truth.

The executable model lives in `src/board_profile/kinematics.py`. Board profiles
may include documented derived values for readability, but tests validate those
values against the input configuration so stale hand-copied constants fail.

## Formula

```text
steps_per_rev = motor_full_steps_per_rev * microsteps
steps_per_mm = steps_per_rev / travel_per_rev_mm
steps_per_um = steps_per_mm / 1000
```

## Current Bring-Up Inputs

The current MKS Robin Mini V2.0 bring-up uses:

```text
motor: NEMA11
driver: A4988
motor_full_steps_per_rev: 200
microsteps: 16
x_travel_per_rev_mm: 2.0
y_travel_per_rev_mm: 2.0
z_travel_per_rev_mm: 0.5
```

Derived values:

```text
X = 1600 steps/mm
Y = 1600 steps/mm
Z = 6400 steps/mm = 6.4 steps/um
```

These values are calculated outputs. If the config changes, the derived values
must be recalculated.

## Homing Note

The current A4988 setup has no sensorless-homing feedback path. Future
RP2040/Pico sensorless homing requires driver hardware with a diagnostic/stall
signal and a separate safe homing validation plan.
