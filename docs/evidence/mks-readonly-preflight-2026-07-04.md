# MKS Scanner-Sync Read-Only Preflight - 2026-07-04

Status: read-only live-state snapshot. This evidence does not approve firmware
flashing, Klipper restarts, GPIO toggling, LED output, XVS pulses, camera
capture, homing or motor motion.

## Scope

Approved read-only actions only:

- connect to Pi5 through private VPN/SSH;
- inspect Klipper, Moonraker, config files, logs, USB serial paths and build
  artifacts;
- compute hashes;
- do not write to the Pi;
- do not send G-code or scanner-sync commands;
- do not open camera capture;
- do not restart Klipper or flash firmware.

## Host And Runtime State

- Host: `pi5`
- SSH peer: `pi@192.0.2.13`
- LAN address reported by host: `192.0.2.30`
- Read date: `2026-07-04`
- Klipper service: `active`
- Moonraker service: `active`
- Moonraker Klippy state: `ready`
- Klipper path: `/home/pi/klipper`
- Klipper config: `/home/pi/printer_data/config/printer.cfg`
- Klipper software version reported by Moonraker:
  `v0.13.0-699-gc707dd192-dirty`
- Klipper git commit: `c707dd19214709dc23684b254a68e3bf69e4cfb3`
- Klipper git status:
  - `M src/Makefile`
  - `?? klippy/extras/scanner_sync.py`
  - `?? src/scanner_sync.c`

## Serial Device State

Current `/dev/serial` enumeration:

- `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 -> ../../ttyUSB1`
- `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0 -> ../../ttyUSB0`
- `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0 -> ../../ttyUSB1`

Active Klipper `[mcu]` serial path:

```text
/dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0
```

The CH340 by-id path remains non-unique and must not be used while both the MKS
controller and Arduino Nano are attached.

## Current Config State

Config hashes:

| Path | SHA256 |
| --- | --- |
| `/home/pi/printer_data/config/printer.cfg` | `b81d18f5fb093d09affba62a65600acc9bb209b136b23eb0f9740d886d12acce` |
| `/home/pi/printer_data/config/moonraker.conf` | `54a0eb6c8f050a01d49c9ca2ebe29c17104e25541dea938e5c75df3bb885d7ea` |
| `/home/pi/printer_data/config/scanner_af_window_test.cfg` | `5a56ad308f015eb78bfc84763f31ecdce5ffc0a2979701bd85c848d61e107d0a` |

The current live config is not the earlier safe-disabled state:

```text
[scanner_sync]
enable: true
protocol_version: 1
white_pin: PB13
red_pin: PA10
green_pin: PA9
xvs_pin: PD6
```

Output pins present in config:

| Logical output | Klipper pin | Startup value | Shutdown value | Notes |
| --- | --- | ---: | ---: | --- |
| `hq_xvs_sync` | `PD6` | `0` | `0` | HQ XVS candidate output |
| `led_green_wifi` | `PA9` | `0` | `0` | PWM, `cycle_time=0.000033333` |
| `led_red_wifi` | `PA10` | `0` | `0` | Digital output |
| `led_white_tc1` | `PB13` | `0` | `0` | Digital output |

Motion state from read-only Moonraker query:

- `toolhead.homed_axes`: empty string
- `stepper_enable.stepper_x`: `false`
- `stepper_enable.stepper_y`: `false`
- `stepper_enable.stepper_z`: `false`
- `toolhead.position`: `[100.0, 100.0, 0.0, 0.0]`

No homing or endstop query was sent during this preflight.

## Current Firmware Artifact On Pi

Build config highlights:

- MCU: `stm32f103xe`
- Clock: `72000000`
- Serial: `USART3`
- Baud: `250000`
- Boot/application offset: `0x8007000`
- Flash artifact: `/home/pi/klipper/out/klipper.bin`

Artifact hashes:

| Path | Size | SHA256 |
| --- | ---: | --- |
| `/home/pi/klipper/out/klipper.bin` | `41168` bytes | `347c4af5b4438ada1ad89ce0dae1418a4fae93faeedd06c7585d16595035ee90` |
| `/home/pi/klipper/out/klipper.dict` | `10993` bytes | `b2bdaf9d8af9aedf1619068e3b8ebd3579b125cce73a14b1aac36577fc07880a` |
| `/home/pi/klipper/.config` | `4059` bytes | `595ea0dee14306a17d8d04e9f6bcdd0e3097b181567a69cdb55a4f2232f45f75` |
| `/home/pi/klipper/klippy/extras/scanner_sync.py` | `4944` bytes | `4f86a2dec1eb54585404b02ec0b7bfd709579955fe9f0adafdf43b0a67afbca9` |
| `/home/pi/klipper/src/scanner_sync.c` | `6711` bytes | `16044e0c4a1a1dbe0f09cc8580389efa7c08bafa22cd029273c5799635e7fc10` |
| `/home/pi/klipper/src/Makefile` | `1399` bytes | `551d54ae94cb317146aa616293b73736adb4b261a1732e7e4353560c2ddf4c0e` |

