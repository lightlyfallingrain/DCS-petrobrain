"""Tests for `perception.source`'s `OwnshipState`/`Observation` types."""

from __future__ import annotations

import math

import pytest

from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _telemetry_dict(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "dcs_model_time_s": 123.5,
        "received_wall_clock_s": 1000.0,
        "position_x_m": 1000.0,
        "position_y_m": 500.0,
        "position_z_m": -2000.0,
        "pitch_rad": 0.01,
        "bank_rad": -0.02,
        "yaw_rad": 0.0,
        "heading_true_rad": 1.5707963267948966,  # 90 degrees
        "ias_mps": 80.0,
        "tas_mps": 85.0,
        "altitude_msl_m": 600.0,
        "altitude_agl_m": 450.0,
        "altitude_radar_m": None,
    }
    data.update(overrides)
    return data


def test_from_telemetry_dict_converts_units() -> None:
    ownship = OwnshipState.from_telemetry_dict(_telemetry_dict())

    assert ownship.t_sim == 123.5
    assert ownship.x == 1000.0
    assert ownship.z == -2000.0
    assert ownship.alt_m == 600.0
    assert ownship.heading_true_deg == pytest.approx(90.0)


def test_from_telemetry_dict_wraps_heading_to_0_360() -> None:
    ownship = OwnshipState.from_telemetry_dict(
        _telemetry_dict(heading_true_rad=-math.pi / 2)  # -90 degrees
    )

    assert ownship.heading_true_deg == pytest.approx(270.0)


def test_from_telemetry_dict_raises_on_missing_field() -> None:
    data = _telemetry_dict()
    del data["position_x_m"]

    with pytest.raises(KeyError):
        OwnshipState.from_telemetry_dict(data)


def test_observation_carries_derived_world_position_as_optional() -> None:
    ownship = OwnshipState.from_telemetry_dict(_telemetry_dict())
    observation = Observation(
        id="OBS_1",
        contact_id=None,
        t_sim=123.5,
        t_wall=1000.0,
        source="proxy_heuristic",
        classification_raw="BMP",
        bearing_deg=32.0,
        range_m=3100.0,
        ownship_at_observation=ownship,
        derived_world_position=None,
        provenance="aircraft_layer/world_objects",
    )

    assert observation.derived_world_position is None
    assert observation.contact_id is None

    with_position = Observation(
        id=observation.id,
        contact_id=observation.contact_id,
        t_sim=observation.t_sim,
        t_wall=observation.t_wall,
        source=observation.source,
        classification_raw=observation.classification_raw,
        bearing_deg=observation.bearing_deg,
        range_m=observation.range_m,
        ownship_at_observation=observation.ownship_at_observation,
        derived_world_position=DerivedWorldPosition(
            x=1500.0, z=-1800.0, confidence=0.6, method="bearing_range_terrain"
        ),
        provenance=observation.provenance,
    )

    assert with_position.derived_world_position is not None
    assert with_position.derived_world_position.method == "bearing_range_terrain"
