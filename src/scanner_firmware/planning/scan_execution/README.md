# Scan Execution

Software-only scan execution state machine.

This package owns the high-level execution states:

- `BOOT`
- `CONFIG_REQUIRED`
- `IDLE_SAFE_DISABLED`
- `READY`
- `SCAN_PREPARE`
- `SCANNING`
- `STOPPING`
- `COMPLETE`
- `FAULT`

The state machine consumes `StartupReadinessDecision` and
`ScanPreflightDecision` values from the readiness and preflight components. It
does not run those checks itself and does not perform hardware IO.

`SCANNING` is allowed only when all of these data gates are true:

- startup readiness can prepare a scan;
- scan preflight is accepted;
- all required scan axes are homed;
- hardware outputs are explicitly armed.

Dry-run execution is simulator-only. It requires hardware outputs to remain
disabled, may pass through `SCAN_PREPARE`, and completes with
`DRY_RUN_COMPLETE` without entering `SCANNING`.

Dry-run trace generation consumes only local `ExecutionScanPlan`,
`ExecutionStripePlan` and `ExecutionFramePlan` DTOs. These DTOs describe the
already-compiled execution trace inputs and do not own host-side scan planning,
camera routing, autofocus routing, tissue maps or tiling.

Terminal states carry a terminal reason:

- `DRY_RUN_COMPLETE`
- `SCAN_COMPLETE`
- `STOPPED`
- `FAULT_DETECTED`

Terminal snapshots do not transition further.
