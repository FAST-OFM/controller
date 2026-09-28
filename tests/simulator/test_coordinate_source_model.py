import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.coordinate_source.errors import CoordinateSourceError  # noqa: E402
from scanner_firmware.domain.coordinate_source.fusion import resolve_coordinate  # noqa: E402
from scanner_firmware.domain.coordinate_source.types import CoordinateSample  # noqa: E402


class CoordinateSourceModelTests(unittest.TestCase):
    def test_step_indexed_uses_commanded_counts(self):
        truth = resolve_coordinate(
            CoordinateSample(10, 20, 3, x_encoder_count=100, y_encoder_count=200),
            "step_indexed",
        )

        self.assertEqual((truth.x_count, truth.y_count, truth.z_count), (10, 20, 3))
        self.assertEqual(truth.flags, ())

    def test_encoder_indexed_requires_encoder_counts(self):
        with self.assertRaises(CoordinateSourceError):
            resolve_coordinate(CoordinateSample(10, 20), "encoder_indexed")

    def test_encoder_indexed_uses_encoder_counts(self):
        truth = resolve_coordinate(
            CoordinateSample(10, 20, x_encoder_count=101, y_encoder_count=202),
            "encoder_indexed",
        )

        self.assertEqual((truth.x_count, truth.y_count), (101, 202))
        self.assertEqual((truth.x_step_commanded, truth.y_step_commanded), (10, 20))

    def test_hybrid_uses_steps_and_flags_missing_encoders(self):
        truth = resolve_coordinate(CoordinateSample(10, 20), "hybrid")

        self.assertEqual((truth.x_count, truth.y_count), (10, 20))
        self.assertEqual(truth.flags, ("x_encoder_missing", "y_encoder_missing"))


if __name__ == "__main__":
    unittest.main()
