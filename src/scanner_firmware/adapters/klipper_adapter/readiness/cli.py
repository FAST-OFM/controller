"""Command-line helpers for passive Klipper scanner-sync checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from scanner_firmware.adapters.klipper_adapter.readiness.config_parser import parse_scanner_sync_config
from scanner_firmware.adapters.klipper_adapter.readiness.dictionary import (
    observation_from_dictionary,
    scan_scanner_sync_dictionary,
)
from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import evaluate_live_metadata_readiness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scanner-klipper-readiness",
        description="Passively evaluate scanner-sync readiness from Klipper dictionary text.",
    )
    parser.add_argument(
        "dictionary",
        nargs="?",
        default="-",
        help="Path to captured klipper.dict/log text, or '-' for stdin.",
    )
    parser.add_argument("--host-extra-present", action="store_true")
    parser.add_argument("--config-section-present", action="store_true")
    parser.add_argument("--config-enable", action="store_true")
    parser.add_argument(
        "--config-file",
        "--config",
        dest="config_file",
        help=(
            "Captured printer.cfg text. If provided, [scanner_sync] supplies "
            "config-section, enable, protocol-version and safety-mode fields."
        ),
    )
    parser.add_argument("--mcu-connected", action="store_true")
    parser.add_argument("--response-dispatch-available", action="store_true")
    parser.add_argument("--hardware-outputs-enabled", action="store_true")
    parser.add_argument("--non-metadata-only", action="store_true")
    parser.add_argument("--protocol-version", type=int, default=1)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero unless readiness status is ready.",
    )
    args = parser.parse_args(argv)

    text = _read_dictionary_text(args.dictionary, sys.stdin)
    config = None
    if args.config_file:
        config = parse_scanner_sync_config(Path(args.config_file).read_text())

    capabilities = scan_scanner_sync_dictionary(text)
    observation = observation_from_dictionary(
        text,
        host_extra_present=args.host_extra_present,
        config_section_present=(
            config.section_present if config is not None else args.config_section_present
        ),
        config_enable=config.enable if config is not None else args.config_enable,
        mcu_connected=args.mcu_connected,
        response_dispatch_available=args.response_dispatch_available,
        metadata_only_mode=(
            config.metadata_only_mode if config is not None else not args.non_metadata_only
        ),
        hardware_outputs_enabled=(
            config.hardware_outputs_enabled
            if config is not None
            else args.hardware_outputs_enabled
        ),
        config_safety_fields_present=(
            config.safety_fields_present if config is not None else True
        ),
        configured_output_keys=config.configured_output_keys if config is not None else (),
        protocol_version=config.protocol_version if config is not None else args.protocol_version,
    )
    readiness = evaluate_live_metadata_readiness(observation)

    payload = {
        "stage": readiness.stage,
        "status": readiness.status,
        "config_source": "file" if config is not None else "flags",
        "can_enable_scanner_sync": readiness.can_enable_scanner_sync,
        "blockers": list(readiness.blockers),
        "missing_command_formats": list(readiness.missing_command_formats),
        "missing_response_formats": list(readiness.missing_response_formats),
        "has_all_required_commands": capabilities.has_all_required_commands,
        "has_all_required_responses": capabilities.has_all_required_responses,
        "configured_output_keys": (
            list(config.configured_output_keys) if config is not None else []
        ),
    }
    print(json.dumps(payload, sort_keys=True))

    if args.require_ready and not readiness.can_enable_scanner_sync:
        return 1
    return 0


def _read_dictionary_text(path: str, stdin: TextIO) -> str:
    if path == "-":
        return stdin.read()
    return Path(path).read_text()


if __name__ == "__main__":
    raise SystemExit(main())
