import importlib
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_core.predictive_z.types import ZCommand  # noqa: E402
from scanner_core.scan_geometry import StripeGeometry, validate_axis  # noqa: E402
from scanner_firmware.domain.board_profile.kinematics import AxisKinematics  # noqa: E402
from scanner_firmware.domain.calibration.types import AxisCalibrationEstimate  # noqa: E402
from scanner_firmware.domain.coordinate_source.types import CoordinateSample  # noqa: E402
from scanner_firmware.domain.platform_config.model import PlatformProfile  # noqa: E402
from scanner_firmware.foundation.protocol.events import FrameEventRecord  # noqa: E402
from scanner_firmware.planning.led_scheduler.types import LedPattern  # noqa: E402
from scanner_firmware.planning.trigger_scheduler.types import StripeSchedule  # noqa: E402


MOVED_TO_SCANNER_PI = (
    "scanner_firmware.adapters.led_brightness",
    "scanner_firmware.domain.camera_config",
    "scanner_firmware.domain.focus_metric",
    "scanner_firmware.domain.scan_mode",
    "scanner_firmware.planning.autofocus_control",
    "scanner_firmware.planning.frame_counter.matching",
    "scanner_firmware.planning.scan_planning",
)

MOVED_TO_SCANNER_CORE = (
    "scanner_firmware.domain.scan_math.geometry",
    "scanner_firmware.domain.scan_math.units",
)

DISALLOWED_PACKAGE_FACADES = (
    "scanner_firmware.domain.calibration",
)


class ScannerFirmwareNamespaceTests(unittest.TestCase):
    def test_firmware_owned_implementations_live_in_layered_namespace(self):
        self.assertEqual(
            FrameEventRecord.__module__,
            "scanner_firmware.foundation.protocol.events",
        )
        self.assertEqual(
            AxisKinematics.__module__,
            "scanner_firmware.domain.board_profile.kinematics",
        )
        self.assertEqual(
            AxisCalibrationEstimate.__module__,
            "scanner_firmware.domain.calibration.types",
        )
        self.assertEqual(
            CoordinateSample.__module__,
            "scanner_firmware.domain.coordinate_source.types",
        )
        self.assertEqual(
            PlatformProfile.__module__,
            "scanner_firmware.domain.platform_config.model",
        )
        self.assertEqual(StripeGeometry.__module__, "scanner_core.scan_geometry")
        self.assertEqual(validate_axis.__module__, "scanner_core.scan_geometry")
        self.assertEqual(
            LedPattern.__module__,
            "scanner_firmware.planning.led_scheduler.types",
        )
        self.assertEqual(
            StripeSchedule.__module__,
            "scanner_firmware.planning.trigger_scheduler.types",
        )
        self.assertEqual(ZCommand.__module__, "scanner_core.predictive_z.types")

    def test_pi_owned_package_roots_are_not_firmware_modules(self):
        for module_name in MOVED_TO_SCANNER_PI:
            with self.subTest(module_name=module_name):
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(module_name)

    def test_pi_owned_namespace_paths_are_absent_from_source_tree(self):
        for module_name in MOVED_TO_SCANNER_PI:
            with self.subTest(module_name=module_name):
                relative = _module_name_to_relative_path(module_name)

                self.assertFalse((REPO_ROOT / "src" / relative).exists())
                self.assertFalse((REPO_ROOT / "src" / f"{relative}.py").exists())

    def test_scanner_core_owned_scan_math_facades_are_absent(self):
        for module_name in MOVED_TO_SCANNER_CORE:
            with self.subTest(module_name=module_name):
                relative = _module_name_to_relative_path(module_name)

                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(module_name)
                self.assertFalse((REPO_ROOT / "src" / relative).exists())
                self.assertFalse((REPO_ROOT / "src" / f"{relative}.py").exists())

    def test_scanner_core_owned_predictive_z_symbols_are_not_reexported(self):
        z_types = importlib.import_module("scanner_firmware.planning.z_scheduler.types")
        z_predictive = importlib.import_module("scanner_firmware.planning.z_scheduler.predictive")

        for symbol in ("ZCommand", "StripeContext", "ZSchedulerConfig"):
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(z_types, symbol))
        for symbol in ("PredictiveZPlanner", "ZFocusErrorSample", "ZPredictivePlannerConfig"):
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(z_predictive, symbol))

    def test_package_level_reexport_facades_are_absent(self):
        for module_name in DISALLOWED_PACKAGE_FACADES:
            with self.subTest(module_name=module_name):
                relative = _module_name_to_relative_path(module_name)

                self.assertFalse((REPO_ROOT / "src" / relative / "__init__.py").exists())


def _module_name_to_relative_path(module_name: str) -> Path:
    return Path(*module_name.split("."))


if __name__ == "__main__":
    unittest.main()
