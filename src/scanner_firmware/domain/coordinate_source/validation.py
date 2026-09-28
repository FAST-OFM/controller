"""Coordinate-source validation helpers."""

from __future__ import annotations

from scanner_firmware.domain.coordinate_source.errors import CoordinateSourceError


def require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CoordinateSourceError(f"{name} must be an integer")


def require_encoder_health(
    name: str,
    value: object,
    allowed_values: tuple[str, ...],
) -> None:
    if value not in allowed_values:
        raise CoordinateSourceError(f"{name} must be healthy, unhealthy or unknown")
