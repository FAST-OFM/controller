# Firmware Base Phase 0 Comparison Report

Status: software-only evidence. This report does not select Klipper, grblHAL or
an external sync board as the final firmware base.

## Inputs

- Source fixture:
  `tests/fixtures/firmware_base_phase0_expected.json`
- Checked comparison report:
  `tests/fixtures/firmware_base_phase0_comparison_report_v1.json`
- Builder:
  `src/scanner_firmware/adapters/firmware_base/comparison_report.py`
- Validator:
  `tests/simulator/test_firmware_base_comparison_report.py`

The report reads existing dry-run metadata only. It does not import or contact
Klipper, grblHAL, GPIO, serial, camera, LED, motor or firmware flashing APIs.

## Result

The phase-0 metadata gate passes for all three candidates because the checked
fixture covers:

- Klipper-like commanded position samples;
- grblHAL-like planner snapshots;
- external RP2040 sync-board-like STEP/DIR pulses.

Each candidate emits position-indexed frame events through the common dry-run
scheduler with contiguous per-candidate frame IDs, contiguous stripe frame
indices, `step_indexed` coordinate source metadata, trigger output metadata and
LED gate metadata. The report also records:

- `software_only=true`;
- `hardware_outputs_enabled=false`;
- `live_hardware_access_used=false`;
- `final_firmware_base_selected=false`;
- `recommendation_state=not_ready_for_final_selection`.

## Remaining Gates

The firmware-base issue cannot close on this report alone. The comparison
report keeps these gates open:

- bench-safe or no-hardware timing result;
- position-indexed output jitter measurement;
- safe-stop or fault-terminal behavior per candidate;
- scheduled-Z bidirectional acknowledgement path;
- homing state and coordinate-source integration;
- future encoder coordinate-source path;
- fork or plugin maintenance cost;
- approved live-hardware procedure before any outputs.

This evidence advances the recommendation by making the existing phase-0
fixture comparable and repeatable. It does not claim live timing, flashing,
motion, camera, GPIO or LED readiness.

Follow-on software-only gate replay evidence is recorded in
`docs/evidence/firmware-base-gate-replay-evidence.md`. It advances common
protocol safe-stop/fault-terminal and scheduled-Z acknowledgement checks while
keeping live readiness and final firmware-base selection explicitly unclaimed.
