"""Scan preflight evaluator."""

from __future__ import annotations

from scanner_firmware.planning.scan_preflight.decisions import (
    ScanPreflightDecision,
    ScanPreflightInput,
)
from scanner_firmware.planning.scan_preflight.validation import (
    blocking_precondition_errors,
    validate_preflight,
)


def evaluate_scan_preflight(
    preflight: ScanPreflightInput,
) -> ScanPreflightDecision:
    """Evaluate whether a scan workflow may start.

    Homing is mandatory for every real scan. The only permitted bypass is an
    explicit dry run with hardware outputs disabled, and that accepted result
    still carries warnings for missing or unimplemented homing evidence.
    """

    validate_preflight(preflight)
    missing_axes = tuple(
        axis for axis in preflight.required_axes if axis not in preflight.homed_axes
    )
    blocking_errors = blocking_precondition_errors(preflight)
    homing_errors = _homing_precondition_errors(preflight, missing_axes)

    if blocking_errors:
        return ScanPreflightDecision(
            accepted=False,
            missing_axes=missing_axes,
            errors=blocking_errors,
        )

    if not homing_errors:
        return ScanPreflightDecision(accepted=True, missing_axes=())

    if preflight.hardware_outputs_enabled:
        return ScanPreflightDecision(
            accepted=False,
            missing_axes=missing_axes,
            errors=homing_errors
            + (
                "hardware outputs cannot be enabled until all required axes are homed",
            ),
        )

    if preflight.dry_run:
        return ScanPreflightDecision(
            accepted=True,
            missing_axes=missing_axes,
            warnings=tuple(
                _dry_run_homing_warning(error) for error in homing_errors
            )
            + (
                "hardware outputs are disabled; simulator-only homing bypass is active",
            ),
        )

    return ScanPreflightDecision(
        accepted=False,
        missing_axes=missing_axes,
        errors=homing_errors
        + (
            "non-dry-run scan workflows require all axes to be homed",
        ),
    )


def _homing_precondition_errors(
    preflight: ScanPreflightInput,
    missing_axes: tuple[str, ...],
) -> tuple[str, ...]:
    errors: list[str] = []
    if not preflight.homing_enabled:
        errors.append("homing is disabled by configuration")
    if missing_axes:
        missing_text = ", ".join(missing_axes)
        errors.append(f"homing is missing for required axes: {missing_text}")
    if preflight.homing_feasibility_status == "unknown":
        errors.append("homing feasibility is unknown")
    if preflight.homing_feasibility_status == "not_implemented":
        errors.append("homing implementation is not implemented")
    return tuple(errors)


def _dry_run_homing_warning(error: str) -> str:
    if error.startswith("homing is missing for required axes: "):
        return error.replace(
            "homing is missing for required axes: ",
            "dry-run scan accepted with missing homing for axes: ",
            1,
        )
    return f"dry-run scan accepted with {error}"
