from __future__ import annotations

import importlib
import json
from pathlib import Path


FIXTURE = Path("tests/fixtures/public_api/scanner_core_public_api_v1.json")


def test_tracked_exported_symbols_import_and_match_module_all() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["schema_id"] == "scanner_core_public_api_v1"
    assert payload["software_only"] is True

    exported_rows = [row for row in payload["rows"] if row["status"] == "exported"]
    assert exported_rows
    for row in exported_rows:
        module = importlib.import_module(row["module"])
        assert hasattr(module, row["symbol"]), row
        module_all = getattr(module, "__all__", None)
        if module_all is not None:
            assert row["symbol"] in module_all, row


def test_module_all_exports_are_all_tracked() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    tracked_by_module: dict[str, set[str]] = {}
    for row in payload["rows"]:
        if row["status"] == "exported":
            tracked_by_module.setdefault(row["module"], set()).add(row["symbol"])

    for module_name, tracked_symbols in tracked_by_module.items():
        module = importlib.import_module(module_name)
        module_all = getattr(module, "__all__", None)
        if module_all is not None:
            assert set(module_all) == tracked_symbols


def test_planned_symbols_are_not_accidentally_exported() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    planned_rows = [row for row in payload["rows"] if row["status"] in {"planned", "not_exported"}]
    assert planned_rows
    for row in planned_rows:
        try:
            module = importlib.import_module(row["module"])
        except ModuleNotFoundError:
            continue
        assert not hasattr(module, row["symbol"]), row
