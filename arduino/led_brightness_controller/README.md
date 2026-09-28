# Arduino LED Safe-Current Contract

This sketch is an unarmed, fail-safe storage and query implementation for the
Rev A.5 LED PWM/VREF hardware. It is not an authorization to compile, upload,
flash, attach, or operate an Arduino or an LED current path.

At boot, reset, `LOAD`, `ZERO`, rejected commands, and all ordinary command
processing, RED, GREEN, and WHITE PWM registers are written to zero. `GET`
always reports `RED_PWM=0 GREEN_PWM=0 WHITE_PWM=0 ARMED=0`. There is no live
brightness state, no retained-RAM restore, and no serial `SET`, `SETC`, `ARM`,
or `ENABLE` path in this revision. These commands are rejected and reassert
safe-zero.

## Version 6 migration

Firmware config version 6 stores calibration evidence only:

- retained legacy `min_pwm`, `max_pwm`, and threshold fields;
- a separate per-channel, versioned two-point PWM-to-current artifact;
- a checksum over the whole v6 record.

A checksum-valid v5 EEPROM record is migrated once. Its calibration ranges are
preserved, but its saved RED/GREEN/WHITE values are deliberately discarded,
including `255/255/255`. v5 ranges prove neither a current map nor reachability,
so every migrated map begins invalid. An invalid or corrupted record defaults
to all-zero, unarmed output and invalid maps.

## Host calibration contract

Electrical targets are versioned host-calibration values, not PWM values:

- `WHITE_BF`: 300.00 mA;
- `RED`: 100.00 mA;
- `GREEN`: 100.00 mA.

Their source is [`calibration/led-current-targets-v1.yaml`](calibration/led-current-targets-v1.yaml).
The schema for the future per-channel map artifact is
[`calibration/led-pwm-current-map.schema.json`](calibration/led-pwm-current-map.schema.json).
The firmware stores or reports an artifact but does not treat legacy `min_pwm`
and `max_pwm` as that artifact.

`CAL MAP SET <channel> <artifact_version> <low_pwm> <low_ma_x100> <high_pwm>
<high_ma_x100> [SAVE]` stores a schema-v1, strictly increasing two-point map
without changing an output. `CAL MAP GET`, `GETCAL`, and `CAL GET` are
read-only queries. `CAL FIND` is rejected because it would energize an unarmed
channel. `CAL SET` remains calibration-evidence storage only.

An intentionally absent future ARM/ENABLE implementation must validate a
schema-supported, nonzero-version artifact for every channel it proposes to
energize, prove its target current lies inside the measured map range, derive
PWM from that map, and record the exact host calibration artifact revision.
That implementation requires separate safety review and is out of scope here.

## Host-only test

Run the deterministic contract test only on a server host:

```text
make host-test
```

It covers v5 migration, checksum rejection, legacy `255` handling, safe reset,
per-channel mapping, query immutability, invalid/missing/reachability rejection,
and current-target-to-PWM separation. It does not access serial hardware.
