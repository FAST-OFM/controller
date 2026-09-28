# scan_math Contract Boundary

This package names firmware-specific scan math contracts only. The canonical
pure math implementation lives in `scanner-core`:

- `scanner_core.scan_geometry` owns stripe geometry, axis validation and
  position samples;
- `scanner_core.scan_units` owns half-away-from-zero rounding and unit
  conversions;
- `scanner_core.axis_resolution` owns screw-pitch/microstep resolution math.

Runtime firmware modules must import those `scanner_core` modules directly.
`scanner_firmware.domain.scan_math` must not add compatibility facades or
re-export shared math symbols. It exists to name firmware-specific contract
constants in `contracts.py`.

The component models one stripe at a time:

- axis is `X` or `Y`;
- `start_position` and `end_position` define inclusive bounds;
- signed `pitch` defines event spacing and scan direction;
- `event_count` controls the immutable event `positions` tuple;
- position samples can report signed overshoot
  (`sample.position - event_position`) without moving the scheduled event
  coordinate.

Shared core also derives exact `steps_per_mm` values from screw pitch,
configured microsteps and motor full steps per revolution.

Physical-unit to integer-count conversion uses explicit half-away-from-zero
rounding helpers. Callers should use those helpers at adapter or calibration
boundaries instead of Python's built-in `round`.

This package is deliberately hardware-free. It does not command motors, read
encoders, open serial ports, toggle GPIO, trigger cameras, drive LEDs or talk
to firmware. Callers must pass already-collected configuration or position
sample values.
