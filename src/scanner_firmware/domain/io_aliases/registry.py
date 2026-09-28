"""Logical IO alias registry policy."""

from __future__ import annotations

from dataclasses import dataclass

from scanner_firmware.domain.io_aliases.errors import IoAliasRegistryError
from scanner_firmware.domain.io_aliases.types import IoAliasEntry, RejectedActivePin


@dataclass(frozen=True)
class IoAliasRegistry:
    """Validated logical alias registry for software-only IO planning."""

    board_id: str
    aliases: tuple[IoAliasEntry, ...]
    rejected_active_pins: tuple[RejectedActivePin, ...]
    hardware_outputs_armed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.board_id, str) or not self.board_id:
            raise IoAliasRegistryError("board_id must be a non-empty string")
        if not isinstance(self.hardware_outputs_armed, bool):
            raise IoAliasRegistryError("hardware_outputs_armed must be a boolean")
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(
            self,
            "rejected_active_pins",
            tuple(self.rejected_active_pins),
        )
        self._validate_unique_aliases()
        self._validate_active_alias_pins()

    def get(self, name: str) -> IoAliasEntry:
        for entry in self.aliases:
            if entry.name == name:
                return entry
        raise IoAliasRegistryError(f"unknown IO alias: {name}")

    def active(self, name: str) -> IoAliasEntry:
        entry = self.get(name)
        if not entry.is_active:
            raise IoAliasRegistryError(f"IO alias is not active: {name}")
        return entry

    def candidates(self) -> tuple[IoAliasEntry, ...]:
        return tuple(entry for entry in self.aliases if entry.is_candidate)

    def active_aliases(self) -> tuple[IoAliasEntry, ...]:
        return tuple(entry for entry in self.aliases if entry.is_active)

    @property
    def rejected_active_pin_keys(self) -> tuple[str, ...]:
        return tuple(item.pin.key for item in self.rejected_active_pins)

    @property
    def rejected_active_physical_pin_keys(self) -> tuple[str, ...]:
        return tuple(item.pin.physical_key for item in self.rejected_active_pins)

    def _validate_unique_aliases(self) -> None:
        seen: set[str] = set()
        duplicates: list[str] = []
        for entry in self.aliases:
            if entry.name in seen:
                duplicates.append(entry.name)
            seen.add(entry.name)
        if duplicates:
            raise IoAliasRegistryError(
                f"duplicate IO alias name(s): {', '.join(sorted(set(duplicates)))}"
            )

    def _validate_active_alias_pins(self) -> None:
        rejected = set(self.rejected_active_pin_keys)
        rejected_physical = set(self.rejected_active_physical_pin_keys)
        for entry in self.aliases:
            if entry.status in ("superseded", "rejected") and entry.is_active:
                raise IoAliasRegistryError(
                    f"superseded or rejected IO alias cannot be active: {entry.name}"
                )
            if not entry.is_active or entry.active_alias_reviewed:
                continue
            if entry.pin.key in rejected or entry.pin.physical_key in rejected_physical:
                raise IoAliasRegistryError(
                    f"active IO alias {entry.name} uses rejected pin {entry.pin.raw}"
                )
