# Klipper Scanner-Sync Phase 3 Stationary AF Live-Output Patch Report

Status: disposable Pi 5 software build evidence only. This report does not
approve flashing the MKS controller, restarting the live Klipper service,
toggling GPIO, triggering the camera, driving LEDs or moving motors.

## Scope

Phase 3 adds a reviewed patch artifact for a no-motion stationary autofocus
timing bench command:

- patch artifact:
  `docs/patches/klipper-scanner-sync-phase3-stationary-af-live-output.patch`;
- host extra mode: `stationary_af_bench`;
- G-code command: `SCANNER_SYNC_RUN_STATIONARY_AF_TEST`;
- MCU command: `scanner_sync_run_stationary_af_test`;
- hardware outputs are allowed only when `hardware_outputs_enabled: true` and
  all four pins are explicitly configured;
- the sequence is stationary and does not command steppers, homing or motion.

## Intended Bench Sequence

For each requested frame:

1. hold XVS inactive;
2. turn white off;
3. turn red and green on together;
4. wait `SETTLE_US`;
5. assert XVS for `XVS_TRIGGER_PULSE_US`;
6. emit `scanner_sync_frame_event`;
7. keep red/green active until `EXPOSURE_HOLD_US`;
8. turn red/green off together;
9. restore white until the next AF window.

`scanner_sync_stop` and MCU shutdown drive all scanner-sync outputs inactive.

## Pi 5 Software Build Evidence

Target:

- host: `pi@192.0.2.13`;
- hostname: `pi5`;
- disposable checkout:
  `/tmp/fast-ofm-klipper-phase3-test`;
- live checkout source commit: `c707dd192`;
- toolchain: `arm-none-eabi-gcc (15:12.2.rel1-1) 12.2.1 20221205`;
- Python: `Python 3.11.2`;
- board config copied from live `~/klipper/.config`;
- MCU target: `stm32f103xe`;
- serial: USART3, 250000 baud;
- boot offset: `0x8007000`.

Commands run:

```bash
git clone --quiet ~/klipper /tmp/fast-ofm-klipper-phase3-test
cp ~/klipper/.config /tmp/fast-ofm-klipper-phase3-test/.config
cd /tmp/fast-ofm-klipper-phase3-test
git apply --check /tmp/klipper-scanner-sync-phase3.patch
git apply /tmp/klipper-scanner-sync-phase3.patch
python3 -m py_compile klippy/extras/scanner_sync.py
make -j2
```

Result:

- `python3 -m py_compile klippy/extras/scanner_sync.py`: passed;
- STM32/MKS firmware build: passed;
- output binary: `out/klipper.bin`;
- output dictionary: `out/klipper.dict`.

Artifact hashes from the disposable Pi build:

```text
1ac5ebd1f8a16b5731f1e525b6f285c3640b8e1a04e27f5f947dcc195d903bf2  out/klipper.bin
4c259f82069ffcd4d462ad03c6ec4d0747c81685729a26a9d0868ae25ae717b4  out/klipper.dict
```

The generated dictionary contains:

- `config_scanner_sync oid=%c protocol_version=%c hardware_outputs_enabled=%c`;
- `config_scanner_sync_output oid=%c output=%c pin=%u active_high=%c`;
- `scanner_sync_start oid=%c next_frame_id=%u`;
- `scanner_sync_stop oid=%c reason=%c`;
- `scanner_sync_schedule_z oid=%c seq=%u stripe_id=%u target_kind=%c target_value=%i z_target_nm=%i`;
- `scanner_sync_arm_af_window oid=%c seq=%u stripe_id=%u frame_id=%u stripe_frame_index=%u position_axis=%c trigger_position_count=%i pattern_id=%u settle_us=%u xvs_trigger_pulse_us=%u exposure_hold_us=%u`;
- `scanner_sync_fire_af_window_now oid=%c seq=%u stripe_id=%u frame_id=%u stripe_frame_index=%u position_axis=%c event_position_count=%i pattern_id=%u settle_us=%u xvs_trigger_pulse_us=%u exposure_hold_us=%u`;
- `scanner_sync_run_stationary_af_test oid=%c seq=%u stripe_id=%u first_frame_id=%u frame_count=%u frame_period_us=%u position_axis=%c event_position_count=%i pattern_id=%u settle_us=%u xvs_trigger_pulse_us=%u exposure_hold_us=%u`;
- `scanner_sync_frame_event ...`;
- `scanner_sync_scheduler_terminal ...`;
- `scanner_sync_z_scheduled ...`;
- `scanner_sync_z_applied ...`;
- `scanner_sync_z_rejected ...`.

## Hostsimulator Follow-Up

An additional `CONFIG_MACH_SIMU` build was attempted for the Klippy regression
test fixture. It failed before Klippy execution with:

```text
Multiple definitions for command 'identify'
make: *** [Makefile:84: out/compile_time_request.o] Error 255
```

The duplicate compile-time request output repeated both base Klipper commands
and scanner-sync commands. The STM32/MKS target build did not exhibit this
failure and successfully produced `out/klipper.bin` and `out/klipper.dict`.

This hostsimulator issue should be handled before relying on Klippy regression
tests as the acceptance gate for Phase 3. It does not block reviewing the
STM32/MKS compile result, but it does block claiming full Klipper test coverage.

## Safety Boundary

This evidence did not:

- patch the live `~/klipper` checkout;
- change `printer.cfg`;
- restart Klipper;
- flash MKS firmware;
- enable `[scanner_sync]`;
- send `SCANNER_SYNC_RUN_STATIONARY_AF_TEST` to live Klipper;
- toggle GPIO;
- trigger the HQ camera;
- drive LEDs;
- move motors.

## Next Controlled Step

Before hardware execution:

1. apply the reviewed patch to the live Klipper checkout;
2. rebuild the MKS firmware from the reviewed patch;
3. prepare the SD-card flash artifact and rollback copy;
4. explicitly review `[scanner_sync]` pin configuration and polarity:
   - `xvs_trigger_pin`: current candidate `PD6`;
   - `led_green_pin`: current candidate `PA9`;
   - `led_red_pin`: current candidate `PA10`;
   - `led_white_pin`: current candidate `PB13`;
5. flash MKS only after explicit human approval;
6. start with a short oscilloscope-only stationary test before camera/LED use.
