"""Pure focus-metric replay projection and hash helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


REQUIRED_CALIBRATION_ROLES = (
    "dark_frame",
    "af_flatfield",
    "focus_curve",
    "led_geometry",
    "objective",
    "camera_mode",
)
REJECTION_CODES = (
    "missing_calibration_id",
    "calibration_mismatch",
    "non_raw_format",
    "nonlinear_data",
    "preview_frame",
)
OFFLINE_REJECTION_CODES = tuple(code for code in REJECTION_CODES if code != "calibration_mismatch")
RAW_FORMATS = frozenset({"raw_bayer", "linear_raw", "raw_sensor"})
COMPRESSED_ENCODINGS = frozenset({"JPEG", "JPG", "H264", "MJPEG"})
LINEAR_DOMAINS = frozenset({"raw_sensor", "linear"})
NONLINEAR_TRANSFORMS = (
    "debayer",
    "gamma",
    "denoise",
    "sharpening",
    "color_correction",
)
SOURCE_PROJECTION_FIELDS = (
    "path",
    "checksum_sha256",
    "format",
    "encoding",
    "pixel_format",
    "cfa_pattern",
    "packing",
    "compression",
    "data_domain",
    "stream_name",
    "width_px",
    "height_px",
    "stride_bytes",
    "bit_depth",
    "linear",
    "preview",
    "pipeline_transforms",
)
CALIBRATION_PROJECTION_FIELDS = (
    "calibration_id",
    "checksum_sha256",
    "active",
)
FRAME_METADATA_PROJECTION_FIELDS = (
    "frame_id",
    "scan_id",
    "pattern",
    "z_cmd_count",
    "camera_mode_id",
    "hardware_outputs_enabled",
)


def canonical_sha256(value: Any) -> str:
    """Return the canonical JSON SHA-256 used by replay contracts."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def manifest_rejection_codes(
    manifest: Mapping[str, Any],
    calibration_registry: Mapping[str, Any] | None = None,
    *,
    required_calibration_roles: Sequence[str] = REQUIRED_CALIBRATION_ROLES,
    include_calibration_mismatch: bool = False,
) -> list[str]:
    """Return deterministic rejection codes for a focus-metric replay manifest."""

    codes: list[str] = []
    source = _mapping(manifest.get("source_frame"))
    codes.extend(source_frame_rejection_codes(source))

    calibrations = _mapping(manifest.get("calibrations"))
    registry = _mapping(calibration_registry)
    missing_calibration_codes = missing_calibration_id_rejection_codes(
        calibrations,
        required_calibration_roles=required_calibration_roles,
        require_active=True,
    )
    codes.extend(missing_calibration_codes)
    if not missing_calibration_codes and include_calibration_mismatch:
        for role in required_calibration_roles:
            ref = calibrations[role]
            if not calibration_matches_registry(role, ref, registry):
                codes.append("calibration_mismatch")
                break
    return codes


def source_frame_rejection_codes(
    source: Mapping[str, Any],
    *,
    raw_formats: frozenset[str] = RAW_FORMATS,
    compressed_encodings: frozenset[str] = COMPRESSED_ENCODINGS,
    linear_domains: frozenset[str] = LINEAR_DOMAINS,
    nonlinear_transforms: Sequence[str] = NONLINEAR_TRANSFORMS,
    require_linear_domain: bool = True,
) -> list[str]:
    """Return RAW/preview/linear source rejection codes in canonical order."""

    codes: list[str] = []
    encoding = str(source.get("encoding", "")).upper()
    compression = str(source.get("compression", "")).lower()
    if (
        source.get("format") not in raw_formats
        or encoding in compressed_encodings
        or compression not in {"none", ""}
    ):
        codes.append("non_raw_format")
    if source.get("preview") is True or source.get("stream_name") == "preview":
        codes.append("preview_frame")

    transforms = _mapping(source.get("pipeline_transforms"))
    if (
        source.get("linear") is not True
        or (require_linear_domain and source.get("data_domain") not in linear_domains)
        or any(transforms.get(key) is True for key in nonlinear_transforms)
    ):
        codes.append("nonlinear_data")
    return codes


