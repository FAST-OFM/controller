import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.domain.coordinate_source.errors import CoordinateSourceError  # noqa: E402
from scanner_firmware.domain.coordinate_source.fusion import resolve_coordinate  # noqa: E402
from scanner_firmware.domain.coordinate_source.types import (  # noqa: E402
    CoordinateFusionConfig,
    CoordinateSample,
)


class CoordinateSourceFusionTests(unittest.TestCase):
    def test_step_indexed_uses_steps_but_reports_encoder_fusion_flags(self):
        truth = resolve_coordinate(
            CoordinateSample(
                100,
                200,
                x_encoder_count=103,
                y_encoder_count=240,
                sample_index=12,
                x_encoder_sample_index=12,
                y_encoder_sample_index=8,
                x_encoder_health="healthy",
                y_encoder_health="unhealthy",
            ),
            "step_indexed",
            CoordinateFusionConfig(
                encoder_stale_after_samples=2,
                disagreement_threshold_counts=5,
                report_encoder_health=True,
            ),
        )

        self.assertEqual((truth.x_count, truth.y_count), (100, 200))
        self.assertEqual(
            truth.flags,
            (
                "x_encoder_health_healthy",
                "y_encoder_health_unhealthy",
                "y_encoder_stale",
                "y_step_encoder_disagreement",
            ),
        )

    def test_step_indexed_missing_encoder_reporting_is_explicit(self):
        default_truth = resolve_coordinate(CoordinateSample(100, 200), "step_indexed")
        reported_truth = resolve_coordinate(
            CoordinateSample(100, 200),
            "step_indexed",
            CoordinateFusionConfig(report_missing_encoders=True),
        )

        self.assertEqual(default_truth.flags, ())
        self.assertEqual(
            reported_truth.flags,
            ("x_encoder_missing", "y_encoder_missing"),
        )

    def test_encoder_indexed_requires_present_encoders_and_preserves_unknown_health(self):
        with self.assertRaises(CoordinateSourceError):
            resolve_coordinate(
                CoordinateSample(
                    100,
                    200,
                    x_encoder_count=100,
                    y_encoder_count=None,
                    sample_index=4,
                    x_encoder_sample_index=4,
                    y_encoder_sample_index=None,
                ),
                "encoder_indexed",
                CoordinateFusionConfig(report_encoder_health=True),
            )

        truth = resolve_coordinate(
            CoordinateSample(
                100,
                200,
                x_encoder_count=99,
                y_encoder_count=202,
                sample_index=4,
                x_encoder_sample_index=4,
                y_encoder_sample_index=4,
            ),
            "encoder_indexed",
            CoordinateFusionConfig(report_encoder_health=True),
        )

        self.assertEqual((truth.x_count, truth.y_count), (99, 202))
        self.assertEqual((truth.x_encoder_health, truth.y_encoder_health), ("unknown", "unknown"))
        self.assertEqual(
            truth.flags,
            ("x_encoder_health_unknown", "y_encoder_health_unknown"),
        )

    def test_hybrid_uses_steps_and_flags_missing_stale_and_disagreement(self):
        truth = resolve_coordinate(
            CoordinateSample(
                100,
                200,
                x_encoder_count=None,
                y_encoder_count=225,
                sample_index=10,
                y_encoder_sample_index=6,
                x_encoder_health="unknown",
                y_encoder_health="healthy",
            ),
            "hybrid",
            CoordinateFusionConfig(
                encoder_stale_after_samples=3,
                disagreement_threshold_counts=10,
                report_encoder_health=True,
            ),
        )

        self.assertEqual((truth.x_count, truth.y_count), (100, 200))
        self.assertEqual(
            truth.flags,
            (
                "x_encoder_missing",
                "x_encoder_health_unknown",
                "y_encoder_health_healthy",
                "y_encoder_stale",
                "y_step_encoder_disagreement",
            ),
        )

    def test_unknown_age_does_not_become_stale(self):
        truth = resolve_coordinate(
            CoordinateSample(
                100,
                200,
                x_encoder_count=100,
                y_encoder_count=200,
                sample_index=None,
                x_encoder_sample_index=None,
                y_encoder_sample_index=1,
            ),
            "hybrid",
            CoordinateFusionConfig(encoder_stale_after_samples=0),
        )

        self.assertNotIn("x_encoder_stale", truth.flags)
        self.assertNotIn("y_encoder_stale", truth.flags)

    def test_rejects_invalid_fusion_config_and_health_values(self):
        with self.assertRaisesRegex(CoordinateSourceError, "encoder_stale_after_samples"):
            CoordinateFusionConfig(encoder_stale_after_samples=-1)
        with self.assertRaisesRegex(CoordinateSourceError, "x_encoder_health"):
            CoordinateSample(100, 200, x_encoder_health="maybe")


if __name__ == "__main__":
    unittest.main()
