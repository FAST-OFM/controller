# MKS Timed-Output Sequence Live Source Snapshot

Status: flashed and smoke-tested on the live MKS Robin Mini V2 bench setup on
2026-07-04. This is still a no-motion bench build: it must not be used for
homing, motor motion, firmware flashing workflows, camera capture automation or
LED current changes without an explicit test procedure.

This directory contains the two live Klipper source files used to prepare the
MKS Robin Mini timed-output sequence firmware build on `pi5`.

Copy mapping:

| Source snapshot | Pi Klipper target |
| --- | --- |
| `klippy/extras/scanner_sync.py` | `/home/pi/klipper/klippy/extras/scanner_sync.py` |
| `src/scanner_sync.c` | `/home/pi/klipper/src/scanner_sync.c` |

The source keeps the current live `[scanner_sync]` config shape:

```ini
[scanner_sync]
enable: true
protocol_version: 1
white_pin: PB13
red_pin: PA10
green_pin: PA9
xvs_pin: PD6
```

It adds:

- staged MCU commands `scanner_sync_begin_timed_output_sequence`,
  `scanner_sync_add_timed_output_step` and
  `scanner_sync_start_timed_output_sequence`;
- compatibility MCU command `scanner_sync_run_timed_output_sequence`;
- MCU command `scanner_sync_stop`;
- response `scanner_sync_timed_output_sequence_status`;
- full-format `scanner_sync_frame_event`;
- G-code command `SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE`;
- G-code command `SCANNER_SYNC_TIMED_OUTPUT_STOP`;
- legacy `SCANNER_SYNC_AF_WINDOW_TEST` and `SCANNER_SYNC_AF_WINDOW_STOP`
  compatibility.

`SCANNER_SYNC_AF_WINDOW_TEST` is the current preferred no-motion bench command
for stable RG/XVS timing sweeps on the live MKS build. Its timing order is:

```text
white preview baseline
white off
red+green on
wait RG_SETTLE_US
XVS high
wait XVS_PULSE_US
XVS low
wait EXPOSURE_HOLD_US while red+green remain on
wait RG_TO_WHITE_US while red+green remain on
red+green off
white restored for idle, or END_WHITE at final stop
```

The external parameter name remains `RG_TO_WHITE_US` for compatibility with the
current G-code interface. In this source snapshot it means
`post_exposure_rg_hold_before_white_restore`, not an already-dark idle delay.
The previous live build turned red/green off before this delay; that older
behavior is unsuitable for tightening post-exposure illumination margins.

`SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE` accepts `STEPS_HEX`, where each step is a
10-byte little-endian record:

| Offset | Size | Field |
| --- | ---: | --- |
| 0 | 1 | `output_mask` |
| 1 | 1 | `output_values` |
| 2 | 1 | `pattern_id` |
| 3 | 1 | `reserved`, must be `0` |
| 4 | 4 | `delay_us` |
| 8 | 2 | `event_flags` |

The host extra rejects encoded step payloads longer than 120 bytes and the live
MCU build accepts at most 12 steps. This is intentional for the MKS Robin Mini
serial receive window. A long white/RG train should encode one short
white/RG-pair pattern and use `REPEAT_COUNT`; it should not inline a long list
of one-off steps. `FRAME_EVENT` frame identity increments per emitted event, so
two event-bearing steps inside one repeated pattern still produce distinct
frame IDs.

The host-facing G-code keeps `STEPS_HEX`, but the live host extra must not send
that full payload as one MCU message. It decodes the payload on the Pi and sends
one bounded Klipper transport command per stage: `begin`, one `add_step` per
encoded step, then `start`.

V1 bench sequences reject any single step with `delay_us > 100000`. Longer
operator-preview waits must be orchestrated by the host using ordinary gate
commands around snapshots, not by keeping the MCU timed-output interpreter in a
multi-second diagnostic sequence. This keeps the low-level sequence bounded for
LED/XVS timing windows and fail-closed if a host script accidentally encodes a
long visual-preview pause.

Logical output bits:

| Bit | Output |
| ---: | --- |
| `0x01` | white LED gate |
| `0x02` | red LED gate |
| `0x04` | green LED gate |
| `0x08` | HQ XVS sync |

This source does not command motors, home axes, flash firmware, capture camera
frames, or change LED current settings.

## Required Slim MCU Build Configuration

The first staged build was compiled with Klipper's broad default optional MCU
features enabled. That produced a 44 KiB `Robin_mini.bin`; the MKS bootloader
accepted and renamed the file to `ROBIN_MINI.CUR`, but the MCU application did
not answer Klipper `identify_response` after reboot.

