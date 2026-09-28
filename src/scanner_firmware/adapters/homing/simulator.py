"""Homing state-machine simulator.

This module models homing state transitions for tests. It does not command
motors, read switches or access firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


Axis = Literal["X", "Y", "Z"]
HomingSource = Literal["physical_switch", "sensorless", "encoder_index"]


class HomingFault(str, Enum):
    ENDSTOP_ACTIVE_BEFORE_START = "endstop_active_before_start"
    TIMEOUT_OR_TRAVEL_LIMIT = "timeout_or_travel_limit"
    SWITCH_STUCK_AFTER_BACKOFF = "switch_stuck_after_backoff"
    WRONG_DIRECTION = "wrong_direction"
    Z_POLICY_MISSING = "z_policy_missing"


@dataclass(frozen=True)
class HomingConfig:
    axis: Axis
    source: HomingSource
    seek_direction: int
    max_travel_counts: int
    backoff_counts: int
    z_policy_configured: bool = True
    driver_supports_sensorless: bool = False


@dataclass(frozen=True)
class HomingSample:
    position_count: int
    switch_active: bool = False
    sensorless_triggered: bool = False
    encoder_index_seen: bool = False


@dataclass(frozen=True)
class HomingResult:
    axis: Axis
    source: HomingSource
    homed: bool
    machine_zero_count: int | None = None
    fault: HomingFault | None = None
    activation_count: int | None = None


class HomingConfigError(ValueError):
    """Raised for invalid homing simulator configuration."""


def simulate_homing(config: HomingConfig, samples: list[HomingSample]) -> HomingResult:
    """Simulate a conservative seek/backoff/verify homing sequence."""

    _validate_config(config)
    if config.axis == "Z" and not config.z_policy_configured:
        return _fault(config, HomingFault.Z_POLICY_MISSING)
    if not samples:
        return _fault(config, HomingFault.TIMEOUT_OR_TRAVEL_LIMIT)
    if _triggered(config.source, samples[0]):
        return _fault(config, HomingFault.ENDSTOP_ACTIVE_BEFORE_START)

    start = samples[0].position_count
    previous = start
    activation: HomingSample | None = None

    for sample in samples[1:]:
        if _moved_wrong_direction(config.seek_direction, previous, sample.position_count):
            return _fault(config, HomingFault.WRONG_DIRECTION)
        if abs(sample.position_count - start) > config.max_travel_counts:
            return _fault(config, HomingFault.TIMEOUT_OR_TRAVEL_LIMIT)
        if _triggered(config.source, sample):
            activation = sample
            break
        previous = sample.position_count

    if activation is None:
        return _fault(config, HomingFault.TIMEOUT_OR_TRAVEL_LIMIT)

    backoff_target = activation.position_count - (config.seek_direction * config.backoff_counts)
    released = any(
        not _triggered(config.source, sample)
        and _backed_off(config.seek_direction, sample.position_count, backoff_target)
        for sample in samples
        if sample.position_count != activation.position_count
    )
    if not released:
        return _fault(config, HomingFault.SWITCH_STUCK_AFTER_BACKOFF, activation)

    return HomingResult(
        axis=config.axis,
        source=config.source,
        homed=True,
        machine_zero_count=activation.position_count,
        activation_count=activation.position_count,
    )


def _validate_config(config: HomingConfig) -> None:
    if config.seek_direction not in (-1, 1):
        raise HomingConfigError("seek_direction must be -1 or 1")
    if config.max_travel_counts <= 0:
        raise HomingConfigError("max_travel_counts must be positive")
    if config.backoff_counts <= 0:
        raise HomingConfigError("backoff_counts must be positive")
    if config.source == "sensorless" and not config.driver_supports_sensorless:
        raise HomingConfigError("sensorless homing requires driver_supports_sensorless")


def _triggered(source: HomingSource, sample: HomingSample) -> bool:
    if source == "physical_switch":
        return sample.switch_active
    if source == "sensorless":
        return sample.sensorless_triggered
    if source == "encoder_index":
        return sample.encoder_index_seen
    raise HomingConfigError(f"unsupported homing source: {source}")


def _moved_wrong_direction(direction: int, previous: int, current: int) -> bool:
    return (current - previous) * direction < 0


def _backed_off(direction: int, position: int, target: int) -> bool:
    if direction > 0:
        return position <= target
    return position >= target


def _fault(
    config: HomingConfig,
    fault: HomingFault,
    activation: HomingSample | None = None,
) -> HomingResult:
    return HomingResult(
        axis=config.axis,
        source=config.source,
        homed=False,
        fault=fault,
        activation_count=activation.position_count if activation else None,
    )
