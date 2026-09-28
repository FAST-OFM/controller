# Klipper Read-Only Inspection

Status: read-only evidence. This is not a firmware-base decision and not an
approval to modify the live Pi/Klipper installation.

## Scope

This inspection looked at the existing Raspberry Pi 5 Klipper checkout without
editing files, restarting Klipper, flashing firmware, moving axes, toggling
GPIO, triggering the camera or powering LEDs.

Observed Klipper checkout:

- host: Raspberry Pi 5 over VPN/SSH
- path: `~/klipper`
- branch: `master`
- commit: `c707dd19214709dc23684b254a68e3bf69e4cfb3`
- repository status at inspection time: clean

## Files Inspected

The following Klipper files provide useful extension patterns:

- `klippy/extras/output_pin.py`
- `klippy/extras/motion_report.py`
- `klippy/extras/pulse_counter.py`
- `klippy/extras/static_digital_output.py`
- `klippy/mcu.py`

## Useful Patterns

`output_pin.py` shows how a host module can queue digital or PWM pin state
changes through Klipper MCU pins and command queues. It uses lookahead and
flush callbacks rather than simple synchronous G-code calls. This is relevant
for studying scheduling mechanics, but it is not enough by itself for the
scanner event path because per-frame host-side G-code round trips are not
acceptable.

`motion_report.py` shows how Klipper exposes requested toolhead position and
trapq-derived motion information. This can support diagnostics and dry-run
fixtures, but frame identity and scanner coordinates must not be inferred from
Linux wall-clock time.

`pulse_counter.py` shows the pattern for scanner-like MCU object ownership:

- allocate an MCU object id with `create_oid()`;
- register configuration callbacks with `register_config_callback(...)`;
- add MCU config commands with `add_config_cmd(...)`;
- register MCU-to-host responses with `register_serial_response(...)`.

`mcu.py` exposes the host-side command and response lookup mechanisms that a
future scanner extension would likely need:

- `create_oid()`;
- `register_config_callback(...)`;
- `add_config_cmd(...)`;
- `lookup_command(...)`;
- `try_lookup_command(...)`;
- `alloc_command_queue(...)`;
- `register_response(...)`;
- `register_serial_response(...)`.

## Candidate Scanner Extension Shape

A future Klipper-based scanner extension should be evaluated as a dedicated
host/MCU scanner module, not as a sequence of per-frame G-code macros.

The likely shape is:

1. A Klipper host extra such as `scanner_sync.py` loads scanner-specific config.
2. The host module registers an MCU object and config commands during Klipper
   configuration.
3. The MCU-side code owns position-indexed scanner event scheduling.
4. The MCU emits `FRAME_EVENT`, `SCHEDULER_TERMINAL`, `Z_SCHEDULED`,
   `Z_APPLIED` and `Z_REJECTED` records to the host.
5. The host can send future-position `schedule_z` commands to the MCU.
6. The Pi acquisition process consumes the scanner event stream and matches
   camera frames by event metadata, not by Linux timestamps.

This shape preserves the architecture requirement that the MCU is the timing
master and acquisition events are position-indexed.

## Dry-Run Contract

The current local dry-run boundary is `src/scanner_sync/dry_run_service.py`.
It composes scan recipes, dry-run scheduling and protocol record serialization
without importing Klipper or touching hardware.

Any first Klipper-adapter code in this repository should stay on that side of
the boundary:

- no serial connection to the live MCU;
- no Klipper service restart;
- no writes to the Pi checkout;
- no pin toggling;
- no camera trigger;
- no LED output;
- no motor motion;
- no firmware flashing.

The first acceptable adapter implementation is a fake/local adapter that
models the Klipper API calls listed above and proves registration flow in
unit tests only.

## Local Adapter Foundation

The local foundation for that first step is:

- `src/klipper_adapter/model.py`: protocol-only Klipper MCU API contract;
- `src/klipper_adapter/fake.py`: dry-run MCU fake that records registration
  calls and blocks serial/send paths;
- `src/klipper_adapter/scanner_sync.py`: dry-run scanner-sync registration
  plan for future Klipper command and response names.
- `src/klipper_adapter/codec.py`: local encode/decode contract for
  `schedule_z` and synthetic scanner-sync response params.
- `src/klipper_adapter/dry_run_harness.py`: local harness that composes fake
  Klipper registration, scan dry-run records and codec conversions.

The registration plan keeps Klipper message names lower-case and maps them to
the project protocol event names:

- `scanner_sync_frame_event` -> `FRAME_EVENT`;
- `scanner_sync_scheduler_terminal` -> `SCHEDULER_TERMINAL`;
- `scanner_sync_z_scheduled` -> `Z_SCHEDULED`;
- `scanner_sync_z_applied` -> `Z_APPLIED`;
- `scanner_sync_z_rejected` -> `Z_REJECTED`.

The current command bindings are `scanner_sync_start`, `scanner_sync_stop` and
`scanner_sync_schedule_z`. They are registration records only; no live command
send path is implemented.

The codec is not an approved live Klipper binary protocol. It exists to keep
field names, units and event-name mapping testable while the firmware base
spike remains in dry-run mode.

The dry-run harness is the highest integration level currently allowed in this
repository. It proves object registration, frame-event generation and
`schedule_z` payload conversion in memory only.

## Open Questions

- Can the MCU-side Klipper command protocol carry scanner events at the needed
  rate without per-frame host scheduling?
- How invasive would a maintainable MCU-side extension be?
- Where should `FRAME_EVENT` records be encoded: Klipper binary message,
  scanner-specific packed payload, or host-side JSONL after decoding?
- How should future `schedule_z` commands be acknowledged when the requested
  correction is too late, too large or outside safe Z limits?
- How will homing state and future encoder metadata enter `FRAME_EVENT`
  records?

The proposed live Klipper patch shape and required review gates are documented
in `docs/klipper/klipper-scanner-sync-patch-proposal.md`.

## Hardware Boundary

This inspection does not approve hardware execution. The next live step must
be reviewed separately before any of the following occur:

- firmware flashing;
- Klipper config writes or service restart;
- motor motion;
- GPIO toggling;
- camera trigger output;
- LED output;
- oscilloscope timing test on live scanner wiring.
