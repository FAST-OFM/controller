# Scanner Firmware Documentation

This directory contains the reusable scanner-controller design, safety and
scheduling documents selected for the clean Fast OFM release. Private process
journals, raw machine snapshots and historical spike transcripts are not part
of this tree.

## Start Here

- [evidence/prototype-checkpoint-2026-09-09.md](evidence/prototype-checkpoint-2026-09-09.md)
  ties the observed live MKS and Arduino state to
  `v0.1.0-prototype.1` without authorizing a flash.
- [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md) defines placement,
  status, evidence, and safety rules for all docs.
- [foundation/custom-firmware-control-document.md](foundation/custom-firmware-control-document.md)
  is the design-control gate for custom firmware direction.
- [foundation/safety-and-homing-guardrails.md](foundation/safety-and-homing-guardrails.md)
  captures boot, homing, and scan preconditions.
- [foundation/architecture-guardrails.md](foundation/architecture-guardrails.md)
  captures software boundaries that do not by themselves approve live hardware
  work.
- [scheduling/position-event-scheduler-spec.md](scheduling/position-event-scheduler-spec.md)
  is the main scheduler specification.
- [`../examples/klipper/README.md`](../examples/klipper/README.md) explains the
  sanitized accepted-prototype configuration example.

## Directory Map

- `foundation/`: active architecture, safety, state-machine, test, and control
  documents.
- `hardware/`: board discovery, board-porting, and hardware feasibility docs.
- `scheduling/`: trigger, frame-event, LED, Z, scan-mode, and homing scheduling
  behavior.
- `evidence/`: the curated accepted-prototype checkpoint.

Historical experimental transcripts and machine-specific raw snapshots are
intentionally excluded. Experimental source remains clearly marked and
disabled by default.

## Working Rules

- Add new docs to the right subdirectory. Do not put new design, evidence, or
  hardware notes at the root of `docs/`.
- Keep active docs distinct from evidence and archive material. Active docs say
  what is intended or approved; evidence says what was observed; archive content
  is historical unless an active doc promotes it.
- Do not rely on hidden chat history as source of truth. Durable decisions,
  assumptions, safety boundaries, commands, and results belong in repository
  docs.
- Any step that can affect hardware, firmware on a live controller, motion,
  homing, camera/LED outputs, or electrical state must state its safety status
  explicitly before the step is executable.
