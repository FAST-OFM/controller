"""Static validator for Klipper scanner-sync Stage B review packages.

The validator accepts already-captured YAML data only. It does not import
Klipper, open serial ports, send commands, toggle GPIO, command motion, trigger
cameras, drive LEDs or flash firmware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from scanner_firmware.adapters.klipper_adapter.readiness.live_metadata import (
    EXPECTED_COMMAND_FORMATS,
    EXPECTED_RESPONSE_FORMATS,
)


class StageBReviewPackageError(ValueError):
    """Raised when Stage B review package YAML cannot be parsed."""


@dataclass(frozen=True)
class StageBReviewValidation:
    """Static validation result for a Stage B review package."""

    accepted: bool
    blockers: tuple[str, ...]


StageBReviewReadinessState = Literal["blocked", "passive_observation_ready"]


@dataclass(frozen=True)
class StageBReviewObservationSummary:
    """Passive observation facts extracted from an accepted Stage B review package."""

    reviewer: str
    review_issue_or_pr: str
    live_pi_hostname: str
    klipper_commit: str
    scanner_sync_enable: bool
    metadata_only_mode: bool
    hardware_outputs_enabled: bool
    output_pins_configured: bool
    expected_capture_jsonl_path: str
    expected_summary_json_path: str
    expected_record_count: int
    expected_frame_count: int
    expected_terminal_count: int
    expected_first_frame_id: int
    expected_last_frame_id: int
    expected_stripes_seen: tuple[int, ...]


@dataclass(frozen=True)
class StageBReviewReadinessSummary:
    """Static Stage B review readiness summary.

    This summary is simulator/static evidence only. It never approves live
    testing, flashing, motion, GPIO, camera or LED work.
    """

    readiness_state: StageBReviewReadinessState
    review_accepted: bool
    blockers: tuple[str, ...]
    observation: StageBReviewObservationSummary | None
    static_simulator_only: bool = field(default=True, init=False)
    live_testing_approved: bool = field(default=False, init=False)
    can_execute_live_stage_b: bool = field(default=False, init=False)
    can_enable_scanner_sync: bool = field(default=False, init=False)


_MISSING = object()

_STRING_FIELDS: tuple[tuple[str, ...], ...] = (
    ("reviewer",),
    ("review_issue_or_pr",),
    ("live_pi_hostname",),
    ("klipper_commit",),
    ("klipper_worktree_status",),
    ("scanner_sync_host_extra_diff",),
    ("scanner_sync_mcu_patch_diff",),
    ("mks_board_identity", "board_name"),
    ("mks_board_identity", "board_revision"),
    ("mks_board_identity", "mcu_model"),
    ("mks_board_identity", "bootloader_or_flash_method"),
    ("firmware_build", "command"),
    ("firmware_build", "output_artifact"),
    ("firmware_build", "expected_dictionary_path"),
    ("firmware_flash", "method"),
    ("firmware_flash", "exact_command_or_ui_steps"),
    ("firmware_flash", "rollback_method"),
    ("firmware_flash", "rollback_artifact"),
    ("printer_cfg", "baseline_backup_path"),
    ("printer_cfg", "scanner_sync_diff"),
    ("printer_cfg", "mode"),
    ("expected_capture", "jsonl_path"),
    ("expected_capture", "summary_json_path"),
)

_BOOL_FIELDS: tuple[tuple[str, ...], ...] = (
    ("printer_cfg", "enable"),
    ("printer_cfg", "hardware_outputs_enabled"),
    ("printer_cfg", "output_pins_configured"),
    ("stop_conditions_reviewed",),
)

_INT_FIELDS: tuple[tuple[str, ...], ...] = (
    ("expected_capture", "expected_record_count"),
    ("expected_capture", "expected_frame_count"),
    ("expected_capture", "expected_terminal_count"),
    ("expected_capture", "expected_first_frame_id"),
    ("expected_capture", "expected_last_frame_id"),
)

_FORMAT_FIELDS: tuple[tuple[str, ...], ...] = (
    ("expected_scanner_sync_formats", "commands"),
    ("expected_scanner_sync_formats", "responses"),
)

_REQUIRED_FIELDS = _STRING_FIELDS + _BOOL_FIELDS + _INT_FIELDS + _FORMAT_FIELDS + (
    ("expected_capture", "expected_stripes_seen"),
)

_FALSEY_APPROVAL_VALUES = {"", "false", "no", "none", "null", "not approved", "unapproved"}
_APPROVAL_VALUES = {
    "approved",
    "approved_for_live_execution",
    "authorized",
    "true",
    "yes",
    "on",
    "1",
}


def validate_stage_b_review_yaml(text: str) -> StageBReviewValidation:
    """Parse and validate a Stage B review package from YAML text."""

    return validate_stage_b_review_package(_load_stage_b_review_yaml(text))


def summarize_stage_b_review_yaml(text: str) -> StageBReviewReadinessSummary:
    """Parse Stage B review YAML and build a passive readiness summary."""

    return summarize_stage_b_review_package(_load_stage_b_review_yaml(text))


def summarize_stage_b_review_package(payload: Any) -> StageBReviewReadinessSummary:
    """Adapt Stage B review package data to a static readiness summary."""

    validation = validate_stage_b_review_package(payload)
    if not validation.accepted:
        return StageBReviewReadinessSummary(
            readiness_state="blocked",
            review_accepted=False,
            blockers=validation.blockers,
            observation=None,
        )

    review = payload["stage_b_review"]
    printer_cfg = review["printer_cfg"]
    expected_capture = review["expected_capture"]

    return StageBReviewReadinessSummary(
        readiness_state="passive_observation_ready",
        review_accepted=True,
        blockers=(),
        observation=StageBReviewObservationSummary(
            reviewer=review["reviewer"],
            review_issue_or_pr=review["review_issue_or_pr"],
            live_pi_hostname=review["live_pi_hostname"],
            klipper_commit=review["klipper_commit"],
            scanner_sync_enable=printer_cfg["enable"],
            metadata_only_mode=printer_cfg["mode"] == "metadata_only",
            hardware_outputs_enabled=printer_cfg["hardware_outputs_enabled"],
            output_pins_configured=printer_cfg["output_pins_configured"],
            expected_capture_jsonl_path=expected_capture["jsonl_path"],
            expected_summary_json_path=expected_capture["summary_json_path"],
            expected_record_count=expected_capture["expected_record_count"],
            expected_frame_count=expected_capture["expected_frame_count"],
            expected_terminal_count=expected_capture["expected_terminal_count"],
            expected_first_frame_id=expected_capture["expected_first_frame_id"],
            expected_last_frame_id=expected_capture["expected_last_frame_id"],
            expected_stripes_seen=_stripe_ids(expected_capture["expected_stripes_seen"]),
        ),
    )


def _load_stage_b_review_yaml(text: str) -> Any:
    """Load Stage B review YAML without performing hardware or network actions."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional dev dependency
        raise StageBReviewPackageError("PyYAML is required to parse review YAML") from exc

    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise StageBReviewPackageError("invalid Stage B review YAML") from exc
    return payload


