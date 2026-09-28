import pytest

from scanner_core.scan_geometry import (
    PositionSample,
    ScanGeometryError,
    StripeGeometry,
    validate_axis,
)


def test_builds_forward_x_geometry_positions_and_direction():
    geometry = StripeGeometry(
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=0,
        event_pitch=25,
        event_count=5,
    )

    assert geometry.direction == 1
    assert geometry.positions == (0, 25, 50, 75, 100)
    assert geometry.position_samples == (
        PositionSample(axis="X", event_index=0, position_count=0),
        PositionSample(axis="X", event_index=1, position_count=25),
        PositionSample(axis="X", event_index=2, position_count=50),
        PositionSample(axis="X", event_index=3, position_count=75),
        PositionSample(axis="X", event_index=4, position_count=100),
    )
    assert geometry.pitch == 25
    assert geometry.last_position == 100
    assert geometry.lower_bound == 0
    assert geometry.upper_bound == 100
    assert geometry.contains_position(75)
    assert geometry.is_event_position(50)
    assert not geometry.is_event_position(60)


def test_builds_reverse_y_geometry_positions_and_direction():
    geometry = StripeGeometry(
        axis="Y",
        start_position=100,
        end_position=0,
        first_event_position=100,
        event_pitch=-30,
        event_count=4,
    )

    assert geometry.direction == -1
    assert geometry.positions == (100, 70, 40, 10)
    assert geometry.last_position == 10
    assert geometry.contains_position(0)
    assert geometry.contains_position(100)


def test_lowercase_axis_is_normalized():
    geometry = StripeGeometry(
        axis="x",
        start_position=0,
        end_position=100,
        first_event_position=0,
        event_pitch=20,
        event_count=1,
    )

    assert validate_axis("x") == "X"
    assert validate_axis("y") == "Y"
    assert geometry.axis == "X"


def test_pitch_alias_defaults_first_event_after_start():
    geometry = StripeGeometry(
        axis="x",
        start_position=100,
        end_position=160,
        pitch=20,
        event_count=3,
    )

    assert geometry.positions == (120, 140, 160)
    assert geometry.position_for_event(0) == PositionSample(
        axis="X",
        event_index=0,
        position_count=120,
    )


def test_allows_zero_event_count_with_empty_positions():
    geometry = StripeGeometry(
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=10,
        event_pitch=10,
        event_count=0,
    )

    assert geometry.positions == ()
    assert geometry.position_samples == ()
    assert geometry.last_position is None
    assert not geometry.is_event_position(0)


def test_allows_first_event_inside_stripe_after_start():
    geometry = StripeGeometry(
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=10,
        event_pitch=20,
        event_count=4,
    )

    assert geometry.positions == (10, 30, 50, 70)
    assert not geometry.is_event_position(0)
    assert geometry.is_event_position(30)


def test_rejects_invalid_axis_direction_pitch_and_counts():
    invalid_cases = (
        {"axis": "Z", "start_position": 0, "end_position": 10, "pitch": 1, "event_count": 1},
        {
            "axis": "X",
            "start_position": 0,
            "end_position": 0,
            "first_event_position": 0,
            "event_pitch": 1,
            "event_count": 1,
        },
        {
            "axis": "X",
            "start_position": 0,
            "end_position": 10,
            "first_event_position": 0,
            "event_pitch": 0,
            "event_count": 1,
        },
        {
            "axis": "X",
            "start_position": 0,
            "end_position": 10,
            "first_event_position": 0,
            "event_pitch": -1,
            "event_count": 1,
        },
        {
            "axis": "Y",
            "start_position": 10,
            "end_position": 0,
            "first_event_position": 10,
            "event_pitch": 1,
            "event_count": 1,
        },
        {
            "axis": "Y",
            "start_position": 10,
            "end_position": 0,
            "first_event_position": 10,
            "event_pitch": -1,
            "event_count": -1,
        },
        {
            "axis": "X",
            "start_position": 0,
            "end_position": 10,
            "first_event_position": 0,
            "event_pitch": 1,
            "event_count": True,
        },
    )

    for kwargs in invalid_cases:
        with pytest.raises(ScanGeometryError):
            StripeGeometry(**kwargs)


def test_rejects_last_position_outside_bounds():
    with pytest.raises(ScanGeometryError, match="last event position"):
        StripeGeometry(
            axis="X",
            start_position=0,
            end_position=10,
            first_event_position=0,
            event_pitch=4,
            event_count=4,
        )


def test_checks_bounds_and_planned_event_positions():
    geometry = StripeGeometry(
        axis="X",
        start_position=10,
        end_position=30,
        first_event_position=10,
        event_pitch=10,
        event_count=2,
    )

    assert geometry.require_within_bounds(20) == 20
    assert geometry.require_event_position(10) == 10
    with pytest.raises(ScanGeometryError, match="outside stripe bounds"):
        geometry.require_within_bounds(31, "sample.position")
    with pytest.raises(ScanGeometryError, match="planned stripe event"):
        geometry.require_event_position(30)


def test_calculates_forward_sample_overshoot():
    geometry = StripeGeometry(
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=0,
        event_pitch=20,
        event_count=5,
    )

    overshoot = geometry.overshoot_for_sample(
        event_position=40,
        sample=PositionSample(axis="X", position=47),
    )

    assert overshoot == 7


def test_calculates_reverse_sample_overshoot_as_signed_position_delta():
    geometry = StripeGeometry(
        axis="Y",
        start_position=100,
        end_position=0,
        first_event_position=100,
        event_pitch=-20,
        event_count=5,
    )

    overshoot = geometry.overshoot_for_sample(
        event_position=60,
        sample=PositionSample(axis="Y", position=52),
    )

    assert overshoot == -8


def test_rejects_sample_axis_mismatch_before_overshoot():
    geometry = StripeGeometry(
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=0,
        event_pitch=20,
        event_count=5,
    )

    with pytest.raises(ScanGeometryError, match="sample axis"):
        geometry.overshoot_for_sample(
            event_position=40,
            sample=PositionSample(axis="Y", position=45),
        )


def test_rejects_sample_that_has_not_reached_event():
    geometry = StripeGeometry(
        axis="X",
        start_position=0,
        end_position=100,
        first_event_position=0,
        event_pitch=20,
        event_count=5,
    )

    with pytest.raises(ScanGeometryError, match="not reached"):
        geometry.overshoot_for_sample(
            event_position=40,
            sample=PositionSample(axis="X", position=35),
        )


def test_position_sample_aliases_and_validation():
    sample = PositionSample(axis="x", position=47, position_count=47, event_index=2)

    assert sample.axis == "X"
    assert sample.position == 47
    assert sample.position_count == 47
    assert sample.event_index == 2

    with pytest.raises(ScanGeometryError, match="position and position_count"):
        PositionSample(axis="X", position=1, position_count=2)
    with pytest.raises(ScanGeometryError, match="event_index"):
        PositionSample(axis="X", position=1, event_index=True)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("start_position", True),
        ("end_position", False),
        ("event_pitch", True),
        ("event_count", False),
    ),
)
def test_bool_as_int_is_invalid(field, value):
    kwargs = {
        "axis": "X",
        "start_position": 0,
        "end_position": 100,
        "first_event_position": 0,
        "event_pitch": 20,
        "event_count": 1,
        field: value,
    }

    with pytest.raises(ScanGeometryError, match="integer"):
        StripeGeometry(**kwargs)
