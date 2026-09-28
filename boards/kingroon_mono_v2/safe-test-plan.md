# Safe Test Plan Draft

Status: draft, not approved for execution.

This file records candidate tests only. Do not run motion, GPIO toggles,
LED outputs or camera triggers without explicit approval.

## No-Motion Readout

Already completed read-only:

- SSH to Pi5 through private VPN.
- Read active Klipper and Moonraker config.
- Read Klipper log for MCU metadata.
- List `/dev/serial/by-id/`.
- Recorded that actual bring-up has been limited to X/Y/Z plus legacy
  `PD6` / E0_STEP trigger/sync signaling from the E0 control-signal area.

No firmware flashing, motor motion or GPIO toggling was performed.

## Not Yet Exercised

- LED strobe outputs.
- Final camera trigger path.
- Spare GPIO.
- Encoder inputs.
- Firmware flashing/debug flow.
- External hardware workflows.

## No-Motion Electrical Review Needed

Before any output test:

- Photograph the controller board front and back.
- Identify board revision and driver chip markings.
- Confirm connector names for X/Y/Z/endstops/Z+/E0_STEP.
- Measure idle output levels with no camera connected.
- Confirm common ground strategy and whether level shifting or isolation is
  required.

## Candidate Diagnostic Output Tests

Do not run yet.

- `PD6` / E0_STEP is the likely current physical camera/sync trigger signal,
  based on active config and photo/user correction.
- Do not confuse `PD6` / E0_STEP with the 4-pin E0 motor coil connector.
- `PA9` / WiFi TXD1 is assigned as the green LED gate after no-load
  WiFi-header identification.
- `PA10` / WiFi RXD1 is assigned as the red LED gate after no-load WiFi-header
  identification.
- Earlier `PD3` / E0_DIR and `!PB3` / E0_ENABLE red/green candidates are
  superseded by the WiFi-header mapping. Treat `!PB3` as inverted/active-low if
  it is ever reused.
- `PB13` / TC1 SCK is assigned as the white LED gate after no-load TC1-header
  blink identification.
- Earlier `PB1` / FAN is superseded as the white LED candidate. Treat it as a
  board fan/MOSFET load output if it is ever reused.
- TC1 `CS` remains unresolved. Attempted `PD15` and `PB12` probes did not blink
  the physical `CS` terminal.
- `PB0` / E0_VREF is not usable as an LED gate; it stayed at 0 V during the
  probe despite Klipper readback showing the temporary output set high.
- `PC4` / Z+ remains in the active config as an old `camera_trigger` output,
  but should be treated as a legacy/config artifact until removed or retained
  intentionally as a disabled diagnostic.
- Any trigger or LED output test must be scoped with no external camera or LED
  connected unless that specific load and protection path is approved.

## Candidate One-Axis Low-Speed Tests

Do not run yet.

This section defines the proposed first motion test for human review. It is
not approval to execute the test.

Preconditions:

- Human approval.
- Board revision and wiring reviewed.
- One motor connected.
- Current limit reviewed for NEMA11 motors.
- No slide/objective installed.
- Emergency power cutoff available.
- Axis travel clear.
- Klipper position origin intentionally set.

Recommended first axis:

- Start with X only.
- Do not start with Z. Z motion has the highest mechanical risk because it
  can move toward the slide/objective path.
- Do not start with Y until one horizontal axis has been confirmed with the
  same controller, motor, current and microstep assumptions.

Known configuration to preserve for the first test:

- Board: Makerbase MKS Robin Mini V2.0.
- Driver type: A4988, documentation-reported.
- Motor: NEMA11.
- X mechanics: 2 mm travel per motor revolution.
- X microsteps: 16.
- X derived resolution is calculated from config inputs:
  `200 full_steps_per_rev * 16 microsteps / 2.0 mm_per_rev = 1600 steps/mm`.
  Do not enter this as an independent source value.
- X pins from active Klipper config: step `PE3`, dir `PE2`, enable `!PE4`,
  endstop `!PA15`.
- X/Y current Vref PWM from active Klipper config: `PA6`, value `0.3`,
  scale `1.5`.
- Do not change firmware, Vref/current, microsteps or pin mapping as part of
  this planning task.

Pre-test checklist:

- Controller powered in the same known-good Klipper configuration.
- Pi5 connected and Klipper state visible.
- X motor connector visually confirmed.
- X carriage/stage has visible free travel in both directions.
- No slide, optics contact risk, loose tooling or cables in the travel path.
- Human operator is physically present at the machine.
- Emergency power-off path is identified and reachable.
- Test command sender is prepared to stop immediately.
- No camera, LED strobe, spare GPIO or legacy trigger test is combined with
  the motion test.
- Test starts from an intentionally set temporary origin, not from an assumed
  homed coordinate system.
- No working homing method has been verified on the current setup. Do not run
  homing as part of the first low-speed motion test.
- The active `[homing_override]` only sets kinematic position and must not be
  treated as physical homing.
- A4988 cannot provide sensorless homing. Any future RP2040/Pico sensorless
  homing test must first replace or add driver hardware with a validated
  diagnostic/stall signal and must not be inferred from the current A4988
  setup.

Proposed motion envelope for first approval:

- Axis: X only.
- Mode: relative jog from a temporary origin.
- First move magnitude: 0.2 mm or less.
- Return move: 0.2 mm or less in the opposite direction only if the first
  move is smooth and in the expected direction.
- Feed rate: 30 mm/min or slower.
- Total travel during first session: 1.0 mm or less unless a human explicitly
  approves a larger range.
- No homing sequence in the first motion test unless a homing method, switch
  or driver feedback path, polarity and safety behavior have been separately
  reviewed.

Stop conditions:

- Unexpected direction.
- Grinding, stall, skipped steps or abnormal noise.
- Any cable strain or connector motion.
- Any motion toward a mechanical limit, slide, fixture, objective or unsafe
  area.
- Klipper error, disconnect or inconsistent reported state.
- Operator uncertainty.

Expected observations to record:

- Axis moved or did not move.
- Direction relative to the command.
- Approximate travel distance.
- Smoothness/noise.
- Whether enable/current behavior appeared normal.
- Whether any endstop state changed unexpectedly.
- Exact command or macro used, if human approval is later granted.

Existing macros in the active config:

- `SCANNER_TEST_X_SMALL`
- `SCANNER_TEST_Y_SMALL`
- `SCANNER_TEST_Z_SMALL`

These macros can move hardware and must not be run as part of documentation.

Approval requirement:

- Before execution, create or update a GitHub issue comment with the exact
  planned command/macro, operator name, physical setup, emergency stop method
  and explicit approval.
- This repository update does not grant that approval.
