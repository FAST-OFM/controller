# Klipper Scanner-Sync Phase 2 Metadata-Only Patch Report

Status: disposable patch sketch and no-hardware validation. This report does
not approve installing the patch on the live Pi, restarting Klipper, flashing
firmware, sending scanner-sync commands to the live MCU, moving motors,
toggling GPIO, triggering the camera or driving LEDs.

Legacy private tracking reference omitted from the clean release snapshot.

## Source Checkout

The patch sketch was prepared outside the live Raspberry Pi checkout.

- upstream repository: `https://github.com/Klipper3d/klipper.git`
- disposable path: `/tmp/fast-ofm-klipper`
- base commit: `c707dd19214709dc23684b254a68e3bf69e4cfb3`
- disposable branch: `scanner-sync-phase2-metadata-only`
- patch artifact:
  `docs/patches/klipper-scanner-sync-phase2-metadata-only.patch`

The base commit matches the Klipper commit observed on the Pi during read-only
Stage B evidence capture.

## Patch Contents

The disposable patch adds these files to Klipper:

- `klippy/extras/scanner_sync.py`
- `src/scanner_sync.c`
- `test/klippy/scanner_sync.cfg`
- `test/klippy/scanner_sync.test`

It also updates:

- `src/Makefile`

## Metadata-Only Behavior

The host extra:

- parses `[scanner_sync]`;
- keeps `enable` defaulting to `false`;
- supports only `protocol_version: 1`;
- requires `mode: metadata_only`;
- rejects `hardware_outputs_enabled: true`;
- allocates one scanner-sync MCU object id when explicitly enabled;
- registers scanner-sync command and response formats;
- preserves decoded scanner-sync callbacks in a durable `callback_events` status
  list with JSONL wrapper shape `{"event_type": ..., "params": {...}}`;
- keeps `last_event` as the latest wrapped callback event.

The MCU sketch:

- adds scanner-sync command and response formats to the MCU dictionary;
- rejects hardware-output operation through `hardware_outputs_enabled=0`;
- emits a metadata-only `FRAME_EVENT` from `scanner_sync_start`;
- emits a `SCHEDULER_TERMINAL` from `scanner_sync_stop`;
- emits `Z_SCHEDULED`, `Z_APPLIED` or `Z_REJECTED` responses from
  `scanner_sync_schedule_z` without moving Z.

The patch does not:

- schedule scanner timing from real motion;
- toggle GPIO;
- trigger a camera;
- drive LEDs;
- command motors;
- apply Z motion;
- configure output pins;
- use Linux wall-clock time for frame identity.

## Contract Differences From Phase 1

- Removes `scanner_sync_debug_emit`.
- Adds `mode: metadata_only` and `hardware_outputs_enabled: false` to the
  smoke-test config.
- Extends `config_scanner_sync` with `hardware_outputs_enabled=%c`.
- Uses the full `SCHEDULER_TERMINAL` response shape with `stripe_id`,
  `last_frame_id` and `next_stripe_frame_index`.
- Preserves callback events as `event_type` plus `params` wrapper records
  instead of overwriting only a flat `last_event` params dict.
- Produces metadata through the scanner-sync command path rather than a debug
  dictionary helper.

## Validation Performed

All validation was local to the disposable Klipper checkout.

Commands run:

```text
python3 -m py_compile klippy/extras/scanner_sync.py
python3 scripts/check_whitespace.py src/scanner_sync.c klippy/extras/scanner_sync.py src/Makefile test/klippy/scanner_sync.cfg test/klippy/scanner_sync.test
git diff --check
cp test/configs/hostsimulator.config .config
make olddefconfig
make -j2
mkdir -p /tmp/klipper-scanner-sync-phase2-dicts /tmp/klipper-scanner-sync-phase2-test
cp out/klipper.dict /tmp/klipper-scanner-sync-phase2-dicts/scanner_sync_hostsimulator.dict
.venv/bin/python scripts/test_klippy.py -d /tmp/klipper-scanner-sync-phase2-dicts -t /tmp/klipper-scanner-sync-phase2-test test/klippy/scanner_sync.test
```

Disposable venv dependencies installed for the smoke test:

```text
greenlet
cffi
pyserial
jinja2
```

Results:

- Python syntax check passed.
- Whitespace check passed after line wrapping.
- `git diff --check` passed.
- Host simulator build passed.
- `out/src/scanner_sync.o` was compiled.
- `out/klipper.elf` linked.
- Klippy smoke test passed: `All 1 test cases passed`.
- The generated dictionary contains:
  - `config_scanner_sync`;
  - `scanner_sync_start`;
  - `scanner_sync_stop`;
  - `scanner_sync_schedule_z`;
  - `scanner_sync_frame_event`;
  - `scanner_sync_scheduler_terminal`;
  - `scanner_sync_z_scheduled`;
  - `scanner_sync_z_applied`;
  - `scanner_sync_z_rejected`.
- The generated dictionary does not contain `scanner_sync_debug_emit`.

## MKS Target Build Evidence

After read-only capture of the Pi `.config`, the same disposable patch was
built locally for the current MKS target. This did not use the live Pi checkout
and did not flash firmware.

