<p align="center">
  <a href="https://github.com/FAST-OFM">
    <img src="https://github.com/FAST-OFM.png?size=200" alt="Fast OFM logo" width="132">
  </a>
</p>

<h1 align="center">Fast OFM Controller</h1>

<p align="center">
  <strong>MKS/Klipper motion, Arduino illumination and scanner-control research</strong>
</p>

<p align="center">
  <a href="https://github.com/FAST-OFM/fast-ofm">Project index</a> ·
  <a href="https://github.com/FAST-OFM/openflexure-wsi">WSI integration</a> ·
  <a href="https://github.com/FAST-OFM/controller">Controller</a> ·
  <a href="https://github.com/FAST-OFM/hardware">Hardware</a>
</p>

<p align="center">
  <sub>Research prototype · Hardware synchronization work remains experimental</sub>
</p>

Controller firmware, configuration and scanner-control models for Alexander
Fridman's Fast OFM research prototype.

This repository deliberately separates two generations:

- `prototype-verified`: the stop-and-shoot MKS Robin Mini V2.0 / Klipper
  motion and illumination-gate setup plus the deployed Arduino-compatible
  brightness controller;
- `experimental-disabled`: scanner-sync, trigger scheduling and continuous
  motion research that was not enabled in the accepted prototype scan.

The exact evidence boundary, source origins and license treatment are recorded
in [STATUS.md](STATUS.md), [UPSTREAM.md](UPSTREAM.md) and
[MODIFICATIONS.md](MODIFICATIONS.md). This is research equipment, not a
clinically validated or production-safe controller.

Original Fast OFM software and firmware in this repository are source-available
for noncommercial use. Klipper-derived patch/source areas remain GPL-3.0-only.
See [LICENSING.md](LICENSING.md) for the exact file-level boundary.

## Development Environment

Use a project-local Python environment for simulator and protocol tests. The
Python support code requires Python `>=3.11`.

Recommended setup with `uv`:

```bash
uv venv --python 3.11
uv pip install -e '.[dev]'
```

Run simulator tests:

```bash
.venv/bin/python -m pytest
```

Arduino build artifacts and local virtual environments are ignored by git.

## Future controller research

Do not write a full motion planner from scratch. First evaluate:

- Klipper-based extension;
- grblHAL plugin/extension;
- external RP2040 sync-board fallback.

## Required scanner-specific modules

- Board profiles.
- Homing support.
- Position-indexed trigger scheduler.
- LED strobe scheduler.
- Frame ID and metadata events.
- Scheduled Z correction.
- Future encoder coordinate source.

## Directory structure

```text
arduino/        Arduino-compatible auxiliary firmware
boards/          Board profiles and pin maps
docs/            Organized firmware documentation
docs/foundation/ Architecture, safety and project guardrails
docs/scheduling/ Timing, trigger, LED, Z and scan-mode models
docs/evidence/   Curated accepted-prototype checkpoint
examples/        Sanitized, machine-specific configuration examples
src/             Scanner-specific modules or prototypes
tests/           Simulation and hardware-in-loop tests
```

## Experimental scanner-sync status

The future synchronized-scanning firmware architecture has not been selected.
The accepted prototype uses Klipper for bounded stop-and-shoot motion. The
experimental modules and scheduling documents are retained for review but are
disabled by default.

Start with `docs/README.md` before adding or moving documentation. New docs
must have an explicit home and safety status; do not leave new files loose in
the top-level `docs/` directory.

Controller discovery, board-porting notes, electrical evidence and homing
hardware feasibility live in `scanner-hardware`, not this repository.

## Reproducibility

The small pure-Python `scanner_core` dependency is vendored under
`src/scanner_core` from the immutable source recorded in `UPSTREAM.md`. This
removes the former private SSH installation dependency and allows offline
tests from a clean checkout.
