"""Frame id allocation for metadata-only frame publication."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.planning.frame_counter.common.validation import require_non_negative


@dataclass
class FrameIdAllocator:
    """Monotonic software-only frame id allocator."""

    first_frame_id: int = 0

    def __post_init__(self) -> None:
        require_non_negative("first_frame_id", self.first_frame_id)
        self._next_frame_id = self.first_frame_id

    @property
    def next_frame_id(self) -> int:
        return self._next_frame_id

    def allocate(self) -> int:
        frame_id = self._next_frame_id
        self._next_frame_id += 1
        return frame_id
