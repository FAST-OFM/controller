"""Firmware-side config ownership guardrails.

The checker is intentionally software-only. It reads already-parsed config
data, or static files through its CLI, and validates repository ownership
boundaries. It does not bind adapters, contact controllers, open cameras,
toggle outputs, drive LEDs, command motion or flash firmware.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


FIRMWARE_OWNED_CONFIG_SECTIONS = (
    "controller",
    "firmware_base",
    "io",
    "motion",
    "motor_controller",
    "profile",
    "protocol",
    "scheduler",
    "scanner_sync",
)

FORBIDDEN_RUNTIME_FIELDS: Mapping[str, str] = {
    "acquisition": "Pi acquisition runtime belongs in scanner-pi",
    "acquisition_pipeline": "Pi acquisition runtime belongs in scanner-pi",
    "acquisition_runtime": "Pi acquisition runtime belongs in scanner-pi",
    "autofocus": "Autofocus runtime belongs in scanner-pi",
    "autofocus_runtime": "Autofocus runtime belongs in scanner-pi",
    "autofocus_worker": "Autofocus runtime belongs in scanner-pi",
    "binning": "Camera mode config belongs in scanner-pi",
    "binning_x": "Camera mode config belongs in scanner-pi",
    "binning_y": "Camera mode config belongs in scanner-pi",
    "calibration_records": "Calibration registry runtime belongs in scanner-pi",
    "calibration_registry": "Calibration registry runtime belongs in scanner-pi",
    "camera": "Camera runtime/config belongs in scanner-pi",
    "camera_adapter": "Camera runtime/config belongs in scanner-pi",
    "camera_config": "Camera runtime/config belongs in scanner-pi",
    "camera_frame_source": "Camera runtime/config belongs in scanner-pi",
    "camera_mode": "Camera mode config belongs in scanner-pi",
    "camera_modes": "Camera mode config belongs in scanner-pi",
    "camera_runtime": "Camera runtime/config belongs in scanner-pi",
    "crop": "Camera crop config belongs in scanner-pi",
    "crop_alignment_px": "Camera crop config belongs in scanner-pi",
    "exposure_us": "Camera mode config belongs in scanner-pi",
    "flatfield": "Image calibration runtime belongs in scanner-pi",
    "flat_field": "Image calibration runtime belongs in scanner-pi",
    "frame_period_us": "Camera mode config belongs in scanner-pi",
    "frame_queue": "Pi acquisition runtime belongs in scanner-pi",
    "image": "Image processing runtime belongs in scanner-pi",
    "image_pipeline": "Image processing runtime belongs in scanner-pi",
    "image_processing": "Image processing runtime belongs in scanner-pi",
    "images": "Image processing runtime belongs in scanner-pi",
    "output_height": "Camera mode config belongs in scanner-pi",
    "output_width": "Camera mode config belongs in scanner-pi",
    "pixel_format": "Camera mode config belongs in scanner-pi",
    "prescan": "Pi acquisition/runtime planning belongs in scanner-pi",
    "raw_frame": "Pi acquisition runtime belongs in scanner-pi",
    "raw_image": "Image processing runtime belongs in scanner-pi",
    "scan_recipe": "Scan recipes and tiling belong in scanner-pi or scanner-docs schemas",
    "sensor_height": "Camera mode config belongs in scanner-pi",
    "sensor_width": "Camera mode config belongs in scanner-pi",
    "tile": "Tile runtime belongs in scanner-pi",
    "tile_height": "Tile runtime belongs in scanner-pi",
    "tile_overlap": "Tile runtime belongs in scanner-pi",
    "tile_pipeline": "Tile runtime belongs in scanner-pi",
    "tile_planner": "Tile runtime belongs in scanner-pi",
    "tile_writer": "Tile runtime belongs in scanner-pi",
    "tile_width": "Tile runtime belongs in scanner-pi",
    "tiles": "Tile runtime belongs in scanner-pi",
    "tiling": "Tile runtime belongs in scanner-pi",
}

UNKNOWN_HARDWARE_PLACEHOLDER_VALUES = frozenset(
    (
        "fixme",
        "placeholder",
        "tbd",
        "todo",
        "to_be_determined",
    )
)

UNKNOWN_HARDWARE_PATH_NAMES = frozenset(
    (
        "diag",
        "endstop",
        "gpio",
        "home",
        "homing",
        "pin",
        "pins",
        "rail",
        "rails",
    )
)

STATIC_CONFIG_PATTERNS = (
    "boards/**/*.json",
    "boards/**/*.yaml",
    "boards/**/*.yml",
    "arduino/**/hardware-config.json",
    "arduino/**/hardware-config.yaml",
    "arduino/**/hardware-config.yml",
)


@dataclass(frozen=True, order=True)
class ConfigSplitViolation:
    source: str
    field_path: str
    field_name: str
    message: str

    def to_json_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "field_path": self.field_path,
            "field_name": self.field_name,
            "message": self.message,
        }


@dataclass(frozen=True)
class ConfigSplitReport:
    checked_paths: tuple[str, ...]
    violations: tuple[ConfigSplitViolation, ...]

    @property
    def accepted(self) -> bool:
        return not self.violations

    def to_json_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "checked_paths": list(self.checked_paths),
            "firmware_owned_config_sections": list(FIRMWARE_OWNED_CONFIG_SECTIONS),
            "violations": [violation.to_json_dict() for violation in self.violations],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_dict(), indent=2, sort_keys=True) + "\n"


def check_firmware_config_split_from_mapping(
    data: Mapping[str, Any],
    *,
    source: str = "<mapping>",
) -> ConfigSplitReport:
    """Return a deterministic ownership report for one parsed config mapping."""

    return ConfigSplitReport(
        checked_paths=(source,),
        violations=tuple(sorted(_iter_violations(data, source=source, path=()))),
    )


def check_firmware_config_split_files(paths: Iterable[Path]) -> ConfigSplitReport:
    """Load static JSON/YAML config files and validate firmware ownership."""

    checked_paths: list[str] = []
    violations: list[ConfigSplitViolation] = []
    for path in sorted({item.resolve() for item in paths}):
        source = _display_path(path)
        checked_paths.append(source)
        try:
            data = load_static_config_file(path)
        except ConfigSplitError as exc:
            violations.append(
                ConfigSplitViolation(
                    source=source,
                    field_path="<file>",
                    field_name="<file>",
                    message=str(exc),
                )
            )
            continue
        if not isinstance(data, Mapping):
            violations.append(
                ConfigSplitViolation(
                    source=source,
                    field_path="<root>",
                    field_name="<root>",
                    message="static firmware config must parse to a mapping",
                )
            )
            continue
        violations.extend(_iter_violations(data, source=source, path=()))
    return ConfigSplitReport(
        checked_paths=tuple(checked_paths),
        violations=tuple(sorted(violations)),
    )


def discover_static_config_paths(repo_root: Path) -> tuple[Path, ...]:
    """Find checked-in firmware-side config candidates for static checks."""

    root = repo_root.resolve()
    paths: set[Path] = set()
    for pattern in STATIC_CONFIG_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file() and "tools" not in path.relative_to(root).parts:
                paths.add(path)
    return tuple(sorted(paths))


def load_static_config_file(path: Path) -> object:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigSplitError(f"invalid JSON: {exc}") from exc
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - exercised only without dev deps
            raise ConfigSplitError("PyYAML is required to parse YAML config files") from exc
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigSplitError(f"invalid YAML: {exc}") from exc
    raise ConfigSplitError(f"unsupported config suffix: {suffix}")


class ConfigSplitError(ValueError):
    """Raised when a static config file cannot be checked."""


def _iter_violations(
    value: object,
    *,
    source: str,
    path: tuple[str, ...],
) -> tuple[ConfigSplitViolation, ...]:
    violations: list[ConfigSplitViolation] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                violations.append(
                    ConfigSplitViolation(
                        source=source,
                        field_path=_format_path((*path, "<non-string-field>")),
                        field_name="<non-string-field>",
                        message="config field names must be strings",
                    )
                )
                continue
            child_path = (*path, key)
            normalized = _normalize_field_name(key)
            message = FORBIDDEN_RUNTIME_FIELDS.get(normalized)
            if message is not None:
                violations.append(
                    ConfigSplitViolation(
                        source=source,
                        field_path=_format_path(child_path),
                        field_name=key,
                        message=message,
                    )
                )
            if _is_unknown_hardware_placeholder(child, child_path):
                violations.append(
                    ConfigSplitViolation(
                        source=source,
                        field_path=_format_path(child_path),
                        field_name=key,
                        message="unknown hardware values must use explicit 'unknown'",
                    )
                )
            violations.extend(_iter_violations(child, source=source, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            violations.extend(_iter_violations(child, source=source, path=(*path, f"[{index}]")))
    return tuple(violations)


def _is_unknown_hardware_placeholder(value: object, path: tuple[str, ...]) -> bool:
    if not isinstance(value, str):
        return False
    if _normalize_field_name(value) not in UNKNOWN_HARDWARE_PLACEHOLDER_VALUES:
        return False
    return _is_unknown_hardware_path(path)


def _is_unknown_hardware_path(path: tuple[str, ...]) -> bool:
    normalized_parts = tuple(
        _normalize_field_name(part)
        for part in path
        if not part.startswith("[")
    )
    for part in normalized_parts:
        if part in UNKNOWN_HARDWARE_PATH_NAMES:
            return True
        if any(name in part for name in UNKNOWN_HARDWARE_PATH_NAMES):
            return True
    return False


def _normalize_field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _format_path(path: tuple[str, ...]) -> str:
    if not path:
        return "<root>"
    output = ""
    for part in path:
        if part.startswith("["):
            output += part
        elif output:
            output += f".{part}"
        else:
            output = part
    return output


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