def missing_calibration_id_rejection_codes(
    calibrations: Mapping[str, Any],
    *,
    required_calibration_roles: Sequence[str] = REQUIRED_CALIBRATION_ROLES,
    require_active: bool = True,
) -> list[str]:
    """Return `missing_calibration_id` when any required calibration ref is absent."""

    for role in required_calibration_roles:
        ref = calibrations.get(role)
        if not _valid_calibration_ref(ref, require_active=require_active):
            return ["missing_calibration_id"]
    return []


def calibration_matches_registry(
    role: str,
    ref: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> bool:
    """Return whether a manifest calibration reference matches the active registry."""

    expected = registry.get(role)
    return (
        isinstance(expected, Mapping)
        and ref.get("calibration_id") == expected.get("calibration_id")
        and ref.get("checksum_sha256") == expected.get("checksum_sha256")
        and ref.get("active") is True
    )


def source_frame_checksum(source: Mapping[str, Any]) -> str:
    """Return the hash for inline source-frame rows."""

    return canonical_sha256(
        {
            "dtype": source.get("dtype"),
            "shape": [source.get("height_px"), source.get("width_px")],
            "inline_rows": source.get("inline_rows"),
        }
    )


def metric_config_sha256(manifest: Mapping[str, Any]) -> str:
    return canonical_sha256(manifest.get("metric_config", {}))


def calibration_reference_sha256(
    manifest: Mapping[str, Any],
    *,
    required_calibration_roles: Sequence[str] = REQUIRED_CALIBRATION_ROLES,
) -> str:
    return canonical_sha256(
        selected_calibration_fields(
            _mapping(manifest.get("calibrations")),
            required_calibration_roles=required_calibration_roles,
        )
    )


def focus_metric_result_sha256(
    manifest: Mapping[str, Any],
    focus_metric_result: Mapping[str, Any],
    *,
    contract_id: str,
    artifact_kind: str,
    required_calibration_roles: Sequence[str] = REQUIRED_CALIBRATION_ROLES,
) -> str:
    return canonical_sha256(
        {
            "schema_version": 1,
            "contract_id": contract_id,
            "artifact_kind": artifact_kind,
            "manifest_id": manifest["manifest_id"],
            "source_frame": selected_source_fields(_mapping(manifest.get("source_frame"))),
            "metric_config": manifest.get("metric_config", {}),
            "calibrations": selected_calibration_fields(
                _mapping(manifest.get("calibrations")),
                required_calibration_roles=required_calibration_roles,
            ),
            "frame_metadata": selected_frame_metadata_fields(
                _mapping(manifest.get("frame_metadata"))
            ),
            "focus_metric_result": focus_metric_result,
        }
    )


def replay_decision_sha256(
    manifest_id: str,
    actual_result: str,
    rejection_codes: Sequence[str],
    *,
    contract_id: str,
) -> str:
    return canonical_sha256(
        {
            "schema_version": 1,
            "contract_id": contract_id,
            "manifest_id": manifest_id,
            "actual_result": actual_result,
            "rejection_codes": sorted(rejection_codes),
        }
    )


def selected_source_fields(source: Mapping[str, Any]) -> dict[str, Any]:
    return {key: source.get(key) for key in SOURCE_PROJECTION_FIELDS}


def selected_calibration_fields(
    calibrations: Mapping[str, Any],
    *,
    required_calibration_roles: Sequence[str] = REQUIRED_CALIBRATION_ROLES,
) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for role in required_calibration_roles:
        ref = calibrations.get(role)
        if isinstance(ref, Mapping):
            selected[role] = {
                key: ref.get(key)
                for key in CALIBRATION_PROJECTION_FIELDS
            }
    return selected


def selected_frame_metadata_fields(frame: Mapping[str, Any]) -> dict[str, Any]:
    return {key: frame.get(key) for key in FRAME_METADATA_PROJECTION_FIELDS}


def _valid_calibration_ref(ref: object, *, require_active: bool) -> bool:
    return (
        isinstance(ref, Mapping)
        and isinstance(ref.get("calibration_id"), str)
        and bool(ref["calibration_id"].strip())
        and (not require_active or ref.get("active") is True)
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
