import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from check_firmware_repo_boundary import (  # noqa: E402
    DEFAULT_ALLOWED_MODEL_PATHS,
    check_firmware_repo_boundary,
)


class FirmwareRepoBoundaryGuardrailTests(unittest.TestCase):
    def test_current_firmware_runtime_tree_has_no_repo_boundary_leaks(self):
        report = check_firmware_repo_boundary(REPO_ROOT)

        self.assertEqual([violation.format() for violation in report.violations], [])
        self.assertGreater(len(report.checked_paths), 0)

    def test_temp_fixture_accepts_focused_firmware_runtime_modules(self):
        root = _fixture_root(self)
        _write(
            root / "src/scanner_firmware/domain/scan_math/units.py",
            """
            from dataclasses import dataclass

            @dataclass(frozen=True)
            class PositionCount:
                value: int
            """,
        )
        _write(
            root / "src/scanner_firmware/domain/scan_math/__init__.py",
            '"""Scan math namespace."""\n',
        )

        report = check_firmware_repo_boundary(
            root,
            allowed_model_paths=(),
            allowed_reexport_facade_paths=(),
        )

        self.assertEqual([violation.format() for violation in report.violations], [])

    def test_temp_fixture_rejects_scanner_pi_and_camera_sdk_imports(self):
        root = _fixture_root(self)
        _write(
            root / "src/scanner_firmware/adapters/controller_adapter/leaky.py",
            """
            import importlib
            import picamera2
            from scanner_pi.camera import CameraRuntime

            importlib.import_module("libcamera.controls")
            __import__("scanner-pi.camera")
            """,
        )

        report = check_firmware_repo_boundary(
            root,
            allowed_model_paths=(),
            allowed_reexport_facade_paths=(),
        )

        self.assertEqual(
            _codes(report),
            ["forbidden-import", "forbidden-import", "forbidden-import", "forbidden-import"],
        )
        self.assertTrue(
            any("scanner_pi.camera" in violation.message for violation in report.violations)
        )
        self.assertTrue(
            any("scanner-pi.camera" in violation.message for violation in report.violations)
        )
        self.assertTrue(any("picamera2" in violation.message for violation in report.violations))
        self.assertTrue(
            any("libcamera.controls" in violation.message for violation in report.violations)
        )

    def test_temp_fixture_rejects_pi_owned_runtime_path_names(self):
        root = _fixture_root(self)
        _write(
            root / "src/scanner_firmware/adapters/camera_runtime/runner.py",
            "class Boundary:\n    pass\n",
        )
        _write(
            root / "src/scanner_firmware/domain/image_processing.py",
            "class Pipeline:\n    pass\n",
        )

        report = check_firmware_repo_boundary(root, allowed_model_paths=())

        self.assertEqual(_codes(report), ["pi-owned-path", "pi-owned-path"])
        self.assertTrue(
            any("camera_runtime" in violation.message for violation in report.violations)
        )
        self.assertTrue(
            any("image_processing" in violation.message for violation in report.violations)
        )

    def test_temp_fixture_rejects_reexport_only_package_facades(self):
        root = _fixture_root(self)
        _write(
            root / "src/scanner_firmware/domain/calibration/types.py",
            "class CalibrationRecord:\n    pass\n",
        )
        _write(
            root / "src/scanner_firmware/domain/calibration/__init__.py",
            """
            from .types import CalibrationRecord

            __all__ = ["CalibrationRecord"]
            """,
        )

        report = check_firmware_repo_boundary(
            root,
            allowed_model_paths=(),
            allowed_reexport_facade_paths=(),
        )

        self.assertEqual(_codes(report), ["reexport-facade"])

    def test_temp_fixture_rejects_dumping_ground_model_modules(self):
        root = _fixture_root(self)
        model_path = root / "src/scanner_firmware/domain/platform_config/model.py"
        _write(
            model_path,
            """
            from .loader import load_config

            __all__ = ["load_config"]
            """,
        )
        _write(
            root / "src/scanner_firmware/domain/platform_config/loader.py",
            "def load_config():\n    return {}\n",
        )

        report = check_firmware_repo_boundary(root)

        self.assertEqual(_codes(report), ["model-dumping-ground", "model-dumping-ground"])

    def test_temp_fixture_rejects_undocumented_model_modules(self):
        root = _fixture_root(self)
        _write(
            root / "src/scanner_firmware/planning/scan_planning/model.py",
            "class ScanPlan:\n    pass\n",
        )

        report = check_firmware_repo_boundary(root)

        self.assertEqual(_codes(report), ["model-not-allowlisted"])

    def test_documented_allowlist_keeps_cohesive_model_modules_accepted(self):
        root = _fixture_root(self)
        relative = next(iter(DEFAULT_ALLOWED_MODEL_PATHS))
        _write(
            root / relative,
            """
            from dataclasses import dataclass

            @dataclass(frozen=True)
            class LocalModel:
                value: int
            """,
        )

        report = check_firmware_repo_boundary(root)

        self.assertEqual([violation.format() for violation in report.violations], [])


def _fixture_root(test_case: unittest.TestCase) -> Path:
    tmp = Path(test_case.enterContext(tempfile.TemporaryDirectory()))
    (tmp / "src/scanner_firmware").mkdir(parents=True)
    return tmp


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def _codes(report) -> list[str]:
    return sorted(violation.code for violation in report.violations)


if __name__ == "__main__":
    unittest.main()
