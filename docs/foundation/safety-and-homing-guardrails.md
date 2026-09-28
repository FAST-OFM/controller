# Safety and Homing Guardrails

## Safe boot

On reset:

- motors disabled or in configured safe idle;
- LEDs off;
- camera trigger inactive;
- no scan state active;
- host must explicitly arm hardware outputs.

## Homing

Homing state machine must include:

- pre-home safe Z policy;
- homing source selection: physical switch, driver-assisted/sensorless, or
  future encoder/index;
- configurable direction/speed/current;
- configurable sensorless/stall threshold when driver-assisted homing is used;
- switch debounce/filtering;
- backoff and re-approach;
- homing failure timeout;
- homing repeatability logging;
- machine coordinate zero assignment.

Homing must fail closed. On any homing fault:

- stop motion;
- keep LEDs off;
- keep camera trigger disabled;
- keep diagnostic GPIO disabled unless explicitly approved for diagnostics;
- mark the affected axes unhomed;
- require operator review before retry.

Failure modes that must be represented in firmware and simulator tests:

- endstop active before motion begins;
- endstop never activates before timeout/travel limit;
- endstop remains active after backoff;
- wrong-direction movement;
- switch bounce/noise;
- sensorless/stall false positive;
- sensorless/stall false negative;
- host stop during homing;
- Klipper/controller disconnect during homing;
- Z policy not configured;
- soft limit missing or invalid.

## Scan preconditions

Scan may start only if:

- required axes are homed or explicit simulator mode is active;
- soft limits are configured;
- scan ROI is within limits;
- LED pattern is valid;
- camera trigger config is valid;
- coordinate source is valid.

The simulator preflight model encodes the same rule in
`src/scan_preflight/model.py`. Simulator mode may bypass missing homing only
when hardware outputs are disabled; it does not bypass invalid soft limits,
out-of-range ROI, invalid LED pattern, invalid trigger config or invalid
coordinate source.

The dry-run scanner sync service requires an accepted preflight decision before
stripe execution. This keeps simulator call paths aligned with the same
start-scan contract instead of letting tests bypass guardrails accidentally.

Dry-run scan recipes may include optional `soft_limits` mappings for `X` and
`Y`. When present, `src/trigger_scheduler/scan_plan.py` validates stripe start,
end, first-event and last-event positions against those limits before schedules
are built.

Coordinate systems:

- Machine coordinates are established by homing.
- Slide coordinates require fixture, slide-origin or calibration context.
- ROI coordinates are planning coordinates derived from scan recipe/prescan
  products.
- Image coordinates are pixel/tile coordinates derived from frame metadata and
  calibration.

Homing establishes machine zero only. It does not prove slide origin, ROI
alignment, camera rotation, pixel scale or tile placement.

Current board status:

- the existing MKS Robin Mini V2.0 setup has no verified homing method;
- its Klipper endstop pin assignments are config candidates, not proof of
  working homing;
- future Pico work may evaluate driver-assisted/sensorless homing, but that
  must be validated before use.

For Pico sensorless homing feasibility, track unknowns and per-axis outcomes in
`scanner-hardware/mechanics/homing/pico-sensorless-homing-feasibility.md`.