## Dictionary Capability Observed

The live dictionary contains:

- `config_scanner_sync_outputs`
- `scanner_sync_af_window_test`
- `scanner_sync_af_window_stop`

The live dictionary does not expose the new foundation contract command:

- `scanner_sync_run_timed_output_sequence`

This means the current MKS firmware is a legacy stationary AF-window command
build, not the final timed-output sequence contract build.

## Current Scanner-Sync Object State

Moonraker object query:

```json
{
  "scanner_sync": {
    "enabled": true,
    "status": "configured",
    "last_test": null
  }
}
```

Recent Klippy log lines include prior `scanner_sync AF window test queued on
MCU` and `scanner_sync AF window test stopped` messages. No new scanner-sync
command was sent during this preflight.

## Decision Required Before Hardware Action

There are two possible next paths.

### Option A: Legacy AF-Window No-Motion Test

Use the already-flashed legacy command:

```text
SCANNER_SYNC_AF_WINDOW_TEST
SCANNER_SYNC_AF_WINDOW_STOP
```

This can validate the current MCU-timed white/RG/XVS window generator, but it
does not validate the new foundation `scanner_sync_run_timed_output_sequence`
protocol.

Required explicit approval must name:

- no-motion only;
- output pins `PB13`, `PA10`, `PA9`, `PD6`;
- exact timing parameters;
- exact cycle count;
- end state, preferably `END_WHITE=0` for safe-off;
- all-off/stop observation method;
- stop condition and power-removal path.

### Option B: Rebuild/Flash Timed-Output Sequence Firmware

Bring the Pi/Klipper checkout to the foundation timed-output sequence patch,
rebuild and flash MKS, then validate dictionary support before output tests.

This is the architecture-aligned path, but it requires a separate flash
approval. Before flashing, the flash package must record:

- exact patch/source files;
- new `klipper.bin` hash;
- new `klipper.dict` hash;
- rollback path to the current artifact hash
  `347c4af5b4438ada1ad89ce0dae1418a4fae93faeedd06c7585d16595035ee90`;
- whether flashing is by USB command, SD-card copy, or another verified method.

## Recommended Next Step

Do not run outputs yet. First decide between Option A and Option B.

Recommended engineering path: Option B, because the current live firmware is a
legacy AF-window command and does not prove the final timed-output sequence
protocol that `scanner-pi`, `scanner-experiments` and `scanner-docs` now gate.

If a quick bench sanity check is needed before the rebuild, Option A can be
approved explicitly as a legacy no-motion diagnostic and must not be promoted
as foundation timed-output evidence.

## Timed-Output Build Preparation

Status: build artifact prepared on Pi5 after the read-only preflight. The MKS
controller has not been flashed by this evidence.

The repository patch artifact
`docs/patches/klipper-scanner-sync-timed-output-sequence.patch` was copied to
Pi5 and checked with:

```text
git -C /home/pi/klipper apply --check \
  /home/pi/fast-ofm-preflight-20260704-timed-output-prep/klipper-scanner-sync-timed-output-sequence.patch
```

The dry-run apply failed with:

```text
error: corrupt patch at line 49
```

The live build therefore used an explicit source snapshot rather than forcing
that patch artifact:

| Source snapshot | Pi Klipper target |
| --- | --- |
| `docs/live-mks/timed-output-sequence/klippy/extras/scanner_sync.py` | `/home/pi/klipper/klippy/extras/scanner_sync.py` |
| `docs/live-mks/timed-output-sequence/src/scanner_sync.c` | `/home/pi/klipper/src/scanner_sync.c` |

Pi backup directory:

```text
/home/pi/fast-ofm-preflight-20260704-timed-output-prep
```

Rollback artifact hash:

```text
/home/pi/fast-ofm-preflight-20260704-timed-output-prep/klipper.bin
SHA256 347c4af5b4438ada1ad89ce0dae1418a4fae93faeedd06c7585d16595035ee90
```

