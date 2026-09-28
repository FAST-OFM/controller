---
name: ADR / Decision
about: Propose or revise an architectural decision
title: "<NNN> [P<0|1|2>] "
labels: ""
assignees: ""
---

## Issue Prefix

The numeric prefix is the local backlog ID, not necessarily the GitHub issue
number. Preserve it when splitting, retitling or linking work, for example
`055 [P0]`.

## Decision Needed

## Context

## Source Of Truth

- Source-of-truth repo:
- Source-of-truth docs / ADRs / specs:
- Hidden chat memory is not a source of truth; record durable claims in repo
  docs, issue bodies, PR bodies, commits, fixtures or evidence files.

## Boundary / Contract Impact

- Owning repo:
- Interface catalog row:
- Contract matrix row:
- Shared-logic ledger impact:
- Lifecycle / error / safety state:

## Allowed / Forbidden Scope

- Allowed owner paths or docs:
- Forbidden scope:

## Duplicate Domain Logic / Facade Checks

- [ ] Decision does not authorize duplicate planner math, protocol parsing,
      scheduler validation, projection/hash helpers, calibration resolution,
      scan geometry or evidence validation without an approved sharing strategy.
- [ ] Decision does not authorize facade-only packages, broad re-export modules
      or unscoped dumping-ground `model.py` surfaces.

## Hardware / Live State

- Hardware access possible:
- Hardware outputs enabled:
- Live-test gate:

## Options Considered

## Proposed Decision

## Consequences

## Related ADRs / Requirements
