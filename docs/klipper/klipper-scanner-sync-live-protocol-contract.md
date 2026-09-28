# Klipper Scanner-Sync Live Protocol Contract

Status: software contract. This document does not approve live firmware
flashing, scanner-sync enablement or hardware outputs.

## Host-To-MCU Commands

The project-level commands map to Klipper scanner-sync command formats as
follows:

| Project action | Klipper command | Notes |
|---|---|---|
| Start metadata scheduler | `scanner_sync_start` | Starts from a host-provided `next_frame_id` |
| Stop scheduler | `scanner_sync_stop` | Must produce `SCHEDULER_TERMINAL` |
| Schedule future Z | `scanner_sync_schedule_z` | Target must be future frame or future position |
| Arm AF illumination window | `scanner_sync_arm_af_window` | Position-indexed scan command; fires at `trigger_position_count` |
| Fire AF window now | `scanner_sync_fire_af_window_now` | Diagnostic bench command only; must carry explicit event position |
| Run stationary AF timing test | `scanner_sync_run_stationary_af_test` | Diagnostic no-motion series for tuning LED/XVS timing |

`scanner_sync_schedule_z` must reject late, ambiguous or out-of-window targets.
It must not be equivalent to an immediate `move_z_now`.

`scanner_sync_arm_af_window` is the normal scan path for red/green AF timing:
the MCU arms a future position-count event, then uses MCU-local timing offsets
inside that window for LED settling, XVS pulse width and exposure hold.

`scanner_sync_fire_af_window_now` exists for local bench tests without motion.
It must not be used as a production scan scheduling primitive and must not
replace position-indexed window arming.

`scanner_sync_run_stationary_af_test` is the repeatable bench command for
tuning no-motion LED/XVS timing. It carries `first_frame_id`, `frame_count`,
`frame_period_us`, `event_position_count`, `settle_us`,
`xvs_trigger_pulse_us` and `exposure_hold_us`. Its intended live sequence is:
white baseline off, red and green on together, wait `settle_us`, pulse XVS,
hold red and green through `exposure_hold_us`, turn red and green off together,
then restore white. The command is diagnostic-only. It must not command motors,
perform homing, replace `scanner_sync_arm_af_window`, or infer frame identity
from Pi/Linux time.

## MCU-To-Host Events

The Klipper response names map to project protocol events:

| Klipper response | Project event |
|---|---|
| `scanner_sync_frame_event` | `FRAME_EVENT` |
| `scanner_sync_scheduler_terminal` | `SCHEDULER_TERMINAL` |
| `scanner_sync_z_scheduled` | `Z_SCHEDULED` |
| `scanner_sync_z_applied` | `Z_APPLIED` |
| `scanner_sync_z_rejected` | `Z_REJECTED` |

These names must remain uniform across Klipper patch code, Pi code, docs,
fixtures and issues.

`SCHEDULER_TERMINAL` is not a clean-completion event. It is emitted only when a
host stop or fault prevents the remaining planned `FRAME_EVENT` records for a
stripe. A clean stripe completion is represented by the expected contiguous
`FRAME_EVENT` records and no terminal record.

## `FRAME_EVENT` Required Meaning

Every `FRAME_EVENT` must describe the acquisition event chosen by MCU-side
logic:

- `frame_id`;
- `stripe_id`;
- `stripe_frame_index`;
- LED or pattern identity;
- coordinate source used;
- X/Y/Z commanded counts;
- future encoder counts when available;
- MCU time for diagnostics only;
- hardware output state;
- homing or coordinate-validity flags when implemented.

The current initial coordinate source is commanded step count. The contract must
remain compatible with future linear encoder coordinates.

Camera frame arrival may wake host processing, but it must not define frame
identity or coordinates.

For the current Phase 1 stub contract:

- `FRAME_EVENT status=0` decodes to `ok`;
- `FRAME_EVENT flags=0` means no additional flags are set;
- non-zero `FRAME_EVENT flags` must be rejected until the bit layout is
  documented.

## Scan Identity

The project protocol includes `scan_id`. If the first Klipper MCU payload cannot
carry a variable-length scan id, the host decoder must attach the active
`scan_id` from the scanner-sync session context. That context must be explicit
and testable; hidden chat memory or ad-hoc operator notes are not source of
truth.

Other host-enriched Phase 1 fields must also be explicit in tests. Current
examples include:

- `coordinate_source_used=step_indexed`;
- `hardware_outputs_enabled=false`;
- terminal `message` defaulting to an empty string;
- terminal `last_frame_id=-1` decoding to absent when no frame has been
  emitted;
- terminal `next_stripe_frame_index` carrying the next per-stripe frame index.

Host-side response dispatch is represented by
`src/klipper_adapter/dispatch.py`. It converts Klipper callback payloads into
project protocol records using an explicit `ScannerSyncDecodeContext`; it does
not send commands or access hardware. The same dispatcher can validate the
decoded sequence with the offline event-stream rules before a capture is
accepted as a usable metadata result.

## Hardware Output Flag

Metadata-only Stage B must report:

```text
hardware_outputs_enabled=false
```

Hardware-output modes require a later reviewed bench-safe plan and must still
emit one `FRAME_EVENT` for every physical camera trigger.

## Homing And Coordinate State

Scanning must not proceed without a valid homing state. The current MKS setup
does not yet implement verified homing hardware. Until homing is implemented,
live scanner-sync work must remain metadata-only planning or explicitly
bench-safe.

Future firmware payloads should reserve flags for:

- not homed;
- homed from physical switch;
- homed from sensorless detection;
- homed from encoder index;
- coordinate source degraded or invalid.

## Z State

Z scheduler acknowledgements are part of the same protocol:

- `Z_SCHEDULED` confirms a future correction was accepted;
- `Z_APPLIED` confirms when the MCU applies it;
- `Z_REJECTED` explains why a correction could not be scheduled.

For the current Phase 1 Klipper wire contract, `Z_APPLIED` carries `seq`,
`frame_id`, `z_cmd_count` and `status`; it does not carry `stripe_id`. The host
decoder must preserve this as `stripe_id=null` unless a later reviewed wire
format adds the field. Correlation must use the explicit scan/session context
and `seq`, not a guessed stripe id.

The host must treat missing Z acknowledgements as a fault or incomplete
experiment result, not as success.
