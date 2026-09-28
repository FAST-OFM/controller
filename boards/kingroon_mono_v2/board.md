# Kingroon / MKS Robin Mini V2 Board Profile

Profile state: `pinmap_candidate`.

Legacy descriptive status:
`board_identity_verified_by_photo_pinmap_candidate_from_existing_klipper_config`.

This profile started as `kingroon_mono_v2` because the controller was
described as a Kingroon Mono V2-like board. The active Raspberry Pi 5
Klipper configuration identifies the working scanner controller as an
`MKS Robin Mini v2.0 scanner bring-up config`.

The board identity is now photo-verified as a Makerbase MKS Robin Mini V2.0.
Do not treat the full pin map or electrical interface as physically verified
until voltage levels, load behavior and boot/default output states are checked
against the actual board and recorded as reviewed evidence.

## Evidence

- Source: `/home/pi/printer_data/config/printer.cfg` on Pi5 via private VPN
  peer `192.0.2.13`.
- Read date: 2026-06-30.
- Klipper host: `pi5`.
- Klipper config file:
  `/home/pi/printer_data/config/printer.cfg`.
- Klipper software version from Moonraker:
  `v0.13.0-699-gc707dd192`.
- Klipper git commit on Pi5:
  `c707dd19214709dc23684b254a68e3bf69e4cfb3`.
- Current MCU serial device on Pi5:
  `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0`.
- Current Arduino Nano brightness-controller serial device on Pi5:
  `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0`.
- Serial note: both the MKS controller and Arduino Nano enumerate as CH340
  devices with the same non-unique by-id string. Use physical by-path entries
  for controller identity when both are connected; do not use
  `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` for either device in this
  dual-CH340 setup.
- MCU reported by Klipper log:
  `stm32f103xe`, `CLOCK_FREQ=72000000`.

Photo evidence from user-provided full-resolution board photos:

- Front photo: `/path/to/board-front.jpg`.
- Back photo: `/path/to/board-back.jpg`.
- Front silkscreen reads: `Makerbase MKS Robin Mini V2.0`.
- Back silkscreen includes Makerbase branding.
- Back PCB code reads: `M-M-B-A-00526`.
- Front debug/programming header labels visible next to the MCU:
  `DIO`, `DCK`, `3V3`, `GND`.
- Stepper connectors are visibly labeled for `X`, `Y`, `Z` and `E0`.
- MCU package marking is not readable clearly enough in the photo; retain
  the MCU identification from Klipper logs.
- Stepper driver chip markings are hidden by heatsinks, but the driver type
  is documentation-reported as `A4988`.

## Current Mechanics From Config

- Motors: NEMA11 on X, Y and Z.
- Stepper drivers: `A4988`, documentation-reported.
- X/Y mechanics: 2 mm travel per motor revolution.
- Z mechanics: 0.5 mm travel per motor revolution.
- Configured microsteps: 16 on X, Y and Z.
- Microstepping note: 1/32 was attempted and did not work; 1/16 works and
  is the active Klipper configuration.
- Config comments assume 200 step/rev motors.
- X/Y motor current Vref PWM: `PA6`, value `0.3` with scale `1.5`.
- Z motor current Vref PWM: `PA7`, value `0.3` with scale `1.5`.

Do not store motion resolution as an independent constant. Derive it from the
machine configuration:

```text
steps_per_rev = motor_full_steps_per_rev * microsteps
steps_per_mm = steps_per_rev / travel_per_rev_mm
steps_per_um = steps_per_mm / 1000
```

Current derived values from the active config inputs:

| Axis | Full steps/rev | Microsteps | Travel/rev | Derived resolution |
|---|---:|---:|---:|---:|
| X | 200 | 16 | 2.0 mm | 1600 steps/mm |
| Y | 200 | 16 | 2.0 mm | 1600 steps/mm |
| Z | 200 | 16 | 0.5 mm | 6400 steps/mm / 6.4 steps/um |

If motor step angle, microstepping, gearing or screw lead changes, recompute
these values from config. Do not patch only the derived number.

## Observed Bring-Up Scope

The work performed with the current Klipper configuration has been limited
to:

- X, Y and Z axis control.
- HQ Camera XVS sync signaling from the E0 control-signal area, now identified
  as `PD6` / `E0_STEP` and configured as `output_pin hq_xvs_sync`.

