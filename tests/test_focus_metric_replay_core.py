from scanner_core.focus_metric_replay import (
    OFFLINE_REJECTION_CODES,
    REJECTION_CODES,
    REQUIRED_CALIBRATION_ROLES,
    calibration_reference_sha256,
    focus_metric_result_sha256,
    manifest_rejection_codes,
    missing_calibration_id_rejection_codes,
    metric_config_sha256,
    replay_decision_sha256,
    selected_calibration_fields,
    selected_frame_metadata_fields,
    selected_source_fields,
    source_frame_checksum,
    source_frame_rejection_codes,
)


def test_manifest_rejection_codes_preserve_order_and_registry_mismatch():
    manifest = _accepted_manifest()
    manifest["source_frame"]["format"] = "jpeg"
    manifest["source_frame"]["preview"] = True
    manifest["source_frame"]["linear"] = False
    manifest["calibrations"]["objective"]["checksum_sha256"] = "1" * 64

    codes = manifest_rejection_codes(
        manifest,
        _registry(),
        include_calibration_mismatch=True,
    )

    assert codes == [
        "non_raw_format",
        "preview_frame",
        "nonlinear_data",
        "calibration_mismatch",
    ]
    assert REJECTION_CODES == (
        "missing_calibration_id",
        "calibration_mismatch",
        "non_raw_format",
        "nonlinear_data",
        "preview_frame",
    )
    assert OFFLINE_REJECTION_CODES == (
        "missing_calibration_id",
        "non_raw_format",
        "nonlinear_data",
        "preview_frame",
    )


def test_manifest_rejection_codes_support_offline_without_registry():
    manifest = _accepted_manifest()
    manifest["calibrations"]["objective"]["calibration_id"] = ""

    assert manifest_rejection_codes(manifest) == ["missing_calibration_id"]


def test_source_frame_rejection_codes_support_af_fixture_shape_without_data_domain():
    raw_fixture = {
        "format": "raw_bayer",
        "encoding": "RAW",
        "linear": True,
        "preview": False,
    }

    assert source_frame_rejection_codes(
        raw_fixture,
        raw_formats=frozenset({"raw_bayer"}),
        require_linear_domain=False,
    ) == []
    assert source_frame_rejection_codes(
        {**raw_fixture, "encoding": "JPEG", "preview": True, "linear": False},
        raw_formats=frozenset({"raw_bayer"}),
        require_linear_domain=False,
    ) == ["non_raw_format", "preview_frame", "nonlinear_data"]


def test_missing_calibration_id_rejection_codes_can_ignore_active_flag():
    calibrations = {
        "dark": {"calibration_id": "dark-v1", "active": False},
        "flatfield": {"calibration_id": "flat-v1"},
    }

    assert missing_calibration_id_rejection_codes(
        calibrations,
        required_calibration_roles=("dark", "flatfield"),
        require_active=False,
    ) == []
    assert missing_calibration_id_rejection_codes(
        calibrations,
        required_calibration_roles=("dark", "flatfield"),
        require_active=True,
    ) == ["missing_calibration_id"]


def test_projection_fields_and_hashes_are_deterministic():
    manifest = _accepted_manifest()
    result = {"focus_metric": 10.0, "shift_px": 1.5, "confidence": 0.8}

    assert tuple(selected_source_fields(manifest["source_frame"])) == (
        "path",
        "checksum_sha256",
        "format",
        "encoding",
        "pixel_format",
        "cfa_pattern",
        "packing",
        "compression",
        "data_domain",
        "stream_name",
        "width_px",
        "height_px",
        "stride_bytes",
        "bit_depth",
        "linear",
        "preview",
        "pipeline_transforms",
    )
    assert selected_calibration_fields(manifest["calibrations"])["objective"] == {
        "calibration_id": "objective-v1",
        "checksum_sha256": "b" * 64,
        "active": True,
    }
    assert selected_frame_metadata_fields(manifest["frame_metadata"]) == {
        "frame_id": 4,
        "scan_id": "scan-1",
        "pattern": "AF_RG",
        "z_cmd_count": 20,
        "camera_mode_id": "hq-raw",
        "hardware_outputs_enabled": False,
    }
    assert source_frame_checksum(manifest["source_frame"]) == (
        "cf26d472d1760b963d3bdbed748739ed954656358cc0a9f044d9eab3a10bb56b"
    )
    assert metric_config_sha256(manifest) == (
        "75a24ea69d3072fa97c308a7309e275c3d9a841c7f5414def2f40ede387d416c"
    )
    assert calibration_reference_sha256(manifest) == (
        "89780595052b17efc39d8a4bf09e4fab13b45bdedee041342425755ed4a6d7fb"
    )
    assert focus_metric_result_sha256(
        manifest,
        result,
        contract_id="focus_metric_contract_v1",
        artifact_kind="focus_metric_output",
    ) == "449b874d7fea0daf3e73a96e69362e4d28fb4bbab397d56e92a62d127cf38251"
    assert replay_decision_sha256(
        "manifest-1",
        "rejected",
        ["preview_frame", "non_raw_format"],
        contract_id="focus_metric_contract_v1",
    ) == "c7c316cee4c8fbb34c8be66664092ffd5d40f6e0b7550384ce07e2f885333aaa"


def _accepted_manifest() -> dict:
    return {
        "manifest_id": "manifest-1",
        "source_frame": {
            "path": "frames/frame-1.raw",
            "checksum_sha256": "a" * 64,
            "format": "raw_bayer",
            "encoding": "RAW",
            "pixel_format": "bayer_rggb10",
            "cfa_pattern": "RGGB",
            "packing": "unpacked16",
            "compression": "none",
            "data_domain": "raw_sensor",
            "stream_name": "main",
            "width_px": 2,
            "height_px": 2,
            "stride_bytes": 4,
            "bit_depth": 10,
            "linear": True,
            "preview": False,
            "pipeline_transforms": {
                "debayer": False,
                "gamma": False,
                "denoise": False,
                "sharpening": False,
                "color_correction": False,
            },
            "dtype": "uint16",
            "inline_rows": [[1, 2], [3, 4]],
        },
        "metric_config": {"method": "gradient_energy", "version": 1},
        "calibrations": {
            role: {
                "calibration_id": f"{role}-v1",
                "checksum_sha256": "b" * 64,
                "active": True,
            }
            for role in REQUIRED_CALIBRATION_ROLES
        },
        "frame_metadata": {
            "frame_id": 4,
            "scan_id": "scan-1",
            "pattern": "AF_RG",
            "z_cmd_count": 20,
            "camera_mode_id": "hq-raw",
            "hardware_outputs_enabled": False,
        },
    }


def _registry() -> dict:
    return {
        role: {
            "calibration_id": f"{role}-v1",
            "checksum_sha256": "b" * 64,
            "active": True,
        }
        for role in REQUIRED_CALIBRATION_ROLES
    }