Prepared artifact hashes after `make clean && make -j2`:

| Path | Size | SHA256 |
| --- | ---: | --- |
| `/home/pi/klipper/out/klipper.bin` | `42648` bytes | `293fbff017a7ae33383144338f3af939e47018790e357f89415ca76d95ad6706` |
| `/home/pi/klipper/out/klipper.dict` | `11696` bytes | `10b67269bb646bec7db912c7d71f5aeceab95b1c40f85c71236392ad6247242c` |
| `/home/pi/klipper/klippy/extras/scanner_sync.py` | `11156` bytes | `4e35582026fad3d1e9ac3cc6d827a551b3320921fe7c1375e712729e915b656b` |
| `/home/pi/klipper/src/scanner_sync.c` | `17873` bytes | `0bdee3ec32060b8cd3c7bc1e91e6d4e3239df0e6aaaff6c85accfbfab52c6fbd` |

Prepared dictionary contains:

- `scanner_sync_run_timed_output_sequence`
- `scanner_sync_stop`
- `scanner_sync_timed_output_sequence_status`
- `scanner_sync_frame_event`
- legacy `scanner_sync_af_window_test`
- legacy `scanner_sync_af_window_stop`

The prepared live source keeps the current `[scanner_sync]` pin config shape:

```text
white_pin: PB13
red_pin: PA10
green_pin: PA9
xvs_pin: PD6
```

No firmware flashing, Klipper restart, GPIO toggling, LED output, XVS pulse,
camera capture, homing or motor motion was performed as part of this build
preparation.

## Remote SD Firmware Update Evidence

Status: remote SD upload and post-power-cycle verify completed on the current
scanner MKS Robin Mini V2.0 board. No GPIO toggling, LED output, XVS pulse,
camera capture, homing or motor motion was commanded.

The current board supports the Klipper `flash-sdcard.sh` remote SD-card upload
path over the existing USB/serial connection when the following board
definition is present in Klipper `scripts/spi_flash/board_defs.py`:

```python
'mks-robin-mini-v2-scanner': {
    'mcu': "stm32f103xe",
    'spi_bus': "swspi",
    'spi_pins': "PC8,PD2,PC12",
    'cs_pin': "PC11",
    'skip_verify': True,
    'conversion_script': "scripts/update_mks_robin.py",
    'firmware_path': "Robin_mini.bin",
    'current_firmware_path': "Robin_mini.cur"
},
```

This is now the preferred MKS update path for the scanner when Pi5 can reach
the controller by USB/serial. Manual SD-card file copy remains the fallback.

Upload command used:

```bash
cd /home/pi/klipper
sudo service klipper stop
./scripts/flash-sdcard.sh \
  -f /home/pi/klipper/out/klipper.bin \
  -d /home/pi/klipper/out/klipper.dict \
  /dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0 \
  mks-robin-mini-v2-scanner
```

Remote SD card observed by `flash-sdcard.sh`:

| Field | Value |
| --- | --- |
| SDHC/SDXC | `True` |
| Write protected | `False` |
| Product name | `SD16G` |
| Capacity | `3.8 GiB` |
| Filesystem | `FAT32` |
| Volume label | `MKSBOOT` |

Upload result:

```text
Firmware Upload Complete: Robin_mini.bin, Size: 42648,
Checksum (SHA1): DD5BF16C99779986F012B863BF3B232386354B58
```

The tool reported that the board requires a manual reboot or full power cycle
to complete the flash process. After MKS power cycle, the verification command
was run:

```bash
cd /home/pi/klipper
./scripts/flash-sdcard.sh \
  -c \
  -f /home/pi/klipper/out/klipper.bin \
  -d /home/pi/klipper/out/klipper.dict \
  /dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0 \
  mks-robin-mini-v2-scanner
```

Verification result:

```text
Firmware Flash Successful
Current Firmware: v0.13.0-699-gc707dd192-dirty-20260704_001821-pi5
```

After verification:

- `klipper` service: `active`
- `moonraker` service: `active`
- Moonraker printer state: `ready`
- `scanner_sync.enabled`: `true`
- `scanner_sync.status`: `configured`
- `scanner_sync.last_test`: `null`
- `scanner_sync.last_status`: `null`
- `scanner_sync.last_frame_event`: `null`
- `toolhead.homed_axes`: empty
- `stepper_x`, `stepper_y`, `stepper_z`: disabled

The loaded dictionary contains:

