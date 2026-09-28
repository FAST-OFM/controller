---
name: Hardware Review
about: Review hardware-affecting changes, assumptions, or procedures
title: "<NNN> [P<0|1|2>] "
labels: ""
assignees: ""
---

## Issue Prefix

The numeric prefix is the local backlog ID, not necessarily the GitHub issue
number. Preserve it when splitting, retitling or linking work, for example
`055 [P0]`.

## Hardware Scope

## Source Of Truth

- Source-of-truth repo:
- Source-of-truth docs / ADRs / specs:
- Hidden chat memory is not a source of truth; record durable claims in repo
  docs, issue bodies, PR bodies, commits, fixtures or evidence files.
- Hardware evidence path:
- Contract matrix row:
- Shared-logic ledger impact:

## Assumptions

## Electrical / Mechanical Risks

## Interface / Lifecycle / Error / Safety State

- Interface catalog row:
- Lifecycle states:
- Fail-closed / stop semantics:
- Safety state:

## Allowed / Forbidden Scope

- Allowed files / procedures:
- Forbidden scope:

## Duplicate Domain Logic / Facade Checks

- [ ] Review does not move runtime ownership into `scanner-hardware`.
- [ ] Review does not introduce duplicate software domain logic without a
      ledger entry or generated artifact strategy.
- [ ] Review does not approve facade-only packages, broad re-export modules or
      unscoped `model.py` surfaces.

## Safe Test Procedure

## Live-Test Gate

Keep this synchronized with the linked PR. `approved=false` and
`executed=false` must remain in place until human approval and execution are
recorded separately.

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

- [ ] Linked PR has the same live-test gate state.
- [ ] Software-only readiness evidence is linked.
- [ ] Exact board, connector, signal, voltage/polarity, load path and stop
      conditions are documented or explicitly unknown.
- [ ] Human approval has not been inferred from readiness.

## Required Measurements

## Rollback / Stop Conditions
