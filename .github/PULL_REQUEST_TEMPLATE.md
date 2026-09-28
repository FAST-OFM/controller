## Purpose


## Linked issue prefix

- [ ] PR links an issue title with the local backlog ID prefix, for example
      `055 [P0]`.
- [ ] Any split or follow-up work preserves the existing numeric prefix.

## Affected subsystem


## Zone / owner repo


## Source of truth

- Source-of-truth repo:
- Source-of-truth docs / ADRs / specs:
- Hidden chat memory is not a source of truth; record durable claims in repo
  docs, issue bodies, PR bodies, commits, fixtures or evidence files.

## Interface or contract


- Interface catalog row:
- Contract matrix row:
- Reserved IDs (`contract_id`, `fixture_id`, `validation_id`,
  `matrix_row_id`):

## Shared-logic ledger impact

- [ ] Not applicable; behavior is repo-local and behavior-free.
- [ ] Ledger entry linked:
- [ ] Uses `scanner-core`, generated artifact or shared parity vectors instead
      of copying domain logic.

## Allowed paths


## Forbidden scope


## Lifecycle / error / safety state

- Lifecycle states:
- Fail-closed / retry / diagnostic-only semantics:
- Safety state:

## Duplicate logic / facade checks

- [ ] Does not duplicate planner math, protocol parsing, scheduler validation,
      projection/hash helpers, calibration resolution, scan geometry or
      evidence validation across repositories.
- [ ] Does not add facade-only packages, broad re-export modules or unscoped
      dumping-ground `model.py` surfaces.
- [ ] Temporary compatibility aliases name an owning cleanup issue and removal
      condition.

## Linked requirements / ADRs / issues


## Tests or experiment plan


## Safety impact

- [ ] No hardware impact
- [ ] Motors affected
- [ ] LEDs affected
- [ ] Camera trigger affected
- [ ] Homing/limits affected
- [ ] Coordinate/focus behavior affected

## Live-test gate

- [ ] No live hardware, camera, GPIO, illumination, motor, firmware flashing or
      network control is performed by this PR.
- [ ] Live-test approval is linked before any hardware-running procedure is
      enabled.
- [ ] Linked issue has the same live-test gate state.
- [ ] Hardware/live state is explicitly software-only, unknown, blocked or
      approved by a separate live-test gate.

For software-only work:

```text
live_test_gate:
  required: false
  scope: "software-only"
  readiness_ref: "<fixture/check or not applicable>"
  approval_ref: ""
  execution_ref: ""
  approved: false
  executed: false
```

For proposed hardware-running work, keep approval and execution false until a
human approval and then execution result are recorded separately:

```text
live_test_gate:
  required: true
  scope: "<one signal, one axis or one subsystem>"
  readiness_ref: "<software-only readiness result or fixture/check>"
  approval_ref: ""
  execution_ref: ""
  approved: false
  executed: false
```

## Data/calibration impact


## Rollback plan


## Notes / known limitations
