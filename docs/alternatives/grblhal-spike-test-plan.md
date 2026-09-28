# grblHAL Spike Test Plan

## Goal

Determine whether grblHAL's CNC/HAL/plugin architecture is a better base for scanner synchronization than Klipper.

## Tests

1. Run dry-run scheduler simulation against grblHAL-like position samples.
2. Add or simulate a plugin/custom output path for position-indexed events.
3. Emit `FRAME_EVENT` metadata without hardware outputs.
4. Only after approval, run constant velocity X motion on RP2040 target if
   possible.
5. Only after approval, add diagnostic trigger/LED-equivalent output signals.
6. Evaluate homing and limit integration.
7. Evaluate license and maintainability.

## Success criteria

- position-indexed trigger works without host jitter;
- scanner-specific logic can be isolated cleanly;
- motion planner remains upstream-compatible where possible;
- encoder input path is plausible.
