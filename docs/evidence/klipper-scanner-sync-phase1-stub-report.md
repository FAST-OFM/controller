# Klipper Scanner-Sync Phase 1 Stub Report

Status: disposable patch sketch and no-hardware validation. This report does
not approve installing the patch on the live Pi, restarting Klipper, flashing
firmware, moving motors, toggling GPIO, triggering the camera or powering LEDs.

## Source Checkout

The patch sketch was prepared outside the live Raspberry Pi checkout.

- upstream repository: `https://github.com/Klipper3d/klipper.git`
- disposable path: `/tmp/fast-ofm-klipper`
- base commit: `c707dd19214709dc23684b254a68e3bf69e4cfb3`
- disposable branch: `scanner-sync-phase1-stub`
- patch artifact:
  `docs/patches/klipper-scanner-sync-phase1-stub.patch`

The base commit matches the Klipper commit observed on the Pi during read-only
inspection.

## Patch Contents

The disposable patch adds these files to Klipper:

- `klippy/extras/scanner_sync.py`
- `src/scanner_sync.c`
- `test/klippy/scanner_sync.cfg`
- `test/klippy/scanner_sync.test`

It also updates:

- `src/Makefile`

## Host Extra Sketch

`klippy/extras/scanner_sync.py` is a minimal Klipper host extra. It is disabled
unless `[scanner_sync] enable: true` is configured.

When enabled, it:

- allocates one scanner-sync MCU object id;
- allocates a command queue;
- emits `config_scanner_sync`;
- looks up `scanner_sync_start`;
- looks up `scanner_sync_stop`;
- looks up `scanner_sync_schedule_z`;
- registers serial responses for:
  - `scanner_sync_frame_event`;
  - `scanner_sync_scheduler_terminal`;
  - `scanner_sync_z_scheduled`;
  - `scanner_sync_z_applied`;
  - `scanner_sync_z_rejected`;
- exposes a minimal status object with the last decoded event.

It does not:

- schedule scanner timing;
- command motion;
- toggle GPIO;
- trigger the camera;
- drive LEDs;
- apply Z motion;
- send commands automatically.

## MCU Stub Sketch

`src/scanner_sync.c` adds command and response naming to the Klipper MCU
dictionary.

Commands:

- `config_scanner_sync oid=%c protocol_version=%c`
- `scanner_sync_start oid=%c next_frame_id=%u`
- `scanner_sync_stop oid=%c reason=%c`
- `scanner_sync_schedule_z oid=%c seq=%u stripe_id=%u target_kind=%c target_value=%i z_target_nm=%i`
- `scanner_sync_debug_emit oid=%c event=%c`

Responses:

- `scanner_sync_frame_event oid=%c frame_id=%u stripe_id=%u stripe_frame_index=%u pattern_id=%u position_axis=%c event_position=%i x_count=%i y_count=%i z_count=%i mcu_time_us=%u status=%c flags=%u`
- `scanner_sync_scheduler_terminal oid=%c stripe_id=%u status=%c reason=%c emitted_frame_count=%u expected_frame_count=%u last_frame_id=%i next_frame_id=%u next_stripe_frame_index=%u mcu_time_us=%u`
- `scanner_sync_z_scheduled oid=%c seq=%u stripe_id=%u status=%c`
- `scanner_sync_z_applied oid=%c seq=%u frame_id=%u z_cmd_count=%i status=%c`
- `scanner_sync_z_rejected oid=%c seq=%u reason=%c status=%c`

The `scanner_sync_debug_emit` command exists only to keep response formats in
the Klipper protocol dictionary during this Phase 1 stub. It must not be treated
as a scanner timing implementation.

## Validation Performed

All validation was local to the disposable Klipper checkout.

Commands run:

```text
python3 -m py_compile klippy/extras/scanner_sync.py
python3 scripts/check_whitespace.py src/scanner_sync.c klippy/extras/scanner_sync.py src/Makefile
git diff --check
cp test/configs/hostsimulator.config .config
make olddefconfig
make -j2
python3 scripts/test_klippy.py -d /tmp/klipper-scanner-sync-dicts -t /tmp/klipper-scanner-sync-test test/klippy/scanner_sync.test
```

Results:

- Python syntax check passed.
- Whitespace check passed.
- `git diff --check` passed.
- Host simulator build passed.
- `out/src/scanner_sync.o` was compiled.
- `out/klipper.elf` linked.
- Klippy smoke test passed: `All 1 test cases passed`.

The generated `out/klipper.dict` contained all scanner-sync command and
response names listed above.

## Validation Not Performed

These were intentionally not performed:

- no build for the MKS Robin Mini V2.0 STM32F103 target;
- no MCU firmware flash;
- no motor motion;
- no GPIO output;
- no camera trigger;
- no LED output.

Full Klipper test dependency installation was not required for this smoke test.
Runtime Klippy dependencies were installed only in the disposable venv used for
the local smoke test.

After this report was first written, a separate live Stage A check installed
only the host extra on the Pi with `[scanner_sync] enable: false` and restarted
Klipper after MKS USB serial recovery. That later check is recorded in
`docs/evidence/klipper-live-metadata-stage-a-attempt.md`. It did not flash firmware,
enable scanner-sync, send commands or use hardware outputs.

## Findings

The Phase 1 stub proves:

- the host extra can be loaded by Klippy with `[scanner_sync] enable: true`;
- the command and response names can be represented in Klipper's MCU protocol
  dictionary;
- the MCU object stub compiles in host simulator mode;
- the host extra can register the scanner-sync response formats against that
  dictionary.

The Phase 1 stub does not prove:

- position-indexed frame timing;
- trigger jitter;
- camera trigger behavior;
- LED strobe behavior;
- Z correction execution;
- homing integration;
- safe stop behavior with real outputs;
- maintainability of a deeper stepper/motion hook.

## Recommended Next Non-Hardware Step

The disabled host-extra Stage A has passed. Before any firmware flash or
`enable: true` test, review the patch artifact and decide whether Phase 2B
should remain metadata-only on Klipper or whether the RP2040 sync-board
fallback should become the primary timing proof.

If Klipper continues, the next non-hardware patch should replace the
`scanner_sync_debug_emit` dictionary helper with a real metadata-only event
source that is still independent of GPIO and motion. The position-coupled
trigger hook must remain blocked until the hook point, data ownership and stop
behavior are reviewed.

## Hardware Boundary

Any step beyond this report requires a separate reviewed bench-safe plan before:

- copying the patch to the Pi;
- modifying live `printer.cfg`;
- restarting Klipper;
- flashing firmware;
- sending scanner-sync commands to the live MCU;
- connecting oscilloscope probes to active output pins for timing;
- toggling GPIO;
- moving any axis;
- triggering the camera;
- driving LEDs.
