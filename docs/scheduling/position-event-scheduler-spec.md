# Position Event Scheduler Specification

## Purpose

Generate deterministic position-indexed frame metadata events when the scan
position reaches scheduled points. Physical camera trigger and LED strobe
outputs are backend actions that may be attached later, after board pins,
voltage levels and safety procedures are reviewed.

The scheduler contract must be valid in simulation before any hardware output
is enabled.

## Non-Negotiable Rules

- MCU-side position is the scheduling authority.
- Event positions are indexed by commanded step count initially.
- The schema must be ready for future encoder-indexed and hybrid coordinate
  sources.
- `FRAME_EVENT` metadata is the source of truth for frame identity and scan
  coordinates.
- Raspberry Pi/Linux wall-clock time must not be used to infer frame identity
  or coordinates.
- Diagnostic GPIO pulses are optional and are not a metadata substitute.
- Hardware trigger, LED strobe and GPIO backends remain disabled until an
  explicit hardware test procedure is approved.

## Implementation Phases

### Phase 0: dry-run scheduler

No pins are toggled. The scheduler consumes synthetic or simulated positions
and produces the exact `FRAME_EVENT` records that would be sent to the
Raspberry Pi. Accepted Phase 0 schedules must explicitly remain in dry-run
mode with hardware outputs disabled.

Phase 0 validates:

- frame ID allocation;
- stripe frame index allocation;
- event spacing and count;
- LED pattern sequencing;
- commanded coordinate metadata;
- coordinate source metadata;
- coordinate-source validation, including encoder count availability;
- stop/fault behavior.

### Phase 1: metadata-only on target firmware

The MCU runs the scheduler against real commanded position state, but physical
camera trigger and LED outputs remain disabled. Events are emitted through the
firmware protocol for host-side matcher development.

### Phase 2: diagnostic output backend

Optional diagnostic GPIO pulses may be enabled for oscilloscope alignment
after the board output and voltage levels are reviewed. These pulses are still
not the source of truth.

### Phase 3: camera/LED output backend

Camera trigger and LED gate outputs may be enabled only after hardware pin
selection, voltage compatibility, LED driver safety and camera trigger timing
are reviewed.

## Inputs

```yaml
stripe_id: int
axis: X | Y
start_position: int
end_position: int
first_event_position: int
event_pitch: int
event_count: int
pattern_sequence: [BF_WHITE, AF_RED_GREEN]
pattern_led_timing:
  BF_WHITE:
    trigger_pulse_us: int
    exposure_start_offset_us: int
    exposure_us: int
    gate_pulse_us: int
    brightness_by_gate:
      led_white: float
  AF_RED_GREEN:
    trigger_pulse_us: int
    exposure_start_offset_us: int
    exposure_us: int
    gate_pulse_us: 0
    gate_pre_trigger_us: int
    gate_post_exposure_us: int
    baseline_gate_names: [led_white]
    brightness_by_gate:
      led_red: float
      led_green: float
coordinate_source: step_indexed | encoder_indexed | hybrid
dry_run: bool
hardware_outputs_enabled: bool
```

`pattern_led_timing` is keyed by logical pattern. `BF_WHITE` and
`AF_RED_GREEN` may have different trigger pulse widths, exposure durations,
light lead/tail windows and brightness setpoints in the same scan. The old
flat input field `led_timing` is rejected so brightfield and autofocus timing
cannot be silently coupled.

## Outputs

- `FRAME_EVENT` record;
- `SCHEDULER_TERMINAL` record on host stop, runtime scheduler fault or
  exhausted position sample stream;
- optional diagnostic pulse if enabled and approved;
- optional camera trigger pulse if a hardware backend is enabled and approved;
- optional LED gate pulse(s) if a hardware backend is enabled and approved.

## Event record

```yaml
frame_id: int
stripe_id: int
stripe_frame_index: int
pattern: BF_WHITE | AF_RED_GREEN | DARK | CUSTOM
coordinate_source_used: step_indexed | encoder_indexed | hybrid
position_axis: X | Y
event_position: int
sample_position: int
position_overshoot_count: int
x_count: int
y_count: int
z_count: int
x_step_commanded: int
y_step_commanded: int
z_step_commanded: int
x_encoder_count: int | null
y_encoder_count: int | null
mcu_time_us: int
coordinate_flags: []
led_timing: object | null
```

