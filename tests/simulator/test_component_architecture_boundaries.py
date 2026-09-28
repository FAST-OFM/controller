import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

IGNORED_SOURCE_ROOTS = frozenset(
    ("__pycache__", "scanner_core", "scanner_firmware", "scanner_firmware.egg-info")
)
NAMESPACE_ROOT = SRC_ROOT / "scanner_firmware"

PACKAGES_BY_LAYER = {
    "foundation": frozenset(("firmware_components", "protocol")),
    "domain": frozenset(
        (
            "board_profile",
            "calibration",
            "coordinate_source",
            "io_aliases",
            "platform_config",
            "scan_math",
        )
    ),
    "planning": frozenset(
        (
            "dry_run_pipeline",
            "frame_counter",
            "led_scheduler",
            "manual_center_bringup",
            "readiness",
            "scanner_sync",
            "scan_execution",
            "scan_preflight",
            "trigger_scheduler",
            "z_scheduler",
        )
    ),
    "adapters": frozenset(
        (
            "controller_adapter",
            "firmware_base",
            "homing",
            "klipper_adapter",
            "scanner_sync",
        )
    ),
}
COMPONENT_ROOTS = tuple(sorted(set().union(*PACKAGES_BY_LAYER.values())))
FLAT_PACKAGE_MODULE_LIMIT = 8
DOCUMENTED_FLAT_PACKAGE_ALLOWLIST = frozenset(
    (
        Path("src/scanner_firmware/domain/calibration"),
    )
)
DOCUMENTED_MODEL_MODULE_ALLOWLIST = frozenset(
    (
        Path("src/scanner_firmware/adapters/klipper_adapter/event_streaming/model.py"),
        Path("src/scanner_firmware/adapters/klipper_adapter/model.py"),
        Path("src/scanner_firmware/domain/platform_config/model.py"),
    )
)
PACKAGE_INIT_IMPORT_ALLOWLIST = frozenset(
    (
        Path("src/scanner_firmware/domain/calibration/__init__.py"),
    )
)

FORBIDDEN_IMPORT_ROOTS = frozenset(
    (
        "Adafruit_BBIO",
        "RPi",
        "adafruit_blinka",
        "board",
        "busio",
        "digitalio",
        "gpiozero",
        "lgpio",
        "periphery",
        "pigpio",
        "pyftdi",
        "requests",
        "serial",
        "smbus",
        "smbus2",
        "socket",
        "spidev",
        "subprocess",
        "urllib",
    )
)

FORBIDDEN_CALL_NAMES = frozenset(
    (
        "capture_frame",
        "capture_image",
        "configure_camera",
        "disable_led",
        "drive_led",
        "enable_led",
        "flash_firmware",
        "gpio_read",
        "gpio_write",
        "home_axis",
        "move_axis",
        "move_motor",
        "move_z_now",
        "open_camera",
        "open_serial",
        "open_socket",
        "popen",
        "raw_send",
        "read_gpio",
        "send",
        "send_wait_ack",
        "set_gpio",
        "set_led",
        "setup_gpio",
        "system",
        "toggle_gpio",
        "trigger_camera",
        "trigger_frame",
        "write_gpio",
    )
)


