# Architecture Guardrails

Status: executable software guardrails. This document does not approve live
firmware flashing, GPIO toggling, motion, camera triggering or LED driving.

## Code Boundary

Python modules under `src/` are simulator, parser, codec, readiness and
host-boundary models. They must not directly import live hardware, network or
process-control libraries such as:

- `serial`;
- `socket`;
- `subprocess`;
- `requests` / `urllib`;
- Raspberry Pi GPIO libraries;
- SPI/I2C hardware libraries.

The executable check is `tests/simulator/test_architecture_guardrails.py`.
Component boundary checks for the software-only component layer are in
`tests/simulator/test_component_architecture_boundaries.py`.
The repo-boundary leakage guardrail is
`scripts/check_firmware_repo_boundary.py`, covered by
`tests/simulator/test_firmware_repo_boundary_guardrail.py`; it rejects
scanner-pi and camera SDK imports, Pi-owned runtime path names, re-export-only
facades and undocumented or classless `model.py` surfaces.
Run it directly with:

```bash
.venv/bin/python -m pytest -m architecture
.venv/bin/python -m pytest tests/simulator/test_component_architecture_boundaries.py
.venv/bin/python scripts/check_firmware_repo_boundary.py
```

## Interfaces

Hardware-facing APIs must sit behind explicit interfaces or injected handlers.
The current guardrail checks:

- `KlipperCommand` is a `Protocol`;
- `KlipperMcu` is a `Protocol`;
- decoded protocol output uses a `ProtocolRecordSink` interface.
- scanner-sync sample providers use a `PositionSampleSource` interface.
- scanner-sync execution backends use a `ScanExecutionBackend` interface.

Dry-run backends may produce synthetic callback captures for replay validation.
Those captures are simulator artifacts only; they do not prove live firmware
behavior.

Dry-run fakes may expose inert methods that raise if called. Production code
must not call `.send()`, `.send_wait_ack()` or `.raw_send()` from simulator
modules.

Code organization, interface, configuration, documentation and multi-agent
rules are defined in `code-architecture-standards.md`. Treat that document as
the review checklist for new component boundaries.

## Worker Boundary

Workers and child agents must stay inside their assigned software-only scope.
They must not open, approve, merge, force-push or direct-push pull requests
unless the lead agent explicitly delegates that operation for one named PR.

## Review Rule

Adding a live dependency is not a small refactor. It requires a reviewed plan
that states:

- why a simulator/parser boundary is insufficient;
- what hardware can be affected;
- how it is disabled by default;
- rollback and stop conditions;
- tests that prove existing offline paths remain inert.
