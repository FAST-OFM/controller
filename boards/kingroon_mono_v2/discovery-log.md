# Controller Discovery Log

## Current Source of Truth

Current implementation-facing output mapping:

- Camera/sync trigger: `PD6` / E0_STEP.
- Green LED gate: `PA9` / WiFi TXD1.
- Red LED gate: `PA10` / WiFi RXD1.
- White LED gate: `PB13` / TC1 SCK.

Legacy or superseded signals:

- `PC4` / Z+ is a legacy position-event/config artifact, not the current
  trigger path.
- `PD3` / E0_DIR and `!PB3` / E0_ENABLE were earlier red/green LED candidates,
  later superseded by the WiFi-header mapping.
- `PB1` / FAN was an earlier white LED candidate, later superseded by
  `PB13` / TC1 SCK.
- TC1 `CS` remains unresolved; `PD15` and `PB12` did not blink the physical
  `CS` terminal during no-load probe.

## 2026-06-30 — Pi5 Klipper Configuration Readout

Access path:

- Local host connected to private VPN peer `private-vpn-peer`.
- VPN server: `192.0.2.1`.
- Pi5 peer: `192.0.2.13`.
- Pi5 SSH user: `pi`.

Read-only files and endpoints inspected:

- `/home/pi/printer_data/config/printer.cfg`
- `/home/pi/printer_data/config/moonraker.conf`
- `/home/pi/printer_data/logs/klippy.log`
- Moonraker `/server/info`
- Moonraker `/printer/info`

Observed facts:

- Hostname: `pi5`.
- Moonraker reports Klippy connected and ready.
- Klipper config path:
  `/home/pi/printer_data/config/printer.cfg`.
- Klipper software version:
  `v0.13.0-699-gc707dd192`.
- Klipper git commit on Pi5:
  `c707dd19214709dc23684b254a68e3bf69e4cfb3`.
- MCU serial path:
  `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`.
- Klipper log reports MCU:
  `stm32f103xe`, `CLOCK_FREQ=72000000`.
- Active config identifies itself as:
  `MKS Robin Mini v2.0 scanner bring-up config`.

Configured mechanics:

- X/Y/Z motors are NEMA11.
- X/Y travel is 2 mm per motor revolution.
- Z travel is 0.5 mm per motor revolution.
- X/Y/Z microsteps are configured as 16.
- Config comments assume 200 step/rev motors.

Observed bring-up scope:

- Work performed with the current Klipper configuration has been limited to
  X, Y and Z axis control plus trigger/sync signaling from the E0
  control-signal area.
- No LED strobe outputs, final camera trigger path, spare GPIO, encoder
  inputs, firmware flashing/debug flow or external hardware workflows have
  been exercised.

Configured pins:

- X: step `PE3`, dir `PE2`, enable `!PE4`, endstop `!PA15`.
- Y: step `PE0`, dir `PB9`, enable `!PE1`, endstop `!PA12`.
- Z: step `PB5`, dir `!PB4`, enable `!PB8`, endstop `!PA11`.
- X/Y current PWM: `PA6`.
- Z current PWM: `PA7`.
- Legacy config output: `PC4` / Z+.
- Camera/sync trigger: `PD6` / E0_STEP.
- E0 direction candidate: `PD3` / E0_DIR.
- E0 enable candidate: `!PB3` / E0_ENABLE.
- E0 Vref/current PWM: `PB0`.
- Earlier green LED gate candidate: `PD3` / E0_DIR.
- Earlier red LED gate candidate: `!PB3` / E0_ENABLE.
- Earlier white LED candidate: `PB1` / FAN.

Homing clarification:

- The Klipper config contains X/Y/Z endstop pin assignments.
- No working homing method has been verified on the current setup.
- Do not treat those config entries as proof of physical switches, correct
  polarity, repeatability or safe homing behavior.

Safety notes:

- The active config still contains older camera-trigger naming for `PC4` /
  Z+. Treat that as a legacy/config artifact until removed or explicitly
  retained as a disabled diagnostic.
- User clarification and photo review indicate the current physical trigger
  wire is connected in the E0 control-signal area, consistent with
  `PD6` / E0_STEP and the active `output_pin e_step_trigger` config.
- Do not confuse `PD6` / E0_STEP with the 4-pin E0 motor coil connector.
- The 4-pin E0 motor connector carries driver coil outputs and must not be
  used as LED or camera-trigger GPIO.
- Existing Klipper macros can move axes or toggle outputs. They were not
  run during this readout.

Still unknown at this stage:

