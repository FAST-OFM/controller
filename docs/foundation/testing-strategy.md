# Testing Strategy

Status: local software testing only. These commands do not approve live
firmware flashing, GPIO toggling, motion, camera triggering or LED driving.

## Marker Groups

Pytest markers are assigned in `tests/simulator/conftest.py`:

- `unit`: focused simulator, model, planner, scheduler, math and validator
  tests for the fast edit loop;
- `contract`: protocol, codec, parser, readiness, metadata and host-boundary
  contract tests;
- `integration`: multi-module dry-run service, backend, replay and
  planner-to-scheduler bridge checks, still hardware-free;
- `architecture`: AST/import guardrails, component boundary checks and patch
  artifact consistency.

Every simulator test file must resolve to exactly one of these marker groups.
The architecture guardrail suite fails when a new `test_*.py` file is not added
to the marker assignment table.

## Common Commands

Fast edit loop:

```bash
.venv/bin/python -m pytest -m unit
```

Focused file while preserving the marker contract:

```bash
.venv/bin/python -m pytest -m unit tests/simulator/test_dry_run_scheduler.py
```

Protocol and host-boundary checks:

```bash
.venv/bin/python -m pytest -m contract
```

Dry-run integration and replay checks:

```bash
.venv/bin/python -m pytest -m integration
```

Architecture guardrails:

```bash
.venv/bin/python -m pytest -m architecture
```

Full software suite:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

The full suite remains required before merging PRs that touch shared contracts,
simulator execution, Klipper adapter boundaries or architecture guardrails.