No other board functions have been brought up yet. In particular, no LED
strobe outputs, spare GPIO, encoder inputs,
firmware flashing/debug flow or external hardware workflows have been
exercised.

## July 1, 2026 Scanner-Sync Live State

After MKS USB serial recovery, Klipper reconnects to the MKS MCU. A disabled
scanner-sync host-extra Stage A check has passed:

- `~/klipper/klippy/extras/scanner_sync.py` is present on the Pi as a live
  host extra;
- `printer.cfg` contains `[scanner_sync] enable: false`;
- the live MKS firmware lacks scanner-sync MCU commands;
- scanner-sync is not enabled;
- no firmware was flashed;
- no scanner-sync commands were sent;
- no GPIO, motor, camera trigger or LED output was commanded.

## July 2, 2026 HQ XVS Rename and Connect Gate

The active Pi5 Klipper config no longer uses the legacy generic
`e_step_trigger` / `ARS_TRIGGER_*` naming for `PD6`. The line is now named for
the intended HQ Camera XVS sync role:

- Klipper output: `output_pin hq_xvs_sync`;
- macros: `HQ_XVS_HIGH`, `HQ_XVS_LOW`, `HQ_XVS_PULSE`,
  `HQ_XVS_TEST_TRAIN`;
- measured MKS-side high level: 3.3 V;
- HQ Camera XVS must be driven through the approved 3.3 V-to-1.8 V level
  shifter.

After this config rename and a serial path update, Klipper loads the host
config but the MKS currently does not answer `identify_response`. Treat this as
a connectivity or firmware-mode gate before flashing or running hardware tests.

This is a safe-disabled software state only. Candidate pins in this profile are
not approval to drive outputs.

## Current Read-Only Runtime Status

Read-only Moonraker/Klipper status check:

- Klippy state: `ready`.
- `toolhead.homed_axes`: empty string.
- `stepper_enable`: `stepper_x=false`, `stepper_y=false`, `stepper_z=false`.
- `query_endstops.last_query`: empty; no endstop query was run during this
  check.
- Active config has `[homing_override]` for `axes: xyz`, but the override
  only runs `SET_KINEMATIC_POSITION X=100 Y=100 Z=0` and `G90`.

After explicit permission for safe testing, `QUERY_ENDSTOPS` was run once.
It does not move motors or toggle outputs. Readback:

- `stepper_x=0`
- `stepper_y=0`
- `stepper_z=0`
- `toolhead.homed_axes` remained empty.
- X/Y/Z steppers remained disabled.

Interpretation:

- Current `G28`/homing behavior in this config is not a physical homing
  sequence.
- It does not seek switches, perform sensorless homing or validate travel
  limits.
- Treat current homing status as not implemented.
- Keep homing disabled in scanner configuration until a reviewed homing method
  is added. No limit switches are connected on the current setup, and A4988
  drivers do not provide driver-assisted end-of-travel detection.
- A4988 does not provide sensorless homing feedback. Future RP2040/Pico
  homing based on driver feedback requires different driver hardware with a
  diagnostic/stall signal, such as TMC-class drivers, and separate validation.
- The endstop readback records only the current input state; it does not prove
  connector mapping, polarity under actuation, repeatability or safe homing.

## Candidate Pin Map From Klipper Config

