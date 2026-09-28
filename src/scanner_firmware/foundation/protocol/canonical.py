"""Canonical protocol-v1 normalization helpers."""

from __future__ import annotations

import json
from typing import Any

from scanner_firmware.foundation.protocol.serialization import (
    JsonDict,
    ProtocolSerializationError,
    to_json_dict,
)


CANONICAL_PROTOCOL_VERSION = "1.0.0"
PROTOTYPE_PROTOCOL_VERSION = 1


def to_canonical_v1_json_dict(record: Any) -> JsonDict:
    """Return a canonical protocol-v1 evidence payload.

    Existing bootstrap DTOs and fixtures may still use prototype compatibility
    shapes such as ``protocol_version=1`` and ``FRAME_EVENT.status="ok"``.
    This helper makes the normalization explicit for contract evidence without
    changing the prototype serializer used by current replay fixtures.
    """

    return canonicalize_protocol_v1_payload(to_json_dict(record))


def canonicalize_protocol_v1_payload(payload: JsonDict) -> JsonDict:
    """Normalize a JSON-safe protocol payload to the canonical v1 surface."""

    canonical = dict(payload)
    protocol_version = canonical.get("protocol_version")
    if protocol_version in (None, PROTOTYPE_PROTOCOL_VERSION):
        canonical["protocol_version"] = CANONICAL_PROTOCOL_VERSION
    elif protocol_version != CANONICAL_PROTOCOL_VERSION:
        raise ProtocolSerializationError(
            "unsupported protocol_version for canonical v1 evidence: %r"
            % protocol_version
        )

    if canonical.get("type") == "FRAME_EVENT" and canonical.get("status") == "ok":
        canonical["status"] = "OK"
    return canonical


def require_canonical_protocol_v1_payload(payload: JsonDict) -> JsonDict:
    """Reject persisted protocol-v1 evidence that still needs normalization."""

    canonical = canonicalize_protocol_v1_payload(payload)
    if canonical != payload:
        raise ProtocolSerializationError(
            "noncanonical protocol-v1 evidence: use canonical exporter before persisting"
        )
    return payload


def to_canonical_v1_json(record: Any, **json_kwargs: Any) -> str:
    return json.dumps(to_canonical_v1_json_dict(record), **json_kwargs)
