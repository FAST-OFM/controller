# External RP2040 Sync-Board Fallback

## Concept

If modifying the motion firmware is slow, use a dedicated RP2040 board to monitor motion signals and generate scanner synchronization.

```text
Motion board STEP/DIR or encoder -> RP2040 sync board -> camera trigger + LED gates + frame metadata
```

## Benefits

- avoids deep motion firmware fork during early R&D;
- can work with Kingroon or SKR Pico driven by existing firmware;
- quickly validates Pi acquisition and LED/trigger pipeline;
- can later evolve into integrated MCU firmware.

## Limitations

- step monitoring sees commanded motion, not necessarily actual motion unless encoders are used;
- integration is more wiring-heavy;
- must handle acceleration/deceleration and direction changes carefully;
- needs clean electrical isolation/leveling.

## First test

First dry-run/bench test, with no scanner hardware connected:

- feed synthetic STEP pulses into RP2040 or a host simulator;
- keep camera and LED outputs disconnected or disabled.

Verify:

- trigger every N pulses;
- LED pattern sequence;
- frame event serial output;
- missed-pulse detection if possible.

Only connect motion-board STEP/DIR or external outputs after an approved
electrical review and bench-safe procedure.
