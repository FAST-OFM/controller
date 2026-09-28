# Controller modification index

This repository provides the controller-side portions of Alexander Fridman's
Fast OFM feature index:

- `WP-1 MOTION` / `STAGE-001` / `MOTION-001`: MKS Robin Mini V2.0 Klipper
  configuration and the host/controller boundary used by the OpenFlexure stage
  backend.
- `WP-2 ILLUMINATION` / `LIGHT-002`: Arduino-compatible high-frequency PWM
  brightness control plus MKS RED/GREEN/WHITE timing gates.
- `SYNC-001`: experimental scanner-sync protocol, scheduling models and Klipper
  patch material. This path is disabled by default and was not part of the
  accepted scan.
- `FUTURE-001`: design work toward global-shutter, hardware-triggered,
  continuous scanning. It is roadmap, not a working release feature.

The release vendors the frozen `scanner_core` pure-math/contract modules rather
than depending on a private Git URL. Operational IP addresses, personal paths,
opaque runtime archives and internal process records are excluded from the
clean snapshot.
