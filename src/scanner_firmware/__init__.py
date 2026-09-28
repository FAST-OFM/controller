"""Scanner firmware compatibility namespace.

The canonical implementation is still in flat top-level packages during
the namespace migration. Layered modules under ``scanner_firmware``
re-export those implementations so existing type identities remain stable.
"""

__all__ = ("foundation", "domain", "planning", "adapters")
