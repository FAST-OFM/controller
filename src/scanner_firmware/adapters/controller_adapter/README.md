# Controller Adapter Boundary

Status: software-only interface layer. This directory does not approve live
firmware flashing, GPIO toggling, motor motion, camera triggering, LED driving,
serial control, network control or hardware tests.

`controller_adapter.interfaces` owns the controller-neutral contracts between
scan scheduler/planner code and future controller-specific adapters.
`controller_adapter.dry_run` provides in-memory conformance adapters for those
contracts, including passive capability negotiation snapshots and command
rejection when dry-run callers request hardware outputs.

The explicit protocols are:

- `MotionPositionProvider`: returns abstract commanded-position samples.
- `ScannerCommandPort`: accepts software command intents and exposes passive
  adapter snapshots.
- `ProtocolEventSink`: receives controller-neutral protocol events.
- `OutputBackend`: applies logical output requests only behind an explicit
  software safety gate.
- `ControllerCapabilities`: reports passive adapter capability snapshots.
- `PassiveMetadataEventSource`: exposes already-captured controller-neutral
  metadata events without command or hardware authority.

Klipper, grblHAL and RP2040 integrations must sit behind these protocols.
Scheduler and planner modules must consume the abstract interfaces and value
objects instead of importing `klipper_adapter` directly.

Hardware outputs default to disabled. A valid capability snapshot or output
request does not authorize physical output toggling, and dry-run output
backends or command ports must reject requests that attempt to enable hardware
outputs.

Adapter modes are intentionally narrow:

- `dry_run` may accept software command intents and synthetic position samples.
- `live_metadata` may expose passive metadata already captured from a reviewed
  controller integration, but it must not submit commands, open serial, toggle
  outputs or imply live scanner-sync approval.
- Live controller command/control adapters require a later reviewed contract and
  are not represented by this software-only boundary.
