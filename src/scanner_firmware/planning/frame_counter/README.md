# frame_counter

Software-only frame/event identity helpers.

`FrameIdAllocator` and `FrameEventPublisher` model metadata/dry-run frame
publication before camera acquisition exists in the host process. The allocator
issues monotonic `frame_id` values from an injected software counter, so frame
identity never depends on Linux wall-clock time. The publisher accepts one
`PlannedFrameTrigger` per planned trigger and emits exactly one
`PublishedFrameEvent` for that trigger. Reusing the same
`(scan_id, stripe_id, stripe_frame_index)` planned trigger is rejected.

Publisher output is metadata-only:

- `hardware_outputs_enabled` is always `false`
- `dry_run` planned triggers are required
- no camera IO, GPIO, motors, LEDs, serial, firmware transport or network access
- `terminal_summary()` reports emitted and expected frame counts only for
  incomplete host-stop or fault streams

`protocol_adapter` converts `PublishedFrameEvent` metadata into
`protocol.events.FrameEventRecord` and supported `FramePublisherTerminal`
metadata into `protocol.events.SchedulerTerminalRecord`. The adapter preserves
frame identity, coordinates, LED pattern/gate metadata and status fields that
the current protocol shape can represent. It rejects any input with
`hardware_outputs_enabled=true`. Clean completion emits the expected contiguous
`FRAME_EVENT` records and no `SCHEDULER_TERMINAL`.

The matcher relates host image arrival records to MCU `FRAME_EVENT` records
strictly by `(scan_id, stripe_id, frame_id)`. Host Linux wall-clock arrival
timestamps may be stored on `HostImageArrival` for diagnostics, but they are
not used for matching.

This package is intentionally isolated from hardware actions: it does not
touch GPIO, motors, LEDs, cameras, firmware transports or network resources.

Terminal stream events close the matcher input. Reports then expose:

- matched image/event pairs
- duplicate record rejection at ingest time
- host images without MCU events
- MCU events without host images
- missing frame IDs from event gaps or terminal expected/emitted counts
