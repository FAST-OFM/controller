"""Scanner-sync codec lookup tables."""

STATUS_CODES = {
    0: "stopped",
    1: "fault",
    "stopped": "stopped",
    "fault": "fault",
    "accepted": "accepted",
    "rejected": "rejected",
    "ok": "ok",
}
FRAME_STATUS_CODES = {
    0: "ok",
    "ok": "ok",
    "OK": "ok",
}
Z_SCHEDULED_STATUS_CODES = {
    0: "accepted",
    "accepted": "accepted",
}
Z_APPLIED_STATUS_CODES = {
    0: "ok",
    "ok": "ok",
}
Z_REJECTED_STATUS_CODES = {
    1: "rejected",
    "rejected": "rejected",
}
TIMED_OUTPUT_SEQUENCE_STATUS_CODES = {
    0: "accepted",
    1: "rejected",
    2: "started",
    3: "completed",
    4: "stopped",
    5: "fault",
    "accepted": "accepted",
    "rejected": "rejected",
    "started": "started",
    "completed": "completed",
    "stopped": "stopped",
    "fault": "fault",
}
TIMED_OUTPUT_SEQUENCE_REASON_CODES = {
    0: "accepted",
    1: "invalid_command",
    2: "started",
    3: "finite_completion",
    4: "host_stop",
    5: "fault",
    "accepted": "accepted",
    "invalid_command": "invalid_command",
    "started": "started",
    "finite_completion": "finite_completion",
    "host_stop": "host_stop",
    "fault": "fault",
}
TERMINAL_REASON_CODES = {
    0: "host_stop",
    1: "scheduler_fault",
    2: "coordinate_source_error",
    3: "position_stream_exhausted",
    "host_stop": "host_stop",
    "scheduler_fault": "scheduler_fault",
    "coordinate_source_error": "coordinate_source_error",
    "position_stream_exhausted": "position_stream_exhausted",
}
Z_REJECT_REASON_CODES = {
    0: "invalid_target",
    1: "scan_or_stripe_mismatch",
    2: "target_already_passed",
    3: "insufficient_lookahead",
    4: "z_limit_exceeded",
    5: "target_outside_stripe",
    6: "no_correction_window",
}
TARGET_KIND_CODES = {
    "frame": 0,
    "position": 1,
    0: "frame",
    1: "position",
}
AXIS_CODES = {
    "X": "X",
    "Y": "Y",
    0: "X",
    1: "Y",
}
