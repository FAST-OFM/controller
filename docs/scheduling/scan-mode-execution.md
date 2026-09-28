# Firmware Scan Mode Execution

Firmware must not assume a single `fly_scan` mode. It should execute scan
recipes with explicit modes while preserving the same event identity model.

## Common responsibilities

For every mode the MCU must:

- own motion timing;
- own camera trigger timing;
- own LED strobe timing;
- emit exactly one `FRAME_EVENT` for every camera trigger;
- keep `FRAME_EVENT` as a post-trigger fact record, not an early advisory;
- include frame ID, position counts, coordinate source and LED pattern;
- handle safe stop and emergency stop;
- reject unsafe Z correction commands.

## Modes

### `stop_and_capture`

State sequence:

```text
MOVE_TO_TARGET -> SETTLE_XY -> OPTIONAL_Z -> SETTLE_Z -> EXECUTE_ILLUMINATION_AND_TRIGGER -> FRAME_EVENT -> NEXT
```

### `micro_stop`

```text
MOVE_INCREMENT -> HOLD -> EXECUTE_ILLUMINATION_AND_TRIGGER -> OPTIONAL_Z_WINDOW -> NEXT_INCREMENT
```

### `segmented_fly_scan`

```text
ACCELERATE -> SCAN_SEGMENT_WITH_POSITION_TRIGGERS -> BOUNDARY_WINDOW -> OPTIONAL_Z -> NEXT_SEGMENT
```

### `fly_scan_open_loop`

```text
ACCELERATE -> CONSTANT_VELOCITY_POSITION_TRIGGERS -> DECELERATE
```

Z target may be preloaded from a focus map, but online corrections are restricted by recipe.

### `fly_scan_predictive_z`

Same as open-loop fly scan, plus scheduled Z queue:

```text
Pi -> MCU: schedule_z(apply_at_position/count/frame_id, z_target)
MCU -> Pi: Z_SCHEDULED | Z_REJECTED
MCU -> Pi: Z_APPLIED once the future command is applied
```

Firmware applies the command only if:

- the target has not passed;
- the actuator can complete safely;
- no no-correction window is active;
- the command matches current scan/stripe;
- safety limits are satisfied.

The command is not an immediate current-frame correction. If the target has
already passed or the Z axis cannot settle safely, firmware rejects the command
instead of trying to catch up.

## Diagnostics

Expose test pins or events for:

- trigger pulse;
- LED pulse;
- Z command start/complete;
- segment boundary;
- frame event emission;
- dropped/rejected Z correction.

Autofocus illumination diagnostics must be able to run without motion and
without claiming hardware acquisition. They should replay the same atomic timing
window used in scan mode: preview-white suppression, red/green enable, settle,
camera-trigger-equivalent edge, exposure hold, red/green disable and preview
white restore. The diagnostic repeat period is invalid if it overlaps the
previous timing window.

## Simulator Policy

`scanner-pi` owns the no-hardware scan-mode selection policy for these
execution modes. Firmware consumes the selected mode as scheduler/controller
input; it does not own camera, host latency or image-processing policy. The
policy uses measured or configured constraints:

- LED brightness sufficiency;
- exposure time;
- LED pulse width and settle time;
- allowed motion blur;
- frame period;
- processing latency;
- Z correction requirement and settle time;
- predictive-Z lookahead;
- segment-boundary Z window.

Continuous scanning is selected only when those inputs allow it. Otherwise the
policy falls back to slower modes. A requested mode is rejected if it violates
the same constraints.
