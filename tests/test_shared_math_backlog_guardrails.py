from __future__ import annotations

import importlib
import json
from pathlib import Path


FIXTURE = Path("tests/fixtures/public_api/scanner_core_public_api_v1.json")

BACKLOG_SYMBOLS = {
    ("scanner_core.scan_geometry", "inclusive_frame_count"),
    ("scanner_core.scan_recipe_geometry", "compile_scan_recipe_geometry"),
    ("scanner_core.scan_recipe_geometry", "RecipeGeometryParityVector"),
    ("scanner_core.scan_plan", "ScanPlan"),
    ("scanner_core.scan_plan", "PlannedFrame"),
    ("scanner_core.scan_plan", "ScanPlanGeometry"),
    ("scanner_core.autofocus.usable_mask", "TileLocalUsableMaskConfig"),
    ("scanner_core.autofocus.usable_mask", "tile_local_usable_mask"),
    ("scanner_core.autofocus.focus_metric", "FocusMetricFrameInput"),
    ("scanner_core.autofocus.focus_metric", "FocusMetricEstimate"),
    ("scanner_core.calibration.error_budget", "AxisErrorBudgetUm"),
    ("scanner_core.calibration.error_budget", "CalibrationErrorBudget"),
    ("scanner_core.calibration.error_budget", "conservative_error_budget_um"),
}


def test_shared_math_backlog_symbols_are_tracked_as_non_exported() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    guarded_rows = {
        (row["module"], row["symbol"])
        for row in payload["rows"]
        if row["status"] in {"planned", "not_exported"}
    }

    assert BACKLOG_SYMBOLS <= guarded_rows


def test_shared_math_backlog_symbols_are_not_accidental_public_api() -> None:
    for module_name, symbol in sorted(BACKLOG_SYMBOLS):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        assert not hasattr(module, symbol), (module_name, symbol)
