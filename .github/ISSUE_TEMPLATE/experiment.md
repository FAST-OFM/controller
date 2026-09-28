---
name: Experiment
about: Plan or report a reproducible hardware or software experiment
title: "<NNN> [P<0|1|2>] "
labels: ""
assignees: ""
---

## Issue Prefix

The numeric prefix is the local backlog ID, not necessarily the GitHub issue
number. Preserve it when splitting, retitling or linking work, for example
`055 [P0]`.

## Goal / Hypothesis

## Source Of Truth

- Source-of-truth repo:
- Source-of-truth docs / ADRs / specs:
- Hidden chat memory is not a source of truth; record durable claims in repo
  docs, issue bodies, PR bodies, commits, fixtures or evidence files.
- Contract matrix row:
- Shared-logic ledger impact:

## Hardware Configuration

## Hardware / Live State

- Hardware access possible:
- Hardware outputs enabled:
- Live-test gate:

## Software / Firmware Commits

## Calibration IDs

## Interface / Contract State

- Interface catalog row:
- Lifecycle states:
- Error / fail-closed semantics:
- Safety state:

## Allowed / Forbidden Scope

- Allowed paths / artifacts:
- Forbidden scope:

## Duplicate Domain Logic / Facade Checks

- [ ] Experiment consumes producer fixtures, schemas or reports by value.
- [ ] Experiment does not import producer runtime internals to satisfy a
      contract.
- [ ] Experiment does not add duplicate domain validators without a ledger
      entry or generated artifact strategy.

## Procedure

## Data / Artifacts

## Success Criteria

## Safety Notes