- `scanner_sync_run_timed_output_sequence`
- `scanner_sync_stop`
- `scanner_sync_timed_output_sequence_status`
- `scanner_sync_frame_event`
- legacy `scanner_sync_af_window_test`
- legacy `scanner_sync_af_window_stop`

## Timed-Output Live Smoke Tests

Status: completed after the remote SD firmware update. These tests did not
command motors, homing or Z movement. X/Y/Z steppers remained disabled and
`toolhead.homed_axes` remained empty.

Logical outputs under test:

| Bit | Output |
| ---: | --- |
| `0x01` | white LED gate |
| `0x02` | red LED gate |
| `0x04` | green LED gate |
| `0x08` | HQ XVS sync |

### Test 1: Finite All-Off Completion

Command:

```text
SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE SEQ=1001 STRIPE_ID=0 SEQ_ID=1001
REPEAT_COUNT=1 FRAME_ID_BASE=-1 PATTERN_ID=0 SAFE_MASK=15 SAFE_VALUES=0
IDLE_MASK=15 IDLE_VALUES=0 STEPS_HEX=0f00e80300000800
```

Step payload:

| Step | Output mask | Output values | Delay | Flags |
| ---: | ---: | ---: | ---: | --- |
| 0 | `0x0f` | `0x00` | `1000 us` | `END` |

Observed status:

```text
status=3
reason=3
repeat_index=1
step_index=0
```

Interpretation: finite sequence completed and left all controlled outputs off.

### Test 2: Single RG + XVS Frame Event

Command:

```text
SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE SEQ=1002 STRIPE_ID=0 SEQ_ID=1002
REPEAT_COUNT=1 FRAME_ID_BASE=3000 PATTERN_ID=1 SAFE_MASK=15 SAFE_VALUES=0
IDLE_MASK=15 IDLE_VALUES=0
STEPS_HEX=0f06e803000000000808c800000013000800b80b000004000f00e80300002800
```

Step payload:

| Step | Output mask | Output values | Delay | Flags |
| ---: | ---: | ---: | ---: | --- |
| 0 | `0x0f` | `0x06` | `1000 us` | none |
| 1 | `0x08` | `0x08` | `200 us` | `FRAME_EVENT`, `XVS_RISING`, `EXPOSURE_START` |
| 2 | `0x08` | `0x00` | `3000 us` | `XVS_FALLING` |
| 3 | `0x0f` | `0x00` | `1000 us` | `EXPOSURE_END`, `END` |

Observed status:

```text
status=3
reason=3
repeat_index=1
step_index=0
```

Observed frame event:

```text
frame_id=3000
stripe_id=0
stripe_frame_index=0
pattern_id=1
event_position=0
x_count=0
y_count=0
z_count=0
flags=19
```

Interpretation: the MCU emitted the expected `FRAME_EVENT` for the XVS rising
step and copied the timed-output event flags into the frame event. `flags=19`
is `FRAME_EVENT | XVS_RISING | EXPOSURE_START`.

### Test 3: Infinite All-Off Stop Path

Start command:

```text
SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE SEQ=1003 STRIPE_ID=0 SEQ_ID=1003
REPEAT_COUNT=0 FRAME_ID_BASE=-1 PATTERN_ID=0 SAFE_MASK=15 SAFE_VALUES=0
IDLE_MASK=15 IDLE_VALUES=0 STEPS_HEX=0f00a08601000800
```

Stop command:

```text
SCANNER_SYNC_TIMED_OUTPUT_STOP REASON=4
```

Observed status after stop:

```text
status=4
reason=4
repeat_index=2
step_index=0
```

Interpretation: explicit host stop produced the expected stopped lifecycle
status and applied the all-off safe state.

### Final Safe State

After the stop-path test, a final finite all-off command was sent:

```text
SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE SEQ=1004 STRIPE_ID=0 SEQ_ID=1004
REPEAT_COUNT=1 FRAME_ID_BASE=-1 PATTERN_ID=0 SAFE_MASK=15 SAFE_VALUES=0
IDLE_MASK=15 IDLE_VALUES=0 STEPS_HEX=0f00e80300000800
```

Final observed status:

```text
status=3
reason=3
repeat_index=1
step_index=0
```

Final observed motion state:

```text
toolhead.homed_axes=""
stepper_x=false
stepper_y=false
stepper_z=false
```

The next live test should connect this timed-output path to the Pi camera frame
receiver and verify that `FRAME_EVENT.frame_id` is matched to the camera frame
arriving from HQ XVS sync-sink mode. Motion must remain disabled until that
camera-only synchronization test is stable.
