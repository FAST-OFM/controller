#!/usr/bin/env python3
"""Static scanner-firmware repository boundary guardrail.

The checker reads Python source files only. It does not import camera SDKs,
open devices, contact controllers, toggle outputs, command motion, drive LEDs,
or flash firmware.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

from scanner_firmware.domain.platform_config.config_split import (  # noqa: E402
    FORBIDDEN_RUNTIME_FIELDS,
)


DEFAULT_RUNTIME_ROOT = Path("src/scanner_firmware")
DEFAULT_ALLOWED_MODEL_PATHS = frozenset(
    (
        Path("src/scanner_firmware/adapters/klipper_adapter/event_streaming/model.py"),
        Path("src/scanner_firmware/adapters/klipper_adapter/model.py"),
        Path("src/scanner_firmware/domain/camera_config/model.py"),
        Path("src/scanner_firmware/domain/platform_config/model.py"),
    )
)
DEFAULT_ALLOWED_REEXPORT_FACADE_PATHS = frozenset(
    (
        Path("src/scanner_firmware/domain/calibration/__init__.py"),
    )
)

FORBIDDEN_REPO_IMPORT_ROOTS = frozenset(("scanner-pi", "scanner_pi", "scannerpi"))
FORBIDDEN_CAMERA_SDK_IMPORT_ROOTS = frozenset(
    (
        "arducam",
        "cv2",
        "gphoto2",
        "libcamera",
        "picamera",
        "picamera2",
        "pypylon",
    )
)
FORBIDDEN_IMPORT_ROOTS = FORBIDDEN_REPO_IMPORT_ROOTS | FORBIDDEN_CAMERA_SDK_IMPORT_ROOTS
FORBIDDEN_DYNAMIC_IMPORT_CALLS = frozenset(("__import__", "import_module"))
FORBIDDEN_PATH_NAMES = (
    frozenset(
        name
        for name, message in FORBIDDEN_RUNTIME_FIELDS.items()
        if "runtime" in message
        or "scanner-pi" in message
        or "Image processing" in message
        or "Tile runtime" in message
    )
    | frozenset(("scanner-pi", "scanner_pi", "scannerpi"))
) - frozenset(
    (
        "binning",
        "binning_x",
        "binning_y",
        "camera_config",
        "camera_mode",
        "camera_modes",
        "crop",
        "crop_alignment_px",
        "exposure_us",
        "frame_period_us",
        "output_height",
        "output_width",
        "pixel_format",
        "sensor_height",
        "sensor_width",
    )
)


@dataclass(frozen=True, order=True)
class RepoBoundaryViolation:
    path: str
    line: int
    code: str
    message: str

    def format(self) -> str:
        location = self.path if self.line == 0 else f"{self.path}:{self.line}"
        return f"{location}: {self.code}: {self.message}"


@dataclass(frozen=True)
class RepoBoundaryReport:
    checked_paths: tuple[str, ...]
    violations: tuple[RepoBoundaryViolation, ...]

    @property
    def accepted(self) -> bool:
        return not self.violations


def check_firmware_repo_boundary(
    repo_root: Path,
    *,
    runtime_root: Path | None = None,
    allowed_model_paths: Iterable[Path] = DEFAULT_ALLOWED_MODEL_PATHS,
    allowed_reexport_facade_paths: Iterable[Path] = DEFAULT_ALLOWED_REEXPORT_FACADE_PATHS,
) -> RepoBoundaryReport:
    root = repo_root.resolve()
    source_root = _resolve_under(root, runtime_root or DEFAULT_RUNTIME_ROOT)
    allowed_models = _relative_path_set(allowed_model_paths)
    allowed_facades = _relative_path_set(allowed_reexport_facade_paths)

    checked_paths: list[str] = []
    violations: list[RepoBoundaryViolation] = []
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root)
        display_path = relative.as_posix()
        checked_paths.append(display_path)
        violations.extend(_path_name_violations(relative))
        try:
            tree = ast.parse(path.read_text(), filename=display_path)
        except SyntaxError as exc:
            violations.append(
                RepoBoundaryViolation(
                    path=display_path,
                    line=exc.lineno or 0,
                    code="python-syntax",
                    message=str(exc),
                )
            )
            continue
        violations.extend(_import_violations(display_path, tree))
        if path.name == "__init__.py" and relative not in allowed_facades:
            violations.extend(_reexport_facade_violations(display_path, tree))
        if path.name == "model.py":
            violations.extend(_model_module_violations(display_path, relative, tree, allowed_models))

    return RepoBoundaryReport(
        checked_paths=tuple(checked_paths),
        violations=tuple(sorted(violations)),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to check.",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=DEFAULT_RUNTIME_ROOT,
        help="Runtime source root, relative to repo root unless absolute.",
    )
    args = parser.parse_args(argv)

    report = check_firmware_repo_boundary(args.repo_root, runtime_root=args.runtime_root)
    for violation in report.violations:
        print(violation.format(), file=sys.stderr)
    return 0 if report.accepted else 1


def _resolve_under(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def _relative_path_set(paths: Iterable[Path]) -> frozenset[Path]:
    return frozenset(Path(path) for path in paths)


def _path_name_violations(relative: Path) -> list[RepoBoundaryViolation]:
    violations: list[RepoBoundaryViolation] = []
    parts = list(relative.parts)
    parts[-1] = relative.stem
    for part in parts:
        normalized = _normalized_path_name(part)
        if normalized in FORBIDDEN_PATH_NAMES:
            violations.append(
                RepoBoundaryViolation(
                    path=relative.as_posix(),
                    line=0,
                    code="pi-owned-path",
                    message=f"Pi-owned runtime name belongs outside scanner-firmware: {part}",
                )
            )
    return violations


def _import_violations(path: str, tree: ast.AST) -> list[RepoBoundaryViolation]:
    violations: list[RepoBoundaryViolation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(_forbidden_import(path, node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                violations.append(_forbidden_import(path, node.lineno, node.module))
        elif isinstance(node, ast.Call) and _call_name(node.func) in FORBIDDEN_DYNAMIC_IMPORT_CALLS:
            imported = _first_string_arg(node)
            if imported:
                root = imported.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(_forbidden_import(path, node.lineno, imported))
    return violations


def _forbidden_import(path: str, line: int, module: str) -> RepoBoundaryViolation:
    return RepoBoundaryViolation(
        path=path,
        line=line,
        code="forbidden-import",
        message=f"Pi-owned or camera SDK import is not allowed in firmware runtime: {module}",
    )


def _reexport_facade_violations(path: str, tree: ast.Module) -> list[RepoBoundaryViolation]:
    statements = [_meaningful_statement(node) for node in tree.body]
    statements = [statement for statement in statements if statement is not None]
    has_import = any(statement == "import" for statement in statements)
    if has_import and all(statement in ("import", "all") for statement in statements):
        return [
            RepoBoundaryViolation(
                path=path,
                line=1,
                code="reexport-facade",
                message="package initializer is a re-export-only facade",
            )
        ]
    return []


def _model_module_violations(
    path: str,
    relative: Path,
    tree: ast.Module,
    allowed_model_paths: frozenset[Path],
) -> list[RepoBoundaryViolation]:
    violations: list[RepoBoundaryViolation] = []
    if relative not in allowed_model_paths:
        violations.append(
            RepoBoundaryViolation(
                path=path,
                line=1,
                code="model-not-allowlisted",
                message="model.py must be a documented cohesive model owner",
            )
        )
    if any(isinstance(node, ast.Assign) and _assigns_name(node, "__all__") for node in tree.body):
        violations.append(
            RepoBoundaryViolation(
                path=path,
                line=1,
                code="model-dumping-ground",
                message="model.py must not act as a re-export surface",
            )
        )
    if not any(isinstance(node, ast.ClassDef) for node in tree.body):
        violations.append(
            RepoBoundaryViolation(
                path=path,
                line=1,
                code="model-dumping-ground",
                message="model.py must own concrete classes or local contracts",
            )
        )
    return violations


def _meaningful_statement(node: ast.stmt) -> str | None:
    if _is_docstring_expr(node):
        return None
    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
        return None
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "import"
    if isinstance(node, ast.Assign) and _assigns_name(node, "__all__"):
        return "all"
    return "other"


def _is_docstring_expr(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _assigns_name(node: ast.Assign, name: str) -> bool:
    return any(isinstance(target, ast.Name) and target.id == name for target in node.targets)


def _first_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    value = node.args[0]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _normalized_path_name(part: str) -> str:
    return re.sub(r"[-.]+", "_", part)


if __name__ == "__main__":
    raise SystemExit(main())
