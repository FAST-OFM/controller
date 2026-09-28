---
name: Task
about: Track implementation, documentation, or research work
title: "<NNN> [P<0|1|2>] "
labels: ""
assignees: ""
---

## Issue Prefix

The numeric prefix is the local backlog ID, not necessarily the GitHub issue
number. Preserve it when splitting, retitling or linking work, for example
`055 [P0]`.

## Goal

## Context

## Zone / Owner Repo

## Source Of Truth

- Source-of-truth repo:
- Source-of-truth docs / ADRs / specs:
- Hidden chat memory is not a source of truth; record durable claims in repo
  docs, issue bodies, PR bodies, commits, fixtures or evidence files.

## Interface Or Contract

- Interface catalog row:
- Contract matrix row:
- Reserved IDs (`contract_id`, `fixture_id`, `validation_id`,
  `matrix_row_id`):

## Shared-Logic Ledger Impact

- Ledger entry or `not applicable`:
- Sharing strategy if behavior may exist in more than one repo:

## Allowed Paths

## Forbidden Scope

Do not include hardware-running behavior unless a linked live-test approval gate
explicitly authorizes it.

## Lifecycle / Error / Safety State

- Lifecycle states:
- Fail-closed / retry / diagnostic-only semantics:
- Safety state:

## Hardware / Live State

- Hardware access possible:
- Hardware outputs enabled:
- Live-test gate:

## Duplicate Domain Logic / Facade Checks

- [ ] Does not copy domain behavior across repositories without a ledger entry.
- [ ] Does not add facade-only packages, broad re-export modules or unscoped
      `model.py` dumping grounds.
- [ ] Temporary aliases or shims have an owning cleanup issue and removal
      condition.

## Acceptance Criteria

## Required Tests / Evidence

## Safety / Hardware Impact

## References
