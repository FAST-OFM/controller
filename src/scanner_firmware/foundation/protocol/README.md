# protocol

Firmware protocol notes.

The first protocol object needed by the scheduler is `FRAME_EVENT`.

Minimum dry-run fields:

- `type`: `FRAME_EVENT`;
- `protocol_version`;
- `scan_id`;
- `stripe_id`;
- `frame_id`;
- `stripe_frame_index`;
- `pattern`;
- `led_gate_names`;
- `trigger_output_name`;
- `coordinate_source_used`;
- `position_axis`;
- `event_position`;
- `sample_position`;
- `position_overshoot_count`;
- `x_step_commanded`;
- `y_step_commanded`;
- `z_step_commanded`;
- resolved `x_count`/`y_count`/`z_count`;
- optional encoder counts;
- coordinate flags;
- `mcu_time_us`;
- `hardware_outputs_enabled`;
- `status`.

Dry-run or metadata-only events must set `hardware_outputs_enabled=false`.
The host must not treat those events as evidence that a camera exposure was
triggered.

Live metadata decoders that receive compact MCU payloads, such as numeric
pattern identifiers, must attach `scan_id`, pattern names and LED gate names
from explicit scanner-sync session context. Camera arrival time or Linux
wall-clock time must not be used as frame identity or coordinate source.

The scheduler may also emit a non-frame terminal record when a host stop,
runtime scheduler fault or exhausted position stream prevents the remaining
planned frame events:

- `type`: `SCHEDULER_TERMINAL`;
- `protocol_version`;
- `scan_id`;
- `stripe_id`;
- `status`: `stopped` or `fault`;
- `reason_code`: `host_stop`, `scheduler_fault`, `coordinate_source_error` or
  `position_stream_exhausted`;
- `emitted_frame_count`;
- `expected_frame_count`;
- `last_frame_id`;
- `next_frame_id`;
- `next_stripe_frame_index`;
- `mcu_time_us`;
- `hardware_outputs_enabled=false`;
- `message`.

`SCHEDULER_TERMINAL` is not an image/frame event and must not be matched to a
camera frame.

Fixture policy: the canonical terminal record only represents incomplete
stopped or faulted stripes. A clean software replay completion is represented by
the expected contiguous `FRAME_EVENT` records and no `SCHEDULER_TERMINAL`.
Terminal records whose expected count equals emitted count are rejected by the
replay validator unless the canonical protocol is explicitly extended later.

## Canonical v1 export

The canonical replay fixture at
`tests/fixtures/frame_event_replay_protocol_v1.jsonl` is stored directly in
canonical protocol-v1 shape. Every record carries `protocol_version="1.0.0"`;
`FRAME_EVENT` records use `status=OK`. Its simulator regression tests assert
that applying `to_canonical_v1_json_dict()` is idempotent, so fixture replay
does not depend on compatibility-profile normalization.

Runtime DTOs and legacy bootstrap records may still use compatibility fields
documented in `scanner-docs/specifications/pi-mcu-protocol.md`, including
`protocol_version=1` and `FRAME_EVENT.status=ok`. Use
`to_canonical_v1_json_dict()` or `to_canonical_v1_json()` only when producing
canonical contract evidence from those legacy DTOs. The normal `to_json_dict()`
helper preserves runtime compatibility shape; the canonical export helper
bridges:

- `protocol_version=1` or missing protocol version to `"1.0.0"`;
- `FRAME_EVENT.status=ok` to `FRAME_EVENT.status=OK`;
- unsupported protocol versions are rejected instead of silently accepted.

Persisted protocol JSONL evidence is stricter than runtime DTOs: decoders reject
records that still need these compatibility normalizations. Produce evidence
with the canonical exporter before writing fixtures or contract artifacts.
