# trigger_scheduler

Position-indexed event scheduler contract.

Initial implementation should be a dry-run/simulator module only. It must not
toggle pins, command motors or assume camera/LED electrical wiring.

Responsibilities:

- consume a scan stripe event schedule;
- consume commanded position counts from a coordinate source;
- emit deterministic `FRAME_EVENT` records at scheduled positions;
- maintain monotonically increasing `frame_id`;
- maintain per-stripe frame indices;
- apply LED pattern IDs to metadata without driving LEDs;
- reject invalid schedules before execution;
- expose fault/stop behavior for host tests.
- queue scheduler metadata through a bounded software FIFO before scanner-sync
  protocol handoff.

Clean dry-run completion emits the planned `FRAME_EVENT` records only. The
local fixture policy reserves `SCHEDULER_TERMINAL` for incomplete `stopped` or
`fault` outcomes; it does not introduce a protocol-level `complete` terminal.

`metadata_queue/` is the Phase 1 scanner-sync integration point. It accepts
already-built scheduler events, validates that `hardware_outputs_enabled` is
false, converts them to protocol records, and stores them in FIFO order with
monotonic queue sequence IDs. Queue records preserve scheduler-owned
`FRAME_EVENT` identity and coordinates (`frame_id`, `stripe_frame_index`,
`event_position`, counts and MCU sample time). The queue does not add Linux
wall-clock identity and does not execute hardware actions.

Out of scope for the first implementation:

- physical camera trigger pulses;
- LED gate pulses;
- GPIO diagnostics;
- firmware flashing or board-specific output pin enablement.

See `docs/scheduling/position-event-scheduler-spec.md`.
