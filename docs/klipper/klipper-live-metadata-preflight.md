# Klipper Live Metadata Preflight

Status: completed for the July 1, 2026 Stage A retry; keep this checklist for
future retries or rollback.

This checklist exists because the first Stage A attempt was blocked by MKS USB
serial failure after Klipper restart. It was completed before the successful
disabled-host-extra retry on July 1, 2026 and must be repeated before future
live metadata retries if the live state changes.

## Required Read-Only Checks

Run on the Pi before modifying files:

```text
hostname
date
git -C ~/klipper rev-parse HEAD
git -C ~/klipper status --short --branch
systemctl is-active klipper
grep -n "^\\[scanner_sync\\]" ~/printer_data/config/printer.cfg || true
ls -l /dev/serial/by-path /dev/serial/by-id
lsusb
lsusb -t
dmesg | tail -140
tail -160 ~/printer_data/logs/klippy.log
```

Preflight pass criteria for a rolled-back clean baseline:

- Klipper checkout is clean.
- `[scanner_sync]` is absent before the retry.
- MKS serial path exists:
  `/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0`.
- Arduino serial path may exist separately:
  `/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0`.
- `dmesg` does not show active CH341 `-71` errors for the MKS device.
- Klipper can open the configured MCU serial path before scanner-sync is
  reintroduced.

July 1, 2026 result: the MKS serial path returned after physical recovery,
Klipper opened it with the original config, and the disabled Stage A retry
passed.

Preflight pass criteria for the retained Stage A baseline:

- Klipper checkout has exactly one expected untracked live file:
  `klippy/extras/scanner_sync.py`.
- `printer.cfg` contains:

  ```ini
  [scanner_sync]
  enable: false
  protocol_version: 1
  ```

- MKS serial path exists:
  `/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0`.
- Klipper service is `active`.
- Klipper can open the configured MCU serial path.
- No scanner-sync MCU commands are assumed to exist.
- `[scanner_sync] enable: true` remains blocked.

## Stage A Retry Plan

Only after preflight passes:

1. Back up `printer.cfg`.
2. Copy `scanner_sync.py` host extra into `~/klipper/klippy/extras/`.
3. Add:

   ```ini
   [scanner_sync]
   enable: false
   protocol_version: 1
   ```

4. Run Python syntax check on the copied host extra.
5. Restart Klipper once.
6. Verify:
   - Klipper service is active;
   - MCU serial is connected;
   - no scanner-sync commands were sent;
   - no GPIO, motion, camera or LED activity occurred.

## Rollback Plan

If Klipper fails to start or the MCU cannot reconnect:

1. Restore the preflight `printer.cfg` backup.
2. Remove `~/klipper/klippy/extras/scanner_sync.py`.
3. Restart Klipper once.
4. Confirm:
   - checkout clean;
   - `[scanner_sync]` absent;
   - Klipper failure mode is documented.

If scanner-sync must be removed after the successful Stage A retry, use the same
rollback steps. The known config backup is:

```text
~/printer_data/config/printer.cfg.before-scanner-sync-stage-a.20260701-122754
```

## Stop Conditions

Stop immediately and do not continue live metadata testing if:

- MKS serial path is absent;
- CH341 `-71` errors recur;
- Klipper cannot reconnect to MCU before scanner-sync is reintroduced;
- Klipper checkout has unexpected local edits beyond the retained Stage A
  host extra;
- `printer.cfg` has unreviewed scanner-sync state or `enable: true`;
- any step would require firmware flashing;
- any step would require GPIO, motor, camera or LED output.

## Hardware Boundary

Restoring MKS power, replugging USB, power-cycling the board, probing signals
or changing wiring are hardware actions. They are outside this non-hardware
preflight.