The verified live build uses a slim MCU configuration. It keeps only the
features required by the current `printer.cfg`: serial, GPIO, steppers,
endstops, hardware PWM for the MKS stepper-current Vref outputs, and
`scanner_sync`.

Required optional-feature state:

```text
# CONFIG_WANT_ADC is not set
# CONFIG_WANT_SPI is not set
# CONFIG_WANT_SOFTWARE_SPI is not set
# CONFIG_WANT_I2C is not set
# CONFIG_WANT_SOFTWARE_I2C is not set
CONFIG_WANT_HARD_PWM=y
# CONFIG_WANT_BUTTONS is not set
# CONFIG_WANT_TMCUART is not set
# CONFIG_WANT_NEOPIXEL is not set
# CONFIG_WANT_PULSE_COUNTER is not set
# CONFIG_WANT_ST7920 is not set
# CONFIG_WANT_HD44780 is not set
# CONFIG_WANT_ADXL345 is not set
# CONFIG_WANT_LIS2DW is not set
# CONFIG_WANT_BMI160 is not set
# CONFIG_WANT_MPU9250 is not set
# CONFIG_WANT_ICM20948 is not set
# CONFIG_WANT_THERMOCOUPLE is not set
# CONFIG_WANT_HX71X is not set
# CONFIG_WANT_ADS131M0X is not set
# CONFIG_WANT_ADS1220 is not set
# CONFIG_WANT_LDC1612 is not set
# CONFIG_WANT_SENSOR_ANGLE is not set
# CONFIG_NEED_SENSOR_BULK is not set
# CONFIG_WANT_TRIGGER_ANALOG is not set
# CONFIG_NEED_SOS_FILTER is not set
```

Verified slim build evidence:

```text
Version: v0.13.0-699-gc707dd192-dirty-20260704_130046-pi5
text/data/bss: 17788 / 52 / 976
out/klipper.bin: 17840 bytes
Robin_mini.bin SHA1: 097d438ac3b91dd7220da1491c7f284bd90bf871
```

After flashing and power-cycling MKS, Klipper loaded:

```text
Loaded MCU 'mcu' 59 commands
MCU 'mcu' config: CLOCK_FREQ=72000000 MCU=stm32f103xe
SERIAL_BAUD=250000
```

Do not rebuild this live MKS image with optional sensor, LCD, SPI, I2C, TMC,
neopixel or ADC modules enabled unless the resulting image is explicitly tested
for boot and Klipper identify.

## Primary Remote Update Procedure

The current scanner MKS Robin Mini V2.0 supports Klipper remote SD-card upload
over the existing USB/serial link. This is the primary update path for this
board, replacing the manual "copy `Robin_mini.bin` to SD card" path when the
board is reachable from Pi5.

Validated board definition fragment:

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

The same fragment is preserved in
`spi_flash_board_def_mks_robin_mini_v2_scanner.py`.

Build and upload:

```bash
cd /home/pi/klipper
make clean
make -j2
sudo service klipper stop
timeout 120s ./scripts/flash-sdcard.sh \
  -f /home/pi/klipper/out/klipper.bin \
  -d /home/pi/klipper/out/klipper.dict \
  /dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0 \
  mks-robin-mini-v2-scanner
```

After upload, perform a full MKS board power cycle so the Robin bootloader
applies `Robin_mini.bin` from the board SD card. Then verify and restart
Klipper:

```bash
cd /home/pi/klipper
./scripts/flash-sdcard.sh \
  -c \
  -f /home/pi/klipper/out/klipper.bin \
  -d /home/pi/klipper/out/klipper.dict \
  /dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0 \
  mks-robin-mini-v2-scanner
sudo service klipper start
```

The verified update path writes firmware to the controller SD card and resets
the MCU. It must not be combined with GPIO toggling, LED output, camera
triggering, homing or motor motion in the same procedure.

## Verified No-Motion Smoke Test

The 2026-07-04 slim build was checked with one repeated two-frame no-motion
sequence:

- RG illumination window with XVS rising `FRAME_EVENT`;
- white illumination window with XVS rising `FRAME_EVENT`;
- `REPEAT_COUNT=2`;
- all controlled outputs off as safe and idle state.

Observed scanner-sync status:

```text
transport: staged
last_status.status: 3  # completed
last_status.reason: 3  # finite_completion
frame_event_count: 4
pattern_id sequence: 2, 1, 2, 1
frame_id sequence: 130046000, 130046001, 130046002, 130046003
```

This smoke test verifies the Klipper staged transport, MCU timer execution,
task-context telemetry, finite completion and frame-event identity ordering. It
does not validate camera image capture, motion-position binding, autofocus math
or LED brightness/current calibration.
