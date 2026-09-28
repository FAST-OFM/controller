# MCU State Machines

## Top-level state machine

```mermaid
stateDiagram-v2
    [*] --> BOOT
    BOOT --> CONFIG_REQUIRED
    CONFIG_REQUIRED --> IDLE: config_loaded
    IDLE --> HOMING: home_request
    HOMING --> READY: homed
    READY --> SCAN_PREPARE: scan_recipe_loaded
    SCAN_PREPARE --> ACCELERATE
    ACCELERATE --> SCAN_STRIPE: constant_velocity
    SCAN_STRIPE --> DECELERATE: stripe_done
    DECELERATE --> NEXT_ROW: more_rows
    NEXT_ROW --> SCAN_PREPARE
    DECELERATE --> FINISHED: no_more_rows
    FINISHED --> READY
    SCAN_STRIPE --> PAUSED: pause_request
    PAUSED --> SCAN_PREPARE: resume
    SCAN_STRIPE --> ERROR: fault
    ERROR --> SAFE_SHUTDOWN
```

## Scan stripe state machine

```mermaid
stateDiagram-v2
    [*] --> WAIT_POSITION
    WAIT_POSITION --> PREPARE_FRAME_WINDOW: future trigger position armed
    PREPARE_FRAME_WINDOW --> EXECUTE_ILLUMINATION_AND_TRIGGER: reached trigger position
    EXECUTE_ILLUMINATION_AND_TRIGGER --> EMIT_FRAME_EVENT
    EMIT_FRAME_EVENT --> APPLY_SCHEDULED_Z
    APPLY_SCHEDULED_Z --> SCHEDULE_NEXT_TRIGGER
    SCHEDULE_NEXT_TRIGGER --> WAIT_POSITION
```

For autofocus frames, `EXECUTE_ILLUMINATION_AND_TRIGGER` is an atomic timing
window owned by the MCU: suppress preview white if configured, enable the
red/green autofocus gates, wait the configured settle time, emit the camera
trigger, hold through the exposure window, disable red/green and restore preview
white. `FRAME_EVENT` is emitted only as the fact record for that completed
trigger/illumination window; future lookahead must use a distinct advisory event
such as `FRAME_ARMED` and must not be consumed as acquired-frame metadata.

## Homing state machine

```mermaid
stateDiagram-v2
    [*] --> CHECK_SAFE
    CHECK_SAFE --> PRE_HOME_Z_POLICY
    PRE_HOME_Z_POLICY --> SEEK_FAST
    SEEK_FAST --> BACKOFF: switch_active
    BACKOFF --> SEEK_SLOW
    SEEK_SLOW --> SET_MACHINE_ZERO: switch_active
    SET_MACHINE_ZERO --> VERIFY_RELEASE_OR_REPEAT
    VERIFY_RELEASE_OR_REPEAT --> HOMED
    SEEK_FAST --> ERROR: timeout_or_travel_limit
    SEEK_SLOW --> ERROR: timeout_or_travel_limit
    BACKOFF --> ERROR: switch_stuck
    PRE_HOME_Z_POLICY --> ERROR: z_policy_missing
```
