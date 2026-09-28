from __future__ import annotations

import unittest
from pathlib import Path

import conftest


REPO_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_TEST_ROOT = REPO_ROOT / "tests" / "simulator"
MARKER_BUCKETS = {
    "architecture": conftest.ARCHITECTURE_TESTS,
    "contract": conftest.CONTRACT_TESTS,
    "integration": conftest.INTEGRATION_TESTS,
    "unit": conftest.UNIT_TESTS,
}


class PytestMarkerClassificationTests(unittest.TestCase):
    def test_every_simulator_test_file_has_exactly_one_marker_bucket(self):
        actual_files = {path.name for path in SIMULATOR_TEST_ROOT.glob("test_*.py")}
        classified_files = set().union(*MARKER_BUCKETS.values())
        duplicate_files = sorted(
            filename
            for filename in classified_files
            if sum(filename in bucket for bucket in MARKER_BUCKETS.values()) != 1
        )

        self.assertEqual(
            {
                "missing": sorted(actual_files - classified_files),
                "stale": sorted(classified_files - actual_files),
                "duplicates": duplicate_files,
            },
            {"missing": [], "stale": [], "duplicates": []},
        )

    def test_marker_buckets_are_registered_in_pyproject(self):
        registered_markers = _registered_pytest_marker_names()

        self.assertEqual(set(MARKER_BUCKETS), registered_markers)

    def test_marker_lookup_rejects_unclassified_or_double_classified_files(self):
        for filename in sorted(set().union(*MARKER_BUCKETS.values())):
            with self.subTest(filename=filename):
                self.assertEqual(len(conftest._markers_for_file(filename)), 1)

        with self.assertRaisesRegex(ValueError, "exactly one simulator pytest marker"):
            conftest._markers_for_file("test_new_unclassified_guardrail.py")


def _registered_pytest_marker_names() -> set[str]:
    names: set[str] = set()
    in_markers = False
    for line in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "markers = [":
            in_markers = True
            continue
        if in_markers and stripped == "]":
            return names
        if in_markers and stripped.startswith('"'):
            names.add(stripped.split(":", 1)[0].lstrip('"'))
    return names


if __name__ == "__main__":
    unittest.main()
