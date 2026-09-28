# Firmware Architecture

## Goals

- Deterministic motion and acquisition timing.
- Position-indexed camera trigger.
- LED strobe synchronized with camera exposure.
- Frame metadata emitted for every trigger.
- Stepper Z now, future fine-Z later.
- Step-indexed now, encoder-indexed later.

## Modules

```text
MotionAdapter
CoordinateSource
TriggerScheduler
LedScheduler
FrameEventPublisher
ZController
HomingController
SafetyController
ProtocolAdapter
Diagnostics
```

## Source Tree Hierarchy

The repository keeps implementation code under one package root:
`src/scanner_firmware`. New packages must be assigned to one layer before
merge; otherwise the architecture guardrail tests should fail.

```text
src/
  scanner_firmware/
    foundation/
      firmware_components    # component interfaces and boundary contracts
      protocol               # host/controller protocol value objects

    domain/
      board_profile          # mechanics, pins and board profile validation
      calibration            # calibration value models and policies
      coordinate_source      # commanded-step now, encoder-compatible later
      io_aliases             # logical IO alias registry metadata
      platform_config        # validated platform config objects/loaders
      scan_math              # scheduler/event geometry and unit-safe math

    planning/
      dry_run_pipeline       # firmware replay fixture generation
      frame_counter          # frame identity allocation and publishing
      led_scheduler          # LED pattern scheduling and drive-mode model
      manual_center_bringup  # bounded no-homing V1 bring-up gate
      readiness              # software readiness gates
      scanner_sync           # neutral scanner sync interfaces/services
      scan_execution         # scan execution state machine
      scan_preflight         # preflight aggregation
      trigger_scheduler      # position-indexed trigger schedule
      z_scheduler            # predictive Z scheduling

    adapters/
      controller_adapter     # hardware-affecting controller boundary
      firmware_base          # candidate firmware-base dry-run adapters
      homing                 # homing simulation and future adapter boundary
      klipper_adapter        # Klipper metadata/protocol adapters
      scanner_sync           # scanner sync adapter backends
```

Pi-owned runtime packages were removed from this repository during the boundary
migration. Camera mode/crop/exposure config, RAW Bayer focus metrics, scan-mode
selection, host scan planning, frame/event matching, autofocus orchestration and
slow brightness setpoint transports live in `scanner-pi`.

This hierarchy is available under `scanner_firmware.<layer>.<package>`.
Implementation code should live in responsibility-specific modules such as
`types`, `errors`, `validation`, `scheduler`, `controller`, `planner`,
`codec_*`, `event_stream_*` or `*_registration`. A `model.py` file is allowed
only when it owns concrete data models or local contracts; it must not be used
as a compatibility facade that re-exports unrelated implementation modules.

Current physical migration status:

- `foundation`: implementation lives under `scanner_firmware.foundation`.
- `domain`: implementation lives under `scanner_firmware.domain`.
- `planning`: implementation lives under `scanner_firmware.planning`.
- `adapters`: implementation lives under `scanner_firmware.adapters`.

All new code should use layered imports directly. New implementation code
should import responsibility-specific modules directly and must not add package
`__init__.py` or `model.py` re-export facades.

Completed cleanup after migration:

1. Neutral scanner sync interfaces and dry-run services live under
   `scanner_firmware.planning.scanner_sync`.
2. Adapter-specific backends, passive live metadata ingest and Klipper
   callback validation live under `scanner_firmware.adapters.*`.
3. Architecture guardrails reject adapter imports inside the neutral
   `planning.scanner_sync` package.

Known adapter coupling after the namespace migration:

- `adapters.scanner_sync.backend` may depend on Klipper adapter modules when it
  builds synthetic Klipper callback payloads or validates decoded callback
  streams.
- `klipper_adapter.harness.dry_run` currently depends on scanner sync,
  trigger scheduler and protocol modules.
- Platform config and scan planning intentionally consume lower-layer domain
  models; keep those imports explicit when enforcing layer direction.

## Coordinate source interface

```c
position_count_t coord_get_commanded(axis_t axis);
bool coord_get_measured(axis_t axis, position_count_t *out);
coordinate_source_mode_t coord_get_mode(void);
```

## Trigger scheduler

The trigger scheduler should not depend on wall-clock frame intervals. It should compare current position count to next trigger count.

## Future encoder support

Encoder support is an extension of `CoordinateSource`, not a rewrite of acquisition.

## Design control

Before starting standalone custom firmware or a deep motion-planner patch,
follow `docs/foundation/custom-firmware-control-document.md`.
