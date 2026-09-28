# Z Scheduler

Simulator-only predictive Z correction support.

This package models queued Z corrections that are scheduled into the future by
frame id or scan-axis position. It deliberately does not model an immediate
`move_z_now` runtime path.

Queued scheduler commands carry:

- `scan_id` and `stripe_id`;
- exactly one of `apply_at_frame_id` or `apply_at_position_count`;
- absolute `z_target_steps`;
- lead and settle validation through `ZSchedulerConfig`;
- optional no-correction windows by frame id or position count.

Position commands are ordered by synthetic stripe progress, not raw encoder
count, so reverse-direction stripes apply queued targets in travel order.
Commands with duplicate targets keep schedule order. Position-targeted commands
apply only when synthetic position progress reaches or crosses the target; frame
progress alone does not apply them.

`PredictiveZSchedulerSimulator` keeps an in-memory outcome ledger for replay
fixtures and protocol tests:

- accepted `schedule_z` requests are queued and recorded as `accepted`;
- rejected requests are recorded as terminal `rejected` outcomes with a reason;
- applied queued requests are recorded as terminal `applied` outcomes with the
  reported frame or position;
- `validate_terminal_outcomes()` fails if any accepted `seq` is still pending.

Predictive focus planning keeps two values separate:

- `focus_error_steps` / `z_correction_steps` is the relative correction delta;
- `reference_z_steps` plus the bounded correction produces absolute
  `z_target_steps`.

The helper `predict_apply_position_count` implements the ADR-0021 formula
`x_apply = x_measure + v_scan * t_total_latency` for integer scheduler
positions. `v_scan` is signed and must agree with stripe direction, so reverse
stripes use negative velocity. Latency values are explicit caller inputs; this
package does not embed measured AF, transport or actuator constants.

Fractional predicted or physical apply positions are converted with the docs
canonical count-direction rule: count-increasing scans use ceiling,
count-decreasing scans use floor, and exact integer targets remain unchanged.
Physical `apply_at_position_um` normalization requires an explicit
`ApplyPositionCountBasis`; unknown motion resolution is rejected rather than
guessed. Rounded targets outside the active stripe remain invalid and are not
clamped to an endpoint.

Public focus/autofocus boundaries may use micrometers. Conversion into
controller steps belongs in `PredictiveZMicrometerAdapter`, not in the focus
metric or autofocus controller. That adapter uses the shared scan-math
half-away-from-zero rounding helper so negative and positive half-step ties are
handled symmetrically.

The simulator rejects commands when:

- the scan or stripe does not match the active stripe context;
- the requested target frame or position has already passed;
- the configured lead plus settle requirement does not fit available lookahead;
- the requested target is inside a configured no-correction window;
- `z_target_steps` is outside configured Z limits.

No code in this package opens serial ports, toggles GPIO, flashes firmware,
commands motors, talks to Klipper, grblHAL, Arduino, or board files. Applied
records always report `hardware_outputs_enabled=false`.
