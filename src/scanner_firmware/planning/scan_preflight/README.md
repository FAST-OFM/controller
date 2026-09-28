# scan_preflight

Simulator-only scan preflight gate for enforcing the homing invariant before a
scan workflow starts.

The required scan axes are fixed to `X`, `Y` and `Z`. A preflight input records
those required axes, the axes currently marked homed by the simulator,
`dry_run`, and `hardware_outputs_enabled`.

Policy:

- accept when all required axes are homed;
- accept missing homing only for explicit dry runs with hardware outputs
  disabled, and return warnings describing the simulator-only bypass;
- reject missing homing for non-dry-run scans;
- reject any missing-homing case that also has hardware outputs enabled.
- reject scan start when the Z policy is not configured, reported separately
  from coordinate-source validity.

This module does not command motion, open serial ports, read GPIO, drive LEDs,
enable motors or interact with firmware. It is a deterministic host-side model
for simulator tests and safety review.
