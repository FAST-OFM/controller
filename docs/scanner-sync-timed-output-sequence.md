# Scanner Sync Timed Output Sequence

This document defines the software-only contract for a generic low-level
MCU-timed output sequence in `scanner_sync`.

The sequence command is intended to replace one-off diagnostic commands for
HQ XVS trains, white/RG illumination windows and delay sweeps. It does not move
motors, home axes, flash firmware or touch GPIO by itself in this repository.
The live Klipper patch must implement the same contract before hardware use.
Before any stationary AF or timed-output live-output bench test, complete the
software-only gate in
`docs/klipper/klipper-timed-output-live-output-gate-checklist.md`.

The command is experimental and must be disabled by default in host
registration. `ScannerSyncKlipperRegistration` only registers
`scanner_sync_run_timed_output_sequence` and
`scanner_sync_timed_output_sequence_status` when
`enable_timed_output_sequence=True` is passed explicitly. Disabling the flag
removes the command and status response from the registration snapshot. Enabling
the flag requires a matching Klipper build; missing command bindings must fail
at config-registration time rather than silently falling back.

## Command

Canonical host-facing command name:

`scanner_sync_run_timed_output_sequence`

The live Klipper transport must not send the full encoded step payload as one
MCU message. Klipper message blocks are small, so the host extra stages the
sequence through bounded MCU commands:

1. `scanner_sync_begin_timed_output_sequence`
2. one `scanner_sync_add_timed_output_step` per encoded step
3. `scanner_sync_start_timed_output_sequence`

This preserves one generic interpreter while avoiding large `encoded_steps`
payloads on the MCU link.

Wire fields:

| Field | Meaning |
| --- | --- |
| `oid` | Klipper scanner_sync object id. |
| `seq` | Host command sequence for command tracking. |
| `stripe_id` | Stripe identity associated with sequence status and frame-event telemetry. |
| `seq_id` | MCU timed sequence identity. Reused in telemetry and stop/status records. |
| `mode` | Execution mode. V1 allows only `diagnostic_immediate`; `position_armed` is reserved. |
| `start_condition` | Start condition. V1 allows only `immediate`; `position_count` is reserved. |
| `start_position_count` | Future position-indexed start count, or unset for immediate diagnostic use. |
| `repeat_count` | Number of repeats. `0` means repeat until explicit stop/safe-state. |
| `frame_id_base` | Optional first expected frame identity for repeated diagnostic frame events. |
| `pattern_id` | Default logical illumination/capture pattern identity for telemetry and frame matching when a step does not provide one. |
| `safe_output_mask` | Logical outputs controlled by the accepted command's stop safe state. |
| `safe_output_values` | Logical values applied on host stop or owner loss after the command is accepted. |
| `idle_output_mask` | Logical outputs controlled by the normal completion idle state. |
| `idle_output_values` | Logical values applied after finite-repeat normal completion. |
| `step_count` | Number of encoded steps. Maximum `12` in the current live MKS contract. |
| `steps_crc32` | CRC32 of `encoded_steps`, for dictionary/transport corruption checks when a bulk transport is used. |
| `encoded_steps` | Compact little-endian step payload. In the live MKS transport this is decoded by the host extra and sent as staged step commands. |

`safe_output_*` defaults to all known controlled outputs off. For bench preview,
`idle_output_*` may restore `led_white` after a finite sequence. Infinite
preview trains (`repeat_count=0`) still require an explicit stop/safe-state
command before changing owner or mode. An all-outputs-off safety command must
be finite one-shot evidence, not an infinite one-microsecond loop.

## Step Encoding

Each step is exactly 10 bytes:

| Offset | Size | Field | Meaning |
| --- | ---: | --- | --- |
| 0 | 1 | `output_mask` | Logical outputs affected by this step. |
| 1 | 1 | `output_values` | New logical values for outputs selected by `output_mask`. |
| 2 | 1 | `pattern_id` | Per-step illumination/capture pattern for emitted `FRAME_EVENT`; `0` falls back to command `pattern_id`. |
| 3 | 1 | `reserved` | Must be `0`. |
| 4 | 4 | `delay_us` | MCU-local delay after applying this step. |
| 8 | 2 | `event_flags` | Optional semantic markers for telemetry. |

`output_values` must not set bits outside `output_mask`. Outputs not selected
by `output_mask` must retain their prior state. This means outputs are latched
by the MCU until a later step changes them.

A pause/hold is encoded as a normal step with `output_mask=0`,
`output_values=0` and a positive `delay_us`. It changes no outputs and advances
only MCU-local time. Use this for exposure hold, post-exposure hold, inter-frame
spacing and diagnostics where the current LED/XVS state must remain unchanged.

The live MKS build limits the encoded step count to 12. Long repeated trains
must encode one short pattern, such as one white/RG pair, and use
`repeat_count`; they must not inline hundreds of one-off steps.

The initial MKS V1 logical output bit assignment is intentionally a contract,
not a board-pin claim:

