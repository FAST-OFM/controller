"""Private telemetry payload safety guardrails."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ._fields import (
    DIAGNOSTIC_IDENTITY_SOURCES as _DIAGNOSTIC_IDENTITY_SOURCES,
    FORBIDDEN_PAYLOAD_FIELDS as _FORBIDDEN_PAYLOAD_FIELDS,
    FORBIDDEN_PAYLOAD_TOKENS as _FORBIDDEN_PAYLOAD_TOKENS,
    IDENTITY_SOURCE_FIELDS as _IDENTITY_SOURCE_FIELDS,
    UNSAFE_PAYLOAD_BOOLEAN_FIELDS as _UNSAFE_PAYLOAD_BOOLEAN_FIELDS,
)

_UNSAFE_PAYLOAD_VALUE_RE = re.compile(
    r"(^[a-z][a-z0-9+.-]*://)|(^|[\s:=])/(dev|sys|proc)/|"
    r"\b(serial|tty|gpio|gcode|klipper|motor|motion|move_z_now|"
    r"led_output|flash|firmware_flash|avrdude|dfu-util|openocd|bossac|picotool)\b",
    re.I,
)


def _validate_payload(payload: Mapping[str, Any], path: str) -> tuple[list[str], int, int]:
    errors: list[str] = []
    unsafe_count = 0
    diagnostic_count = 0
    for key, value in payload.items():
        key_text = str(key)
        normalized_key = key_text.lower()
        key_tokens = _name_tokens(key_text)
        child_path = f"{path}.{key_text}"
        if normalized_key in _FORBIDDEN_PAYLOAD_FIELDS or _forbidden_payload_key(key_tokens, value):
            unsafe_count += 1
            errors.append(f"{child_path}: forbidden telemetry payload field")
        if normalized_key in _UNSAFE_PAYLOAD_BOOLEAN_FIELDS and value is not False:
            unsafe_count += 1
            errors.append(f"{child_path}: expected false")
        if normalized_key in _IDENTITY_SOURCE_FIELDS:
            values = value if isinstance(value, list | tuple | set) else [value]
            forbidden = sorted(
                source
                for source in values
                if isinstance(source, str) and source in _DIAGNOSTIC_IDENTITY_SOURCES
            )
            if forbidden:
                diagnostic_count += len(forbidden)
                errors.append(
                    f"{child_path}: cannot use diagnostic clock/camera fields for identity: "
                    + ", ".join(forbidden)
                )
        if isinstance(value, Mapping):
            child_errors, child_unsafe_count, child_diagnostic_count = _validate_payload(value, child_path)
            errors.extend(child_errors)
            unsafe_count += child_unsafe_count
            diagnostic_count += child_diagnostic_count
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    child_errors, child_unsafe_count, child_diagnostic_count = _validate_payload(
                        item,
                        f"{child_path}[{index}]",
                    )
                    errors.extend(child_errors)
                    unsafe_count += child_unsafe_count
                    diagnostic_count += child_diagnostic_count
                elif isinstance(item, str) and _is_unsafe_payload_text(item):
                    unsafe_count += 1
                    errors.append(f"{child_path}[{index}]: forbidden live hardware/control value")
        elif isinstance(value, str) and _is_unsafe_payload_text(value):
            unsafe_count += 1
            errors.append(f"{child_path}: forbidden live hardware/control value")
    return errors, unsafe_count, diagnostic_count


def _name_tokens(name: str) -> set[str]:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).replace("-", "_").replace(".", "_")
    return {part.lower() for part in snake.split("_") if part}


def _forbidden_payload_key(key_tokens: set[str], value: Any) -> bool:
    forbidden_tokens = key_tokens.intersection(_FORBIDDEN_PAYLOAD_TOKENS)
    if not forbidden_tokens:
        return False
    if forbidden_tokens == {"path"} and isinstance(value, str) and value.startswith(("$", "#")):
        return False
    return True


def _is_unsafe_payload_text(value: str) -> bool:
    return bool(_UNSAFE_PAYLOAD_VALUE_RE.search(value))
