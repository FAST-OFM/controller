# Firmware Base Evaluation

Status: V1 path selected for continued implementation. Klipper scanner-sync
live metadata is the current firmware-base path for this prototype phase.
grblHAL and an external RP2040 sync-board remain fallback/evaluation paths, not
active implementation targets.

This spike exists to avoid writing a full motion planner from scratch. The
decision must be based on tests, maintainability and safety constraints, not
preference for a specific firmware stack.

## Candidates

| Candidate | Why consider it | Main risk |
|---|---|---|
| Klipper | Raspberry Pi + MCU architecture, SKR Pico support, mature step scheduling | 3D-printer assumptions, deep integration may be needed |
| grblHAL | CNC-oriented, HAL/plugin architecture, RP2040 support | Host/metadata model must be tested |
| External RP2040 sync-board | Fastest fallback, can monitor STEP/DIR and generate trigger/LED | Adds board and sync complexity |
| Custom Pico SDK from scratch | Maximum control | Motion planning burden too high initially |

## Spike scenario

For each candidate, the same minimum scenario must be evaluated:

1. Move X at constant velocity.
2. Generate camera trigger every N X steps or equivalent position interval.
3. Generate LED pattern: BF, BF, BF, AF.
4. Emit frame_id and position metadata to Pi.
5. Accept a scheduled Z command.
6. Demonstrate safe stop.

Before any hardware output test, run a dry-run/simulator variant:

1. Feed synthetic commanded X positions into the position-event scheduler.
2. Emit `FRAME_EVENT` records only.
3. Confirm `hardware_outputs_enabled=false`.
4. Confirm frame IDs, stripe indices, pattern sequence and positions.
5. Confirm invalid schedules are rejected.
6. Confirm stop/fault prevents further event emission.

## Measurement

Use oscilloscope or logic analyzer only after a hardware test procedure is
approved:

- X STEP;
- CAMERA_TRIG;
- LED_WHITE;
- LED_RED;
- LED_GREEN;
- diagnostic frame GPIO.

Metadata checks:

- exactly one `FRAME_EVENT` per emitted trigger in hardware-output mode;
- strictly increasing `frame_id`;
- correct stripe frame index;
- correct LED pattern ID;
- commanded position matches scheduled position within documented tolerance;
- missing/extra frame events are detected as faults.

Timing and jitter criteria must be recorded per candidate:

- trigger edge jitter relative to scheduled position;
- LED gate timing relative to trigger edge;
- diagnostic frame GPIO timing relative to `FRAME_EVENT` emission;
- safe stop latency to outputs inactive;
- whether the result depends on host/Linux userspace timing.

Any candidate that requires Linux wall-clock timing for frame identity or
coordinates fails the architecture requirement.

## Recommendation rule

Choose the base that passes the spike with the least invasive fork and best maintainability.

Do not recommend a base until:

- the dry-run scheduler path passes;
- at least one candidate has a reviewed no-hardware or bench-safe test result;
- hardware-impacting assumptions are explicit;
- fork/plugin maintenance cost is documented;
- homing and coordinate-source metadata paths are documented.

## Current Status

- Current board discovery is complete for MKS Robin Mini V2.0 identity and
  active Klipper X/Y/Z pin map.
- Existing bring-up has used Klipper for X/Y/Z and current `PD6` / E0_STEP
  trigger/sync signaling. `PC4` / Z+ is retained only as a legacy/config
  artifact unless explicitly revalidated.
- A dry-run position-event scheduler simulator exists.
- Scanner-sync protocol, event-stream, Stage A disabled host-extra and
  software-only atomic illumination-window work now make Klipper the selected
  V1 implementation path for live metadata development.
- The selected V1 path is not approval to enable scanner-sync outputs, flash
  the MKS, move motors, trigger the camera or strobe LEDs. Those remain gated
  by separate reviewed live-test procedures.
- No LED strobe outputs, final camera trigger path, spare GPIO, encoder
  inputs, firmware flashing/debug flow or external hardware workflows have
  been exercised.
- Therefore the next implementation step should stay in dry-run/simulator mode
  until a separately approved bench-safe procedure authorizes live metadata or
  output tests.

See `docs/evidence/firmware-base-spike-evidence.md` for the current no-hardware
evidence record and remaining candidate-specific gaps.

See `docs/foundation/bench-safe-timing-procedure.md` before proposing any timing capture
that uses real controller signals, motion, GPIO, LED or camera outputs.

## Current V1 Recommendation

Use the Klipper scanner-sync live metadata path for V1.

This recommendation is intentionally bounded:

- It selects the next implementation path, not a permanent product firmware
  base.
- It does not approve live GPIO, LED, XVS, motor, homing or flashing tests.
- It keeps grblHAL as an alternate firmware-base candidate if Klipper becomes
  too invasive.
- It keeps the external RP2040 sync-board as the fallback if Klipper cannot
  provide maintainable position-indexed trigger/LED timing and metadata.
- It preserves the architecture rule that the MCU side owns timing and
  `FRAME_EVENT` identity; Linux userspace must not define frame coordinates.
