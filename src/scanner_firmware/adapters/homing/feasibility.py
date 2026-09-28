"""Software-only homing feasibility contracts.

These value objects keep unresolved homing evidence explicit. They do not
contact controllers, read endstops, move motors, toggle outputs or interpret a
Klipper ``homing_override`` as physical homing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Axis = Literal["X", "Y", "Z"]
HomingEvidenceOutcome = Literal[
    "unknown",
    "not_supported",
    "bench_only",
    "candidate_with_limits",
    "accepted",
]
HomingImplementationStatus = Literal["implemented", "not_implemented", "unknown"]
SensorlessSupport = Literal["supported", "not_supported", "unknown"]
HomingSourceName = Literal["physical_switch", "sensorless", "encoder_index"]

REQUIRED_HOMING_AXES: tuple[Axis, ...] = ("X", "Y", "Z")
HOMING_EVIDENCE_OUTCOMES: tuple[HomingEvidenceOutcome, ...] = (
    "unknown",
    "not_supported",
    "bench_only",
    "candidate_with_limits",
    "accepted",
)
HOMING_IMPLEMENTATION_STATUSES: tuple[HomingImplementationStatus, ...] = (
    "implemented",
    "not_implemented",
    "unknown",
)
SENSORLESS_SUPPORT_VALUES: tuple[SensorlessSupport, ...] = (
    "supported",
    "not_supported",
    "unknown",
)


@dataclass(frozen=True)
class AxisHomingFeasibility:
    """Per-axis evidence for possible homing sources."""

    axis: Axis
    physical_switch: HomingEvidenceOutcome = "unknown"
    sensorless: HomingEvidenceOutcome = "unknown"
    encoder_index: HomingEvidenceOutcome = "unknown"
    driver_type: str = "unknown"
    sensorless_support: SensorlessSupport = "unknown"

    def __post_init__(self) -> None:
        if self.axis not in REQUIRED_HOMING_AXES:
            raise HomingFeasibilityError(f"unsupported axis: {self.axis}")
        for name, value in (
            ("physical_switch", self.physical_switch),
            ("sensorless", self.sensorless),
            ("encoder_index", self.encoder_index),
        ):
            if value not in HOMING_EVIDENCE_OUTCOMES:
                raise HomingFeasibilityError(f"{name} has unsupported outcome: {value}")
        if self.sensorless_support not in SENSORLESS_SUPPORT_VALUES:
            raise HomingFeasibilityError(
                f"sensorless_support has unsupported value: {self.sensorless_support}"
            )
        if not isinstance(self.driver_type, str):
            raise HomingFeasibilityError("driver_type must be a string")

    @property
    def accepted_sources(self) -> tuple[HomingSourceName, ...]:
        accepted: list[HomingSourceName] = []
        if self.physical_switch == "accepted":
            accepted.append("physical_switch")
        if self.sensorless == "accepted":
            accepted.append("sensorless")
        if self.encoder_index == "accepted":
            accepted.append("encoder_index")
        return tuple(accepted)

    @property
    def has_accepted_source(self) -> bool:
        return bool(self.accepted_sources)


@dataclass(frozen=True)
class HomingFeasibilitySnapshot:
    """Aggregate software model for scan-start homing feasibility."""

    axes: tuple[AxisHomingFeasibility, ...]
    implementation_status: HomingImplementationStatus = "unknown"
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.implementation_status not in HOMING_IMPLEMENTATION_STATUSES:
            raise HomingFeasibilityError(
                "implementation_status has unsupported value: "
                f"{self.implementation_status}"
            )
        if not isinstance(self.axes, tuple):
            raise HomingFeasibilityError("axes must be a tuple")
        if not isinstance(self.notes, tuple):
            raise HomingFeasibilityError("notes must be a tuple")
        seen: set[Axis] = set()
        for axis in self.axes:
            if not isinstance(axis, AxisHomingFeasibility):
                raise HomingFeasibilityError(
                    "axes must contain AxisHomingFeasibility entries"
                )
            if axis.axis in seen:
                raise HomingFeasibilityError(f"duplicate homing axis: {axis.axis}")
            seen.add(axis.axis)
        for note in self.notes:
            if not isinstance(note, str):
                raise HomingFeasibilityError("notes must contain strings")

    @property
    def missing_axes(self) -> tuple[Axis, ...]:
        by_axis = {axis.axis: axis for axis in self.axes}
        return tuple(
            axis
            for axis in REQUIRED_HOMING_AXES
            if axis not in by_axis or not by_axis[axis].has_accepted_source
        )

    @property
    def scan_preflight_status(self) -> HomingImplementationStatus:
        if self.implementation_status != "implemented":
            return self.implementation_status
        if self.missing_axes:
            return "unknown"
        return "implemented"


class HomingFeasibilityError(ValueError):
    """Raised when homing feasibility evidence is malformed."""


def sensorless_support_for_driver(driver_type: str) -> SensorlessSupport:
    """Return explicit sensorless support for known driver families."""

    normalized = driver_type.strip().lower()
    if normalized == "a4988":
        return "not_supported"
    return "unknown"


def axis_feasibility_from_driver(
    axis: Axis,
    *,
    driver_type: str,
    physical_switch: HomingEvidenceOutcome = "unknown",
    encoder_index: HomingEvidenceOutcome = "unknown",
) -> AxisHomingFeasibility:
    """Build per-axis feasibility without assuming sensorless capability."""

    sensorless_support = sensorless_support_for_driver(driver_type)
    sensorless: HomingEvidenceOutcome = (
        "not_supported" if sensorless_support == "not_supported" else "unknown"
    )
    return AxisHomingFeasibility(
        axis=axis,
        physical_switch=physical_switch,
        sensorless=sensorless,
        encoder_index=encoder_index,
        driver_type=driver_type,
        sensorless_support=sensorless_support,
    )


def current_mks_a4988_homing_feasibility() -> HomingFeasibilitySnapshot:
    """Return the current documented scanner homing feasibility snapshot."""

    return HomingFeasibilitySnapshot(
        axes=tuple(
            axis_feasibility_from_driver(axis, driver_type="A4988")
            for axis in REQUIRED_HOMING_AXES
        ),
        implementation_status="not_implemented",
        notes=(
            "current Klipper homing_override only sets kinematic position",
            "A4988 does not provide sensorless homing feedback",
        ),
    )
