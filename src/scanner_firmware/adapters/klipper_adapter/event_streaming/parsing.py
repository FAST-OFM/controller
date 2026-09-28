"""Parsing and decoding helpers for passive scanner-sync callback streams."""

from __future__ import annotations

import json
from typing import Any, Iterable

from scanner_firmware.adapters.klipper_adapter.event_streaming.model import (
    PROTOCOL_EVENT_TYPES,
    RawScannerSyncEvent,
    ScannerSyncEventStreamError,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.decode import (
    decode_scanner_sync_response,
)
from scanner_firmware.adapters.klipper_adapter.sync_codec.types import ScannerSyncDecodeContext
from scanner_firmware.foundation.protocol.events import ProtocolRecord


def decode_raw_scanner_sync_event(
    payload: dict[str, Any],
    *,
    context: ScannerSyncDecodeContext,
    require_event_type: bool = False,
) -> ProtocolRecord:
    """Decode one captured scanner-sync callback payload into a protocol record."""

    raw_event = parse_raw_scanner_sync_event(
        payload,
        require_event_type=require_event_type,
    )
    return decode_scanner_sync_response(
        raw_event.event_type,
        raw_event.params,
        context=context,
    )


def decode_scanner_sync_json_lines(
    lines: Iterable[str],
    *,
    context: ScannerSyncDecodeContext,
    require_event_type: bool = False,
) -> list[ProtocolRecord]:
    """Decode newline-delimited JSON scanner-sync callback payloads."""

    records: list[ProtocolRecord] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ScannerSyncEventStreamError(
                f"line {line_number}: invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ScannerSyncEventStreamError(
                f"line {line_number}: expected JSON object"
            )
        try:
            records.append(
                decode_raw_scanner_sync_event(
                    payload,
                    context=context,
                    require_event_type=require_event_type,
                )
            )
        except ValueError as exc:
            raise ScannerSyncEventStreamError(f"line {line_number}: {exc}") from exc
    return records


def parse_raw_scanner_sync_event(
    payload: dict[str, Any],
    *,
    require_event_type: bool = False,
) -> RawScannerSyncEvent:
    """Parse the minimal host callback wrapper around scanner-sync params."""

    if require_event_type and "event_type" not in payload:
        raise ScannerSyncEventStreamError("scanner-sync event requires event_type")

    event_type = payload.get("event_type", payload.get("type"))
    if event_type not in PROTOCOL_EVENT_TYPES:
        raise ScannerSyncEventStreamError(f"unsupported scanner-sync event type: {event_type!r}")

    params = payload.get("params")
    if not isinstance(params, dict):
        raise ScannerSyncEventStreamError("scanner-sync event requires object params")

    return RawScannerSyncEvent(event_type=event_type, params=params)
