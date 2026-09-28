import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scanner_firmware.planning.led_scheduler.errors import LedPatternError  # noqa: E402
from scanner_firmware.planning.led_scheduler.patterns import LogicalLedPatternResolver  # noqa: E402


class LedSchedulerModelTests(unittest.TestCase):
    def test_resolves_brightfield_to_white_gate(self):
        pattern = LogicalLedPatternResolver().resolve("BF_WHITE")

        self.assertEqual(pattern.gate_names, ("led_white",))
        self.assertEqual(pattern.frame_use, "tile")

    def test_resolves_red_green_autofocus_to_two_gates(self):
        pattern = LogicalLedPatternResolver().resolve("AF_RED_GREEN")

        self.assertEqual(pattern.gate_names, ("led_red", "led_green"))
        self.assertEqual(pattern.frame_use, "autofocus")

    def test_resolves_dark_to_no_gates(self):
        pattern = LogicalLedPatternResolver().resolve("DARK")

        self.assertEqual(pattern.gate_names, ())
        self.assertEqual(pattern.frame_use, "diagnostics")

    def test_rejects_unknown_pattern(self):
        with self.assertRaises(LedPatternError):
            LogicalLedPatternResolver().resolve("UNREVIEWED_PATTERN")


if __name__ == "__main__":
    unittest.main()
