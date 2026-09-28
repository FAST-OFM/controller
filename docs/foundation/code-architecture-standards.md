# Code Architecture Standards

Status: software-only architecture guardrail. This document does not approve
live firmware flashing, GPIO toggling, motion, camera triggering, LED driving,
serial control, network control or hardware tests.

## Purpose

Scanner firmware code must stay reviewable as multiple agents work in
parallel. The goal is not more files, more abstractions or smaller functions by
default. The goal is clear ownership, stable interfaces, testable behavior and
explicit hardware boundaries.

## Source Of Truth

- Repository docs, ADRs, issues, tests and handoff files are source of truth.
- Hidden chat memory is not source of truth.
- A design decision that affects architecture, hardware behavior, safety,
  timing, scan semantics, units or interfaces must be written in the repo.
- Unknown hardware values must remain unknown until documented by evidence.

## Code Shape

- Top-level packages under `src/` are not an unstructured namespace. Each
  package must belong to the source-tree hierarchy in
  `docs/foundation/firmware-architecture.md`.
- Do not add a new top-level package unless its layer and ownership boundary
  are documented and covered by the architecture guardrail tests.
- Prefer a dedicated compatibility PR for physical package moves. Keep imports
  stable or provide shims when moving existing modules.
- Keep modules cohesive. One module should own one meaningful concept or
  boundary, not a bag of helpers.
- Do not use `model.py` as the default home for all code in a package. It may
  be a small cohesive value-object module or local contract module, but it must
  not be a compatibility facade that re-exports implementation from focused
  modules such as `types`, `policy`, `validation`, `scheduler`, `planner`,
  `parser`, `codec`, `backend` or `estimation`.
- Do not split code into tiny functions just to reduce line count. Split when
  the extracted function has a clear name, reusable contract, independent test
  value or isolates a policy/validation boundary.
- Do not hide the main algorithm behind a long chain of one-line wrappers.
  A reviewer should be able to read the orchestration path without chasing ten
  files.
- Prefer typed value objects for structured domain data over loose dictionaries.
- Prefer pure functions or immutable dataclasses for math, planning, parsing
  and validation.
- Put hardware, process, network and filesystem effects behind explicit
  adapter boundaries. Simulator/model code must not perform those effects.
- Do not introduce global mutable state for scan state, calibration state,
  frame matching or controller state.
- Do not hardcode scanner mechanics, LED limits, camera timing, GPIO aliases,
  Z conversion factors or safety limits inside algorithms. These come from
  validated config/domain objects.

## Interfaces

- Interfaces define ownership boundaries, not decoration.
- A component interface should state:
  - input value objects;
  - output value objects;
  - units;
  - timing/position semantics;
  - rejected states;
  - whether the boundary is software-only or hardware-affecting.
- Public planner and autofocus boundaries use physical units where practical
  (`um`, `us`, frame id, position count). Controller-specific steps/pins belong
  in adapters or validated board profiles.
- MCU `FRAME_EVENT` metadata is the source of frame identity, coordinates, LED
  pattern metadata and Z state. Linux camera arrival time is diagnostic only.
- Focus metric interfaces must accept RAW Bayer or explicitly linear image
  data. JPEG, preview and nonlinear frames are invalid focus inputs.
- Scan geometry must distinguish stripe movement bounds from event positions.
  `start_position` is not automatically the first acquisition event.
- Predictive Z commands must target a future frame or future position. Do not
  implement autofocus correction as immediate current-frame `move_z_now`.

## Configuration

- Configuration is layered by domain:
  - platform/board profile;
  - controller/printer config;
  - motion/kinematics/homing config;
  - IO aliases and inactive output states;
  - camera mode, crop and timing config;
  - illumination config;
  - scan recipe and scan mode config;
  - readiness/self-check state.
- Parsing files and validating domain objects are separate concerns.
- Algorithms consume validated value objects, not raw YAML/JSON text.
- Camera crop/binning is camera-mode configuration. It may reduce processed
  image area, but it does not make the camera a timing source.
- Hardware-output arming is a separate explicit state. A valid config does not
  automatically authorize output toggling.

