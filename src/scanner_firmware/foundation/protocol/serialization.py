"""JSON serialization helpers for scanner protocol records."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Union


JsonScalar = Union[str, int, float, bool, None]
JsonValue = Union[JsonScalar, List["JsonValue"], Dict[str, "JsonValue"]]
JsonDict = Dict[str, JsonValue]


class ProtocolSerializationError(ValueError):
    """Raised when an object cannot be represented as a protocol payload."""


class JsonRecordMixin:
    """Mixin for protocol dataclasses that serialize to JSON-safe objects."""

    def to_json_dict(self) -> JsonDict:
        return _json_safe(asdict(self))

    def to_json(self, **json_kwargs: Any) -> str:
        return json.dumps(self.to_json_dict(), **json_kwargs)


def to_json_dict(record: Any) -> JsonDict:
    if isinstance(record, JsonRecordMixin):
        return record.to_json_dict()
    if is_dataclass(record):
        return _json_safe(asdict(record))
    if isinstance(record, dict):
        return _json_safe(record)
    raise ProtocolSerializationError("expected protocol dataclass or dict")


def to_json(record: Any, **json_kwargs: Any) -> str:
    return json.dumps(to_json_dict(record), **json_kwargs)


def _json_safe(value: Any) -> JsonValue:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ProtocolSerializationError(
        "%s is not JSON-safe for protocol serialization" % type(value).__name__
    )
