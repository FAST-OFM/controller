# Klipper AF Window No-Motion Smoke Test - 2026-07-02

Status: bench diagnostic evidence only.

This test did not command motors, flash firmware, enable scanner-sync, or prove
position-indexed scan timing. It only verified that the currently configured
Klipper output aliases can execute a short no-motion AF-window-like sequence and
return to safe-off.

## Environment

- Host: `pi5`
- Pi address: `192.0.2.13`
- Klipper: `v0.13.0-699-gc707dd192-dirty`
- MKS serial path: `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0`
- Arduino serial path: `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0`
- `[scanner_sync] enable: false`

## Verified Output Aliases

- Green AF gate: `led_green_wifi`, PA9
- Red AF gate: `led_red_wifi`, PA10
- White illumination gate: `led_white_tc1`, PB13
- HQ camera XVS sync: `hq_xvs_sync`, PD6

All aliases are logic outputs only. LED current is not sourced by MCU GPIO.

## Diagnostic Sequence

Executed through local Moonraker G-code script:

```gcode
SET_PIN PIN=led_green_wifi VALUE=0
SET_PIN PIN=led_red_wifi VALUE=0
SET_PIN PIN=led_white_tc1 VALUE=0
SET_PIN PIN=hq_xvs_sync VALUE=0
G4 P100
SET_PIN PIN=led_green_wifi VALUE=1
SET_PIN PIN=led_red_wifi VALUE=1
G4 P1
SET_PIN PIN=hq_xvs_sync VALUE=1
G4 P0.2
SET_PIN PIN=hq_xvs_sync VALUE=0
G4 P2
SET_PIN PIN=led_green_wifi VALUE=0
SET_PIN PIN=led_red_wifi VALUE=0
SET_PIN PIN=led_white_tc1 VALUE=0
SET_PIN PIN=hq_xvs_sync VALUE=0
```

Moonraker returned:

```json
{"result":"ok"}
```

Final Klipper object state:

```json
{
  "output_pin led_green_wifi": {"value": 0.0},
  "output_pin led_red_wifi": {"value": 0.0},
  "output_pin led_white_tc1": {"value": 0.0},
  "output_pin hq_xvs_sync": {"value": 0.0}
}
```

## Boundary

This is the diagnostic `fire_now` class of test. It is useful for local wiring,
camera sync, and LED gate checks without motion.

It is not the production scan path. The production path must use
`scanner_sync_arm_af_window` and fire from `trigger_position_count` on the MCU,
with MCU-local offsets for LED settle, XVS pulse width, and exposure hold.

## HQ Camera XVS Capture Smoke

Additional no-motion camera capture was run with the MKS board generating the
XVS pulse train. This still does not prove position-indexed scan timing; it only
proves that the current MKS XVS output can trigger the HQ camera when the camera
is already in external-trigger mode.

Runtime camera setup:

```bash
echo 2 | sudo tee /sys/module/imx477/parameters/trigger_mode
```

Camera command:

```bash
rpicam-vid --nopreview \
  --width 2028 --height 1080 --framerate 10 --timeout 7000 \
  --shutter 2000 --gain 1 --awb custom --awbgains 1,1 \
  --codec h264 \
  --output /home/pi/fast-ofm-camera-test/mks_xvs_rg_faststart_20260702-234343.h264
```

MKS pulse train:

```gcode
SET_PIN PIN=led_white_tc1 VALUE=0
SET_PIN PIN=led_green_wifi VALUE=1
SET_PIN PIN=led_red_wifi VALUE=1
SET_PIN PIN=hq_xvs_sync VALUE=0
G4 P1
# repeated 80 times:
SET_PIN PIN=hq_xvs_sync VALUE=1
G4 P0.2
SET_PIN PIN=hq_xvs_sync VALUE=0
G4 P99.8
SET_PIN PIN=led_green_wifi VALUE=0
SET_PIN PIN=led_red_wifi VALUE=0
SET_PIN PIN=led_white_tc1 VALUE=0
SET_PIN PIN=hq_xvs_sync VALUE=0
```

Result:

- Output file:
  `/home/pi/fast-ofm-camera-test/mks_xvs_rg_faststart_20260702-234343.h264`
- File size: 21 KiB
- Encoder summary: 3 I-frames, 11 P-frames, 8 B-frames
- Final Klipper output state:

```json
{
  "output_pin led_green_wifi": {"value": 0.0},
  "output_pin led_red_wifi": {"value": 0.0},
  "output_pin led_white_tc1": {"value": 0.0},
  "output_pin hq_xvs_sync": {"value": 0.0}
}
```

Notes:

- `rpicam-vid --sync client` did not work for this setup; the camera frontend
  timed out and no H.264 file was produced.
- Passing the PiSP pipeline JSON/YAML file via `rpicam-vid --config` is
  incorrect; that option expects an rpicam app options file.
- Starting the MKS XVS train shortly after camera start avoided the initial
  frontend timeout seen in slower-start tests.
