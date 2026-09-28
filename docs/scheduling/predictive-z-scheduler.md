# Firmware Predictive Z Scheduler

The firmware receives scheduled Z corrections from the Pi. It does not interpret autofocus images.

The correction is always scheduled for a future position or frame. The firmware
must not expose an autofocus feedback path that applies `move_z_now` to the
current frame position during a scan.

When the firmware base is Klipper, `schedule_z` should be carried by a
scanner-specific Klipper host/MCU extension. It must not require per-frame
G-code round trips.

## Command

```json
{
  "cmd": "schedule_z",
  "seq": 101,
  "scan_id": "scan_001",
  "stripe_id": 42,
  "apply_at_position_count": 1234567,
  "apply_at_frame_id": null,
  "z_target_um": 42.5,
  "source": "two_color_oblique_af",
  "confidence": 0.86
}
```

## Queue rules

- Commands are ordered by apply coordinate/frame.
- Commands at or behind current frame/position are rejected with reason
  `target_already_passed`.
- Commands too close to execute safely are rejected with reason
  `insufficient_lookahead`.
- Commands outside current stripe/scan are rejected.
- Commands violating Z velocity/range/safety limits are rejected.
- Stepper Z commands may be deferred to a configured safe window.
- The in-memory firmware fixture records every schedule request as an
  `accepted`, `rejected` or `applied` outcome. Rejected requests are terminal
  immediately. Accepted requests must later receive exactly one terminal
  `applied` outcome for the same `seq`.

## Events

```json
{"type":"Z_SCHEDULED","seq":101,"status":"accepted"}
{"type":"Z_APPLIED","seq":101,"frame_id":1842,"z_cmd_count":3456}
{"type":"Z_REJECTED","seq":102,"reason":"insufficient_lookahead"}
```

The Pi must use these acknowledgements to update focus-map, QA and matcher
state. A missing acknowledgement is a protocol/synchronization fault, not an
implicit success.

## Stepper-Z safety

For current hardware, stepper Z is a slow correction mechanism. Firmware must not try to apply a backlog of per-frame corrections if the axis cannot settle. It should either reject, coalesce or defer based on recipe policy.
