"""Dry-run pipeline exceptions."""


class DryRunPipelineError(ValueError):
    """Raised when dry-run pipeline inputs cannot be safely connected."""
