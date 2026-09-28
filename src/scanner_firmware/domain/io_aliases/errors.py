"""Logical IO alias registry errors."""

from __future__ import annotations


class IoAliasRegistryError(ValueError):
    """Raised when an IO alias registry config is invalid or unsafe to resolve."""
