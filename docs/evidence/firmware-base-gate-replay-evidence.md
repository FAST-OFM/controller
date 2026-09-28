# Firmware Base Gate Replay Evidence

Status: software-only evidence. This artifact does not select a firmware base
and does not claim live hardware readiness.

## Inputs

- Checked report:
  `tests/fixtures/firmware_base_gate_replay_evidence_v1.json`
- Builder:
  `src/scanner_firmware/adapters/firmware_base/gate_replay_evidence.py`
- Validator:
  `tests/simulator/test_firmware_base_gate_replay_evidence.py`
- Source replay fixtures:
  - `tests/fixtures/frame_event_replay_protocol_v1.jsonl`
  - `tests/fixtures/frame_event_replay_protocol_v1_clean_completion.jsonl`
  - `tests/fixtures/frame_event_replay_protocol_v1_fault_terminal.jsonl`

The builder reads checked scanner-sync protocol JSONL only. It does not import
or contact Klipper, grblHAL, GPIO, serial, camera, LED, motor or firmware
flashing APIs.

## Result

The replay evidence advances two remaining firmware-base spike gates:

- safe-stop or fault-terminal behavior: a stopped terminal, a fault terminal
  and clean-completion-without-terminal policy are all validated through the
  protocol event-stream acceptance path;
- scheduled-Z bidirectional acknowledgement path: existing fixtures validate
  `Z_SCHEDULED` followed by `Z_APPLIED` for both frame-target and
  position-target examples, plus a rejected Z command path.

The report records:

- `software_only=true`;
- `hardware_outputs_enabled=false`;
- `live_hardware_access_used=false`;
- `live_readiness_claimed=false`;
- `final_firmware_base_selected=false`;
- `candidate_coverage=common_protocol_fixture_only`.

## Remaining Gates

This artifact is not enough to close scanner-firmware#2. It provides common
protocol replay evidence only; it does not prove per-candidate live timing,
motion, GPIO, LEDs, cameras, flashing, homing, encoder coordinate truth or
maintenance cost. The report keeps the full closeout gate list explicit in
`remaining_spike_gates_before_close`.