def validate_stage_b_review_package(payload: Any) -> StageBReviewValidation:
    """Validate static Stage B review package data."""

    blockers: list[str] = []
    if not isinstance(payload, Mapping):
        return StageBReviewValidation(
            accepted=False,
            blockers=("stage_b_review_package_must_be_mapping",),
        )

    review = payload.get("stage_b_review")
    if not isinstance(review, Mapping):
        return StageBReviewValidation(
            accepted=False,
            blockers=("stage_b_review_missing",),
        )

    blockers.extend(_validate_required_fields(review))
    blockers.extend(_validate_safety_fields(review))
    blockers.extend(_validate_expected_formats(review))
    blockers.extend(_validate_expected_capture(review))
    blockers.extend(_validate_no_approval_claims(payload))

    return StageBReviewValidation(accepted=not blockers, blockers=tuple(blockers))


def _validate_required_fields(review: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path in _REQUIRED_FIELDS:
        value = _lookup(review, path)
        field = _field_name(path)
        if value is _MISSING:
            blockers.append(f"{field}_missing")
        elif _contains_unknown(value):
            blockers.append(f"{field}_unknown")

    for path in _STRING_FIELDS:
        value = _lookup(review, path)
        if value is _MISSING or _contains_unknown(value):
            continue
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"{_field_name(path)}_must_be_nonempty_string")

    for path in _BOOL_FIELDS:
        value = _lookup(review, path)
        if value is _MISSING or _contains_unknown(value):
            continue
        if not isinstance(value, bool):
            blockers.append(f"{_field_name(path)}_must_be_boolean")

    for path in _INT_FIELDS:
        value = _lookup(review, path)
        if value is _MISSING or _contains_unknown(value):
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            blockers.append(f"{_field_name(path)}_must_be_integer")
        elif value < 0:
            blockers.append(f"{_field_name(path)}_must_be_nonnegative")

    stripes_seen = _lookup(review, ("expected_capture", "expected_stripes_seen"))
    if (
        stripes_seen is not _MISSING
        and not _contains_unknown(stripes_seen)
        and not _stripe_ids(stripes_seen)
    ):
        blockers.append("expected_capture.expected_stripes_seen_must_be_nonempty")

    return blockers


