"""CLI for software-only firmware config ownership checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from scanner_firmware.domain.platform_config.config_split import (
    check_firmware_config_split_files,
    discover_static_config_paths,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scanner-firmware-config-split",
        description="Validate firmware-side static config ownership boundaries.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Static JSON/YAML config files to check. Defaults to firmware config candidates.",
    )
    parser.add_argument(
        "--check-static",
        action="store_true",
        help="Run software-only static config split checks.",
    )
    parser.add_argument(
        "--output",
        help="Write deterministic JSON report to this path instead of stdout.",
    )
    args = parser.parse_args(argv)

    if not args.check_static:
        parser.error("--check-static is required")

    repo_root = Path.cwd()
    paths = tuple(Path(path) for path in args.paths)
    if not paths:
        paths = discover_static_config_paths(repo_root)

    report = check_firmware_config_split_files(paths)
    output = report.to_json()
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
