import ast
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


FORBIDDEN_IMPORT_ROOTS = frozenset(
    (
        "gpiozero",
        "paramiko",
        "pigpio",
        "requests",
        "RPi",
        "serial",
        "smbus",
        "socket",
        "spidev",
        "subprocess",
        "urllib",
    )
)
FORBIDDEN_CALL_NAMES = frozenset(("system", "popen"))
FORBIDDEN_METHOD_NAMES = frozenset(("raw_send", "send", "send_wait_ack"))
TEST_MARKER_GROUPS = ("architecture", "contract", "integration", "unit")
PI_OWNED_PACKAGE_PATHS = (
    SRC_ROOT / "scanner_firmware" / "adapters" / "led_brightness",
    SRC_ROOT / "scanner_firmware" / "domain" / "camera_config",
    SRC_ROOT / "scanner_firmware" / "domain" / "focus_metric",
    SRC_ROOT / "scanner_firmware" / "domain" / "scan_mode",
    SRC_ROOT / "scanner_firmware" / "planning" / "autofocus_control",
    SRC_ROOT / "scanner_firmware" / "planning" / "frame_counter" / "matching",
    SRC_ROOT / "scanner_firmware" / "planning" / "scan_planning",
)


class ArchitectureGuardrailTests(unittest.TestCase):
    def test_src_python_modules_do_not_import_live_hardware_or_process_libraries(self):
        violations = []
        for path, tree in _src_python_trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".", 1)[0]
                        if root in FORBIDDEN_IMPORT_ROOTS:
                            violations.append(f"{path}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".", 1)[0]
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        violations.append(f"{path}:{node.lineno} from {node.module}")

        self.assertEqual(violations, [])

    def test_src_python_modules_do_not_call_live_hardware_or_process_apis(self):
        violations = []
        for path, tree in _src_python_trees():
            if path.name == "fake.py":
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call_name = _call_name(node.func)
                if call_name in FORBIDDEN_CALL_NAMES:
                    violations.append(f"{path}:{node.lineno} call {call_name}()")
                method_name = _method_name(node.func)
                if method_name in FORBIDDEN_METHOD_NAMES:
                    violations.append(f"{path}:{node.lineno} call .{method_name}()")

        self.assertEqual(violations, [])

    def test_klipper_adapter_keeps_explicit_protocol_interfaces(self):
        model_tree = ast.parse(
            (
                SRC_ROOT / "scanner_firmware" / "adapters" / "klipper_adapter" / "model.py"
            ).read_text()
        )
        dispatch_tree = ast.parse(
            (
                SRC_ROOT
                / "scanner_firmware"
                / "adapters"
                / "klipper_adapter"
                / "event_streaming"
                / "dispatch.py"
            ).read_text()
        )
        scanner_sync_interfaces_tree = ast.parse(
            (
                SRC_ROOT
                / "scanner_firmware"
                / "planning"
                / "scanner_sync"
                / "interfaces.py"
            ).read_text()
        )

        self.assertTrue(_class_inherits(model_tree, "KlipperCommand", "Protocol"))
        self.assertTrue(_class_inherits(model_tree, "KlipperMcu", "Protocol"))
        self.assertTrue(_class_inherits(dispatch_tree, "ProtocolRecordSink", "Protocol"))
        self.assertTrue(
            _class_inherits(scanner_sync_interfaces_tree, "PositionSampleSource", "Protocol")
        )
        self.assertTrue(
            _class_inherits(scanner_sync_interfaces_tree, "ScanExecutionBackend", "Protocol")
        )

    def test_every_simulator_test_file_has_exactly_one_marker_group(self):
        import conftest  # noqa: PLC0415

        violations = []
        for path in sorted((REPO_ROOT / "tests" / "simulator").glob("test_*.py")):
            markers = [
                marker
                for marker in conftest._markers_for_file(path.name)
                if marker in TEST_MARKER_GROUPS
            ]
            if len(markers) != 1:
                violations.append(f"{path.name}: {markers}")

        self.assertEqual(violations, [])

    def test_pi_owned_package_roots_are_not_reintroduced_in_firmware(self):
        existing = [path.relative_to(REPO_ROOT).as_posix() for path in PI_OWNED_PACKAGE_PATHS if path.exists()]

        self.assertEqual(existing, [])


def _src_python_trees():
    for path in sorted(SRC_ROOT.rglob("*.py")):
        yield path.relative_to(REPO_ROOT), ast.parse(path.read_text())


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _method_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _class_inherits(tree: ast.AST, class_name: str, base_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == base_name:
                return True
            if isinstance(base, ast.Attribute) and base.attr == base_name:
                return True
    return False


if __name__ == "__main__":
    unittest.main()
