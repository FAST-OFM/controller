"""Validation helpers for frame counter records."""

from __future__ import annotations


def require_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be bool")


def require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def require_non_negative(name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative int")


def tuple_of_str(values: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(values)
    if not all(isinstance(value, str) for value in result):
        raise ValueError("expected a tuple of strings")
    return result
