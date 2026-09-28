"""Trigger-scheduler recipe errors."""


class ScanPlanError(ValueError):
    """Raised when scan recipe data cannot produce a safe dry-run schedule."""