Captured target configuration:

```text
CONFIG_MACH_STM32=y
CONFIG_MCU="stm32f103xe"
CONFIG_CLOCK_FREQ=72000000
CONFIG_FLASH_APPLICATION_ADDRESS=0x8007000
CONFIG_STM32_SERIAL_USART3=y
CONFIG_SERIAL_BAUD=250000
```

Local user-space toolchain setup:

```text
apt-get download gcc-arm-none-eabi binutils-arm-none-eabi libnewlib-arm-none-eabi libnewlib-dev
dpkg-deb -x ... /tmp/scanner-arm-none-eabi/root
PATH=/tmp/scanner-arm-none-eabi/root/usr/bin:$PATH
CPATH=/tmp/scanner-arm-none-eabi/root/usr/include/newlib
```

Build commands:

```text
cp /tmp/pi5-klipper-mks.config .config
PATH=/tmp/scanner-arm-none-eabi/root/usr/bin:$PATH CPATH=/tmp/scanner-arm-none-eabi/root/usr/include/newlib make olddefconfig
PATH=/tmp/scanner-arm-none-eabi/root/usr/bin:$PATH CPATH=/tmp/scanner-arm-none-eabi/root/usr/include/newlib make clean
PATH=/tmp/scanner-arm-none-eabi/root/usr/bin:$PATH CPATH=/tmp/scanner-arm-none-eabi/root/usr/include/newlib make -j2
```

The local `.deb` extraction required a local symlink so the unpacked toolchain
could find newlib in the same relative layout as a system installation:

```text
/tmp/scanner-arm-none-eabi/root/usr/lib/arm-none-eabi/lib -> newlib
```

Results:

- `out/src/scanner_sync.o` compiled for the STM32 target.
- `out/klipper.elf` linked.
- `out/klipper.bin` was created.
- `arm-none-eabi-size out/klipper.elf`:

```text
   text	   data	    bss	    dec	    hex	filename
  34616	     52	   1028	  35696	   8b70	out/klipper.elf
```

Artifact hashes from the disposable checkout:

```text
63ed48170f0d48f78bd6fa845bd2917299b4022fce740be9c09b46e9d2f51ea7  out/klipper.bin
b46207fd5c7ba2a9b3bedd7311cc0d1b1e7bad804692da98acbf8ba47f6ab326  out/klipper.elf
229874707976e49349d6d0b15dbe153b36c28c099c9d70c75b43412b30576c0c  out/klipper.dict
```

The target `out/klipper.dict` contains all scanner-sync command and response
formats listed above and does not contain `scanner_sync_debug_emit`.

The passive readiness checker was also run against the target
`out/klipper.dict` and the disposable metadata-only scanner-sync config:

```text
.venv/bin/python -m klipper_adapter.cli /tmp/fast-ofm-klipper/out/klipper.dict --config-file /tmp/fast-ofm-klipper/test/klippy/scanner_sync.cfg --host-extra-present --mcu-connected --response-dispatch-available --require-ready
```

Result:

```json
{"blockers": [], "can_enable_scanner_sync": true, "config_source": "file", "has_all_required_commands": true, "has_all_required_responses": true, "missing_command_formats": [], "missing_response_formats": [], "stage": "ready_to_enable", "status": "ready"}
```

This readiness result applies only to the disposable target build artifacts. It
does not mean the live Pi or live MKS controller is ready, because the patch has
not been installed on the live Pi, Klipper has not been restarted, and firmware
has not been flashed.

## Artifact Maintenance Validation

After updating the metadata-only artifact contract to preserve callback events
as JSONL wrapper-shaped records, this scanner-firmware consistency test was
run locally:

```text
.venv/bin/python -m unittest tests.simulator.test_klipper_patch_artifact_consistency.KlipperPatchArtifactConsistencyTests.test_phase2_patch_is_metadata_only_and_removes_debug_emit
```

Result:

- passed;
- no hardware or network commands were run.

## Validation Not Performed

These were intentionally not performed:

- no MCU firmware flash;
- no live Pi checkout modification;
- no Klipper service restart on the Pi;
- no scanner-sync command sent to the live MCU;
- no motor motion;
- no GPIO output;
- no camera trigger;
- no LED output.

## Review Notes

This patch remains a sketch. It is suitable for review of names, formats,
metadata-only gating and no-output behavior. It is not a final scanner timing
implementation because it emits a single metadata frame from `start` rather than
from a reviewed motion/position hook.

Before any live use, issue #85 must still be completed with:

- exact host-extra diff;
- exact MCU patch diff;
- exact MKS firmware build command;
- exact flashing and rollback method;
- reviewed `printer.cfg` diff;
- captured dictionary evidence from the target build;
- expected callback JSONL;
- expected `scanner-klipper-decode-events --summary-json` report.

## Hardware Boundary

Any step beyond this report requires separate reviewed approval before:

- copying the patch to the Pi;
- modifying live `printer.cfg`;
- restarting Klipper;
- flashing firmware;
- sending scanner-sync commands to the live MCU;
- probing output pins;
- toggling GPIO;
- moving any axis;
- triggering the camera;
- driving LEDs.
