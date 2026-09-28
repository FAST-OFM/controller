# Klipper Spike Test Plan

## Goal

Determine whether Klipper can support scanner-specific position-indexed
trigger/LED/frame events and future scheduled Z corrections with acceptable
maintainability.

Read-only evidence from the current Pi/Klipper checkout is recorded in
`docs/evidence/klipper-readonly-inspection.md`. That evidence does not approve live
Klipper edits or hardware tests.

The proposed live patch shape is documented in
`docs/klipper/klipper-scanner-sync-patch-proposal.md`. It is a design proposal only.

## Tests

1. Run dry-run scheduler simulation using synthetic commanded X positions.
2. Confirm `FRAME_EVENT` metadata without any GPIO or camera output.
3. Evaluate whether Klipper can expose commanded position state to a scheduler
   without per-frame G-code round trips.
4. Evaluate a bidirectional scanner extension path:
   - MCU-to-host `FRAME_EVENT`;
   - host-to-MCU `schedule_z`;
   - MCU-to-host `Z_SCHEDULED`, `Z_APPLIED` and `Z_REJECTED`;
   - MCU-to-host `SCHEDULER_TERMINAL`.
5. Implement a local fake Klipper-adapter registration test that models the
   required host APIs without importing real Klipper or opening serial devices.
6. Only after approval, run constant velocity X motion on target board or a
   bench-safe simulator.
7. Only after approval, generate diagnostic trigger/LED-equivalent signals at
   fixed step intervals or scheduled positions.
8. Emit frame metadata to host.
9. Verify safe boot and stop behavior.
10. Evaluate how invasive changes are to Klipper host/MCU layers.

Before tests 6 or 7, follow `docs/foundation/bench-safe-timing-procedure.md` and record
explicit approval in the relevant GitHub issue.

## Success criteria

- deterministic trigger timing visible on scope;
- frame ID and pattern match expected sequence;
- no per-frame G-code round trips required;
- future Z corrections are queued by position/frame, not executed as immediate
  scan-time `move_z_now` commands;
- accepted, applied and rejected Z commands are reported back to the Pi with
  uniform event names;
- clear path to homing and coordinate-source metadata;
- maintainable patch/plugin strategy documented.
