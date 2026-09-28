# Klipper Live Metadata Stage B Plan

Status: planning gate only. Stage B is not approved for live execution.

## Goal

Stage B should prove live scanner-sync metadata transport without hardware
outputs:

- `FRAME_EVENT` records are emitted by MCU-side scanner-sync code;
- Z scheduler acknowledgements are emitted as `Z_SCHEDULED`, `Z_APPLIED` or
  `Z_REJECTED`;
- `SCHEDULER_TERMINAL` is emitted only when host stop or fault prevents the
  remaining planned `FRAME_EVENT` records; clean completion emits no terminal
  record;
- all records report `hardware_outputs_enabled=false`;
- no GPIO, motor, camera or LED output is commanded.

## Required Inputs Before Execution

Do not run Stage B until a reviewed issue or PR contains:

- completed `docs/klipper/klipper-live-metadata-stage-b-review-checklist.md`;
- exact Klipper commit;
- exact host-extra diff;
- exact MCU patch diff;
- exact MKS firmware build command;
- exact MKS flashing method and rollback method;
- full `printer.cfg` scanner-sync diff;
- proof that scanner-sync defaults to `enable: false`;
- confirmation that no output pins are configured for scanner-sync;
- expected serial log and event records;
- expected `scanner-klipper-decode-events --summary-json` acceptance report;
- stop conditions.

## Live State From Stage A

Current retained Stage A state:

- MKS USB serial path exists;
- Klipper connects to the MKS MCU;
- `~/klipper/klippy/extras/scanner_sync.py` is installed;
- `printer.cfg` contains `[scanner_sync] enable: false`;
- live MKS firmware lacks scanner-sync MCU commands.

This state is safe-disabled. It is not ready to enable scanner-sync.
Safe-disabled means the disabled preflight may remain installed and configured
with `enable: false` while it commands no outputs. It does not require MCU
scanner-sync command formats, response formats or response dispatch to be
present.

Current read-only evidence for the retained live state is recorded in
`docs/evidence/klipper-live-metadata-stage-b-current-evidence.md`.

## Disabled Preflight Vs Enabled Readiness

The reviewed disabled preflight config must keep:

```ini
[scanner_sync]
enable: false
protocol_version: 1
mode: metadata_only
hardware_outputs_enabled: false
```

Pins must remain unset or `none` in Stage B. Candidate camera and LED pins from
board discovery are not approval to drive outputs.

Any future `enable: true` metadata-only readiness test requires a separate
reviewed step after firmware patch and flash evidence are accepted. Enabled
readiness requires all of the following evidence in the reviewed issue or PR:

- explicit reviewed `[scanner_sync]` config with `enable: true`,
  `mode: metadata_only` and `hardware_outputs_enabled: false`;
- reviewed MCU dictionary containing the required scanner-sync command and
  response formats;
- reviewed host response dispatch for every expected scanner-sync response;
- confirmation that scanner-sync output pins remain unset or `none`.

Without all of that evidence, the system may only be considered safe-disabled,
not ready for enabled metadata-only scanner-sync.

## Expected Event Contract

The metadata stream must use these project event names:

- `FRAME_EVENT`
- `SCHEDULER_TERMINAL`
- `Z_SCHEDULED`
- `Z_APPLIED`
- `Z_REJECTED`

`FRAME_EVENT` must carry frame identity and coordinates from MCU metadata. The
Pi must not infer frame identity or coordinates from Linux wall-clock time or
camera arrival time.

Z corrections must be future-scheduled by frame or position. Stage B must not
implement autofocus as an immediate scan-time `move_z_now`.

## Stop Conditions

Stop and roll back if any of the following occur:

- Klipper cannot reconnect to the MKS MCU;
- the scanner-sync host extra cannot parse config;
- expected scanner-sync MCU command formats are missing after a supposed
  firmware patch;
- any output pin is configured unexpectedly;
- any motor, camera trigger or LED output would be commanded;
- event records omit frame identity, coordinates or `hardware_outputs_enabled`;
- firmware flash or boot verification is ambiguous.

## Rollback Requirements

The reviewed plan must include commands to:

- restore the previous Klipper checkout;
- restore the previous `printer.cfg`;
- restart Klipper;
- verify MKS serial reconnection;
- verify scanner-sync is disabled or absent.
