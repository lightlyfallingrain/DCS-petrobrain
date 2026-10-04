"""Tests for `belief.mission_phase` -- `plans/bl7-mission-phase-relevance/
plan.md`. Fixture-based throughout, no live Mission Interpreter dependency:
`tests/fixtures/mission_understanding_sample.json` is a hand-written
compact-artifact-shaped JSON (a real MI-6 `--emit-compact` output's
`dataclasses.asdict` shape, verified against `runtime.compact.
RuntimeMissionUnderstanding` at authorship time) with 4 route points
(indices 0-3, spaced 5000m apart along +x) and 3 phases (ingress@0,
attack@2, egress@3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from belief.mission_phase import (
    WAYPOINT_CAPTURE_RADIUS_M,
    CompactRoutePoint,
    MissionPhaseInfo,
    MissionPhaseTracker,
    MissionUnderstandingData,
    load_mission_understanding,
    mission_phase_relevance,
)
from perception.geometry import GeoPosition

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mission_understanding_sample.json"


def _position(x: float, alt_m: float = 500.0) -> GeoPosition:
    return GeoPosition(x=x, z=0.0, alt_m=alt_m)


# --- load_mission_understanding ---------------------------------------------


def test_load_mission_understanding_parses_the_fixture() -> None:
    data = load_mission_understanding(_FIXTURE_PATH)
    assert [phase.name for phase in data.phases] == ["ingress", "attack", "egress"]
    assert [phase.waypoint_index for phase in data.phases] == [0, 2, 3]
    assert len(data.route) == 4
    assert data.route[0].place_name == "Home Base"
    assert data.route[1].place_name is None
    assert data.phases[0].epistemic_status == "FACT"
    assert data.phases[0].basis == ("mi3:phase_boundary",)
    assert data.route[2].epistemic_status == "OBSERVATION"
    assert data.theatre is not None
    assert data.theatre.value == "Syria"
    assert data.theatre.epistemic_status == "FACT"
    assert data.theatre.basis == ("miz:theatre",)


def test_load_mission_understanding_raises_on_missing_theatre_key(
    tmp_path: Path,
) -> None:
    """`theatre` (Stage 5, multi-theatre-afghanistan plan) is required --
    every real compact artifact carries it -- same fail-loud posture as
    `phases`/`route`."""
    raw = json.loads(_FIXTURE_PATH.read_text())
    del raw["theatre"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="theatre"):
        load_mission_understanding(bad_path)


def test_load_mission_understanding_sorts_phases_by_waypoint_index(
    tmp_path: Path,
) -> None:
    raw = json.loads(_FIXTURE_PATH.read_text())
    raw["phases"] = list(reversed(raw["phases"]))
    unsorted_path = tmp_path / "unsorted.json"
    unsorted_path.write_text(json.dumps(raw))
    data = load_mission_understanding(unsorted_path)
    assert [phase.waypoint_index for phase in data.phases] == [0, 2, 3]


def test_load_mission_understanding_accepts_empty_phases_and_route(
    tmp_path: Path,
) -> None:
    raw = json.loads(_FIXTURE_PATH.read_text())
    raw["phases"] = []
    raw["route"] = []
    empty_path = tmp_path / "empty.json"
    empty_path.write_text(json.dumps(raw))
    data = load_mission_understanding(empty_path)
    assert data.phases == ()
    assert data.route == ()
    tracker = MissionPhaseTracker(data=data)
    tracker.update(_position(0.0))
    assert tracker.current_phase() is None


def test_load_mission_understanding_raises_on_missing_route_key(
    tmp_path: Path,
) -> None:
    raw = json.loads(_FIXTURE_PATH.read_text())
    del raw["route"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_mission_understanding(bad_path)


def test_load_mission_understanding_raises_on_malformed_phase_value(
    tmp_path: Path,
) -> None:
    raw = json.loads(_FIXTURE_PATH.read_text())
    del raw["phases"][0]["value"]["waypoint_index"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_mission_understanding(bad_path)


def test_load_mission_understanding_raises_on_missing_basis(tmp_path: Path) -> None:
    raw = json.loads(_FIXTURE_PATH.read_text())
    del raw["phases"][0]["basis"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_mission_understanding(bad_path)


# --- MissionPhaseTracker -----------------------------------------------------


def test_tracker_starts_with_no_active_phase() -> None:
    data = load_mission_understanding(_FIXTURE_PATH)
    tracker = MissionPhaseTracker(data=data)
    assert tracker.current_phase() is None


def test_tracker_advances_across_a_walked_route() -> None:
    data = load_mission_understanding(_FIXTURE_PATH)
    tracker = MissionPhaseTracker(data=data)

    tracker.update(_position(0.0))
    assert tracker.last_reached_waypoint_index == 0
    assert tracker.current_phase() is not None
    assert tracker.current_phase().name == "ingress"  # type: ignore[union-attr]

    tracker.update(_position(5000.0))
    assert tracker.last_reached_waypoint_index == 1
    assert tracker.current_phase().name == "ingress"  # type: ignore[union-attr]

    tracker.update(_position(10000.0))
    assert tracker.last_reached_waypoint_index == 2
    assert tracker.current_phase().name == "attack"  # type: ignore[union-attr]

    tracker.update(_position(15000.0))
    assert tracker.last_reached_waypoint_index == 3
    assert tracker.current_phase().name == "egress"  # type: ignore[union-attr]


def test_tracker_is_monotonic_and_never_decrements() -> None:
    data = load_mission_understanding(_FIXTURE_PATH)
    tracker = MissionPhaseTracker(data=data)
    tracker.update(_position(10000.0))
    assert tracker.last_reached_waypoint_index == 2

    # Regress toward an earlier waypoint -- must not decrement.
    tracker.update(_position(0.0))
    assert tracker.last_reached_waypoint_index == 2
    assert tracker.current_phase() is not None
    assert tracker.current_phase().name == "attack"  # type: ignore[union-attr]


def test_tracker_advances_past_a_skipped_intermediate_waypoint() -> None:
    """A poll gap that lands ownship near waypoint 2 without ever coming
    near waypoint 1 must still advance past both -- `update` checks every
    not-yet-reached point, not just the immediate next one."""
    data = load_mission_understanding(_FIXTURE_PATH)
    tracker = MissionPhaseTracker(data=data)
    tracker.update(_position(10000.0))
    assert tracker.last_reached_waypoint_index == 2
    assert tracker.current_phase() is not None
    assert tracker.current_phase().name == "attack"  # type: ignore[union-attr]


def test_tracker_does_not_advance_outside_capture_radius() -> None:
    """`x=6001` is within `WAYPOINT_CAPTURE_RADIUS_M` of waypoint 1 (x=5000,
    distance 1001m) but not of waypoint 2 (x=10000, distance 3999m) --
    `last_reached_waypoint_index` must stop at 1, not jump to 2."""
    data = load_mission_understanding(_FIXTURE_PATH)
    tracker = MissionPhaseTracker(data=data)
    x = 5000.0 + WAYPOINT_CAPTURE_RADIUS_M - 1999.0
    tracker.update(_position(x))
    assert tracker.last_reached_waypoint_index == 1
    assert tracker.current_phase() is not None
    assert tracker.current_phase().name == "ingress"  # type: ignore[union-attr]


# --- mission_phase_relevance -------------------------------------------------


def test_mission_phase_relevance_returns_none_for_no_active_phase() -> None:
    data = load_mission_understanding(_FIXTURE_PATH)
    assert mission_phase_relevance(_position(0.0), None, data.route) is None


def test_mission_phase_relevance_returns_distance_to_active_phase_waypoint() -> None:
    data = load_mission_understanding(_FIXTURE_PATH)
    phase = MissionPhaseInfo(
        name="attack", waypoint_index=2, epistemic_status="FACT", basis=()
    )
    relevance = mission_phase_relevance(_position(8000.0), phase, data.route)
    assert relevance == pytest.approx(2000.0)


def test_mission_phase_relevance_returns_none_if_waypoint_not_in_route() -> None:
    route = (
        CompactRoutePoint(
            index=0, x=0.0, y=0.0, place_name=None, epistemic_status="FACT", basis=()
        ),
    )
    phase = MissionPhaseInfo(
        name="attack", waypoint_index=5, epistemic_status="FACT", basis=()
    )
    assert mission_phase_relevance(_position(0.0), phase, route) is None


def test_mission_understanding_data_is_a_frozen_dataclass() -> None:
    data = MissionUnderstandingData(phases=(), route=())
    with pytest.raises(AttributeError):
        data.phases = ()  # type: ignore[misc]
