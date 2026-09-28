# Timed-Output MCU Communication Loss Evidence - 2026-07-04

## Scope

This is a no-motion bench evidence note for the experimental
`SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE` path.

No homing, axis motion, Z motion, motor test, firmware flashing, or GPIO test
outside the configured light/XVS outputs was intentionally commanded during the
run.

## Command Under Test

The Pi runtime invoked:

```bash
python3 -m scanner.cli.light_xvs_capture \
  --machine-config configs/machines/prototype-a.yaml \
  --output-dir /home/pi/fast-ofm-camera-test/light-xvs-cli-20260704 \
  --mode white_steady \
  --enable-hardware-output \
  --seq 1401 \
  --frame-id-base 4401 \
  --pattern-id 0 \
  --white-pwm 255 \
  --red-pwm 0 \
  --green-pwm 0 \
  --pre-light-settle-ms 750 \
  --post-xvs-snapshot-delay-ms 50 \
  --pre-trigger-lead-us 1000 \
  --xvs-pulse-us 200 \
  --exposure-hold-us 3200 \
  --post-exposure-guard-us 1000 \
  --frame-period-us 25000 \
  --final-mode off
```

The generated MKS wrapper command was:

```text
SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE SEQ=1401 STRIPE_ID=0 SEQ_ID=1401 REPEAT_COUNT=1 FRAME_ID_BASE=4401 PATTERN_ID=0 SAFE_MASK=8 SAFE_VALUES=0 IDLE_MASK=8 IDLE_VALUES=0 STEPS_HEX=0800e803000000000808c800000013000800b80b000004000000e803000020000800584d00000800
```

## Artifacts

- Remote artifact root:
  `/home/pi/fast-ofm-camera-test/light-xvs-cli-20260704`
- Remote image:
  `/home/pi/fast-ofm-camera-test/light-xvs-cli-20260704/white_steady-20260703-211714.jpg`
- Remote manifest:
  `/home/pi/fast-ofm-camera-test/light-xvs-cli-20260704/white_steady-20260703-211714.json`
- Local copied image:
  `/path/to/private-evidence/white_steady.jpg`

The saved image was visually valid brightfield tissue imagery.

## Observed State

Before the test:

- `fast-ofm-preview.service` was active.
- Moonraker/Klipper reported `state=ready`.
- Preview snapshot endpoint returned JPEG.

After the test:

- The image and manifest were saved.
- Arduino brightness cleanup completed:
  `BrightnessSetpoint(red=0, green=0, white=0)`.
- Klipper reported:
  `Lost communication with MCU 'mcu'`.
- `FIRMWARE_RESTART` returned `ok` but Klipper then reported:
  `Failed automated reset of MCU 'mcu'`.

## Klipper Log Signature

Relevant log excerpt:

```text
scanner_sync timed output sequence queued on MCU
...
Timeout with MCU 'mcu' (eventtime=31477.370174)
Transition to shutdown state: Lost communication with MCU 'mcu'
...
Received ... "SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE SEQ=1401 ... REPEAT_COUNT=1 ... STEPS_HEX=0800e803000000000808c800000013000800b80b000004000000e803000020000800584d00000800"
Received ... "SET_PIN PIN=led_red_wifi VALUE=0.0\nSET_PIN PIN=led_green_wifi VALUE=0.0\nSET_PIN PIN=hq_xvs_sync VALUE=0.0\nSET_PIN PIN=led_white_tc1 VALUE=0.0"
Exception in analyze_shutdown handler
...
Lost communication with MCU 'mcu'
```

The stats immediately after timed-output dispatch showed a sharp
`bytes_write` / `bytes_read` / sequence-number increase before timeout. This is
consistent with a firmware/protocol path problem rather than a failed camera
capture.

## Current Safety Decision

Until this is fixed and reproduced:

- Do not run `SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE` as part of normal bench
  testing.
- Do not promote timed-output sequence tests to delay sweeps.
- Do not move axes, home, or perform scan motion while this blocker is open.
- Treat the current live MKS timed-output path as experimental.
- Pi-side `scanner-light-xvs-capture` now requires an extra
  `--acknowledge-experimental-mcu-timed-output` flag in addition to
  `--enable-hardware-output`.

Follow-up no-motion testing on the same date isolated a stable lower-level path:

- `SCANNER_SYNC_AF_WINDOW_TEST` completed repeated RG/XVS single-frame sweeps
  with Klipper returning to `ready`.
- MKS output gates after the sweep were observed inactive.
- Steppers remained disabled; no homing, axis motion, Z motion or firmware
  flashing was commanded.
- The selected conservative RG pre-trigger lead is `50000 us`.
- The selected old-semantics post-frame idle/tail is `10000 us`.

This does not close the generic timed-output sequence blocker. The stable
`AF_WINDOW_TEST` path is currently the preferred no-motion bench path for
tightening light/XVS timing until the generic encoded-step transport is fixed.

The live `AF_WINDOW_TEST` build used for the follow-up sweep turned red/green
off before `RG_TO_WHITE_US`. The next source snapshot changes that state machine
so `RG_TO_WHITE_US` holds red/green on after exposure and before restoring
white. That source change still requires build/flash and repeat bench evidence.

## Next Firmware Work

Investigate the live MKS timed-output sequence implementation before further
hardware use:

1. Reproduce with a minimal one-step all-off timed-output sequence after manual
   MCU recovery.
2. Reproduce with the previous four-step XVS-only smoke sequence.
3. Reproduce with the five-step canonical sequence above.
4. Verify the `encoded_steps=%*s` command layout on the active Klipper/MCU
   build.
5. Confirm finite `REPEAT_COUNT=1` completion with exactly one frame event and
   one terminal `completed` status.
6. Add a host-side watchdog/status expectation before any future live loop.
7. Keep all tests no-motion until the timed-output status lifecycle is stable.
