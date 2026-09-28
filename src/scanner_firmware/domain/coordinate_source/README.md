# coordinate_source

Coordinate source abstraction for simulator and future firmware.

Initial coordinate source is commanded step count. The data model must also
support future encoder-indexed and hybrid modes.

Modes:

- `step_indexed`: frame/event coordinates come from commanded step counts.
- `encoder_indexed`: frame/event coordinates come from measured encoder
  counts; missing encoder counts are a fault.
- `hybrid`: scheduling may still use commanded steps while metadata records
  available encoder counts for QA/calibration.

Fusion diagnostics are host-side metadata only. They report only facts present
in the sample: missing encoder counts, configured stale encoder observations,
configured step-vs-encoder count disagreement, and explicit encoder health
values (`healthy`, `unhealthy`, or `unknown`). Unknown age or health is preserved
as unknown; the model does not infer real encoder behavior. Step-indexed
missing-encoder flags are opt-in because step-only samples are valid.

See `model.py` for the host-side simulator model.
