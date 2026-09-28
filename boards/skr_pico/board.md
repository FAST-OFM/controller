# SKR Pico Board Profile

Profile state: `placeholder`.

Status: incoming.

## Purpose

Target RP2040-based motion board for first serious scanner controller experiments.

## Tasks

- Confirm board revision.
- Confirm firmware base support.
- Map stepper axes.
- Decide homing approach per axis:
  - physical endstop switch;
  - driver-assisted/sensorless homing if the selected drivers support
    reliable stall/load detection;
  - future encoder/index homing.
- Assign camera trigger output.
- Assign LED gate outputs.
- Assign diagnostics outputs.
- Confirm voltage levels and need for camera trigger level shifting.

## Sensorless Homing Candidate

The Pico-based controller may support homing based on stepper-driver feedback
instead of discrete endstop switches. This is a candidate feature only until
the exact board revision, driver model, firmware base and safe test procedure
are reviewed.

Current feasibility outcome: `unknown` for X, Y and Z.

Requirements before use:

- verify driver support for stall/load detection;
- define current, speed and threshold limits per axis;
- validate repeatability against the scan accuracy budget;
- handle false positives from friction, cable drag and acceleration;
- keep Z policy conservative because Z sensorless homing can create
  objective/slide collision risk.

See `docs/hardware/pico-sensorless-homing-feasibility.md`.
