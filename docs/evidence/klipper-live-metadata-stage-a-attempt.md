# Klipper Live Metadata Stage A Attempt

Status: Stage A passed after MKS USB serial recovery. Scanner-sync remains
disabled and no hardware-output path has been enabled.

## Scope

Stage A was intended to prove the safest live boundary:

- install the Klipper host extra only;
- add `[scanner_sync] enable: false`;
- restart Klipper once;
- verify Klipper starts with scanner-sync disabled;
- do not flash firmware;
- do not send scanner-sync commands;
- do not toggle GPIO;
- do not move motors;
- do not trigger the camera;
- do not drive LEDs.

## Live System

Observed on Pi:

- host: `pi5`
- Klipper checkout: `~/klipper`
- Klipper commit: `c707dd19214709dc23684b254a68e3bf69e4cfb3`
- service: system `klipper.service`
- config: `~/printer_data/config/printer.cfg`
- MKS serial path in config:
  `/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0`
- Arduino serial path remained present:
  `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0`

## Actions Performed

The following live changes were made:

1. Backed up `printer.cfg`.
2. Copied `klippy/extras/scanner_sync.py` to the live Klipper checkout.
3. Appended:

   ```ini
   [scanner_sync]
   enable: false
   protocol_version: 1
   ```

4. Verified Python syntax for the host extra.
5. Restarted Klipper once.

No firmware was flashed. No G-code was sent. No scanner-sync commands were
sent. No output pins were toggled.

## Result

Klipper process restarted and remained `active`, but MCU serial reconnect
failed:

```text
mcu 'mcu': Unable to open serial port:
/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0
Input/output error
```

Kernel logs showed repeated CH341 errors on the MKS port:

```text
ch341-uart ttyUSB0: usb_serial_generic_write_bulk_callback - nonzero urb status: -71
usb 1-1: failed to send control message: -71
usb 1-1: failed to receive control message: -71
ch341-uart ttyUSB0: failed to read modem status: -71
```

After a USB driver unbind/bind attempt on the MKS USB device, the old MKS serial
path no longer appeared:

```text
/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0
```

`lsusb` still showed a CH340 device on Bus 001, but the kernel did not expose
the corresponding tty device. Arduino remained available as the other CH340
device on Bus 003 / `ttyUSB1`.

## Rollback Performed

The live scanner-sync changes were rolled back:

- restored `printer.cfg` from the Stage A backup;
- removed `~/klipper/klippy/extras/scanner_sync.py`;
- restarted Klipper;
- confirmed `~/klipper` is clean;
- confirmed `[scanner_sync]` is absent from `printer.cfg`.

The serial failure remained after rollback. This indicates the blocker is the
MKS USB/board state, not scanner-sync config parsing.

## Original Blocker

Live metadata testing cannot continue until the MKS controller presents a
working serial device again.

Current observed state:

- Klipper service: `active`;
- Klipper checkout: clean;
- scanner-sync config: absent;
- MKS CH340: visible in `lsusb`;
- MKS serial tty/by-path: absent;
- Klipper MCU connection: failing because configured serial path does not
  exist;
- Arduino CH340: still present as `ttyUSB1`.

## Follow-Up After MKS Power Cycle

After a physical MKS power-cycle was attempted, read-only checks were repeated
on July 1, 2026.

Observed state:

- Klipper service remained `active`;
- `~/klipper` remained clean;
- `[scanner_sync]` remained absent from `printer.cfg`;
- Arduino CH340 remained present as
  `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0`;
- the configured MKS path
  `/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0` was still absent;
- `lsusb -t` did not show an enumerated CH340 device on Bus 001 Port 1;
- `dmesg` showed USB enumeration failures:

```text
usb 1-1: device descriptor read/64, error -71
usb 1-1: Device not responding to setup address.
usb 1-1: device not accepting address, error -71
usb usb1-port1: unable to enumerate USB device
```

This keeps the live metadata retry blocked. The next recovery action is still
physical: check MKS power and USB cabling, then replug or power-cycle until the
MKS CH340 enumerates as a tty device.

Likely physical recovery actions:

- confirm MKS board power is on;
- replug MKS USB;
- power-cycle MKS board;
- confirm `/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0`
  returns;
- restart Klipper after the serial path is restored.

These are physical/hardware boundary actions.

## Next Safe Non-Hardware Actions

Allowed without hardware:

- keep local simulator tests running;
- keep disposable Klipper patch artifacts updated;
- document the live attempt;
- prepare a reviewed metadata-only retry checklist.

Not allowed until MKS serial is restored and explicitly approved:

- reinstall scanner-sync host extra on live Pi;
- edit live `printer.cfg`;
- restart Klipper for another live metadata attempt;
- send any G-code;
- send scanner-sync commands;
- flash firmware;
- toggle GPIO;
- move axes;
- trigger the camera;
- drive LEDs.

## Successful Stage A Retry

After the MKS board was physically power-cycled and replugged again, the
configured serial path returned on July 1, 2026:

```text
/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0 -> ../../ttyUSB0
```

Klipper was restarted once with the original configuration first. The baseline
connection passed:

```text
mcu 'mcu': Starting serial connect
Loaded MCU 'mcu' 139 commands (v0.13.0-699-gc707dd192 ...)
Configured MCU 'mcu' (1024 moves)
```

Stage A was then retried:

1. Backed up `printer.cfg` to
   `printer.cfg.before-scanner-sync-stage-a.20260701-122754`.
2. Installed `klippy/extras/scanner_sync.py` into the live Klipper checkout.
3. Appended the disabled config:

   ```ini
   [scanner_sync]
   enable: false
   protocol_version: 1
   ```

4. Ran `python3 -m py_compile` on the installed host extra.
5. Restarted Klipper once.

The retry passed. Klipper remained `active`, opened the MKS serial path and
configured the MCU with scanner-sync disabled:

```text
Loaded MCU 'mcu' 139 commands (v0.13.0-699-gc707dd192 ...)
Configured MCU 'mcu' (1024 moves)
```

No firmware was flashed. No G-code was sent. No scanner-sync commands were
sent. No output pins were toggled. No motors, camera trigger or LED outputs were
commanded.

Current live state:

- `~/klipper/klippy/extras/scanner_sync.py` is installed as an untracked live
  host-extra file;
- `printer.cfg` contains `[scanner_sync] enable: false`;
- the live MKS firmware does not contain scanner-sync MCU commands;
- enabling scanner-sync would require a reviewed firmware patch and flash step,
  and remains outside this Stage A result.

## Next Boundary

The next safe software step is not a hardware test. It is to prepare the Phase
1 live metadata implementation so that `FRAME_EVENT` and Z-scheduler command
names, payloads and host parsing are consistent with the dry-run patch artifact.

The next hardware boundary remains blocked until explicitly approved:

- firmware flashing;
- enabling `[scanner_sync] enable: true`;
- sending scanner-sync commands;
- toggling GPIO;
- moving axes;
- triggering the camera;
- driving LEDs.
