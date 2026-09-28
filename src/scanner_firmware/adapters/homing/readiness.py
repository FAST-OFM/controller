"""Software-only homing readiness contracts.

Readiness is stricter than feasibility: an axis is ready for scan start only
when real homing evidence exists. A controller macro that only sets the
kinematic position is position evidence, not homing evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.adapters.homing.feasibility import REQUIRED_HOMING_AXES, Axis


PhysicalHomingSource = Literal["physical_switch", "sensorless", "encoder_index"]
PositionOnlySource = Literal["homing_override_sets_position"]
HomingReadinessStatus = Literal["ready", "blocked", "simulator_safe_disabled"]
PHYSICAL_HOMING_SOURCES: tuple[PhysicalHomingSource, ...] = (
    "physical_switch",
    "sensorless",
    "encoder_index",
)
POSITION_ONLY_SOURCES: tuple[PositionOnlySource, ...] = (
    "homing_override_sets_position",
)


@dataclass(frozen=True)
class AxisHomingReadiness:
    """Per-axis scan-start homing readiness evidence."""

    axis: Axis
    homed_by: tuple[PhysicalHomingSource, ...] = ()
    position_only_sources: tuple[PositionOnlySource, ...] = ()

    def __post_init__(self) -> None:
        if self.axis not in REQUIRED_HOMING_AXES:
            raise HomingReadinessError(f"unsupported axis: {self.axis}")
        _validate_unique_tuple("homed_by", self.homed_by, PHYSICAL_HOMING_SOURCES)
        _validate_unique_tuple(
            "position_only_sources",
            self.position_only_sources,
            POSITION_ONLY_SOURCES,
        )

    @property
    def physically_homed(self) -> bool:
        return bool(self.homed_by)

    @property
    def has_position_only_evidence(self) -> bool:
        return bool(self.position_only_sources)


@dataclass(frozen=True)
class HomingReadinessInput:
    """Input facts for passive homing readiness evaluation."""

    axes: tuple[AxisHomingReadiness, ...]
    required_axes: tuple[Axis, ...] = REQUIRED_HOMING_AXES
    z_policy_configured: bool = True
    simulator_mode: bool = False
    hardware_outputs_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.axes, tuple):
            raise HomingReadinessError("axes must be a tuple")
        if not isinstance(self.required_axes, tuple):
            raise HomingReadinessError("required_axes must be a tuple")
        for name, value in (
            ("z_policy_configured", self.z_policy_configured),
            ("simulator_mode", self.simulator_mode),
            ("hardware_outputs_enabled", self.hardware_outputs_enabled),
        ):
            if not isinstance(value, bool):
                raise HomingReadinessError(f"{name} must be a boolean")
        _validate_axes("required_axes", self.required_axes)
        if set(self.required_axes) != set(REQUIRED_HOMING_AXES):
            raise HomingReadinessError("homing readiness requires X, Y and Z axes")
        if len(self.required_axes) != len(REQUIRED_HOMING_AXES):
            raise HomingReadinessError("required_axes must not contain duplicates")

        seen: set[Axis] = set()
        for axis in self.axes:
            if not isinstance(axis, AxisHomingReadiness):
                raise HomingReadinessError(
                    "axes must contain AxisHomingReadiness entries"
                )
            if axis.axis in seen:
                raise HomingReadinessError(f"duplicate homing axis: {axis.axis}")
            seen.add(axis.axis)


@dataclass(frozen=True)
class HomingReadinessDecision:
    status: HomingReadinessStatus
    accepted: bool
    physically_homed_axes: tuple[Axis, ...]
    missing_axes: tuple[Axis, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class HomingReadinessError(ValueError):
    """Raised when homing readiness evidence is malformed."""


def evaluate_homing_readiness(
    readiness: HomingReadinessInput,
) -> HomingReadinessDecision:
    """Evaluate scan-start homing readiness without touching hardware."""

    by_axis = {axis.axis: axis for axis in readiness.axes}
    physically_homed_axes = tuple(
        axis
        for axis in readiness.required_axes
        if axis in by_axis and by_axis[axis].physically_homed
    )
    missing_axes = tuple(
        axis for axis in readiness.required_axes if axis not in physically_homed_axes
    )
    blockers = _blocking_reasons(readiness, missing_axes, by_axis)

    if not blockers:
        return HomingReadinessDecision(
            status="ready",
            accepted=True,
            physically_homed_axes=physically_homed_axes,
            missing_axes=(),
        )

    if readiness.simulator_mode and not readiness.hardware_outputs_enabled:
        return HomingReadinessDecision(
            status="simulator_safe_disabled",
            accepted=True,
            physically_homed_axes=physically_homed_axes,
            missing_axes=missing_axes,
            warnings=tuple(_simulator_warning(blocker) for blocker in blockers),
        )

    return HomingReadinessDecision(
        status="blocked",
        accepted=False,
        physically_homed_axes=physically_homed_axes,
        missing_axes=missing_axes,
        blockers=blockers,
    )


def current_mks_a4988_homing_readiness(
    *,
    simulator_mode: bool = False,
    hardware_outputs_enabled: bool = True,
) -> HomingReadinessInput:
    """Return current MKS/A4988 readiness facts from passive board evidence."""

    return HomingReadinessInput(
        axes=tuple(
            AxisHomingReadiness(
                axis=axis,
                position_only_sources=("homing_override_sets_position",),
            )
            for axis in REQUIRED_HOMING_AXES
        ),
        z_policy_configured=False,
        simulator_mode=simulator_mode,
        hardware_outputs_enabled=hardware_outputs_enabled,
    )


def future_pico_homing_readiness_candidate(
    *,
    simulator_mode: bool = False,
    hardware_outputs_enabled: bool = True,
) -> HomingReadinessInput:
    """Return the conservative future Pico baseline: candidate, not homed."""

    return HomingReadinessInput(
        axes=tuple(AxisHomingReadiness(axis=axis) for axis in REQUIRED_HOMING_AXES),
        z_policy_configured=False,
        simulator_mode=simulator_mode,
        hardware_outputs_enabled=hardware_outputs_enabled,
    )


def _blocking_reasons(
    readiness: HomingReadinessInput,
    missing_axes: tuple[Axis, ...],
    by_axis: dict[Axis, AxisHomingReadiness],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if missing_axes:
        missing_text = ", ".join(missing_axes)
        blockers.append(f"physical homing is missing for required axes: {missing_text}")
    position_only_axes = tuple(
        axis
        for axis in missing_axes
        if axis in by_axis and by_axis[axis].has_position_only_evidence
    )
    if position_only_axes:
        axes_text = ", ".join(position_only_axes)
        blockers.append(
            "homing override only sets position and does not physically home axes: "
            f"{axes_text}"
        )
    if not readiness.z_policy_configured:
        blockers.append("Z homing policy must be configured before scan start")
    if blockers and readiness.hardware_outputs_enabled:
        blockers.append("hardware outputs cannot be enabled until homing is ready")
    return tuple(blockers)


def _simulator_warning(blocker: str) -> str:
    return f"simulator safe-disabled mode accepted with blocker: {blocker}"


def _validate_axes(name: str, axes: tuple[Axis, ...]) -> None:
    for axis in axes:
        if axis not in REQUIRED_HOMING_AXES:
            raise HomingReadinessError(f"{name} contains unsupported axis: {axis}")


def _validate_unique_tuple(
    name: str,
    values: tuple[str, ...],
    allowed: tuple[str, ...],
) -> None:
    if not isinstance(values, tuple):
        raise HomingReadinessError(f"{name} must be a tuple")
    if len(set(values)) != len(values):
        raise HomingReadinessError(f"{name} must not contain duplicates")
    for value in values:
        if value not in allowed:
            raise HomingReadinessError(f"{name} contains unsupported value: {value}")
