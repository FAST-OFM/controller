"""Frozen firmware math contracts for units, signs and rounding.

The shared stripe geometry implementation lives in ``scanner_core.scan_geometry``.
This module names the firmware-owned boundary conventions that adapters and
dry-run fixtures need to agree on without duplicating scanner-core primitives.
"""

from __future__ import annotations


FIRMWARE_MATH_CONTRACT_ID = "firmware_math_units_sign_rounding_v1"
GEOMETRY_SOURCE_MODULE = "scanner_core.scan_geometry"
ROUNDING_MODE = "round_half_away_from_zero"
POSITION_COUNT_UNIT = "controller_count"
PHYSICAL_DISTANCE_UNIT = "micrometer"
NANOMETERS_PER_MICROMETER = 1000
MICROMETERS_PER_MILLIMETER = 1000
INITIAL_COORDINATE_SOURCE = "commanded_step_count"
FUTURE_COORDINATE_SOURCE = "encoder_count"
OVERSHOOT_SIGN_CONVENTION = "sample_position_minus_event_position"
SCHEDULED_EVENT_POSITION_RULE = "event_position_remains_scheduled_count"