`x_count`, `y_count` and `z_count` are the resolved event coordinates for the
selected `coordinate_source_used`. Commanded step fields and encoder fields are
preserved as raw metadata so the host can audit which source produced the
event coordinates.

If a coarse position sample crosses more than one scheduled event position,
`event_position` remains the scheduled position that caused the event. The
sample position is retained separately as `sample_position`, and the signed
difference `sample_position - event_position` is recorded as
`position_overshoot_count`. For `step_indexed` and `hybrid` modes, the active
axis in `x_count`/`y_count` uses `event_position`, not the overshot sample
position.

For `encoder_indexed` mode, `x_count` and `y_count` remain the encoder counts
present in the sample that crossed the scheduled event position. The Phase 0
dry-run scheduler does not interpolate encoder counts back to the scheduled
event position.

When pattern timing is configured, `led_timing` carries the disabled-output
contract for the selected frame pattern. It includes logical trigger timing,
exposure timing, gate windows, brightness setpoints and baseline transitions.
It does not include physical pin names or approval to enable outputs.

## Terminal record

`SCHEDULER_TERMINAL` is not a camera-frame metadata event. It is emitted when a
host stop request, runtime scheduler fault or exhausted position sample stream
prevents the remaining planned `FRAME_EVENT` records for a stripe.

```yaml
type: SCHEDULER_TERMINAL
protocol_version: int
scan_id: str
stripe_id: int
status: stopped | fault
reason_code: host_stop | scheduler_fault | coordinate_source_error | position_stream_exhausted
emitted_frame_count: int
expected_frame_count: int
last_frame_id: int | null
next_frame_id: int
next_stripe_frame_index: int
mcu_time_us: int
hardware_outputs_enabled: false
message: str
```

`next_frame_id` advances only by emitted `FRAME_EVENT` records. Planned but
not-emitted frames do not consume frame IDs.

## Scheduling Algorithm

For monotonic positive-axis stripes:

```text
next_position = first_event_position
frame_index = 0

while frame_index < event_count:
    if current_position_count >= next_position:
        event = build_frame_event(frame_index, next_position)
        emit_or_queue(event)
        if hardware_outputs_enabled:
            run_approved_output_backend(event)
        frame_index += 1
        next_position += event_pitch
```

For negative-axis stripes, the comparison reverses and `event_pitch` is
subtracted from `next_position`.

The implementation must reject schedules where:

- `event_pitch` is zero;
- `event_count` is negative;
- event positions do not fit within the stripe bounds;
- the axis direction and pitch sign disagree;
- `encoder_indexed` coordinate source is requested without X and Y encoder
  counts available for each emitted event;
- the position sample stream ends before all planned events are emitted;
- `dry_run` is false for the Phase 0 dry-run scheduler;
- hardware outputs are requested without an approved backend.

## Timing rule

Illumination timing is selected by frame pattern. `BF_WHITE` and
`AF_RED_GREEN` may have different trigger pulse widths, exposure offsets,
exposure durations, gate windows and brightness setpoints in the same stripe.
Gate windows may start before the trigger event and may end after exposure
completion when the pattern profile declares `gate_pre_trigger_us` and
`gate_post_exposure_us`. The scheduler records those windows as disabled-output
metadata until an approved hardware backend exists.

## Fault Behavior

On stop or fault:

- no further events are emitted for the active stripe;
- hardware outputs, if ever enabled, are driven to safe inactive state;
- a `SCHEDULER_TERMINAL` status/fault record is reported to the host;
- the host must treat unmatched camera frames/events as invalid data.

## Current Board Status

For the current MKS Robin Mini V2.0 setup:

- X/Y/Z commanded step pins are documented from Klipper config.
- Current `PD6` / E0_STEP trigger/sync signaling has been exercised as the
  current non-axis output path. `PC4` / Z+ is legacy/config artifact only unless
  explicitly revalidated.
- Loaded LED strobe outputs, final camera exposure trigger validation, spare GPIO, encoder inputs
  and firmware flashing/debug flow have not been exercised.
- Therefore #5 work should start with Phase 0 dry-run scheduler behavior and
  must not enable physical outputs.
