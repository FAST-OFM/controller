# Controller status

Release target: `v0.3.0-prototype.1`
Product status: research prototype; not clinically validated

## Prototype-verified

- MKS Robin Mini V2.0 running a Klipper build based on commit
  `c707dd19214709dc23684b254a68e3bf69e4cfb3`.
- Bounded host-orchestrated XYZ movement in stop-and-shoot scanning.
- Arduino Nano-compatible brightness controller at 62.5 kHz PWM.
- Deployed Arduino configuration v4 with the observed profile
  `RED150/GREEN150/WHITE255`.
- MKS illumination gates observed as GREEN `PA9`, RED `PA10`, WHITE `PB14`.

## Not release-verified

- Arduino v5/v6 source candidates were not the firmware deployed for the
  accepted scan.
- `scanner_sync`, frame-event scheduling and timed-output patches were disabled
  in the accepted scan.
- The Arduino flash was not read back; the retained hex digest is cache
  evidence, not proof of MCU contents.
- There is no verified physical homing or encoder position feedback.
- Stepper current limits, electrical margins and safe GPIO loading require
  machine-specific verification.

## Safe interpretation

Configuration examples are starting points, not universal board truth. Keep
experimental sync paths disabled, outputs off and motors disabled until the
companion hardware repository's pin, current and bring-up checks are completed.
