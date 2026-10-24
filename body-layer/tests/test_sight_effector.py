"""Tests for `belief.sight_effector` -- `[[BL-B80]]` v2 (`plans/
9k113-sight-pointing/plan.md`) and the readback-only module that remains
after `plans/effector-sequences/plan.md` Stage 2 moved the power-up/
OBSERV/weapons-safety *sequencing* half out to `belief.effector_engine`
(see `test_effector_engine.py` for that half's own tests, and `belief.
sight_effector`'s own module docstring for exactly what moved). No live
DCS/aircraft-layer needed -- every write goes through a fake
`AircraftLayerClient` double, same posture as every other body-layer
effector test.

v1's degree<->raw conversions, `GYRO_ALIGNMENT_S`/`in_gyro_alignment`, and
the zero-real-warm-up `sight_ready` field are removed with the code they
tested (the Removal commit) -- `sight_ready()` now reads the real 960
lamp, and the wire carries degrees directly (`write_sight_target`'s own
test)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.sight_effector import (
    GuidanceUnitState,
    refresh_readback,
    sight_ready,
    write_sight_target,
)

_SRC = Path(__file__).resolve().parent.parent / "src"


class _RecordingAircraftClient:
    """A fake `AircraftLayerClient` that records every sight-target write
    and never raises."""

    def __init__(self) -> None:
        self.sight_target_writes: list[tuple[float, float, float, float, float]] = []

    def write_sight_target(
        self,
        goal_az_deg: float,
        goal_el_deg: float,
        goal_rate_az_deg_s: float,
        goal_rate_el_deg_s: float,
        t_sim: float,
    ) -> None:
        self.sight_target_writes.append(
            (goal_az_deg, goal_el_deg, goal_rate_az_deg_s, goal_rate_el_deg_s, t_sim)
        )


class _FailingAircraftClient:
    """A fake `AircraftLayerClient` whose `write_sight_target` always
    raises `AircraftLayerError`."""

    def __init__(self) -> None:
        self.attempts = 0

    def write_sight_target(
        self,
        goal_az_deg: float,
        goal_el_deg: float,
        goal_rate_az_deg_s: float,
        goal_rate_el_deg_s: float,
        t_sim: float,
    ) -> None:
        self.attempts += 1
        raise AircraftLayerError("simulated failure")


def _client(fake: object) -> AircraftLayerClient:
    return cast(AircraftLayerClient, fake)


# --- sight_ready (`[[BL-B80]]` v2: the real 960 lamp) ----------------------


def test_sight_ready_reflects_ready_observed() -> None:
    assert sight_ready(GuidanceUnitState()) is False
    assert sight_ready(GuidanceUnitState(ready_observed=False)) is False
    assert sight_ready(GuidanceUnitState(ready_observed=True)) is True


# --- refresh_readback (Stage 4: the continuous feed's raw "args" map) ----


def test_refresh_readback_is_a_no_op_when_no_sample_yet() -> None:
    state = GuidanceUnitState()
    result = refresh_readback(state, None)
    assert result is state


def test_refresh_readback_sets_observed_fields_from_the_args_map() -> None:
    state = GuidanceUnitState()
    result = refresh_readback(state, {"886": 1.0, "898": 0.0, "960": 1.0})
    assert result.observ_observed is True
    assert result.align_observed is False
    assert result.ready_observed is True


def test_refresh_readback_thresholds_at_half_not_equality() -> None:
    """Same `>= 0.5` threshold `Export.lua` used to apply itself before
    Stage 4 moved it here -- a mid-transit raw value must still read as
    the decided boolean."""
    state = GuidanceUnitState()
    result = refresh_readback(state, {"886": 0.64})
    assert result.observ_observed is True
    result = refresh_readback(state, {"886": 0.32})
    assert result.observ_observed is False


def test_refresh_readback_leaves_fields_unchanged_when_keys_are_missing() -> None:
    state = GuidanceUnitState(observ_observed=True, ready_observed=False)
    result = refresh_readback(state, {})
    assert result.observ_observed is True
    assert result.ready_observed is False


def test_refresh_readback_leaves_fields_unchanged_on_a_non_finite_value() -> None:
    """A NaN/inf must never be read as a value -- same posture as an
    absent key, never coerced to `False` (mutation: drop the
    `math.isfinite` guard)."""
    state = GuidanceUnitState(observ_observed=True)
    result = refresh_readback(state, {"886": float("nan")})
    assert result.observ_observed is True


def test_refresh_readback_does_not_touch_weapon_safety_or_launch_perm() -> None:
    """Stage 4 removed these two args' old per-frame reader with
    nothing replacing it yet (673/962 are no longer polled by code) --
    `refresh_readback` must not read them from the "args" map at all,
    even if a caller mistakenly passed them in (which the real
    `REQUIRED_POLLED_ARGS`-driven set never would)."""
    state = GuidanceUnitState(weapon_safety_observed=True, launch_perm_observed=False)
    result = refresh_readback(state, {"673": 0.0, "962": 1.0})
    assert result.weapon_safety_observed is True
    assert result.launch_perm_observed is False


# --- write_sight_target (`[[BL-B80]]` v2: degrees on the wire, no raw) ----


def test_write_sight_target_passes_the_world_goal_through_unconverted() -> None:
    client = _RecordingAircraftClient()
    write_sight_target(
        _client(client),
        goal_azimuth_deg=22.5,
        goal_elevation_deg=-10.0,
        rate_azimuth_deg_s=1.5,
        rate_elevation_deg_s=-0.2,
        t_sim=123.0,
    )
    assert client.sight_target_writes == [(22.5, -10.0, 1.5, -0.2, 123.0)]


def test_write_sight_target_raises_on_a_failed_write() -> None:
    client = _FailingAircraftClient()
    with pytest.raises(AircraftLayerError):
        write_sight_target(
            _client(client),
            goal_azimuth_deg=0.0,
            goal_elevation_deg=0.0,
            rate_azimuth_deg_s=0.0,
            rate_elevation_deg_s=0.0,
            t_sim=0.0,
        )


# --- single construction site (plan's "Construction-site check") -------


def test_guidance_unit_state_is_constructed_in_exactly_one_place_in_body_py() -> None:
    """`ConsolePerceptionRunner`'s `field(default_factory=GuidanceUnitState)`
    is the plan's named single construction site -- grepped, not counted
    by eye, per the `BL-B71` lesson the plan explicitly transfers here
    (plan's "Construction-site check"). A `default_factory=ClassName`
    dataclass field never spells out a literal `ClassName(` call -- the
    machinery calls it -- so this checks for the factory reference itself,
    not a call-shaped substring (unlike the sibling test below, which
    checks `sight_effector.py` never calls this constructor directly)."""
    text = (_SRC / "body.py").read_text()
    hits = re.findall(r"default_factory=GuidanceUnitState\b", text)
    assert len(hits) == 1, (
        f"expected exactly one `default_factory=GuidanceUnitState` "
        f"construction site in body.py, found {len(hits)}"
    )
    # And no *literal* construction call anywhere in body.py either --
    # `reset_for_new_mission`'s re-run `__init__` reaches the same single
    # factory above, never a second, independent `GuidanceUnitState(...)`.
    assert re.findall(r"\bGuidanceUnitState\(", text) == []


def test_sight_effector_never_constructs_guidance_unit_state_directly() -> None:
    """Every function in this module must return `replace(state, ...)`,
    never a fresh `GuidanceUnitState(...)` mid-sequence."""
    text = (_SRC / "belief" / "sight_effector.py").read_text()
    # The class's own definition line and its docstrings mention the name
    # without calling it; only a literal `GuidanceUnitState(` -- a call --
    # would be a second construction site.
    hits = re.findall(r"\bGuidanceUnitState\(", text)
    assert hits == [], (
        f"belief/sight_effector.py constructs GuidanceUnitState() directly: "
        f"{len(hits)} occurrence(s)"
    )
