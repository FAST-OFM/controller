# Firmware Frame Event Emission

## Requirement

For every camera trigger emitted by the MCU, the firmware must emit exactly
one `FRAME_EVENT` to the Raspberry Pi.

For dry-run and metadata-only scheduler phases, the firmware may emit
`FRAME_EVENT` records without a physical camera trigger. Those records are
for simulation, host matcher development and diagnostics only; they must not
be treated as valid image captures.

The event is the authoritative metadata record for that image.

## Event timing

The MCU may emit the event immediately before, during or immediately after the trigger pulse, provided ordering is deterministic and documented.

Recommended MVP behavior:

```text
1. trigger position reached
2. determine frame_id and LED pattern
3. resolve the selected pattern's `pattern_led_timing` profile
4. apply the profile's LED gate/baseline timing and camera trigger timing
5. enqueue FRAME_EVENT with the same frame_id, pattern and `led_timing`
   contract metadata
6. increment next trigger position
```

Recommended dry-run behavior:

```text
1. scheduled position reached in simulated or metadata-only execution
2. determine frame_id and LED pattern
3. enqueue FRAME_EVENT with hardware_outputs_enabled=false
4. increment next trigger position
```

The event must include the commanded coordinate at the trigger point. If encoders are present, it should include measured encoder counts as well.

## Required fields

- protocol version
- scan ID
- stripe ID
- global frame ID
- stripe frame index
- LED pattern
- x/y/z commanded counts
- coordinate source used
- optional encoder counts
- MCU-local timestamp
- trigger pulse interval from the selected pattern timing profile
- `led_timing` contract metadata when pattern timing is configured
- status

## Guarantees

- `frame_id` is monotonically increasing within a scan.
- no two trigger pulses share a frame ID.
- no trigger pulse is emitted without a matching event unless firmware enters fault state.
- no dry-run event is treated as a captured image event.
- on emergency stop, LEDs and trigger outputs are driven safe before further events.
- if `led_timing` is present, its logical channels match the event LED pattern
  and its `frame_start_us` matches the event MCU timestamp.

## Diagnostics

The firmware should optionally emit diagnostic GPIO pulses for oscilloscope alignment, but GPIO pulses are not a substitute for `FRAME_EVENT` metadata.
