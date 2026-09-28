# scanner_sync

Neutral scanner-sync planning boundary.

This package owns hardware-free scanner synchronization interfaces and dry-run
service composition. It may depend on firmware protocol, scan preflight and
trigger scheduler modules. It must not import adapter packages such as Klipper
integration, live metadata backends, serial/network transports, GPIO helpers,
camera code, LED drivers or firmware flashing tools.

Current modules:

- `interfaces.py`: substitution protocols and loaded-plan summary records.
- `service.py`: dry-run scanner-sync service that composes scan recipe parsing,
  preflight, position-event scheduling, metadata queueing and protocol
  serialization.

Adapter packages must use `interfaces.py` for scanner-sync planning contracts
instead of importing lower-level planning packages directly.

`DryRunScannerSyncService.start_stripe()` now passes scheduler events through
the trigger scheduler metadata queue before returning protocol records. The
queue is bounded, metadata-only and simulator-safe: it preserves scheduler
`FRAME_EVENT` identity and coordinates while keeping
`hardware_outputs_enabled=false`. Use `start_stripe_metadata_queue()` in
harness tests when the queue contents themselves need inspection.

Adapter packages may depend on this planning boundary. This planning boundary
must not depend on adapter packages.
