"""Logical LED scheduler errors."""


class LedPatternError(ValueError):
    """Raised when a logical LED pattern is unknown or unsafe."""


class LedTimingError(ValueError):
    """Raised when a logical LED timing plan is invalid or unsafe."""
