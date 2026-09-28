"""Frame event publisher errors."""


class FrameEventPublishError(ValueError):
    """Base error for invalid planned frame publication inputs."""


class DuplicatePlannedFrameError(FrameEventPublishError):
    """Raised when the same planned trigger is published twice."""


class FramePublishScopeError(FrameEventPublishError):
    """Raised when publication violates per-stream terminal state."""


class FramePublishTerminalError(FrameEventPublishError):
    """Raised when terminal summary semantics are invalid."""
