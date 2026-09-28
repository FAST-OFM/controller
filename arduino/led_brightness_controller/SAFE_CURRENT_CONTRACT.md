# Safe-current protocol v1

## Scope and state

This protocol defines only storage, validation, and reporting semantics for
future review. Firmware v6 has one state: `ARMED=0`, with all PWM outputs zero.
Neither a valid map nor a valid host target changes that state.

## Required future enable proof

A separately reviewed ARM/ENABLE change must atomically establish, per channel:

1. the selected host target is from a versioned artifact;
2. the per-channel map has a supported schema and nonzero artifact version;
3. measured PWM and current points are strictly increasing;
4. the target is bracketed by the measured current points;
5. derived PWM is calculated from the map, not set from a target literal;
6. failure of any check retains `ARMED=0` and writes PWM zero.

The legacy `min_pwm`/`max_pwm` calibration range is retained as EEPROM evidence
only. It is never enough for any of these proofs.

## Commands

| Command | Output effect | Storage effect |
| --- | --- | --- |
| `GET`, `GETCAL`, `CAL GET`, `CAL MAP GET` | Safe-zero; read-only | none |
| `CAL SET`, `CAL MAP SET` | Safe-zero | updates calibration evidence only; `SAVE` persists it |
| `CAL FIND`, `SET`, `SETC`, `ARM`, `ENABLE` | rejected; safe-zero reasserted | none |
| `ZERO`, `LOAD` | Safe-zero | `LOAD` may migrate/read calibration only |

No calibration procedure, hardware execution, serial access, or firmware flash
is authorized by this document.
