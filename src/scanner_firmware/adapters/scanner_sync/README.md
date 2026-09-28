# scanner_sync

Scanner-sync adapter boundary.

Current modules:

- `backend.py`: provides the dry-run `ScanExecutionBackend` implementation.
- `live_metadata_backend.py`: provides a passive metadata ingest backend for
  already-received scanner-sync callback payloads after readiness has been
  evaluated.

Neutral scanner-sync interfaces and the dry-run service live in
`scanner_firmware.planning.scanner_sync`. Adapter modules may depend on that
planning boundary. Adapter modules must not import lower-level planning
packages directly. The planning boundary must not depend on adapter modules.

This adapter package does not open serial ports, command motion, toggle GPIO,
trigger cameras or drive LEDs. Future live integration remains gated by the
live-test approval process.
