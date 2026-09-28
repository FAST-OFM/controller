# Documentation Standards

These standards keep scanner-firmware documentation reviewable after the move
into topic subdirectories. Prefer concise docs, but preserve engineering context:
status, scope, constraints, rationale, evidence, and safety boundaries should not
be summarized away.

## Placement

- Put every new document in the correct subdirectory:
  - `foundation/` for architecture, safety, state machines, tests, and
    design-control gates.
  - `hardware/` for board discovery, board-porting, wiring, feasibility, and
    hardware-specific review.
  - `scheduling/` for trigger scheduling, scan modes, timing, frame events,
    LED behavior, Z behavior, and homing experiments.
  - `klipper/` for active Klipper plans, contracts, readiness gates, and review
    checklists.
  - `alternatives/` for options under evaluation or fallback approaches.
  - `evidence/` for captured observations, command output summaries, reports,
    validation records, and completed attempts.
  - `patches/` for patch artifacts referenced by docs.
- Do not add new root-level docs except root documentation infrastructure such
  as this file and `README.md`.
- If a document spans categories, choose the directory that owns the decision
  and link to supporting docs in other directories.

## Status And Authority

- Start each non-index document with an explicit status when it affects design,
  safety, hardware, firmware, or execution readiness.
- Active docs describe the current intended design, plan, contract, or gate.
- Evidence docs record what happened or what was observed. They do not approve
  future work unless an active doc references them and states the decision.
- Archive material, if introduced, is historical. Do not treat it as current
  authority unless an active doc explicitly re-promotes it.
- No hidden chat memory is a source of truth. If a decision, command, result,
  assumption, or safety boundary matters, write it in the repo.

## Required Engineering Context

Preserve the context needed for a future reviewer to understand the decision:

- what problem or boundary the doc covers;
- what is in scope and out of scope;
- current knowns, unknowns, and assumptions;
- commands, artifacts, or evidence that support the claim;
- decision rules, rejection criteria, and stop conditions where applicable;
- links to related active docs, evidence, or patch artifacts.

Avoid replacing specific constraints with broad summaries. For example, keep
phase names, safety gates, command formats, board assumptions, and validation
limits visible when they are part of the engineering decision.

## Hardware Safety

Any doc that describes steps which can affect hardware must include an explicit
safety status before those steps:

- `software-only`: cannot affect live hardware, motion, outputs, or firmware on
  a live controller.
- `read-only live`: observes a live system without changing configuration,
  firmware, motion state, outputs, or electrical state.
- `metadata-only live`: changes software state or metadata but must not enable
  motion, camera/LED outputs, or electrical trigger outputs.
- `hardware-affecting`: may change firmware, motion, homing, outputs, wiring,
  electrical state, or controller behavior.
- `not approved for execution`: written for review only.

Hardware-affecting docs must also include preconditions, stop conditions,
rollback or recovery expectations, and the human review gate required before
execution.

## Evidence Hygiene

- Keep evidence factual: date, environment, command or artifact, observed result,
  validation limits, and hardware boundary.
- Do not edit evidence to make it look like a plan. Create or update an active
  doc for the plan, then link to the evidence.
- Do not delete failed attempts or blockers when they explain the current
  boundary. Record the result and the next safe action instead.
- Patch files should be referenced from an evidence or active doc that explains
  their purpose and validation state.

## Maintenance

- Update links when moving docs between subdirectories.
- Prefer relative links within `docs/`.
- Keep filenames lowercase with hyphens except root infrastructure files that
  already use uppercase names.
- When changing an active decision, update the owning active doc and add or link
  evidence. Do not leave the decision only in a pull request, issue, or chat.
