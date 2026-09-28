# simulator

Simulator test scope for position-event scheduling.

The simulator must validate scheduler behavior before any hardware backend is
enabled.

Required cases:

- positive X stripe emits `event_count` events at `first_event_position + n *
  event_pitch`;
- negative X stripe emits events with reversed comparison and decreasing
  positions;
- Y stripe uses Y commanded counts while preserving X metadata;
- coarse samples that overshoot scheduled event positions preserve the
  scheduled event position as frame metadata and report the sample overshoot;
- `frame_id` strictly increases across stripes;
- `stripe_frame_index` resets per stripe;
- LED pattern sequence repeats or stops according to recipe policy;
- `hardware_outputs_enabled=false` in dry-run mode;
- invalid zero pitch is rejected;
- event positions outside stripe bounds are rejected;
- stop/fault prevents further event emission.

Additional homing and coordinate-source simulator scope:

- physical-switch homing success and fault paths;
- driver-assisted/sensorless homing modeled as feedback samples, not real
  motor current or driver registers;
- encoder-index homing modeled as an index sample;
- Z homing requires an explicit Z policy;
- `step_indexed`, `encoder_indexed` and `hybrid` coordinate-source modes.

The simulator must not require a connected controller board.

Firmware-base spike adapter tests also stay no-hardware only. They convert
synthetic Klipper-like commanded positions, grblHAL-like planner snapshots and
external sync-board STEP/DIR pulses into the common scheduler input so the same
`FRAME_EVENT` contract can be compared across candidates.

The Phase 0 fixture in `tests/fixtures/firmware_base_phase0_expected.json`
records expected dry-run event streams for all three candidates and must remain
hardware-output-free.

## Marker classification

Simulator tests are assigned exactly one pytest marker by file in
`tests/simulator/conftest.py`:

- `unit`: focused model, planner, scheduler, math and validator tests for the
  fast edit loop;
- `contract`: protocol, codec, parser, readiness, metadata and host-boundary
  contract tests;
- `integration`: multi-module dry-run service, backend, replay and
  planner-to-scheduler bridge tests;
- `architecture`: AST/import guardrails, component boundary checks and patch
  artifact consistency tests.

Fast local subsets:

```bash
.venv/bin/python -m pytest -m unit
.venv/bin/python -m pytest -m contract
.venv/bin/python -m pytest -m integration
.venv/bin/python -m pytest -m architecture
```

Run the full software suite before handing off shared simulator, protocol or
architecture changes:

```bash
.venv/bin/python -m pytest
```
