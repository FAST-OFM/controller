"""Board profile evidence state machine.

The state machine validates documentation/config metadata only. It does not
probe boards, infer electrical facts, flash firmware, command motion or toggle
outputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal


BoardProfileState = Literal[
    "placeholder",
    "identity_candidate",
    "identity_verified",
    "pinmap_candidate",
    "pinmap_verified",
    "hardware_tested",
    "superseded",
]

BOARD_PROFILE_STATES: tuple[BoardProfileState, ...] = (
    "placeholder",
    "identity_candidate",
    "identity_verified",
    "pinmap_candidate",
    "pinmap_verified",
    "hardware_tested",
    "superseded",
)

VERIFIED_PINMAP_EVIDENCE_FIELDS = (
    "voltage_levels_measured",
    "load_behavior_tested",
    "boot_default_states_measured",
)
HARDWARE_TESTED_EVIDENCE_FIELDS = (
    "hardware_test_report",
    "safe_test_procedure_reviewed",
)


class BoardProfileStateError(ValueError):
    """Raised when board profile evidence state is inconsistent."""


def validate_board_profile_state(profile: Mapping[str, object]) -> None:
    """Validate profile state without converting candidates into facts."""

    state = profile_state(profile)
    if state == "superseded" and _is_active_profile(profile):
        raise BoardProfileStateError("superseded board profiles cannot be active")
    if state in ("pinmap_verified", "hardware_tested"):
        _validate_pinmap_verified_evidence(profile, state=state)
    if state == "hardware_tested":
        _validate_hardware_tested_evidence(profile)


def profile_state(profile: Mapping[str, object]) -> BoardProfileState:
    raw_state = profile.get("profile_state", profile.get("status"))
    if not isinstance(raw_state, str):
        raise BoardProfileStateError("profile_state must be declared")
    normalized = raw_state.strip().lower()
    if normalized not in BOARD_PROFILE_STATES:
        raise BoardProfileStateError(
            "profile_state must be one of: " + ", ".join(BOARD_PROFILE_STATES)
        )
    return normalized  # type: ignore[return-value]


def is_pinmap_candidate(profile: Mapping[str, object]) -> bool:
    return profile_state(profile) == "pinmap_candidate"


def _validate_pinmap_verified_evidence(
    profile: Mapping[str, object],
    *,
    state: BoardProfileState,
) -> None:
    raw_evidence = profile.get("verification_evidence")
    evidence = raw_evidence if isinstance(raw_evidence, Mapping) else {}
    missing = [
        field
        for field in VERIFIED_PINMAP_EVIDENCE_FIELDS
        if evidence.get(field) is not True
    ]
    if missing:
        raise BoardProfileStateError(
            f"{state} requires accepted voltage, load and boot/default-state evidence: "
            + ", ".join(missing)
        )


def _validate_hardware_tested_evidence(profile: Mapping[str, object]) -> None:
    evidence = _mapping(profile.get("verification_evidence"), "verification_evidence")
    missing = [
        field
        for field in HARDWARE_TESTED_EVIDENCE_FIELDS
        if not _truthy_evidence_value(evidence.get(field))
    ]
    if missing:
        raise BoardProfileStateError(
            "hardware_tested requires reviewed hardware test evidence: "
            + ", ".join(missing)
        )


def _is_active_profile(profile: Mapping[str, object]) -> bool:
    active = profile.get("profile_active", True)
    if not isinstance(active, bool):
        raise BoardProfileStateError("profile_active must be a boolean")
    return active


def _state_index(state: BoardProfileState) -> int:
    return BOARD_PROFILE_STATES.index(state)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BoardProfileStateError(f"{name} must be a mapping")
    return value


def _truthy_evidence_value(value: object) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and bool(value.strip()) and value != "unknown"
