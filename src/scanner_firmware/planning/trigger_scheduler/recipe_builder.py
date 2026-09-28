"""Build dry-run stripe schedules from plain scan recipe dictionaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scanner_firmware.planning.trigger_scheduler.errors import ScanPlanError
from scanner_firmware.planning.led_scheduler.types import (
    LedPatternTimingProfile,
    LedPatternTimingSet,
)
from scanner_firmware.planning.trigger_scheduler.geometry_validation import (
    validate_event_geometry,
)
from scanner_firmware.planning.trigger_scheduler.recipe_fields import (
    is_sequence,
    optional_bool,
    optional_coordinate_source,
    require_aliased_int,
    require_int,
    require_non_empty_string,
    require_pattern_sequence,
)
from scanner_firmware.planning.trigger_scheduler.soft_limits import (
    SoftLimits,
    optional_soft_limits,
    validate_axis_soft_limits,
)
from scanner_firmware.planning.trigger_scheduler.types import StripeSchedule


def build_stripe_schedule(
    scan_recipe: Mapping[str, Any],
    *,
    stripe_index: int = 0,
) -> StripeSchedule:
    """Build one ``StripeSchedule`` from a YAML-like scan recipe mapping."""

    if not isinstance(stripe_index, int) or isinstance(stripe_index, bool):
        raise ScanPlanError("stripe_index must be an integer")
    if stripe_index < 0:
        raise ScanPlanError("stripe_index must be non-negative")
    schedules = build_stripe_schedules(scan_recipe)
    if stripe_index >= len(schedules):
        raise ScanPlanError("stripe_index is outside the recipe stripe range")
    return schedules[stripe_index]


def build_stripe_schedules(scan_recipe: Mapping[str, Any]) -> tuple[StripeSchedule, ...]:
    """Build dry-run ``StripeSchedule`` records from plain scan recipe data."""

    if not isinstance(scan_recipe, Mapping):
        raise ScanPlanError("scan recipe must be a mapping")

    scan_id = require_non_empty_string(scan_recipe, "scan_id", "scan_id")
    recipe_dry_run = optional_bool(scan_recipe, "dry_run", default=True)
    recipe_hardware_outputs_enabled = optional_bool(
        scan_recipe, "hardware_outputs_enabled", default=False
    )
    _validate_dry_run_flags(
        dry_run=recipe_dry_run,
        hardware_outputs_enabled=recipe_hardware_outputs_enabled,
    )
    soft_limits = optional_soft_limits(scan_recipe)
    _reject_legacy_led_timing(scan_recipe, "led_timing")
    recipe_pattern_led_timing = optional_pattern_led_timing(
        scan_recipe.get("pattern_led_timing"),
        "pattern_led_timing",
    )

    stripes = scan_recipe.get("stripes")
    if not is_sequence(stripes) or not stripes:
        raise ScanPlanError("stripes must be a non-empty sequence")

    return tuple(
        _build_schedule_from_stripe(
            scan_id=scan_id,
            stripe=stripe,
            recipe_dry_run=recipe_dry_run,
            recipe_hardware_outputs_enabled=recipe_hardware_outputs_enabled,
            soft_limits=soft_limits,
            recipe_pattern_led_timing=recipe_pattern_led_timing,
            index=index,
        )
        for index, stripe in enumerate(stripes)
    )


def _build_schedule_from_stripe(
    *,
    scan_id: str,
    stripe: Any,
    recipe_dry_run: bool,
    recipe_hardware_outputs_enabled: bool,
    soft_limits: SoftLimits,
    recipe_pattern_led_timing: LedPatternTimingSet | None,
    index: int,
) -> StripeSchedule:
    if not isinstance(stripe, Mapping):
        raise ScanPlanError(f"stripes[{index}] must be a mapping")

    dry_run = optional_bool(stripe, "dry_run", default=recipe_dry_run)
    hardware_outputs_enabled = optional_bool(
        stripe,
        "hardware_outputs_enabled",
        default=recipe_hardware_outputs_enabled,
    )
    _validate_dry_run_flags(
        dry_run=dry_run,
        hardware_outputs_enabled=hardware_outputs_enabled,
    )

    stripe_id = require_int(stripe, "stripe_id", f"stripes[{index}].stripe_id")
    if stripe_id < 0:
        raise ScanPlanError(f"stripes[{index}].stripe_id must be non-negative")

    axis = stripe.get("axis")
    if axis not in ("X", "Y"):
        raise ScanPlanError(f"stripes[{index}].axis must be X or Y")

    start_position = require_aliased_int(
        stripe, ("start_position", "start"), f"stripes[{index}].start_position"
    )
    end_position = require_aliased_int(
        stripe, ("end_position", "end"), f"stripes[{index}].end_position"
    )
    first_event_position = require_aliased_int(
        stripe,
        ("first_event_position", "first_event"),
        f"stripes[{index}].first_event_position",
    )
    event_pitch = require_int(stripe, "event_pitch", f"stripes[{index}].event_pitch")
    event_count = require_int(stripe, "event_count", f"stripes[{index}].event_count")
    pattern_sequence = require_pattern_sequence(
        stripe, "pattern_sequence", f"stripes[{index}].pattern_sequence"
    )
    coordinate_source = optional_coordinate_source(
        stripe, f"stripes[{index}].coordinate_source"
    )
    _reject_legacy_led_timing(stripe, f"stripes[{index}].led_timing")
    pattern_led_timing = merged_pattern_led_timing(
        base=recipe_pattern_led_timing,
        override=optional_pattern_led_timing(
            stripe.get("pattern_led_timing"),
            f"stripes[{index}].pattern_led_timing",
        ),
    )

    validate_event_geometry(
        start_position=start_position,
        end_position=end_position,
        first_event_position=first_event_position,
        event_pitch=event_pitch,
        event_count=event_count,
        prefix=f"stripes[{index}]",
    )
    validate_axis_soft_limits(
        axis=axis,
        soft_limits=soft_limits,
        start_position=start_position,
        end_position=end_position,
        first_event_position=first_event_position,
        event_pitch=event_pitch,
        event_count=event_count,
        prefix=f"stripes[{index}]",
    )

    return StripeSchedule(
        scan_id=scan_id,
        stripe_id=stripe_id,
        axis=axis,
        start_position=start_position,
        end_position=end_position,
        first_event_position=first_event_position,
        event_pitch=event_pitch,
        event_count=event_count,
        pattern_sequence=pattern_sequence,
        coordinate_source=coordinate_source,
        dry_run=dry_run,
        hardware_outputs_enabled=hardware_outputs_enabled,
        pattern_led_timing=pattern_led_timing,
    )


def _validate_dry_run_flags(
    *, dry_run: bool, hardware_outputs_enabled: bool
) -> None:
    if not dry_run:
        raise ScanPlanError("dry_run must be true for dry-run scan plans")
    if hardware_outputs_enabled:
        raise ScanPlanError(
            "hardware_outputs_enabled must be false for dry-run scan plans"
        )


def _reject_legacy_led_timing(mapping: Mapping[str, Any], display_name: str) -> None:
    if "led_timing" in mapping:
        raise ScanPlanError(
            f"{display_name} was replaced by pattern_led_timing keyed by pattern"
        )


LED_TIMING_PROFILE_FIELDS = frozenset(
    (
        "exposure_start_offset_us",
        "exposure_us",
        "gate_pulse_us",
        "settle_us",
        "frame_period_us",
        "trigger_pulse_us",
        "gate_pre_trigger_us",
        "gate_post_exposure_us",
        "baseline_gate_names",
        "baseline_suppress_pre_gate_us",
        "baseline_restore_post_gate_us",
        "polarity",
        "brightness_by_gate",
    )
)


def optional_pattern_led_timing(
    value: object,
    display_name: str,
) -> LedPatternTimingSet | None:
    if value is None:
        return None
    if isinstance(value, LedPatternTimingSet):
        return value
    if not isinstance(value, Mapping):
        raise ScanPlanError(f"{display_name} must be a mapping")
    if not value:
        raise ScanPlanError(f"{display_name} must be a non-empty mapping")
    parsed_profiles = []
    for pattern, profile_value in value.items():
        if not isinstance(pattern, str) or not pattern:
            raise ScanPlanError(f"{display_name} keys must be non-empty strings")
        parsed_profiles.append(
            _led_timing_profile(
                pattern=pattern,
                value=profile_value,
                display_name=f"{display_name}.{pattern}",
            )
        )
    try:
        return LedPatternTimingSet(profiles=tuple(parsed_profiles))
    except ValueError as exc:
        raise ScanPlanError(f"{display_name}: {exc}") from exc


def merged_pattern_led_timing(
    *,
    base: LedPatternTimingSet | None,
    override: LedPatternTimingSet | None,
) -> LedPatternTimingSet | None:
    if base is None:
        return override
    if override is None:
        return base
    profiles = {profile.pattern: profile for profile in base.profiles}
    profiles.update({profile.pattern: profile for profile in override.profiles})
    return LedPatternTimingSet(profiles=tuple(profiles.values()))


def _led_timing_profile(
    *,
    pattern: str,
    value: object,
    display_name: str,
) -> LedPatternTimingProfile:
    if not isinstance(value, Mapping):
        raise ScanPlanError(f"{display_name} must be a mapping")
    unknown_fields = sorted(str(key) for key in value if key not in LED_TIMING_PROFILE_FIELDS)
    if unknown_fields:
        raise ScanPlanError(
            f"{display_name} unknown fields: {', '.join(unknown_fields)}"
        )
    for required in ("exposure_start_offset_us", "exposure_us", "gate_pulse_us"):
        if required not in value:
            raise ScanPlanError(f"{display_name}.{required} is required")
    brightness = value.get("brightness_by_gate")
    if brightness is not None:
        brightness = _brightness_by_gate(
            brightness,
            f"{display_name}.brightness_by_gate",
        )
    try:
        return LedPatternTimingProfile(
            pattern=pattern,
            exposure_start_offset_us=require_int(
                value,
                "exposure_start_offset_us",
                f"{display_name}.exposure_start_offset_us",
            ),
            exposure_us=require_int(value, "exposure_us", f"{display_name}.exposure_us"),
            gate_pulse_us=require_int(
                value,
                "gate_pulse_us",
                f"{display_name}.gate_pulse_us",
            ),
            settle_us=require_int(value, "settle_us", f"{display_name}.settle_us")
            if "settle_us" in value
            else 0,
            frame_period_us=require_int(
                value,
                "frame_period_us",
                f"{display_name}.frame_period_us",
            )
            if "frame_period_us" in value
            else None,
            trigger_pulse_us=require_int(
                value,
                "trigger_pulse_us",
                f"{display_name}.trigger_pulse_us",
            )
            if "trigger_pulse_us" in value
            else None,
            gate_pre_trigger_us=require_int(
                value,
                "gate_pre_trigger_us",
                f"{display_name}.gate_pre_trigger_us",
            )
            if "gate_pre_trigger_us" in value
            else None,
            gate_post_exposure_us=require_int(
                value,
                "gate_post_exposure_us",
                f"{display_name}.gate_post_exposure_us",
            )
            if "gate_post_exposure_us" in value
            else None,
            baseline_gate_names=_logical_gate_names(
                value.get("baseline_gate_names", ()),
                f"{display_name}.baseline_gate_names",
            ),
            baseline_suppress_pre_gate_us=require_int(
                value,
                "baseline_suppress_pre_gate_us",
                f"{display_name}.baseline_suppress_pre_gate_us",
            )
            if "baseline_suppress_pre_gate_us" in value
            else 0,
            baseline_restore_post_gate_us=require_int(
                value,
                "baseline_restore_post_gate_us",
                f"{display_name}.baseline_restore_post_gate_us",
            )
            if "baseline_restore_post_gate_us" in value
            else 0,
            polarity=value.get("polarity", "active_high"),
            brightness_by_gate=brightness,
        )
    except ValueError as exc:
        raise ScanPlanError(f"{display_name}: {exc}") from exc


def _brightness_by_gate(value: object, display_name: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ScanPlanError(f"{display_name} must be a mapping")
    output: dict[str, float] = {}
    for key, brightness in value.items():
        if not isinstance(key, str) or not key:
            raise ScanPlanError(f"{display_name} keys must be non-empty strings")
        if isinstance(brightness, bool) or not isinstance(brightness, int | float):
            raise ScanPlanError(f"{display_name}.{key} must be a number")
        output[key] = float(brightness)
    return output


def _logical_gate_names(value: object, display_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ScanPlanError(f"{display_name} must be a list")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ScanPlanError(f"{display_name}[{index}] must be a non-empty string")
        output.append(item)
    return tuple(output)
