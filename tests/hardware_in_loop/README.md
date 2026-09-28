# hardware_in_loop

HIL scaffolding notes.

No HIL tests are approved by this repository state.

Before any HIL test:

- the equivalent simulator test must pass;
- the exact board, driver model and wiring must be documented;
- the command sequence must be reviewed;
- emergency stop/power-off must be defined;
- LEDs, camera trigger and unrelated GPIO outputs must remain disabled unless
  explicitly in scope.

HIL tests must be separate from host-side simulator tests so CI or local unit
tests cannot accidentally access hardware.
