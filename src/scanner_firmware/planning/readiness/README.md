# Readiness

Software-only startup and self-check readiness aggregation.

This package combines already-validated domain status into explicit startup
states. It does not perform live checks itself. Live adapters may observe a
system and then pass passive status flags into this package.

`ReadinessReason` records provide the stable reason model for parent
integration. Reasons are grouped by `board`, `scanner_sync` and
`live_test_gate` domains. Board and scanner-sync reasons preserve unknown
hardware facts as `unknown` instead of converting them into approval. The
live-test gate is always represented separately because software readiness in
this repository never approves firmware flashing, GPIO, motion, LEDs, camera
triggers or live controller commands.
