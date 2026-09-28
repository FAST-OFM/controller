# MKS Robin Mini V2.0 prototype example

`observed-prototype.cfg` is a sanitized, non-portable record of the relevant
Klipper configuration used by one Fast OFM prototype. It is not a generic MKS
board profile and must not be copied directly to a new machine.

Before use, verify at minimum:

- the exact board/MCU build and serial device;
- motor current/Vref values and thermal margin;
- direction, rotation distance and conservative travel bounds;
- physical endstops or an explicit bounded local-reference procedure;
- that `PA9`, `PA10` and `PB14` are safe logic-only inputs to external LED
  drivers and are OFF during boot/shutdown;
- that no LED current is sourced directly from MCU GPIO.

The accepted prototype used no verified homing or encoder. The example leaves
the original virtual-reference behavior visible because hiding it would make
the evidence misleading, but it is not suitable for production safety.

Experimental camera-trigger and `scanner_sync` sections are intentionally
absent. They were not enabled in the accepted scan.