- Physical board silkscreen name and revision.
- Stepper driver chip markings.
- Flash/debug connector and boot mode procedure.
- Physical connector mapping and measured voltage levels beyond prior
  `PD6` / E0_STEP and `PC4` / Z+ checks.
- Working homing method on the current board.
- Whether any legacy position-event GPIO should remain as a diagnostic path.
- White/red/green LED gate outputs.

## 2026-06-30 — Full-Resolution Board Photo Review

Photo inputs:

- Front photo: `/path/to/board-front.jpg`.
- Back photo: `/path/to/board-back.jpg`.

Observed facts:

- Front silkscreen reads `Makerbase MKS Robin Mini V2.0`.
- Back silkscreen includes Makerbase branding.
- Back PCB code reads `M-M-B-A-00526`.
- A front header near the MCU has visible labels:
  `DIO`, `DCK`, `3V3`, `GND`.
- The right-side stepper motor connectors are visibly labeled `X`, `Y`, `Z`
  and `E0`.
- The MCU package marking is not readable clearly enough from the photo;
  keep using the Klipper log as the MCU evidence source.
- The stepper driver markings are hidden by heatsinks and remain unknown.

Safety notes:

- No hardware commands were run during photo review.
- No firmware flashing, GPIO toggling, LED strobing, camera triggering or
  motion testing was performed.

Still unknown after photo review:

- Exact marketed Kingroon machine/controller variant, if different from the
  Makerbase board silkscreen.
- Stepper driver chip markings.
- Flash/debug connector electrical function and boot mode procedure.
- Physical endstop/output connector mapping and measured voltage levels.
- Whether any legacy position-event GPIO should remain as a diagnostic path.
- White/red/green LED gate outputs.

## 2026-06-30 — Z+ Legacy Position-Event Clarification

User-provided measurement and history:

- Z+ measures `3.3 V`.
- An earlier simpler prototype used this signal into Raspberry Pi GPIO.
- In that prototype, the camera captured independently; the board sent an
  event when it was in the intended position.

Interpretation:

- The old config name/comment should not be interpreted as the desired current
  physical trigger wiring.
- `PC4` / Z+ remains a legacy/config artifact unless it is explicitly
  revalidated and retained as a disabled diagnostic.
- Target architecture: camera frame arrival starts processing, and MCU
  `FRAME_EVENT` supplies frame identity, position, LED pattern and Z state
  for matching. Frame identity and coordinates must not be inferred from
  Linux wall-clock time.

## 2026-06-30 — E0 STEP Trigger Wiring Correction

User correction:

- The current camera/sync trigger wire is connected to one of the E driver
  control signals, not to Z+.
- Photo review shows the purple trigger wire in the E0 control-signal area,
  separate from the 4-pin E0 motor coil connector.
- Active Klipper config has `output_pin e_step_trigger` on `PD6`, described as
  `E0_STEP / PD6`, with `ARS_TRIGGER_ON`, `ARS_TRIGGER_OFF` and
  `SCANNER_E_STEP_TRIGGER*` macros.

Interpretation:

- Treat `PD6` / E0_STEP as the likely current physical camera/sync trigger
  signal.
- Treat `PC4` / Z+ as an old config entry / legacy diagnostic candidate, not
  the current physical trigger.
- The 4-pin E0 motor connector provides driver coil outputs, not usable logic
  GPIO.
- E0 control signals before the driver may be LED-control candidates after
  no-motion electrical review: `PD3` / E0_DIR and possibly `PB3` / E0_ENABLE.
- Do not use `PB0` / E0_VREF as a normal LED gate; it is part of the analog
  driver current-limit path.

## 2026-07-02 — PD6 Renamed to HQ XVS Sync

Live Pi5/MKS config review and multimeter check:

- `PD6` / E0_STEP was driven high and measured at 3.3 V by the operator.
- The signal is no longer named as a generic ARS/camera trigger in the active
  config. The active Klipper output is now `output_pin hq_xvs_sync`.
- Active macros are `HQ_XVS_HIGH`, `HQ_XVS_LOW`, `HQ_XVS_PULSE` and
  `HQ_XVS_TEST_TRAIN`.
- `PD6` is a 3.3 V MKS logic output. HQ Camera XVS must be driven through the
  approved 3.3 V-to-1.8 V level shifter, not directly from the MKS pin.
- After the rename and serial path update, Klipper loads the config but the
  MKS currently does not answer `identify_response`; this is a connectivity or
  firmware-mode blocker before any MKS flashing or hardware test.