| Function | Pin | Status | Notes |
|---|---:|---|---|
| X step | `PE3` | likely | From active Klipper config. |
| X dir | `PE2` | likely | From active Klipper config. |
| X enable | `!PE4` | likely | Active-low in Klipper syntax. |
| X endstop config | `!PA15` | not exercised | Active-low in Klipper syntax. This is not a verified homing implementation. |
| Y step | `PE0` | likely | From active Klipper config. |
| Y dir | `PB9` | likely | From active Klipper config. |
| Y enable | `!PE1` | likely | Active-low in Klipper syntax. |
| Y endstop config | `!PA12` | not exercised | Active-low in Klipper syntax. This is not a verified homing implementation. |
| Z step | `PB5` | likely | From active Klipper config. |
| Z dir | `!PB4` | likely | Inverted in Klipper syntax. |
| Z enable | `!PB8` | likely | Active-low in Klipper syntax. |
| Z endstop config | `!PA11` | not exercised | Active-low in Klipper syntax. This is not a verified homing implementation. |
| X/Y Vref PWM | `PA6` | likely | Configured as PWM output. |
| Z Vref PWM | `PA7` | likely | Configured as PWM output. |
| Legacy config output | `PC4` / Z+ | legacy/config artifact | Active config still contains `output_pin camera_trigger` on this pin, but user clarification and photo review indicate the current physical trigger wire is not on Z+. |
| HQ XVS sync | `PD6` / E0_STEP | assigned current physical sync output | Configured as `output_pin hq_xvs_sync`; photo shows the trigger wire in the E0 control-signal area. It is 3.3 V at MKS and requires the approved 3.3 V-to-1.8 V level shifter before HQ XVS. Do not connect to the 4-pin E0 motor coil connector. |
| Green LED gate | `PA9` / WiFi TXD1 | assigned candidate | Identified by no-load WiFi-header probe. Requires external MOSFET/transistor and current limiting. |
| Red LED gate | `PA10` / WiFi RXD1 | assigned candidate | Identified by no-load WiFi-header probe. Requires external MOSFET/transistor and current limiting. |
| White LED gate | `PB13` / TC1 SCK | assigned candidate | Identified by no-load TC1-header blink probe. Requires external MOSFET/transistor and current limiting. |
| Prior green LED candidate | `PD3` / E0_DIR | superseded | Earlier no-load candidate, replaced by WiFi-header `PA9`. |
| Prior red LED candidate | `!PB3` / E0_ENABLE | superseded | Earlier no-load candidate, replaced by WiFi-header `PA10` to avoid the inverted E0 enable path. |
| Prior white LED candidate | `PB1` / FAN | superseded | Earlier no-load candidate, replaced by TC1 SCK `PB13`. Treat as board fan/MOSFET load output if ever reused. |
| TC1 CS physical mapping | unknown | unresolved | Attempted `PD15` and `PB12` probes did not blink the physical `CS` terminal. Do not assign until found by measurement. |
| E0 Vref/current PWM | `PB0` | not usable for LED | Analog current-limit/Vref path for E driver. Probe readback could be set high, but measured node remained 0 V. |

## Current 20x Red/Green LED Geometry

The installed red and green AF LEDs are currently documented as 100 mA-class
devices mounted for the `20x` objective:

- lateral offset from optical center: 10 mm;
- distance from tissue plane: 35 mm;
- placement angle: 16 degrees.

This geometry is not valid for `40x`. The `40x` objective needs a separate
red/green LED pair with a different placement angle and separate calibration
records. Do not encode the 20x geometry as a firmware constant for all
objectives.

## Existing Klipper Test Macros

The active config contains small-motion and trigger-test macros:

- `SCANNER_SET_TEST_ORIGIN`
- `SCANNER_TEST_X_SMALL`
- `SCANNER_TEST_Y_SMALL`
- `SCANNER_TEST_XY_SMALL`
- `SCANNER_TEST_Z_SMALL`
- `HQ_XVS_HIGH`
- `HQ_XVS_LOW`
- `HQ_XVS_PULSE`
- `HQ_XVS_TEST_TRAIN`
- `SCANNER_CAMERA_TRIGGER`
- `SCANNER_CAMERA_TRIGGER_TEST`

Do not run these macros during documentation work. Running them can move
hardware or toggle outputs and requires explicit human approval plus a safe
test setup.

## Remaining Unknowns

- Exact marketed Kingroon machine/controller variant, if different from the
  Makerbase board silkscreen.
- Exact stepper driver chip markings remain hidden under heatsinks.
- Flashing/debug connector and boot mode procedure.
- Physical connector mapping for each endstop and output.
- Any working homing method on the current board.
- Whether `PC4` / Z+ should be removed from active config or retained only as
  a disabled diagnostic.
- Exact physical pad/testpoint used for the `PD6` / E0_STEP HQ XVS wire.
- MKS connection timeout root cause after the HQ XVS rename and serial path
  update.
- I/O voltage levels for any outputs beyond prior `PD6` / E0_STEP and `PC4` /
  Z+ checks.
- Safe dummy-load test for `PA9`, `PA10` and `PB13` LED candidates.
- TC1 SCK/PB13 boot/reset state.
- TC1 CS physical mapping.
- Safe no-motion electrical test procedure approval.
- Safe one-axis low-speed test procedure approval.