def _validate_safety_fields(review: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    printer_cfg = review.get("printer_cfg")
    if not isinstance(printer_cfg, Mapping):
        return blockers

    if printer_cfg.get("mode") != "metadata_only":
        blockers.append("printer_cfg.mode_must_be_metadata_only")
    if printer_cfg.get("hardware_outputs_enabled") is not False:
        blockers.append("printer_cfg.hardware_outputs_enabled_must_be_false")
    if printer_cfg.get("output_pins_configured") is not False:
        blockers.append("printer_cfg.output_pins_configured_must_be_false")

    unsafe_outputs = _unsafe_output_fields(printer_cfg, prefix=("printer_cfg",))
    blockers.extend(f"{field}_must_be_unset" for field in unsafe_outputs)

    if review.get("stop_conditions_reviewed") is not True:
        blockers.append("stop_conditions_reviewed_must_be_true")

    return blockers


def _validate_expected_formats(review: Mapping[str, Any]) -> list[str]:
    formats = review.get("expected_scanner_sync_formats")
    if not isinstance(formats, Mapping):
        return []

    blockers: list[str] = []
    commands = _format_items(formats.get("commands"))
    responses = _format_items(formats.get("responses"))
    missing_commands = tuple(
        msgformat for msgformat in EXPECTED_COMMAND_FORMATS if msgformat not in commands
    )
    missing_responses = tuple(
        msgformat for msgformat in EXPECTED_RESPONSE_FORMATS if msgformat not in responses
    )
    if missing_commands:
        blockers.append("expected_scanner_sync_formats.commands_incomplete")
    if missing_responses:
        blockers.append("expected_scanner_sync_formats.responses_incomplete")
    return blockers


def _validate_expected_capture(review: Mapping[str, Any]) -> list[str]:
    capture = review.get("expected_capture")
    if not isinstance(capture, Mapping):
        return []

    blockers: list[str] = []
    record_count = capture.get("expected_record_count")
    frame_count = capture.get("expected_frame_count")
    terminal_count = capture.get("expected_terminal_count")
    first_frame_id = capture.get("expected_first_frame_id")
    last_frame_id = capture.get("expected_last_frame_id")

    if isinstance(frame_count, int) and not isinstance(frame_count, bool) and frame_count < 1:
        blockers.append("expected_capture.expected_frame_count_must_be_positive")
    if (
        isinstance(terminal_count, int)
        and not isinstance(terminal_count, bool)
        and terminal_count < 1
    ):
        blockers.append("expected_capture.expected_terminal_count_must_be_positive")
    if (
        isinstance(record_count, int)
        and not isinstance(record_count, bool)
        and isinstance(frame_count, int)
        and not isinstance(frame_count, bool)
        and isinstance(terminal_count, int)
        and not isinstance(terminal_count, bool)
        and record_count < frame_count + terminal_count
    ):
        blockers.append("expected_capture.expected_record_count_too_small")
    if (
        isinstance(first_frame_id, int)
        and not isinstance(first_frame_id, bool)
        and isinstance(last_frame_id, int)
        and not isinstance(last_frame_id, bool)
        and isinstance(frame_count, int)
        and not isinstance(frame_count, bool)
        and frame_count > 0
        and last_frame_id - first_frame_id + 1 != frame_count
    ):
        blockers.append("expected_capture.frame_id_range_must_match_frame_count")

    return blockers


def _validate_no_approval_claims(review: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(review):
        key = path[-1].lower() if path else ""
        if "approved" in key and not _is_effectively_false(value):
            blockers.append(f"{'.'.join(path)}_must_not_claim_approval")
        elif "approval" in key and _value_claims_approval(value):
            blockers.append(f"{'.'.join(path)}_must_not_claim_approval")
        elif key in ("status", "state", "claim") and _value_claims_approval(value):
            blockers.append(f"{'.'.join(path)}_must_not_claim_approval")
    return blockers


def _lookup(root: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = root
    for segment in path:
        if not isinstance(node, Mapping) or segment not in node:
            return _MISSING
        node = node[segment]
    return node


def _contains_unknown(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().upper() == "UNKNOWN"
    if isinstance(value, Mapping):
        return any(_contains_unknown(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unknown(item) for item in value)
    return False


def _field_name(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _format_items(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset(item.strip() for item in value.replace(",", "\n").splitlines() if item.strip())
    if isinstance(value, (list, tuple)):
        return frozenset(item.strip() for item in value if isinstance(item, str) and item.strip())
    return frozenset()


def _stripe_ids(value: Any) -> tuple[int, ...]:
    if isinstance(value, int) and not isinstance(value, bool):
        return (value,)
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return ()

    stripe_ids: list[int] = []
    for item in values:
        if isinstance(item, bool):
            return ()
        try:
            stripe_id = int(item)
        except (TypeError, ValueError):
            return ()
        if stripe_id < 0:
            return ()
        stripe_ids.append(stripe_id)
    return tuple(stripe_ids)


def _unsafe_output_fields(node: Mapping[str, Any], prefix: tuple[str, ...] = ()) -> tuple[str, ...]:
    unsafe: list[str] = []
    for raw_key, value in node.items():
        key = str(raw_key)
        path = (*prefix, key)
        normalized_key = key.lower()
        if isinstance(value, Mapping):
            unsafe.extend(_unsafe_output_fields(value, path))
            continue
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    unsafe.extend(_unsafe_output_fields(item, (*path, str(index))))
            if _looks_like_output_mapping(normalized_key) and not _is_unset_output_value(value):
                unsafe.append(_field_name(path))
            continue
        if _looks_like_output_mapping(normalized_key) and not _is_unset_output_value(value):
            unsafe.append(_field_name(path))
    return tuple(unsafe)


def _looks_like_output_mapping(key: str) -> bool:
    if key in ("hardware_outputs_enabled", "output_pins_configured"):
        return False
    return any(token in key for token in ("pin", "output", "trigger", "strobe", "led"))


def _is_unset_output_value(value: Any) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("", "none", "null", "unset", "disabled", "false", "0")
    if isinstance(value, (list, tuple)):
        return all(_is_unset_output_value(item) for item in value)
    return False


def _walk(node: Any, path: tuple[str, ...] = ()) -> tuple[tuple[tuple[str, ...], Any], ...]:
    items: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            child_path = (*path, str(key))
            items.append((child_path, value))
            items.extend(_walk(value, child_path))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            items.extend(_walk(value, (*path, str(index))))
    return tuple(items)


def _value_claims_approval(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        return normalized in _APPROVAL_VALUES or "approved_for" in normalized
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _is_effectively_false(value: Any) -> bool:
    if value is False or value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _FALSEY_APPROVAL_VALUES
    return False
