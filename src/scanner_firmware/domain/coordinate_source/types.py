"""Coordinate-source data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scanner_firmware.domain.coordinate_source.errors import CoordinateSourceError
from scanner_firmware.domain.coordinate_source.validation import (
    require_encoder_health,
    require_int,
)


CoordinateSourceMode = Literal["step_indexed", "encoder_indexed", "hybrid"]
EncoderHealth = Literal["healthy", "unhealthy", "unknown"]
ENCODER_HEALTH_VALUES: tuple[EncoderHealth, ...] = (
    "healthy",
    "unhealthy",
    "unknown",
)


@dataclass(frozen=True)
class CoordinateSample:
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int = 0
    x_encoder_count: int | None = None
    y_encoder_count: int | None = None
    sample_index: int | None = None
    x_encoder_sample_index: int | None = None
    y_encoder_sample_index: int | None = None
    x_encoder_health: EncoderHealth = "unknown"
    y_encoder_health: EncoderHealth = "unknown"

    def __post_init__(self) -> None:
        for name, value in (
            ("x_step_commanded", self.x_step_commanded),
            ("y_step_commanded", self.y_step_commanded),
            ("z_step_commanded", self.z_step_commanded),
            ("x_encoder_count", self.x_encoder_count),
            ("y_encoder_count", self.y_encoder_count),
            ("sample_index", self.sample_index),
            ("x_encoder_sample_index", self.x_encoder_sample_index),
            ("y_encoder_sample_index", self.y_encoder_sample_index),
        ):
            if value is not None:
                require_int(name, value)
        require_encoder_health(
            "x_encoder_health",
            self.x_encoder_health,
            ENCODER_HEALTH_VALUES,
        )
        require_encoder_health(
            "y_encoder_health",
            self.y_encoder_health,
            ENCODER_HEALTH_VALUES,
        )
        for name, value in (
            ("sample_index", self.sample_index),
            ("x_encoder_sample_index", self.x_encoder_sample_index),
            ("y_encoder_sample_index", self.y_encoder_sample_index),
        ):
            if value is not None and value < 0:
                raise CoordinateSourceError(f"{name} must be non-negative")


@dataclass(frozen=True)
class CoordinateFusionConfig:
    encoder_stale_after_samples: int | None = None
    disagreement_threshold_counts: int | None = None
    report_missing_encoders: bool = False
    report_encoder_health: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("encoder_stale_after_samples", self.encoder_stale_after_samples),
            ("disagreement_threshold_counts", self.disagreement_threshold_counts),
        ):
            if value is not None:
                require_int(name, value)
                if value < 0:
                    raise CoordinateSourceError(f"{name} must be non-negative")
        for name, value in (
            ("report_missing_encoders", self.report_missing_encoders),
            ("report_encoder_health", self.report_encoder_health),
        ):
            if not isinstance(value, bool):
                raise CoordinateSourceError(f"{name} must be a boolean")


@dataclass(frozen=True)
class CoordinateTruth:
    source: CoordinateSourceMode
    x_count: int
    y_count: int
    z_count: int
    x_step_commanded: int
    y_step_commanded: int
    z_step_commanded: int
    x_encoder_count: int | None
    y_encoder_count: int | None
    sample_index: int | None = None
    x_encoder_sample_index: int | None = None
    y_encoder_sample_index: int | None = None
    x_encoder_health: EncoderHealth = "unknown"
    y_encoder_health: EncoderHealth = "unknown"
    flags: tuple[str, ...] = ()