| Bit | Logical output |
| ---: | --- |
| 0 | `led_white` |
| 1 | `led_red` |
| 2 | `led_green` |
| 3 | `hq_xvs_sync` |

Board-specific pin mapping remains in board profiles and live Klipper config.
Unknown output bits must be rejected until the logical output map is updated and
versioned.

## Event Flags

| Flag | Meaning |
| ---: | --- |
| `0x0001` | Emit or associate a `FRAME_EVENT` at this step. |
| `0x0002` | XVS rising edge starts at this step. |
| `0x0004` | XVS falling edge starts at this step. |
| `0x0008` | Logical sequence window end. |
| `0x0010` | Expected exposure window starts at this step. |
| `0x0020` | Expected exposure window ends at this step. |

Future flags may add ADC sampling, safe-state, exposure-window markers or
debug timestamp capture. Unknown flags must be rejected until documented.

When a step sets `0x0001`, the MCU must emit the associated `FRAME_EVENT` at
that step, copy the step `pattern_id`, and copy the full known `event_flags`
bitmask into the response `flags` field. Host decoding must expose the copied bitmask as
`event_flags` and derive `event_flag_names` from the documented table above.
The host must reject any `FRAME_EVENT.flags` bits outside the known mask. Frame
identity must increment per emitted frame event, not merely per repeat. Frame
coordinates and `mcu_time_us` remain MCU-local metadata; Linux arrival time or
wall-clock time must not be used to infer the frame.

## Status Event

MCU-to-host status telemetry uses:

`scanner_sync_timed_output_sequence_status`

Wire fields:

| Field | Meaning |
| --- | --- |
| `oid` | Klipper scanner_sync object id. |
| `seq` | Host command sequence from the request, when available. |
| `stripe_id` | Stripe identity associated with the sequence. |
| `seq_id` | MCU timed sequence identity from the request. |
| `status` | Lifecycle state: `accepted`, `rejected`, `started`, `completed`, `stopped` or `fault`. |
| `reason` | Machine-readable reason code, such as `accepted`, `invalid_command`, `finite_completion`, `host_stop` or `fault`. |
| `repeat_index` | Number of completed repeats at the status point. |
| `step_index` | Next step index at the status point. |
| `mcu_time_us` | MCU-local timestamp for the status event. |

`repeat_index` is the canonical firmware-side name for repeat progress. Pi
adapters may expose a compatibility alias such as `completed_repeats`, but
persisted evidence should preserve `repeat_index`.

## State Model

The interpreter is a linear MCU-local state machine:

1. Validate the envelope, CRC and step count.
2. Apply or verify the requested start condition. V1 starts immediately.
3. For each step, atomically update all outputs selected by `output_mask`.
4. Wait `delay_us` on the MCU clock.
5. Repeat from the first step when `repeat_count` requires another cycle.
6. On finite completion, apply `idle_output_*`.
7. On host stop or owner loss after command acceptance, apply `safe_output_*`.
8. On invalid command, CRC failure or internal fault where command state may be
   untrusted, force all known controlled outputs off.

Timer callbacks must not call `sendf()` directly. The timer state machine stores
`FRAME_EVENT` and sequence status records in bounded MCU queues and wakes a
Klipper task. The task handler sends responses to the host.

The live MKS Robin Mini V2 bench build must use a slim MCU configuration. The
staged interpreter has been smoke-tested with GPIO, steppers, endstops,
hardware PWM and `scanner_sync` enabled, while unused Klipper MCU optional
features such as ADC, SPI, I2C, TMCUART, LCD, neopixel and sensor modules are
disabled. A broad default Klipper MCU feature build produced a larger image
that the board bootloader accepted but the MCU app did not answer after reboot.
Treat slim MCU configuration as part of the live MKS protocol contract until
the exact controller flash limits are characterized.

The sequencer must not command steppers, change LED brightness/current, perform
camera capture, infer frame identity from Linux time or run autofocus math.
Brightness belongs to the illumination driver layer. Frame identity and
coordinates belong to `FRAME_EVENT` metadata.

## HQ Sync-Sink Preview Shape

For HQ camera sync-sink preview, use a nonblocking repeated sequence rather
than a blocking G-code macro:

1. Apply RG or white state before the camera frame boundary.
2. Wait `RG_LEAD_US` or the selected white lead interval.
3. Raise `hq_xvs_sync` and mark `FRAME_EVENT | XVS_RISING`.
4. Hold `XVS_PULSE_US`.
5. Lower `hq_xvs_sync` and mark `XVS_FALLING`.
6. Keep illumination active through the rolling-shutter frame coverage window
   with one or more pause/hold steps.
7. Restore the idle illumination state and mark `EXPOSURE_END | END` when the
   configured post-exposure guard interval has elapsed.
8. Delay to complete `FRAME_PERIOD_US`, then repeat.

The command supports `repeat_count=0` so preview can keep the camera alive until
an explicit stop command. Production fly-scan must still use future
position-indexed arming; Linux wall-clock time must not become the frame source
of truth.
