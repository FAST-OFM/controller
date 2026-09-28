"""Logical LED pattern resolution."""

from __future__ import annotations

import re

from scanner_firmware.planning.led_scheduler.constants import (
    LED_GREEN_GATE,
    LED_RED_GATE,
    LED_WHITE_GATE,
)
from scanner_firmware.planning.led_scheduler.errors import LedPatternError, LedTimingError
from scanner_firmware.planning.led_scheduler.types import LedPattern


LOGICAL_GATE_NAME = re.compile(r"^led_[a-z0-9_]+$")

DEFAULT_LED_PATTERNS: dict[str, LedPattern] = {
    "BF_WHITE": LedPattern(
        pattern="BF_WHITE",
        gate_names=(LED_WHITE_GATE,),
        frame_use="tile",
    ),
    "AF_RED_GREEN": LedPattern(
        pattern="AF_RED_GREEN",
        gate_names=(LED_RED_GATE, LED_GREEN_GATE),
        frame_use="autofocus",
    ),
    "DARK": LedPattern(
        pattern="DARK",
        gate_names=(),
        frame_use="diagnostics",
    ),
}


class LogicalLedPatternResolver:
    """Resolve scan pattern names into logical LED gate names."""

    def __init__(self, patterns: dict[str, LedPattern] | None = None):
        self._patterns = patterns or DEFAULT_LED_PATTERNS

    def resolve(self, pattern: str) -> LedPattern:
        try:
            return self._patterns[pattern]
        except KeyError as exc:
            raise LedPatternError(f"unknown LED pattern: {pattern}") from exc


def validate_logical_gate_name(gate_name: str) -> None:
    if not LOGICAL_GATE_NAME.match(gate_name):
        raise LedTimingError(f"LED gate must be a logical alias, got: {gate_name}")
