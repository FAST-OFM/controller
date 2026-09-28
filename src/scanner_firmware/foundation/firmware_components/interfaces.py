"""Software-only interfaces for parallel firmware component work.

These protocols are contracts for simulator and planner code. They do not
perform hardware I/O, send controller commands, toggle outputs, trigger cameras,
drive LEDs, move motors or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Literal, Protocol


Axis = Literal["X", "Y", "Z"]
CoordinateTargetKind = Literal["frame", "position"]
BayerPattern = Literal["RGGB", "GRBG", "GBRG", "BGGR"]
ImageEncoding = Literal["raw_bayer_linear"]
LedBrightnessChannel = Literal["red", "green", "white"]
LED_BRIGHTNESS_CHANNELS: tuple[LedBrightnessChannel, ...] = ("red", "green", "white")


@dataclass(frozen=True)
class ComponentSafety:
    """Declared safety boundary for a component implementation."""

    software_only: bool = True
    hardware_outputs_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.software_only:
            raise ValueError("component interfaces are software-only")
        if self.hardware_outputs_enabled:
            raise ValueError("component interfaces cannot enable hardware outputs")


@dataclass(frozen=True)
class StripeGeometryInput:
    axis: Literal["X", "Y"]
    start_position: int
    end_position: int
    first_event_position: int
    event_pitch: int
    event_count: int

    def __post_init__(self) -> None:
        _require_axis_xy(self.axis)
        for name, value in (
            ("start_position", self.start_position),
            ("end_position", self.end_position),
            ("first_event_position", self.first_event_position),
            ("event_pitch", self.event_pitch),
            ("event_count", self.event_count),
        ):
            _require_int(name, value)
        if self.start_position == self.end_position:
            raise ValueError("start_position and end_position must differ")
        if self.event_pitch == 0:
            raise ValueError("event_pitch must be non-zero")
        if self.event_count < 0:
            raise ValueError("event_count must be non-negative")


@dataclass(frozen=True)
class StripeGeometryResult:
    axis: Literal["X", "Y"]
    direction: int
    event_positions: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_axis_xy(self.axis)
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")
        for position in self.event_positions:
            _require_int("event_position", position)


class StripeGeometryModel(Protocol):
    safety: ComponentSafety

    def build_geometry(self, geometry: StripeGeometryInput) -> StripeGeometryResult:
        """Compute position-indexed event geometry."""


@dataclass(frozen=True)
class RawBayerFocusFrameInput:
    """RAW Bayer focus input after camera/acquisition adapters have decoded it.

    Focus components consume linear, unsqueezed RAW Bayer sample rows. JPEG,
    preview, gamma-encoded and already-color-processed frames are intentionally
    outside this contract.
    """

    encoding: ImageEncoding
    width: int
    height: int
    bayer_pattern: BayerPattern
    rows: tuple[tuple[float, ...], ...]
    black_level: int = 0
    white_level: int | None = None

    def __post_init__(self) -> None:
        if self.encoding != "raw_bayer_linear":
            raise ValueError("focus frame encoding must be raw_bayer_linear")
        if self.bayer_pattern not in ("RGGB", "GRBG", "GBRG", "BGGR"):
            raise ValueError("unsupported Bayer pattern")
        _require_positive_int("width", self.width)
        _require_positive_int("height", self.height)
        _require_int("black_level", self.black_level)
        if self.white_level is not None:
            _require_int("white_level", self.white_level)
            if self.white_level <= self.black_level:
                raise ValueError("white_level must be greater than black_level")
        if len(self.rows) != self.height:
            raise ValueError("rows height must match height")
        for row in self.rows:
            if len(row) != self.width:
                raise ValueError("rows width must match width")
            for sample in row:
                _require_finite_number("sample", sample)


@dataclass(frozen=True)
class FocusEstimate:
    score_red: float
    score_green: float
    focus_error: float
    confidence: float
    accepted: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("score_red", self.score_red),
            ("score_green", self.score_green),
            ("focus_error", self.focus_error),
            ("confidence", self.confidence),
        ):
            _require_finite_number(name, value)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        _require_bool("accepted", self.accepted)


class FocusEstimator(Protocol):
    safety: ComponentSafety

    def estimate_focus(self, frame: RawBayerFocusFrameInput) -> FocusEstimate:
        """Estimate focus from RAW/linear image samples."""


@dataclass(frozen=True)
class AxisCalibrationObservation:
    axis: Axis
    commanded_steps: int
    measured_mm: float

    def __post_init__(self) -> None:
        _require_axis(self.axis)
        _require_int("commanded_steps", self.commanded_steps)
        _require_finite_number("measured_mm", self.measured_mm)


@dataclass(frozen=True)
class AxisCalibrationEstimate:
    axis: Axis
    steps_per_mm: float
    sample_count: int
    residual_rms_mm: float

    def __post_init__(self) -> None:
        _require_axis(self.axis)
        _require_finite_number("steps_per_mm", self.steps_per_mm)
        _require_positive_int("sample_count", self.sample_count)
        _require_finite_number("residual_rms_mm", self.residual_rms_mm)
        if self.steps_per_mm <= 0.0:
            raise ValueError("steps_per_mm must be positive")
        if self.residual_rms_mm < 0.0:
            raise ValueError("residual_rms_mm must be non-negative")


class AxisCalibrationEstimator(Protocol):
    safety: ComponentSafety

    def estimate_axis(
        self,
        observations: tuple[AxisCalibrationObservation, ...],
    ) -> AxisCalibrationEstimate:
        """Estimate axis calibration from commanded steps and measured travel."""


@dataclass(frozen=True)
class FocusCorrectionSample:
    scan_id: str
    stripe_id: int
    focus_error_um: float
    reference_z_um: float
    frame_id: int | None = None
    position_count: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        _require_finite_number("focus_error_um", self.focus_error_um)
        _require_finite_number("reference_z_um", self.reference_z_um)
        _require_exactly_one_target(self.frame_id, self.position_count)
        if self.frame_id is not None:
            _require_non_negative_int("frame_id", self.frame_id)
        if self.position_count is not None:
            _require_int("position_count", self.position_count)


@dataclass(frozen=True)
class PredictiveZCorrection:
    scan_id: str
    stripe_id: int
    target_kind: CoordinateTargetKind
    target_value: int
    z_correction_um: float
    z_target_um: float
    accepted: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty("scan_id", self.scan_id)
        _require_non_negative_int("stripe_id", self.stripe_id)
        if self.target_kind not in ("frame", "position"):
            raise ValueError("target_kind must be frame or position")
        _require_int("target_value", self.target_value)
        if self.target_kind == "frame":
            _require_non_negative_int("target_value", self.target_value)
        _require_finite_number("z_correction_um", self.z_correction_um)
        _require_finite_number("z_target_um", self.z_target_um)
        _require_bool("accepted", self.accepted)


class PredictiveZPlanner(Protocol):
    safety: ComponentSafety

    def plan_correction(self, sample: FocusCorrectionSample) -> PredictiveZCorrection:
        """Schedule a future Z correction by frame or position."""


@dataclass(frozen=True)
class LedBrightnessState:
    """Logical slow LED brightness state.

    Brightness values are scanner-side normalized 8-bit setpoints. They are
    logical values, not pin numbers, timers, currents or direct PWM hardware
    access.
    """

    red: int = 0
    green: int = 0
    white: int = 0

    def __post_init__(self) -> None:
        _require_brightness_value("red", self.red)
        _require_brightness_value("green", self.green)
        _require_brightness_value("white", self.white)

    def value_for(self, channel: LedBrightnessChannel) -> int:
        _require_led_brightness_channel(channel)
        return getattr(self, channel)

    def with_channel(
        self,
        channel: LedBrightnessChannel,
        brightness: int,
    ) -> LedBrightnessState:
        _require_led_brightness_channel(channel)
        _require_brightness_value("brightness", brightness)
        return LedBrightnessState(
            red=brightness if channel == "red" else self.red,
            green=brightness if channel == "green" else self.green,
            white=brightness if channel == "white" else self.white,
        )

    def as_channels(self) -> tuple[tuple[LedBrightnessChannel, int], ...]:
        return (
            ("red", self.red),
            ("green", self.green),
            ("white", self.white),
        )


class LedBrightnessPort(Protocol):
    """Software-only logical port for slow LED brightness setpoints."""

    safety: ComponentSafety

    def report_state(self) -> LedBrightnessState:
        """Return the last accepted logical brightness state."""

    def set_channel(
        self,
        channel: LedBrightnessChannel,
        brightness: int,
    ) -> LedBrightnessState:
        """Set one logical channel while preserving other channel values."""

    def set_all(self, state: LedBrightnessState) -> LedBrightnessState:
        """Atomically replace all logical channel brightness values."""

    def zero_all(self) -> LedBrightnessState:
        """Set every logical channel brightness value to zero."""


def _require_axis(axis: object) -> None:
    if axis not in ("X", "Y", "Z"):
        raise ValueError("axis must be X, Y or Z")


def _require_axis_xy(axis: object) -> None:
    if axis not in ("X", "Y"):
        raise ValueError("axis must be X or Y")


def _require_int(name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")


def _require_positive_int(name: str, value: object) -> None:
    _require_int(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_non_negative_int(name: str, value: object) -> None:
    _require_int(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_finite_number(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _require_bool(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")


def _require_non_empty(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _require_exactly_one_target(frame_id: int | None, position_count: int | None) -> None:
    if (frame_id is None) == (position_count is None):
        raise ValueError("exactly one of frame_id or position_count is required")


def _require_led_brightness_channel(channel: object) -> None:
    if channel not in LED_BRIGHTNESS_CHANNELS:
        raise ValueError("LED brightness channel must be red, green or white")


def _require_brightness_value(name: str, value: object) -> None:
    _require_int(name, value)
    if value < 0 or value > 255:
        raise ValueError(f"{name} must be between 0 and 255")
