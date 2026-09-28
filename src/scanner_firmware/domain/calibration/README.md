# Calibration

Software-only calibration estimators and lookup tables.

This package consumes already-measured observations:

- commanded steps and measured travel;
- forward/reverse travel observations;
- repeated homing or positioning observations;
- LED brightness/current calibration samples.

It does not read ADCs, talk to Arduino/RP2040/Klipper, move motors, power LEDs,
toggle GPIO, open serial ports or access hardware. Live measurement procedures
belong behind reviewed hardware gates; this package only processes their
recorded results.

## LED workflow model

`calibration.led_workflow` separates calibration mode from runtime mode:

- calibration mode consumes recorded sense-resistor voltage samples only when
  the matching LED current path was on;
- off-time samples are rejected because they do not represent LED current;
- each channel carries sense-resistor resistance, power rating and optional
  target-current limits;
- accepted samples are converted to current and normalized brightness/current
  points, then stored in the existing `LedCurrentLookup`;
- runtime mode uses an existing lookup to validate target current and select a
  calibrated brightness setpoint.

This workflow still performs no live ADC reads and does not command LED output.
