# Prototype firmware checkpoint — 2026-09-09

Version: `v0.1.0-prototype.1`  
Status: observed R&D prototype state; no firmware was flashed.

This record ties the running MKS and Arduino software to Git history without
claiming that the current prototype uses the future MCU-timed scanner
architecture. The accepted scan remains stop-and-shoot and does not use XVS,
hardware camera triggering or `scanner_sync`.

## MKS / Klipper state observed on the Pi

- Version string:
  `v0.13.0-699-gc707dd192-dirty-20260704_130046-pi5`.
- Base Klipper commit:
  `c707dd19214709dc23684b254a68e3bf69e4cfb3`.
- Working tree state at inspection:
  - modified `scripts/spi_flash/board_defs.py`;
  - modified `src/Makefile`;
  - untracked `klippy/extras/scanner_sync.py`;
  - untracked `src/scanner_sync.c`.

Observed SHA-256 values:

| Live file | SHA-256 |
| --- | --- |
| `scripts/spi_flash/board_defs.py` | `e54a65aaceec1b932b622202d11cd1da476fb3ad362b6c2429e6cd30faa90041` |
| `src/Makefile` | `551d54ae94cb317146aa616293b73736adb4b261a1732e7e4353560c2ddf4c0e` |
| `klippy/extras/scanner_sync.py` | `91f86ee2152a0d7906915350e60a6cdae8d9f93464df843e288e15a76e03ff8f` |
| `src/scanner_sync.c` | `dfbe1d09354ef12defb0653006ebd6cfbd1ad16fce53acf757d61d4958b34ebb` |

The live `scanner_sync.c` is byte-identical to the repository blob at commit
`b3c2a78105096de55aac307c5af4f3eba5f33ffc`. The file on current `main`
differs only in two status-timestamp lines preserved by commit `9e98b62`.

The live host-side `scanner_sync.py` is an older 104-line Phase 2
metadata-only sketch and does not match the later repository snapshots. This
does not affect the checkpoint scan because scanner-sync registration and use
are disabled. Preserve this difference as evidence; do not silently present
the live Pi as the future firmware implementation.

## Arduino brightness controller observed on the Pi

- Live source SHA-256:
  `79d7f1651b2f94870f60343c37f4e7a5c44022ba6df643da4d5177f11c62ade1`.
- Matching repository commit:
  `6089fc9bedf8b54f2c45860c9dadbe9fa8b3e0cf` (`Preserve Arduino live brightness across serial reset`).
- Runtime PWM: 62.5 kHz.
- Runtime configuration version: 4.
- Saved simultaneous R/G profile: `RED150/GREEN150/WHITE255`.
- Cached Pi HEX SHA-256:
  `c9d3a184668c2a991b1f6abc33a17cb208b7ec090e590d1dac9cbc2b22ede609`.

The HEX value identifies the cached build artifact on the Pi; it was not read
back from the ATmega328P and is not independent proof of flash contents. A
later version 5 source candidate is present in repository history but was not
deployed for this checkpoint.

## Exact runtime preservation added after the first tag

The original `v0.1.0-prototype.1` evidence recorded identities and hashes but
did not commit the active `printer.cfg` or the complete runtime file set. The
follow-up `v0.1.2-prototype.1` checkpoint closes that gap under
`docs/evidence/prototype-runtime-snapshot-2026-09-09/`. It contains readable
copies plus exact-byte base64 tarballs of the live controller configuration,
Klipper source differences/build configuration, Arduino source/HEX artifacts
and controller service files. See the snapshot README for checksums and the
explicit MKS/Arduino readback limitation.

## Safety and scope

- No MKS or Arduino flash was performed.
- No Arduino EEPROM value was changed.
- The scan used host-orchestrated stop-and-shoot capture.
- All LED gates were verified off after the run.
- Motors were released and the local stage reference was invalidated.

This tag is a reproducibility marker for the prototype, not firmware release
approval and not a clinical or diagnostic claim.
