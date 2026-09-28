"""CLI for passive decoding of captured scanner-sync callback payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    ScannerSyncCaptureReport,
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.parsing import (
    decode_scanner_sync_json_lines,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.report import (
    build_scanner_sync_capture_report,
)
from scanner_firmware.adapters.klipper_adapter.event_streaming.validation import (
    validate_scanner_sync_event_sequence,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import (
    ScannerSyncCodecError,
    ScannerSyncDecodeContext,
)
from scanner_firmware.foundation.protocol.events import (
    ProtocolSerializationError,
    to_canonical_v1_json_dict,
)
from scanner_firmware.foundation.protocol.parsing import decode_protocol_json_lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scanner-klipper-decode-events",
        description=(
            "Passively decode captured scanner-sync JSONL callback payloads "
            "into project protocol JSONL records."
        ),
    )
    parser.add_argument(
        "events",
        nargs="?",
        default="-",
        help="Path to JSONL callback payloads, or '-' for stdin.",
    )
    parser.add_argument("--scan-id")
    parser.add_argument(
        "--input-format",
        choices=("raw", "protocol-records"),
        default="raw",
        help=(
            "Input JSONL shape: raw scanner-sync callback wrappers, or already "
            "serialized project protocol records."
        ),
    )
    parser.add_argument(
        "--output",
        help="Write decoded records or summary JSON to this path instead of stdout.",
    )
    parser.add_argument("--protocol-version", type=int, default=1)
    parser.add_argument(
        "--coordinate-source-used",
        default="step_indexed",
        choices=("step_indexed", "encoder_indexed", "hybrid"),
    )
    parser.add_argument(
        "--trigger-output-name",
        default="camera_or_sync_trigger",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Pattern name by numeric pattern_id order. May be repeated.",
    )
    parser.add_argument(
        "--validate-stream",
        action="store_true",
        help="Validate frame ordering and terminal counters before printing records.",
    )
    parser.add_argument(
        "--summary-json",
        action="store_true",
        help="Print one compact capture acceptance JSON object instead of decoded records.",
    )
    parser.add_argument("--expect-record-count", type=int)
    parser.add_argument("--expect-frame-count", type=int)
    parser.add_argument("--expect-terminal-count", type=int)
    parser.add_argument("--expect-first-frame-id", type=int)
    parser.add_argument("--expect-last-frame-id", type=int)
    parser.add_argument(
        "--expect-stripes-seen",
        help="Comma-separated stripe ids expected in the decoded capture, for example 0,1.",
    )
    args = parser.parse_args(argv)
    if args.input_format == "raw" and args.scan_id is None:
        parser.error("--scan-id is required for raw scanner-sync input")

    try:
        text = _read_text(args.events, sys.stdin)
        acceptance_mode = args.summary_json or args.validate_stream or _has_capture_expectations(args)
        if args.input_format == "protocol-records":
            records = decode_protocol_json_lines(text.splitlines())
        else:
            context = ScannerSyncDecodeContext(
                scan_id=args.scan_id,
                protocol_version=args.protocol_version,
                coordinate_source_used=args.coordinate_source_used,
                trigger_output_name=args.trigger_output_name,
                pattern_names=tuple(args.pattern),
            )
            records = decode_scanner_sync_json_lines(
                text.splitlines(),
                context=context,
                require_event_type=acceptance_mode,
            )
        if args.summary_json or _has_capture_expectations(args):
            report = build_scanner_sync_capture_report(records)
            _check_capture_expectations(report, args)
        elif args.validate_stream:
            validate_scanner_sync_event_sequence(records)
    except (
        ProtocolSerializationError,
        ScannerSyncCodecError,
        ScannerSyncEventStreamError,
    ) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    if args.summary_json:
        _write_output(json.dumps(report.to_json_dict(), sort_keys=True) + "\n", args.output)
        return 0

    output = "".join(
        json.dumps(to_canonical_v1_json_dict(record), sort_keys=True) + "\n"
        for record in records
    )
    _write_output(output, args.output)
    return 0


def _read_text(path: str, stdin: TextIO) -> str:
    if path == "-":
        return stdin.read()
    return Path(path).read_text()


def _write_output(text: str, path: str | None) -> None:
    if path is None:
        print(text, end="")
        return
    Path(path).write_text(text, encoding="utf-8")


def _has_capture_expectations(args: argparse.Namespace) -> bool:
    return any(
        value is not None
        for value in (
            args.expect_record_count,
            args.expect_frame_count,
            args.expect_terminal_count,
            args.expect_first_frame_id,
            args.expect_last_frame_id,
            args.expect_stripes_seen,
        )
    )


def _check_capture_expectations(
    report: ScannerSyncCaptureReport,
    args: argparse.Namespace,
) -> None:
    expected_values = (
        ("record_count", args.expect_record_count, report.record_count),
        ("frame_count", args.expect_frame_count, report.validation.frame_count),
        ("terminal_count", args.expect_terminal_count, report.validation.terminal_count),
        ("first_frame_id", args.expect_first_frame_id, report.validation.first_frame_id),
        ("last_frame_id", args.expect_last_frame_id, report.validation.last_frame_id),
    )
    for name, expected, actual in expected_values:
        if expected is not None and expected != actual:
            raise ScannerSyncEventStreamError(
                f"{name} expectation failed: expected {expected}, got {actual}"
            )

    if args.expect_stripes_seen is not None:
        expected_stripes = _parse_expected_stripes(args.expect_stripes_seen)
        if expected_stripes != report.validation.stripes_seen:
            raise ScannerSyncEventStreamError(
                "stripes_seen expectation failed: "
                f"expected {list(expected_stripes)}, got {list(report.validation.stripes_seen)}"
            )


def _parse_expected_stripes(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    try:
        return tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ScannerSyncEventStreamError("--expect-stripes-seen must contain integers") from exc


if __name__ == "__main__":
    raise SystemExit(main())
