"""Private telemetry envelope type-validation helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _require_literal(
    payload: Mapping[str, Any],
    field: str,
    expected: Any,
    path: str,
    errors: list[str],
) -> None:
    value = payload.get(field)
    if value != expected:
        errors.append(f"{path}.{field}: expected {expected!r}, got {value!r}")


def _string(value: Any, path: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value:
        errors.append(f"{path}: expected non-empty string")
        return ""
    return value


def _non_negative_int(value: Any, path: str, errors: list[str]) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"{path}: expected non-negative integer")
        return 0
    return value


def _copy_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))
