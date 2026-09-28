"""Coordinate-source fusion policy."""

from __future__ import annotations

from typing import Literal

from scanner_firmware.domain.coordinate_source.errors import CoordinateSourceError
from scanner_firmware.domain.coordinate_source.types import (
    CoordinateFusionConfig,
    CoordinateSample,
    CoordinateSourceMode,
    CoordinateTruth,
    EncoderHealth,
)


def resolve_coordinate(
    sample: CoordinateSample,
    mode: CoordinateSourceMode,
    fusion_config: CoordinateFusionConfig | None = None,
) -> CoordinateTruth:
    """Resolve a coordinate sample according to the selected source mode."""

    config = fusion_config or CoordinateFusionConfig()

    if mode == "step_indexed":
        flags = _fusion_flags(
            sample,
            config,
            include_missing=config.report_missing_encoders,
        )
        return _truth_from_sample(sample, mode=mode, x_count=sample.x_step_commanded, y_count=sample.y_step_commanded, flags=flags)

    if mode == "encoder_indexed":
        _require_encoders(sample)
        flags = _fusion_flags(sample, config, include_missing=True)
        return _truth_from_sample(sample, mode=mode, x_count=sample.x_encoder_count, y_count=sample.y_encoder_count, flags=flags)

    if mode == "hybrid":
        flags = _fusion_flags(sample, config, include_missing=True)
        return _truth_from_sample(sample, mode=mode, x_count=sample.x_step_commanded, y_count=sample.y_step_commanded, flags=flags)

    raise CoordinateSourceError(f"unsupported coordinate source: {mode}")


def _truth_from_sample(
    sample: CoordinateSample,
    *,
    mode: CoordinateSourceMode,
    x_count: int,
    y_count: int,
    flags: tuple[str, ...],
) -> CoordinateTruth:
    return CoordinateTruth(
        source=mode,
        x_count=x_count,
        y_count=y_count,
        z_count=sample.z_step_commanded,
        x_step_commanded=sample.x_step_commanded,
        y_step_commanded=sample.y_step_commanded,
        z_step_commanded=sample.z_step_commanded,
        x_encoder_count=sample.x_encoder_count,
        y_encoder_count=sample.y_encoder_count,
        sample_index=sample.sample_index,
        x_encoder_sample_index=sample.x_encoder_sample_index,
        y_encoder_sample_index=sample.y_encoder_sample_index,
        x_encoder_health=sample.x_encoder_health,
        y_encoder_health=sample.y_encoder_health,
        flags=flags,
    )


def _require_encoders(sample: CoordinateSample) -> None:
    if sample.x_encoder_count is None or sample.y_encoder_count is None:
        raise CoordinateSourceError(
            "encoder_indexed mode requires X and Y encoder counts"
        )


def _fusion_flags(
    sample: CoordinateSample,
    config: CoordinateFusionConfig,
    *,
    include_missing: bool,
) -> tuple[str, ...]:
    flags: list[str] = []

    _append_axis_flags(
        flags,
        axis="x",
        step_count=sample.x_step_commanded,
        encoder_count=sample.x_encoder_count,
        sample_index=sample.sample_index,
        encoder_sample_index=sample.x_encoder_sample_index,
        encoder_health=sample.x_encoder_health,
        config=config,
        include_missing=include_missing,
    )
    _append_axis_flags(
        flags,
        axis="y",
        step_count=sample.y_step_commanded,
        encoder_count=sample.y_encoder_count,
        sample_index=sample.sample_index,
        encoder_sample_index=sample.y_encoder_sample_index,
        encoder_health=sample.y_encoder_health,
        config=config,
        include_missing=include_missing,
    )

    return tuple(flags)


def _append_axis_flags(
    flags: list[str],
    *,
    axis: Literal["x", "y"],
    step_count: int,
    encoder_count: int | None,
    sample_index: int | None,
    encoder_sample_index: int | None,
    encoder_health: EncoderHealth,
    config: CoordinateFusionConfig,
    include_missing: bool,
) -> None:
    if include_missing and encoder_count is None:
        flags.append(f"{axis}_encoder_missing")

    if config.report_encoder_health:
        flags.append(f"{axis}_encoder_health_{encoder_health}")

    if encoder_count is None:
        return

    if _is_stale(sample_index, encoder_sample_index, config.encoder_stale_after_samples):
        flags.append(f"{axis}_encoder_stale")

    if _disagrees(step_count, encoder_count, config.disagreement_threshold_counts):
        flags.append(f"{axis}_step_encoder_disagreement")


def _is_stale(
    sample_index: int | None,
    encoder_sample_index: int | None,
    stale_after_samples: int | None,
) -> bool:
    if sample_index is None or encoder_sample_index is None or stale_after_samples is None:
        return False
    return sample_index - encoder_sample_index > stale_after_samples


def _disagrees(
    step_count: int,
    encoder_count: int,
    threshold_counts: int | None,
) -> bool:
    if threshold_counts is None:
        return False
    return abs(step_count - encoder_count) > threshold_counts
