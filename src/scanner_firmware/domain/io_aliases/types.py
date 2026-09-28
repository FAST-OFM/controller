"""Logical IO alias registry value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.domain.io_aliases.errors import IoAliasRegistryError
from scanner_firmware.domain.io_aliases.pin_ref import PinReference


AliasStatus = Literal["candidate", "active", "superseded", "rejected"]
ElectricalValue = Literal[0, 1, "unknown"]
LoadStatus = Literal["not_load_tested", "load_tested", "unknown"]

ALIAS_STATUSES: tuple[AliasStatus, ...] = (
    "candidate",
    "active",
    "superseded",
    "rejected",
)
ELECTRICAL_VALUES: tuple[ElectricalValue, ...] = (0, 1, "unknown")
LOAD_STATUSES: tuple[LoadStatus, ...] = ("not_load_tested", "load_tested", "unknown")


@dataclass(frozen=True)
class OutputState:
    """Declared output levels for a logical alias.

    Unknown means the registry has no reviewed evidence for that value. It is
    intentionally not inferred from pin inversion or candidate status.
    """

    active_value: ElectricalValue = "unknown"
    inactive_value: ElectricalValue = "unknown"

    def __post_init__(self) -> None:
        _require_electrical_value("active_value", self.active_value)
        _require_electrical_value("inactive_value", self.inactive_value)


@dataclass(frozen=True)
class IoAliasEntry:
    name: str
    pin: PinReference
    status: AliasStatus
    output_state: OutputState
    evidence: str
    load_status: LoadStatus = "unknown"
    active_alias_reviewed: bool = False
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_alias_name(self.name)
        if not isinstance(self.pin, PinReference):
            raise IoAliasRegistryError("pin must be a PinReference")
        if self.status not in ALIAS_STATUSES:
            raise IoAliasRegistryError(f"unsupported alias status: {self.status}")
        if not isinstance(self.output_state, OutputState):
            raise IoAliasRegistryError("output_state must be an OutputState")
        if not isinstance(self.evidence, str) or not self.evidence:
            raise IoAliasRegistryError("evidence must be a non-empty string")
        if self.load_status not in LOAD_STATUSES:
            raise IoAliasRegistryError(f"unsupported load_status: {self.load_status}")
        if not isinstance(self.active_alias_reviewed, bool):
            raise IoAliasRegistryError("active_alias_reviewed must be a boolean")
        object.__setattr__(self, "notes", tuple(self.notes))
        for note in self.notes:
            if not isinstance(note, str) or not note:
                raise IoAliasRegistryError("notes must contain non-empty strings")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_candidate(self) -> bool:
        return self.status == "candidate"


@dataclass(frozen=True)
class RejectedActivePin:
    pin: PinReference
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.pin, PinReference):
            raise IoAliasRegistryError("rejected pin must be a PinReference")
        if not isinstance(self.reason, str) or not self.reason:
            raise IoAliasRegistryError("rejected pin reason must be a non-empty string")


def _require_alias_name(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise IoAliasRegistryError("alias name must be a non-empty string")
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise IoAliasRegistryError(f"unsupported alias name: {value}")


def _require_electrical_value(name: str, value: object) -> None:
    if value not in ELECTRICAL_VALUES:
        raise IoAliasRegistryError(f"{name} must be 0, 1 or unknown")
