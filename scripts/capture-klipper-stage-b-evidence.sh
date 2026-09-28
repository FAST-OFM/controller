#!/usr/bin/env bash
set -eu

# Read-only Stage B evidence capture for a Pi/Klipper checkout.
#
# This script does not restart services, flash firmware, send G-code, open
# serial devices, toggle GPIO, command motion, trigger cameras or drive LEDs.

KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
PRINTER_CFG="${PRINTER_CFG:-$HOME/printer_data/config/printer.cfg}"
KLIPPY_LOG="${KLIPPY_LOG:-$HOME/printer_data/logs/klippy.log}"
DICT_PATH="${DICT_PATH:-$KLIPPER_DIR/out/klipper.dict}"
TMP_STATUS="$(mktemp)"
trap 'rm -f "$TMP_STATUS"' EXIT

section() {
  printf '\n## %s\n\n' "$1"
}

run_or_unknown() {
  "$@" 2>/dev/null || printf 'UNKNOWN\n'
}

section "Capture Metadata"
printf 'captured_at: "%s"\n' "$(date -Is)"
printf 'hostname: "%s"\n' "$(hostname)"
printf 'user: "%s"\n' "$(id -un)"

section "Klipper Checkout"
printf 'klipper_dir: "%s"\n' "$KLIPPER_DIR"
printf 'klipper_commit: "%s"\n' "$(run_or_unknown git -C "$KLIPPER_DIR" rev-parse HEAD)"
printf 'klipper_status:\n'
if git -C "$KLIPPER_DIR" status --short --branch >"$TMP_STATUS" 2>/dev/null; then
  sed 's/^/  /' "$TMP_STATUS"
else
  printf '  UNKNOWN\n'
fi

section "Klipper Service"
printf 'klipper_service_active: "%s"\n' "$(run_or_unknown systemctl is-active klipper)"

section "Scanner Sync Config"
printf 'printer_cfg: "%s"\n' "$PRINTER_CFG"
if [ -f "$PRINTER_CFG" ]; then
  grep -n \
    -e '^\[scanner_sync\]' \
    -e '^enable[[:space:]]*[:=]' \
    -e '^protocol_version[[:space:]]*[:=]' \
    -e '^mode[[:space:]]*[:=]' \
    -e '^hardware_outputs_enabled[[:space:]]*[:=]' \
    "$PRINTER_CFG" || true
else
  printf 'UNKNOWN: printer.cfg not found\n'
fi

section "Serial Paths"
printf 'serial_by_path:\n'
if [ -d /dev/serial/by-path ]; then
  ls -l /dev/serial/by-path | sed 's/^/  /'
else
  printf '  UNKNOWN\n'
fi
printf '\nserial_by_id:\n'
if [ -d /dev/serial/by-id ]; then
  ls -l /dev/serial/by-id | sed 's/^/  /'
else
  printf '  UNKNOWN\n'
fi

section "Klipper Build Config"
printf 'klipper_dot_config: "%s/.config"\n' "$KLIPPER_DIR"
if [ -f "$KLIPPER_DIR/.config" ]; then
  grep -E \
    '^(CONFIG_MACH|CONFIG_MACH_STM32|CONFIG_MCU|CONFIG_CLOCK_FREQ|CONFIG_STM32|CONFIG_BOOTLOADER|CONFIG_USB|CONFIG_SERIAL|CONFIG_FLASH|CONFIG_LOW_LEVEL|CONFIG_BOARD|CONFIG_WANT|CONFIG_HAVE)' \
    "$KLIPPER_DIR/.config" || true
else
  printf 'UNKNOWN: .config not found\n'
fi

section "Scanner Sync Dictionary Tokens"
printf 'dictionary_path: "%s"\n' "$DICT_PATH"
if [ -f "$DICT_PATH" ]; then
  for token in \
    config_scanner_sync \
    scanner_sync_start \
    scanner_sync_stop \
    scanner_sync_schedule_z \
    scanner_sync_run_stationary_af_test \
    scanner_sync_frame_event \
    scanner_sync_scheduler_terminal \
    scanner_sync_z_scheduled \
    scanner_sync_z_applied \
    scanner_sync_z_rejected \
    scanner_sync_debug_emit
  do
    if grep -q "$token" "$DICT_PATH"; then
      printf '%s: present\n' "$token"
    else
      printf '%s: missing\n' "$token"
    fi
  done
else
  printf 'UNKNOWN: dictionary not found\n'
fi

section "Klippy Log Tail"
printf 'klippy_log: "%s"\n' "$KLIPPY_LOG"
if [ -f "$KLIPPY_LOG" ]; then
  tail -120 "$KLIPPY_LOG"
else
  printf 'UNKNOWN: klippy.log not found\n'
fi
