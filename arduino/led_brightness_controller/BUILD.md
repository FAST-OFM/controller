# Build the Arduino brightness controller

Target used by the prototype:

- Arduino Nano-compatible ATmega328P;
- old Nano bootloader;
- FQBN `arduino:avr:nano:cpu=atmega328old`;
- runtime serial `115200 8N1`;
- PWM frequency 62.5 kHz.

The release-candidate validation toolchain is pinned to:

- `arduino-cli` 1.5.1;
- official `arduino:avr` core 1.8.6;
- AVR GCC `7.3.0-atmel3.6.1-arduino7` (installed by that core).

The Linux x86-64 Arduino CLI archive used for validation was the official
`arduino-cli_1.5.1_Linux_64bit.tar.gz` release asset with SHA-256
`28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b`.

Install that CLI version using the Arduino project's instructions, then install
the exact core and compile from the repository root without uploading:

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr@1.8.6
arduino-cli compile \
  --fqbn arduino:avr:nano:cpu=atmega328old \
  arduino/led_brightness_controller
```

The candidate validated on 2026-09-28 used 8156 bytes of flash and 472 bytes
of global RAM. The preserved deployed-v4 reference also compiles with this
toolchain; because its archival filename intentionally does not match its
directory name, copy it to an isolated temporary sketch directory with a
matching `.ino` basename before compiling. It used 9688 bytes of flash and 424
bytes of global RAM. These size figures are validation evidence, not fixed
acceptance thresholds.

Uploading is machine-specific and is not authorized by this document. Before
any upload, independently verify the exact serial device, board/bootloader,
external current limiting, LED gates OFF and a recovery path. The MKS and many
Nano-compatible boards may expose the same CH340 USB identifier; use a verified
physical/by-path identity rather than guessing `/dev/ttyUSB0`.

The main source is a newer safety-oriented candidate. The exact v4 source
captured with the accepted prototype is preserved under `reference/deployed-v4`
with its digest and evidence limitations.
