# LED Scheduler

Simulator-only logical LED pattern support.

This package resolves scan pattern names into logical gate aliases:

- `BF_WHITE` -> `led_white`
- `AF_RED_GREEN` -> `led_red`, `led_green`
- `DARK` -> no gates

It deliberately does not know physical GPIO pins. Board profiles map logical
aliases such as `led_white` onto board-specific pins such as `PB13` / TC1 SCK.
No code in this package opens serial ports, toggles GPIO, flashes firmware,
commands motors, triggers cameras or powers LEDs.

`LogicalLedTimingModel` adds an isolated simulator timing plan:

- brightness setpoints are separate from frame-synchronous gate windows
- exposure windows are absolute microsecond intervals
- gate windows use only logical aliases and carry active-high/active-low
  polarity metadata
- preview baseline channels can be suppressed and restored around a pattern
  window, for example `led_white` off while `AF_RED_GREEN` is active and then
  back on after the exposure hold
- settle time is applied before the first gate pulse inside the exposure
- all gate pulses must fit inside the exposure window
- `DARK` emits no brightness setpoints and no gate windows
- `AF_RED_GREEN` emits red before green deterministically when using sequential
  gate pulses, or drives red and green together when the profile uses a
  pattern-level lead/tail window

`LedPatternTimingProfile` describes the timing for one logical pattern, and
`LedPatternTimingSet` groups the profiles used by one stripe schedule. The
trigger scheduler consumes `pattern_led_timing` profiles keyed by pattern name
and emits protocol `led_timing` metadata for the selected frame pattern.

`DisabledOutputLedTimingContract` is the protocol fixture metadata shape for
one `FRAME_EVENT`:

- `frame_start_us` is the event `mcu_time_us`; no Linux wall-clock identity is
  used for frame identity or timing
- `logical_channel_names` must match `FRAME_EVENT.led_gate_names`
- `gate_windows` are absolute MCU-time windows for logical timing/control
  signals only
- `baseline_transitions` describe firmware-owned default-light state changes
  such as `led_white` off before the AF trigger and back on after exposure
- `backend` is `disabled_output_metadata`
- `hardware_outputs_enabled` is always `false`

The contract deliberately does not include physical pin names, rail budgets,
drive current, GPIO ownership or live output approval. MCU pins remain
timing/control signals in this model, not LED current sources.

## MKS V1 Atomic AF Window

`atomic_window.py` adds the software-only V1 MKS no-motion autofocus window
contract tracked by `199 [P0]`.

The sequence is represented as disabled-output metadata only:

1. `led_white` baseline inactive at the AF window start.
2. `led_red` and `led_green` active together.
3. The configured settle interval elapses before XVS trigger time.
4. XVS trigger starts at `FRAME_EVENT.mcu_time_us`.
5. Red and green stay active through the exposure hold.
6. Red and green turn off together.
7. `led_white` baseline restores at the same end time.

The validator rejects non-atomic red/green edges, missing white
suppress/restore transitions, physical pin names in logical gate fields and
any `hardware_outputs_enabled=true` payload. Current MKS pins (`PD6` trigger,
`PA9` green, `PA10` red, `PB13` white, active high) remain board-profile
context; this package still emits only logical aliases and does not issue
`SET_PIN`, serial, GPIO, camera-trigger, motor or flashing commands.

For scan execution, the AF window is armed by position or commanded step count.
The MCU records `frame_start_us` when that position-indexed trigger fires; it is
not a Linux-wall-clock or free-running timer schedule. The microsecond fields in
this package describe only the MCU-local offsets inside that already-fired
position event.

## Stationary AF Timing Test

`stationary_af_test.py` builds the matching software-only `FRAME_EVENT` series
for `scanner_sync_run_stationary_af_test`. It keeps X/Y/Z counts stationary,
reuses the same atomic red/green + white baseline timing contract for each
frame and increments only frame identity and MCU time by `frame_period_us`.

This path is for no-motion bench tuning of `settle_us`,
`xvs_trigger_pulse_us` and `exposure_hold_us`. It is not the production scan
primitive; production scanning must use position-indexed
`scanner_sync_arm_af_window`.