Do not restore the old `e_step_trigger`, `ARS_TRIGGER_*` or
`SCANNER_E_STEP_TRIGGER*` names for new work.

## 2026-06-30 — E0 Control-Signal LED Candidate Identification

No-load multimeter probe, with no LED connected:

- `PD6` / E0_STEP was confirmed and retained as camera/sync trigger.
- `PD3` / E0_DIR toggled between LOW and approximately 3.3 V and was assigned
  at that point as the green LED gate candidate. It was later superseded by
  `PA9` / WiFi TXD1.
- `PB3` / E0_ENABLE toggled between LOW and approximately 3.3 V and is
  assigned at that point as the red LED gate candidate. It was later
  superseded by `PA10` / WiFi RXD1.
- `PB3` is an inverted/active-low enable signal in the original stepper-driver
  context; keep this inversion explicit in firmware config or external logic.

Safety scope:

- no firmware flashing;
- no motor motion;
- no LED connected or powered;
- no dummy load connected;
- X/Y/Z steppers remained disabled in Klipper readback.

Remaining LED output unknown at that point:

- safe dummy-load and low-current LED behavior for `PD3`, `PB3` and `PB1`;
- FAN/PB1 rail voltage, current budget and boot/reset state.

## 2026-06-30 — WiFi Header Red/Green LED Gate Reassignment

No-load probe, with no LED connected:

- The unused WiFi header was reviewed against the official MKS Robin Mini V2.0
  schematic.
- `PA9` / WiFi TXD1 was configured as a temporary Klipper output and toggled
  successfully. Assign it as the green LED gate.
- `PA10` / WiFi RXD1 was configured as a temporary Klipper output and toggled
  successfully. Assign it as the red LED gate.
- `PA8` / WiFi IO0 and `PC7` / WiFi IO1 remain candidates with explicit pull-up
  caveats. Do not use them without boot/reset-state review or removing/working
  around the pull-ups.
- `PD3` / E0_DIR and `!PB3` / E0_ENABLE are now superseded red/green LED
  candidates. `!PB3` remains undesirable for this role because it is an
  inverted E0 enable path.

Current LED gate assignment at that point:

- GREEN gate: `PA9` / WiFi TXD1.
- RED gate: `PA10` / WiFi RXD1.
- WHITE gate: `PB1` / FAN, later superseded by TC1 SCK/PB13.

Safety scope:

- no firmware flashing;
- no motor motion;
- no LED connected or powered;
- no dummy load connected.

Remaining LED output unknown:

- safe dummy-load and low-current LED behavior for `PA9`, `PA10` and `PB1`;
- boot/reset state at the physical WiFi header pins;
- FAN/PB1 rail voltage and current budget.

## 2026-06-30 — FAN/PB1 White LED Candidate Identification

No-load multimeter probe, with no LED connected:

- `PB1` / FAN was toggled through temporary `output_pin fan_probe`.
- User confirmed the output was found and assigned it at that point as the
  white LED candidate. It was later superseded by `PB13` / TC1 SCK.
- User confirmed positive polarity: command value `1` is active/on and command
  value `0` is inactive/off.
- Treat FAN/PB1 as a board fan/MOSFET load output, not raw 3.3 V GPIO.

Safety scope:

- no firmware flashing;
- no motor motion;
- no LED connected or powered;
- no dummy load connected;
- X/Y/Z steppers remained disabled in Klipper readback.

Additional E0 Vref result:

- `PB0` / E0_VREF was temporarily exposed as `output_pin e_vref_probe`.
- Klipper accepted `VALUE=1`, but user measured the physical node as still
  0 V.
- Do not use `PB0` / E0_VREF as an LED gate.

## 2026-06-30 — TC1 SCK White LED Gate Reassignment

No-load probe, with no LED connected:

- The black six-pin `TC1` header silkscreen was read as `VIN`, `NC`, `G`,
  `D0`, `CS`, `SCK`.
- The physical `SCK` terminal was found by blink probe on `PB13`.
- Assign `PB13` / TC1 SCK as the white LED gate.
- `PB1` / FAN is now a superseded white LED candidate. Keep it documented as a
  prior candidate, but do not treat it as the primary white gate.
- Attempted CS probes on `PD15` and `PB12` did not blink the physical `CS`
  terminal. Do not assign TC1 CS until it is found by measurement.
- `D0` / MISO was temporarily probed as `PB14`, but it is not assigned as an
  LED gate.

Current LED gate assignment:

