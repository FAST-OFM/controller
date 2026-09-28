from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS_DOC = REPO_ROOT / "docs" / "foundation" / "software-to-hardware-readiness.md"


def test_v1_hardware_readiness_doc_preserves_no_homing_live_gate() -> None:
    text = READINESS_DOC.read_text(encoding="utf-8")
    lower = text.lower()

    required_phrases = (
        "software-only readiness audit",
        "manual-centered bounded non-scan",
        "normal scan workflows still require homing for x, y and z",
        "+/-10 mm",
        "numeric minimal z search envelope",
        "hq camera xvs",
        "mcu `frame_event` remains the source",
        "metadata-only with `hardware_outputs_enabled: false`",
        "arduino is only a slow brightness/vref controller",
        "mks timing firmware owns frame-synchronous led gate timing",
        "red/green current feedback remains unknown",
        "current homing remains incomplete",
        "treating dry-run readiness as live-test approval",
    )
    for phrase in required_phrases:
        assert phrase in lower


def test_v1_hardware_readiness_doc_lists_p0_blockers() -> None:
    text = READINESS_DOC.read_text(encoding="utf-8").lower()

    p0_blockers = (
        "no merged reviewed live-test procedure",
        "no live-approved artifact proving the `+/-10 mm` x/y envelope",
        "no live-approved z focus envelope",
        "no hq xvs electrical sync-sink evidence",
        "no complete mks scanner-sync enabled metadata-only readiness evidence",
        "no loaded led gate and per-channel current-limit evidence",
        "no hardware evidence schema/result",
    )
    for blocker in p0_blockers:
        assert blocker in text
