"""Logical LED scheduler value objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from scanner_firmware.planning.led_scheduler.constants import ACTIVE_HIGH, LED_POLARITIES
from scanner_firmware.planning.led_scheduler.errors import LedTimingError


LED_TIMING_CONTRACT_ID = "led_scheduler_timing_contract_v1"
DISABLED_OUTPUT_LED_BACKEND = "disabled_output_metadata"
LOGICAL_GATE_NAME = re.compile(r"^led_[a-z0-9_]+$")


@dataclass(frozen=True)
class LedPatternTimingProfile:
    """Software-only timing settings for one logical LED pattern."""

    pattern: str
    exposure_start_offset_us: int
    exposure_us: int
    gate_pulse_us: int
    settle_us: int = 0
    frame_period_us: int | None = None
    trigger_pulse_us: int | None = None
    gate_pre_trigger_us: int | None = None
    gate_post_exposure_us: int | None = None
    baseline_gate_names: tuple[str, ...] = ()
    baseline_suppress_pre_gate_us: int = 0
    baseline_restore_post_gate_us: int = 0
    polarity: str = ACTIVE_HIGH
    brightness_by_gate: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pattern, str) or not self.pattern:
            raise LedTimingError("pattern timing profile requires a non-empty pattern")
        _require_non_negative_int(
            "exposure_start_offset_us",
            self.exposure_start_offset_us,
        )
        _require_non_negative_int("settle_us", self.settle_us)
        if self.frame_period_us is not None:
            _require_positive_int("frame_period_us", self.frame_period_us)
        if self.trigger_pulse_us is not None:
            _require_positive_int("trigger_pulse_us", self.trigger_pulse_us)
        if self.gate_pre_trigger_us is not None:
            _require_non_negative_int("gate_pre_trigger_us", self.gate_pre_trigger_us)
        if self.gate_post_exposure_us is not None:
            _require_non_negative_int(
                "gate_post_exposure_us",
                self.gate_post_exposure_us,
            )
        if not isinstance(self.baseline_gate_names, tuple):
            raise LedTimingError("baseline_gate_names must be a tuple")
        for gate_name in self.baseline_gate_names:
            if not isinstance(gate_name, str) or not LOGICAL_GATE_NAME.match(gate_name):
                raise LedTimingError(
                    f"baseline LED gate must be a logical alias, got: {gate_name}"
                )
        _require_non_negative_int(
            "baseline_suppress_pre_gate_us",
            self.baseline_suppress_pre_gate_us,
        )
        _require_non_negative_int(
            "baseline_restore_post_gate_us",
            self.baseline_restore_post_gate_us,
        )
        if isinstance(self.exposure_us, bool) or not isinstance(self.exposure_us, int):
            raise LedTimingError("exposure_us must be an integer")
        if self.exposure_us <= 0:
            raise LedTimingError("exposure_us must be positive")
        if isinstance(self.gate_pulse_us, bool) or not isinstance(self.gate_pulse_us, int):
            raise LedTimingError("gate_pulse_us must be an integer")
        if self.gate_pulse_us < 0:
            raise LedTimingError("gate_pulse_us must be non-negative")
        if not isinstance(self.polarity, str) or self.polarity not in LED_POLARITIES:
            raise LedTimingError(f"unsupported LED polarity: {self.polarity}")
        if self.brightness_by_gate is not None and not isinstance(
            self.brightness_by_gate,
            dict,
        ):
            raise LedTimingError("brightness_by_gate must be a mapping")
        if self.brightness_by_gate is not None:
            for gate_name, brightness in self.brightness_by_gate.items():
                if not isinstance(gate_name, str) or not LOGICAL_GATE_NAME.match(gate_name):
                    raise LedTimingError(
                        f"LED gate must be a logical alias, got: {gate_name}"
                    )
                if isinstance(brightness, bool) or not isinstance(
                    brightness,
                    int | float,
                ):
                    raise LedTimingError(
                        f"brightness for {gate_name} must be numeric"
                    )
                if brightness < 0.0 or brightness > 1.0:
                    raise LedTimingError(
                        f"brightness for {gate_name} must be between 0.0 and 1.0"
                    )
            object.__setattr__(self, "brightness_by_gate", dict(self.brightness_by_gate))


@dataclass(frozen=True)
class LedPatternTimingSet:
    """Pattern-indexed timing profiles for one dry-run scan schedule."""

    profiles: tuple[LedPatternTimingProfile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profiles, tuple):
            raise LedTimingError("pattern timing profiles must be a tuple")
        if not self.profiles:
            raise LedTimingError("pattern timing set requires at least one profile")
        seen: set[str] = set()
        for profile in self.profiles:
            if not isinstance(profile, LedPatternTimingProfile):
                raise LedTimingError(
                    "pattern timing profiles must contain LedPatternTimingProfile"
                )
            if profile.pattern in seen:
                raise LedTimingError(f"duplicate LED timing profile: {profile.pattern}")
            seen.add(profile.pattern)

    @property
    def patterns(self) -> tuple[str, ...]:
        return tuple(profile.pattern for profile in self.profiles)

    def profile_for(self, pattern: str) -> LedPatternTimingProfile:
        for profile in self.profiles:
            if profile.pattern == pattern:
                return profile
        raise LedTimingError(f"missing LED timing profile for pattern: {pattern}")


@dataclass(frozen=True)
class LedPattern:
    pattern: str
    gate_names: tuple[str, ...]
    frame_use: str


@dataclass(frozen=True)
class LedExposureWindow:
    start_us: int
    end_us: int

    @property
    def duration_us(self) -> int:
        return self.end_us - self.start_us


@dataclass(frozen=True)
class LedBrightnessSetpoint:
    gate_name: str
    brightness: float


@dataclass(frozen=True)
class LedGateWindow:
    gate_name: str
    start_us: int
    end_us: int
    polarity: str

    @property
    def active_level(self) -> int:
        return 1 if self.polarity == ACTIVE_HIGH else 0

    @property
    def duration_us(self) -> int:
        return self.end_us - self.start_us


@dataclass(frozen=True)
class LedBaselineTransition:
    gate_name: str
    time_us: int
    state: Literal["inactive", "active"]
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.gate_name, str) or not LOGICAL_GATE_NAME.match(self.gate_name):
            raise LedTimingError(f"LED gate must be a logical alias, got: {self.gate_name}")
        _require_non_negative_int("time_us", self.time_us)
        if self.state not in ("inactive", "active"):
            raise LedTimingError("baseline transition state must be inactive or active")
        if not self.reason:
            raise LedTimingError("baseline transition reason must be non-empty")


@dataclass(frozen=True)
class LedTimingPlan:
    pattern: LedPattern
    frame_start_us: int
    exposure: LedExposureWindow
    brightness_setpoints: tuple[LedBrightnessSetpoint, ...]
    gate_windows: tuple[LedGateWindow, ...]
    baseline_gate_names: tuple[str, ...] = ()
    baseline_transitions: tuple[LedBaselineTransition, ...] = ()
    frame_period_us: int | None = None
    trigger_start_us: int | None = None
    trigger_end_us: int | None = None


@dataclass(frozen=True)
class DisabledOutputLedTimingContract:
    """Protocol-safe LED timing metadata for one planned frame.

    This is evidence metadata only. It identifies logical channels and
    absolute MCU-time pulse windows while keeping physical LED outputs disabled.
    """

    pattern: str
    frame_use: str
    logical_channel_names: tuple[str, ...]
    frame_start_us: int
    exposure_start_us: int
    exposure_end_us: int
    brightness_setpoints: tuple[LedBrightnessSetpoint, ...]
    gate_windows: tuple[LedGateWindow, ...]
    baseline_gate_names: tuple[str, ...] = ()
    baseline_transitions: tuple[LedBaselineTransition, ...] = ()
    frame_period_us: int | None = None
    trigger_start_us: int | None = None
    trigger_end_us: int | None = None
    hardware_outputs_enabled: bool = False
    backend: Literal["disabled_output_metadata"] = DISABLED_OUTPUT_LED_BACKEND
    contract_id: Literal[
        "led_scheduler_timing_contract_v1"
    ] = LED_TIMING_CONTRACT_ID

    def __post_init__(self) -> None:
        if self.contract_id != LED_TIMING_CONTRACT_ID:
            raise LedTimingError("unsupported LED timing contract_id")
        if self.backend != DISABLED_OUTPUT_LED_BACKEND:
            raise LedTimingError("unsupported LED timing backend")
        if self.hardware_outputs_enabled is not False:
            raise LedTimingError("LED timing contract must keep hardware outputs disabled")
        if not self.pattern:
            raise LedTimingError("LED timing contract requires a pattern")
        if not self.frame_use:
            raise LedTimingError("LED timing contract requires frame_use")
        _require_non_negative_int("frame_start_us", self.frame_start_us)
        if self.frame_period_us is not None:
            _require_positive_int("frame_period_us", self.frame_period_us)
        if self.trigger_start_us is not None:
            _require_non_negative_int("trigger_start_us", self.trigger_start_us)
        if self.trigger_end_us is not None:
            _require_positive_int("trigger_end_us", self.trigger_end_us)
            trigger_start_us = self.trigger_start_us
            if trigger_start_us is None:
                trigger_start_us = self.frame_start_us
            if self.trigger_end_us <= trigger_start_us:
                raise LedTimingError("trigger_end_us must be after trigger_start_us")
        _require_non_negative_int("exposure_start_us", self.exposure_start_us)
        _require_non_negative_int("exposure_end_us", self.exposure_end_us)
        if self.exposure_start_us < self.frame_start_us:
            raise LedTimingError("exposure_start_us must be at or after frame_start_us")
        if self.exposure_end_us <= self.exposure_start_us:
            raise LedTimingError("exposure_end_us must be after exposure_start_us")
        object.__setattr__(
            self,
            "logical_channel_names",
            tuple(self.logical_channel_names),
        )
        object.__setattr__(
            self,
            "brightness_setpoints",
            tuple(self.brightness_setpoints),
        )
        object.__setattr__(self, "gate_windows", tuple(self.gate_windows))
        object.__setattr__(self, "baseline_gate_names", tuple(self.baseline_gate_names))
        object.__setattr__(
            self,
            "baseline_transitions",
            tuple(self.baseline_transitions),
        )
        for gate_name in self.baseline_gate_names:
            if not isinstance(gate_name, str) or not LOGICAL_GATE_NAME.match(gate_name):
                raise LedTimingError(
                    f"baseline LED gate must be a logical alias, got: {gate_name}"
                )
        for transition in self.baseline_transitions:
            if not isinstance(transition, LedBaselineTransition):
                raise LedTimingError("baseline_transitions must contain LedBaselineTransition")
            if transition.gate_name not in self.baseline_gate_names:
                raise LedTimingError("baseline transition gate must be listed in baseline_gate_names")

    @property
    def exposure_us(self) -> int:
        return self.exposure_end_us - self.exposure_start_us

    def to_json_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))

    @classmethod
    def from_json_dict(
        cls,
        payload: dict[str, Any],
    ) -> "DisabledOutputLedTimingContract":
        return cls(
            contract_id=payload["contract_id"],
            backend=payload["backend"],
            hardware_outputs_enabled=payload["hardware_outputs_enabled"],
            pattern=payload["pattern"],
            frame_use=payload["frame_use"],
            logical_channel_names=tuple(payload["logical_channel_names"]),
            frame_start_us=payload["frame_start_us"],
            exposure_start_us=payload["exposure_start_us"],
            exposure_end_us=payload["exposure_end_us"],
            brightness_setpoints=tuple(
                LedBrightnessSetpoint(**setpoint)
                for setpoint in payload["brightness_setpoints"]
            ),
            gate_windows=tuple(
                LedGateWindow(**window) for window in payload["gate_windows"]
            ),
            baseline_gate_names=tuple(payload.get("baseline_gate_names", ())),
            baseline_transitions=tuple(
                LedBaselineTransition(**transition)
                for transition in payload.get("baseline_transitions", ())
            ),
            frame_period_us=payload.get("frame_period_us"),
            trigger_start_us=payload.get("trigger_start_us"),
            trigger_end_us=payload.get("trigger_end_us"),
        )


def _require_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedTimingError(f"{name} must be an integer")
    if value < 0:
        raise LedTimingError(f"{name} must be non-negative")


def _require_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedTimingError(f"{name} must be an integer")
    if value <= 0:
        raise LedTimingError(f"{name} must be positive")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
