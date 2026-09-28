"""Shared command-boundary exceptions."""

from __future__ import annotations


class ScannerSyncCommandBoundaryError(ValueError):
    """Raised when a host-originated command record is unsafe or malformed."""
