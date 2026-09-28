# Klipper Live Metadata Stage B Current Evidence

Status: read-only evidence captured for review. This document does not approve
Stage B live execution, firmware flashing, GPIO toggling, motion, camera
triggering or LED driving.

Captured: 2026-07-01T16:16:52+04:00 from `pi5` over SSH using the read-only
Stage B evidence script.

Tracking issues:

- Legacy private tracking references are intentionally omitted from the clean
  release snapshot.

## Commands Run

The latest inspection used the read-only evidence script over SSH:

```bash
ssh pi@192.0.2.13 'bash -s' < scripts/capture-klipper-stage-b-evidence.sh
```

No service restart, firmware flashing, Klipper command send, GPIO command,
motion command, camera trigger or LED command was run.

Future evidence captures should use:

```bash
scripts/capture-klipper-stage-b-evidence.sh > stage-b-evidence.md
```

Review the output before copying it into an issue or PR. Unknown values must
remain unknown if the script cannot read the source file.

## Observed Live State

```yaml
stage_b_current_evidence:
  live_pi_hostname: pi5
  captured_at: "2026-07-01T16:16:52+04:00"
  klipper_commit: "c707dd19214709dc23684b254a68e3bf69e4cfb3"
  klipper_branch_status: "master...origin/master"
  klipper_worktree_expected_untracked:
    - "klippy/extras/scanner_sync.py"
  klipper_service: active
  scanner_sync_config:
    section_present: true
    enable: false
    protocol_version: 1
    mode: UNKNOWN
    hardware_outputs_enabled: UNKNOWN
  serial_by_path:
    mks_candidate: "/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1:1.0-port0 -> ../../ttyUSB0"
    arduino_candidate: "/dev/serial/by-path/platform-xhci-hcd.1-usb-0:1:1.0-port0 -> ../../ttyUSB1"
  serial_by_id:
    usb_1a86: "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 -> ../../ttyUSB1"
  klippy_mcu_line:
    mcu: "stm32f103xe"
    clock_hz: 72000000
    adc_max: 4095
    firmware_version: "v0.13.0-699-gc707dd192"
    configured_moves: 1024
  klipper_build_config:
    CONFIG_LOW_LEVEL_OPTIONS: true
    CONFIG_MACH_STM32: true
    CONFIG_BOARD_DIRECTORY: "stm32"
    CONFIG_MCU: "stm32f103xe"
    CONFIG_CLOCK_FREQ: 72000000
    CONFIG_SERIAL: true
    CONFIG_FLASH_SIZE: "0x10000"
    CONFIG_FLASH_BOOT_ADDRESS: "0x8000000"
    CONFIG_FLASH_APPLICATION_ADDRESS: "0x8007000"
    CONFIG_MACH_STM32F103: true
    CONFIG_STM32_SERIAL_USART3: true
    CONFIG_SERIAL_BAUD: 250000
    CONFIG_HAVE_GPIO: true
    CONFIG_HAVE_STRICT_TIMING: true
    CONFIG_HAVE_BOOTLOADER_REQUEST: true
  live_dictionary_scanner_sync_tokens:
    config_scanner_sync: missing
    scanner_sync_start: missing
    scanner_sync_stop: missing
    scanner_sync_schedule_z: missing
    scanner_sync_frame_event: missing
    scanner_sync_scheduler_terminal: missing
    scanner_sync_z_scheduled: missing
    scanner_sync_z_applied: missing
    scanner_sync_z_rejected: missing
    scanner_sync_debug_emit: missing
```

## Scanner-Sync Config Evidence

Captured `printer.cfg` lines:

```text
269:[scanner_sync]
270:enable: false
271:protocol_version: 1
```

The retained live config is still safe-disabled. It does not provide Stage B
approval because the live MKS firmware still needs reviewed scanner-sync MCU
patch evidence before metadata-only enablement can be considered.

## Existing Output Pin Context

The `klippy.log` tail includes previously configured manual output pins and
macros:

- `camera_trigger` on `PC4`;
- `e_step_trigger` / `SCANNER_E_STEP_TRIGGER` for earlier trigger testing;
- `led_green_wifi` on `PA9`;
- `led_red_wifi` on `PA10`;
- `led_white_tc1` on `PB13`.

These existing outputs are not scanner-sync Stage B approval. Stage B must keep
scanner-sync output pins unset or `none`, and must not invoke these macros or
drive these pins.

## Evidence Still Missing

Stage B remains blocked until issue #201, issue #85 or a linked PR records:

- completed passive MKS flash/connectivity gate package, validated with
  `validate_mks_flash_gate_yaml`;
- captured Klipper `.config`, target dictionary, firmware binary, active
  `printer.cfg`, MKS serial paths and rollback plan;
- proof the MKS MCU handshake is restored with no unresolved
  `identify_response` timeout before any flash attempt;
- accepted scanner-sync host-extra diff;
- accepted MCU patch diff;
- exact firmware build command and output artifact for the MKS target;
- exact flashing method and rollback method;
- captured Klipper dictionary with scanner-sync command and response formats
  after a reviewed target build;
- full reviewed `printer.cfg` scanner-sync diff;
- proof `mode=metadata_only`;
- proof `hardware_outputs_enabled=false`;
- proof scanner-sync output pins are unset or `none`;
- expected callback JSONL capture;
- expected `scanner-klipper-decode-events --summary-json` acceptance report.

Unknown values above must remain `UNKNOWN` until captured from the live system
or reviewed artifacts. Do not infer them from hidden chat memory.
