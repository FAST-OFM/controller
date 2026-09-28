"""Physical pin reference parsing for logical IO aliases."""

from __future__ import annotations

from dataclasses import dataclass
import re

from scanner_firmware.domain.io_aliases.errors import IoAliasRegistryError


UNKNOWN_PIN = "unknown"
_PIN_NAME_PATTERN = re.compile(r"^[A-Z]{1,3}[0-9]+$")


@dataclass(frozen=True)
class PinReference:
    """Physical pin token with Klipper-style inversion preserved."""

    raw: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw, str) or not self.raw:
            raise IoAliasRegistryError("pin must be a non-empty string")
        if self.raw == UNKNOWN_PIN:
            return
        name = self.name
        if not _PIN_NAME_PATTERN.fullmatch(name):
            raise IoAliasRegistryError(f"unsupported pin reference: {self.raw}")

    @property
    def inverted(self) -> bool:
        return self.raw.startswith("!")

    @property
    def name(self) -> str:
        return self.raw[1:] if self.inverted else self.raw

    @property
    def is_unknown(self) -> bool:
        return self.raw == UNKNOWN_PIN

    @property
    def key(self) -> str:
        """Return the exact normalized pin token, including inversion."""

        return self.raw

    @property
    def physical_key(self) -> str:
        """Return the physical pin identity without output inversion."""

        return self.name


def parse_pin_reference(value: object, *, field_name: str = "pin") -> PinReference:
    if not isinstance(value, str):
        raise IoAliasRegistryError(f"{field_name} must be a string")
    return PinReference(value)