class ComponentArchitectureBoundaryTests(unittest.TestCase):
    def test_component_roots_are_present_under_scanner_firmware_namespace(self):
        missing_required = []
        for layer, packages in PACKAGES_BY_LAYER.items():
            for package in packages:
                if not (NAMESPACE_ROOT / layer / package).exists():
                    missing_required.append(f"{layer}/{package}")

        self.assertEqual(missing_required, [])
        self.assertGreater(len(_component_python_paths()), 0)

    def test_top_level_source_contains_only_scanner_firmware_package_root(self):
        actual = {
            path.name
            for path in SRC_ROOT.iterdir()
            if path.is_dir() and path.name not in IGNORED_SOURCE_ROOTS
        }

        self.assertEqual(actual, set())

    def test_source_tree_hierarchy_is_documented(self):
        architecture = (REPO_ROOT / "docs" / "foundation" / "firmware-architecture.md").read_text()
        contracts = (REPO_ROOT / "docs" / "foundation" / "firmware-contracts.md").read_text()

        self.assertIn("Source Tree Hierarchy", architecture)
        self.assertIn("Implementation modules are imported directly", contracts)
        documented_exceptions = (
            DOCUMENTED_FLAT_PACKAGE_ALLOWLIST
            | DOCUMENTED_MODEL_MODULE_ALLOWLIST
            | PACKAGE_INIT_IMPORT_ALLOWLIST
        )
        for exception in documented_exceptions:
            self.assertIn(str(exception), contracts)
        for layer, packages in PACKAGES_BY_LAYER.items():
            self.assertIn(layer, architecture)
            for package in packages:
                self.assertIn(package, architecture)

    def test_scanner_firmware_namespace_layers_match_architecture_layers(self):
        self.assertTrue(NAMESPACE_ROOT.exists())
        for layer, packages in PACKAGES_BY_LAYER.items():
            layer_root = NAMESPACE_ROOT / layer
            self.assertTrue(layer_root.exists(), layer)
            actual = {
                path.name
                for path in layer_root.iterdir()
                if path.is_dir() and path.name != "__pycache__"
            }
            self.assertEqual(actual, set(packages))

    def test_component_modules_do_not_import_live_hardware_network_or_process_libraries(self):
        violations = []
        for path, tree in _component_python_trees():
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

    def test_neutral_scanner_sync_planning_boundary_does_not_import_adapters(self):
        violations = []
        boundary_root = NAMESPACE_ROOT / "planning" / "scanner_sync"
        for path in sorted(boundary_root.rglob("*.py")):
            tree = ast.parse(path.read_text())
            relative = path.relative_to(REPO_ROOT)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("scanner_firmware.adapters"):
                            violations.append(f"{relative}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("scanner_firmware.adapters"):
                        violations.append(f"{relative}:{node.lineno} from {node.module}")

        self.assertEqual(violations, [])

    def test_scanner_sync_adapters_depend_on_neutral_planning_boundary_only(self):
        violations = []
        adapter_root = NAMESPACE_ROOT / "adapters" / "scanner_sync"
        allowed_planning_prefix = "scanner_firmware.planning.scanner_sync"
        for path in sorted(adapter_root.rglob("*.py")):
            tree = ast.parse(path.read_text())
            relative = path.relative_to(REPO_ROOT)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if (
                            alias.name.startswith("scanner_firmware.planning")
                            and not alias.name.startswith(allowed_planning_prefix)
                        ):
                            violations.append(f"{relative}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if (
                        node.module.startswith("scanner_firmware.planning")
                        and not node.module.startswith(allowed_planning_prefix)
                    ):
                        violations.append(f"{relative}:{node.lineno} from {node.module}")

        self.assertEqual(violations, [])

    def test_runtime_firmware_modules_import_shared_scan_math_from_core(self):
        violations = []
        allowed_compat_paths = {
            Path("src/scanner_firmware/domain/scan_math/geometry.py"),
            Path("src/scanner_firmware/domain/scan_math/units.py"),
            Path("src/scanner_firmware/domain/scan_math/contracts.py"),
            Path("src/scanner_firmware/domain/scan_math/__init__.py"),
        }
        for path, tree in _component_python_trees():
            if path in allowed_compat_paths:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("scanner_firmware.domain.scan_math"):
                            violations.append(f"{path}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("scanner_firmware.domain.scan_math"):
                        violations.append(f"{path}:{node.lineno} from {node.module}")

        self.assertEqual(violations, [])

    def test_component_modules_do_not_call_obvious_hardware_or_live_process_verbs(self):
        violations = []
        for path, tree in _component_python_trees():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_name(node.func)
                if name in FORBIDDEN_CALL_NAMES:
                    violations.append(f"{path}:{node.lineno} call {name}()")

        self.assertEqual(violations, [])

    def test_worker_and_child_pr_merge_boundary_is_documented(self):
        guardrails = (REPO_ROOT / "docs" / "foundation" / "architecture-guardrails.md").read_text()
        standards = (
            REPO_ROOT / "docs" / "foundation" / "code-architecture-standards.md"
        ).read_text()
        combined = f"{guardrails}\n{standards}".lower()

        self.assertIn("workers and child agents", combined)
        self.assertIn("must not open", combined)
        self.assertIn("merge", combined)
        self.assertIn("force-push", combined)

    def test_agent_role_and_foundation_contract_rules_are_documented(self):
        standards = (
            REPO_ROOT / "docs" / "foundation" / "code-architecture-standards.md"
        ).read_text()
        contracts = (REPO_ROOT / "docs" / "foundation" / "firmware-contracts.md").read_text()
        combined = f"{contracts}\n{standards}".lower()

        for role in (
            "lead integrator",
            "firmware architect",
            "math architect",
            "protocol architect",
            "component developer",
            "test and simulation engineer",
            "documentation steward",
        ):
            self.assertIn(role, combined)
        self.assertIn("foundation contract", combined)
        self.assertIn("child-agent limit", combined)
        self.assertIn("typed boundaries", combined)

    def test_package_initializers_do_not_become_reexport_facades(self):
        violations = []
        for path in sorted(NAMESPACE_ROOT.rglob("__init__.py")):
            relative = path.relative_to(REPO_ROOT)
            if relative in PACKAGE_INIT_IMPORT_ALLOWLIST:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    violations.append(f"{relative}:{node.lineno} import in package initializer")

        self.assertEqual(violations, [])

    def test_model_modules_are_documented_concrete_model_owners(self):
        actual = {path.relative_to(REPO_ROOT) for path in NAMESPACE_ROOT.rglob("model.py")}
        self.assertEqual(actual, DOCUMENTED_MODEL_MODULE_ALLOWLIST)

        violations = []
        for relative in sorted(actual):
            path = REPO_ROOT / relative
            tree = ast.parse(path.read_text())
            if any(isinstance(node, ast.Assign) and _assigns_name(node, "__all__") for node in tree.body):
                violations.append(f"{relative}: defines __all__")
            if not any(isinstance(node, ast.ClassDef) for node in tree.body):
                violations.append(f"{relative}: has no concrete classes or contracts")

        self.assertEqual(violations, [])

    def test_component_packages_do_not_grow_flat_dumping_ground_module_lists(self):
        violations = []
        for path in sorted(NAMESPACE_ROOT.rglob("*")):
            if not path.is_dir() or path.name == "__pycache__":
                continue
            direct_modules = [
                child
                for child in path.glob("*.py")
                if child.name != "__init__.py"
            ]
            relative = path.relative_to(REPO_ROOT)
            if (
                len(direct_modules) > FLAT_PACKAGE_MODULE_LIMIT
                and relative not in DOCUMENTED_FLAT_PACKAGE_ALLOWLIST
            ):
                violations.append(
                    f"{relative}: {len(direct_modules)} direct modules exceeds "
                    f"{FLAT_PACKAGE_MODULE_LIMIT}"
                )

        self.assertEqual(violations, [])


def _component_python_paths() -> list[Path]:
    return sorted(NAMESPACE_ROOT.rglob("*.py"))


def _component_python_trees():
    for path in _component_python_paths():
        yield path.relative_to(REPO_ROOT), ast.parse(path.read_text())


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _assigns_name(node: ast.Assign, name: str) -> bool:
    return any(isinstance(target, ast.Name) and target.id == name for target in node.targets)


if __name__ == "__main__":
    unittest.main()
