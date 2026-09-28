# Board definition fragment for Klipper scripts/spi_flash/board_defs.py.
#
# This fragment was validated on the current scanner MKS Robin Mini V2.0 board
# using Klipper's flash-sdcard.sh remote SD upload path. It is intentionally a
# fragment because upstream Klipper owns board_defs.py.

MKS_ROBIN_MINI_V2_SCANNER_BOARD_DEF = {
    "mks-robin-mini-v2-scanner": {
        "mcu": "stm32f103xe",
        "spi_bus": "swspi",
        "spi_pins": "PC8,PD2,PC12",
        "cs_pin": "PC11",
        "skip_verify": True,
        "conversion_script": "scripts/update_mks_robin.py",
        "firmware_path": "Robin_mini.bin",
        "current_firmware_path": "Robin_mini.cur",
    }
}
