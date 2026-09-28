# firmware_base

Dry-run scaffolding for firmware-base spike candidates.

This package exists to compare candidate event streams before any hardware
backend exists. It must not:

- command motors;
- flash firmware;
- toggle GPIO;
- trigger cameras;
- drive LEDs;
- depend on Linux wall-clock time for frame identity or coordinates.

Candidate-specific adapters should emit common `PositionSample` records for the
dry-run scheduler. Hardware-output tests require a separate reviewed procedure.