## Documentation

- Add or update the owning doc when changing a contract, module boundary,
  safety gate, unit convention, config domain or workflow.
- Cross-cutting development starts with an owning foundation contract. Naming,
  state machines, event semantics, math conventions and interface boundaries
  belong in `firmware-contracts.md` or a linked foundation document before
  isolated component work begins.
- Do not create a new doc when an existing owning doc is the right place.
- Do not scatter one decision across many partial docs. Put the decision in one
  canonical doc and link supporting evidence or implementation notes.
- Evidence docs record observations. Active foundation/scheduling/klipper docs
  state the current rule or design.
- Keep docs concise, but preserve engineering context: status, scope,
  assumptions, known unknowns, safety boundary, validation and next action.

## Tests

- Every new component needs focused simulator tests for accepted behavior and
  rejection behavior.
- Classify expensive or broad tests with pytest markers so normal local runs do
  not become noisy.
- Architecture guardrails should catch accidental imports of hardware,
  network, subprocess or live-controller APIs from simulator/model modules.
- Tests must not require connected hardware unless they are explicitly placed
  behind a reviewed hardware-affecting gate.

## Multi-Agent Work

- Agents may work in parallel only on disjoint ownership scopes.
- A worker may spawn child agents only when the child task is bounded,
  software-only and has the same safety constraints.
- Default child-agent limit per worker is two unless the lead agent assigns a
  larger limit for a specific scope.
- Child agents must inherit these foundation contracts. They may split their
  task further only when each child owns a narrow module, math proof,
  interface review or test gap and reports back through the parent.
- Agents may install local project dependencies and prepare local repos needed
  for their assigned software-only task, but must not configure live hardware,
  create secrets, flash firmware or enable hardware-running workflows.
- A worker must report changed files, tests run and any unverified assumptions.
- Workers must not revert or overwrite changes outside their assigned scope.
- Cross-cutting interface changes are owned by the lead agent or an explicitly
  assigned architecture worker.
- The lead agent must close completed child agents after their result is
  accepted, integrated, superseded or rejected. Completed agents must not be
  left open to occupy concurrency slots.

## Agent Roles

Use these roles when splitting parallel firmware work. A role is an ownership
scope, not permission to touch hardware:

- Lead integrator: owns final scope selection, conflict resolution, tests,
  commits, PR creation and merge decision.
- Firmware architect: owns naming, package hierarchy, state-machine,
  event-contract and interface boundaries.
- Math architect: owns geometry, units, calibration transforms, focus metrics,
  predictive Z constraints and deterministic numerical behavior.
- Protocol architect: owns host/controller event and command semantics,
  versioning, frame identity and rejection records.
- Component developer: implements one bounded package against the accepted
  contracts and simulator tests.
- Test and simulation engineer: owns offline tests, fixtures, fakes, markers
  and non-hardware validation.
- Documentation steward: keeps the owning foundation docs concise, canonical
  and linked to implementation evidence.

Do not launch broad "clean up everything" agents. Give each worker one package,
one contract or one measurable test gap.

## Merge Protocol

- Workers and child agents do not open, approve, merge, force-push or
  direct-push pull requests unless the lead agent explicitly delegates that
  operation for one named PR.
- Workers return patches, changed-file lists, validation output and assumptions
  to the lead agent.
- The lead agent owns final integration: review, conflict resolution, test
  selection, commit message, PR creation and merge decision.
- A worker branch is not source of truth until the lead agent integrates it and
  the repo tests/docs pass the agreed gates.
- Cross-repository changes need one lead-owned integration plan that states
  affected repos, branch names, dependency order and rollback/stop conditions.
- Hardware-affecting changes must not be merged behind a software-only PR.
  They require their own reviewed hardware gate.

## Review Checklist

Before merging a component change, verify:

- the module has one clear owner and boundary;
- units are explicit;
- config values are injected, not hardcoded;
- hardware effects are absent or isolated behind an adapter;
- simulator tests cover acceptance and rejection paths;
- docs were updated in the owning foundation/scheduling/klipper area;
- unknown hardware values were not guessed.