- GREEN gate: `PA9` / WiFi TXD1.
- RED gate: `PA10` / WiFi RXD1.
- WHITE gate: `PB13` / TC1 SCK.

Safety scope:

- no firmware flashing;
- no motor motion;
- no LED connected or powered;
- no dummy load connected.

Remaining LED output unknown:

- safe dummy-load and low-current LED behavior for `PA9`, `PA10` and `PB13`;
- boot/reset state for `PB13` / TC1 SCK;
- unresolved TC1 CS physical mapping.

## 2026-06-30 — Read-Only Runtime Homing Status Check

Read-only endpoints/files inspected:

- Moonraker `/server/info`.
- Moonraker `/printer/info`.
- Moonraker `/printer/objects/list`.
- Moonraker `/printer/objects/query?configfile&query_endstops&stepper_enable&toolhead&gcode_move`.
- `/home/pi/printer_data/config/printer.cfg`.
- `/home/pi/printer_data/logs/klippy.log`.

No G-code command was sent. `QUERY_ENDSTOPS` was not run. No motion, output
toggle, LED, camera trigger or firmware flashing was performed.

Observed runtime facts:

- Klippy reports `ready`.
- `toolhead.homed_axes` is empty.
- `stepper_enable` reports X/Y/Z disabled.
- `query_endstops.last_query` is empty.
- Parsed config includes `[homing_override]` for `axes: xyz`.
- The homing override does not physically home; it runs:
  `SET_KINEMATIC_POSITION X=100 Y=100 Z=0` and `G90`.

Interpretation:

- The current Klipper config has no verified physical homing sequence.
- Configured `endstop_pin` values remain pin candidates only.
- Running homing in this config would set a temporary kinematic position, not
  discover machine zero.

## 2026-06-30 — Endstop Readback Check

After explicit user permission for safe testing, a single `QUERY_ENDSTOPS`
command was sent through Moonraker/Klipper.

Safety scope:

- no motion;
- no firmware flashing;
- no GPIO/output toggling;
- no LED strobe;
- no camera trigger;
- steppers remained disabled.

Readback:

- `stepper_x=0`;
- `stepper_y=0`;
- `stepper_z=0`;
- `toolhead.homed_axes` remained empty.

Interpretation:

- This confirms only the current readback state of the configured endstop
  inputs at the time of the query.
- It does not verify physical connector mapping, switch polarity under
  actuation, repeatability or safe homing behavior.
- Current homing remains not implemented.

## 2026-06-30 — Driver Type and Microstepping Note

User-provided documentation note:

- Stepper driver type is `A4988`.
- 1/32 microstepping was attempted and did not work.
- 1/16 microstepping works and is the active Klipper configuration for X/Y/Z.

Interpretation:

- Treat `A4988` as documentation-reported, not photo-read from the IC package.
- Keep the exact physical chip markings unresolved because the heatsinks hide
  the driver packages in the available photos.
- Use 1/16 as the current known-good microstepping setting for documentation
  and future safe test planning.

## 2026-06-30 — CH340 Serial Identity Correction

After the Arduino Nano LED brightness controller was connected, the Pi5 had two
CH340 USB serial devices:

- MKS controller: `/dev/ttyUSB0`
- Arduino Nano: `/dev/ttyUSB1`

Both devices expose the same non-unique by-id name:

```text
/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
```

The active Klipper config was changed to pin the MKS controller by physical
USB path:

```text
/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0
```

Do not use the non-unique CH340 by-id path for the MKS controller while both
devices are connected.

Update on 2026-07-02:

- After later USB replug/reboot state, the old MKS by-path was absent and MKS
  appeared as `/dev/ttyUSB1`.
- Active Klipper config was updated to
  `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`, with current by-path
  `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0`.
- This is acceptable only while it resolves to the MKS. If Arduino Nano or any
  other CH340 device creates ambiguity, revalidate by-path/by-id before
  restarting Klipper or flashing.

## 2026-07-02 — 20x Red/Green AF LED Geometry

User-reported current geometry for the installed red and green AF LEDs:

- objective: `20x`;
- red LED rated current: 100 mA;
- green LED rated current: 100 mA;
- lateral offset from optical center: 10 mm;
- distance from tissue plane: 35 mm;
- placement angle: 16 degrees.

This is the current `20x` build geometry only. The `40x` objective must use a
different red/green LED pair with its own placement angle, intensity/current
limits, AF flat-field and focus-curve calibration records.

The project expects stronger red/green LEDs in a later revision. Do not treat
the current 100 mA LED rating as the final LED-driver requirement.
