# Dry Run Pipeline

Software-only FRAME_EVENT replay for scanner firmware fixtures.

This package starts from already-planned `PlannedFrameTrigger` values and emits
metadata-only `FRAME_EVENT` protocol records. It deliberately does not compile
scan recipes, match host images, run autofocus decisions or schedule predictive
Z corrections. It does not open cameras, talk to controllers, toggle GPIO, drive
LEDs, run motors, flash firmware or use Linux wall-clock time as frame identity.

The pipeline is a simulator/integration boundary. Production hardware adapters
must remain outside this package and feed it validated value objects or
recorded metadata.
