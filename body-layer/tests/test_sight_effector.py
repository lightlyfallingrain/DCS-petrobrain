"""Tests for `belief.sight_effector` -- `BL-B66` Stages 2-4 and `[[BL-B80]]`
v2 (`plans/9k113-effectors/plan.md`, `plans/9k113-sight-pointing/plan.md`).
No live DCS/aircraft-layer needed -- every effector write goes through a
fake `AircraftLayerClient` double, same posture as every other body-layer
effector test.

v1's degree<->raw conversions, `GYRO_ALIGNMENT_S`/`in_gyro_alignment`, and
the zero-real-warm-up `sight_ready` field are removed with the code they
tested (the Removal commit) -- `sight_ready()` now reads the real 960
lamp, and the wire carries degrees directly (`write_sight_target`'s own
test)."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.sight_effector import (
    GUIDANCE_UNIT_SWITCH_DELAY_S,
    GuidanceUnitState,
    advance_power_up,
    refresh_readback,
    sight_ready,
    start_power_up,
    write_observ,
    write_sight_target,
    write_weapon_safety,
)

_SRC = Path(__file__).resolve().parent.parent / "src"


class _RecordingAircraftClient:
    """A fake `AircraftLayerClient` that records every cockpit-switch/
    sight-target write and never raises."""

    def __init__(self) -> None:
        self.writes: list[tuple[int, int, float]] = []
        self.sight_target_writes: list[tuple[float, float, float, float, float]] = []

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        self.writes.append((device, cmd, value))

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

    def get_cockpit_switch_state_latest(self) -> dict[str, object] | None:
        return None


class _FailingAircraftClient:
    """A fake `AircraftLayerClient` whose `write_cockpit_switch`/
    `write_sight_target` always raise `AircraftLayerError`."""

    def __init__(self) -> None:
        self.attempts = 0

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        self.attempts += 1
        raise AircraftLayerError("simulated failure")

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

    def get_cockpit_switch_state_latest(self) -> dict[str, object] | None:
        return None


def _client(fake: object) -> AircraftLayerClient:
    return cast(AircraftLayerClient, fake)


# --- start_power_up / advance_power_up --------------------------------------


def test_start_power_up_sets_takeoff_seen_and_fires_immediately() -> None:
    state = GuidanceUnitState()
    started = start_power_up(state, now_sim=10.0)

    assert started.takeoff_seen is True
    assert started.next_switch_due_sim == 10.0
    assert started.power_up_stage == 0


def test_start_power_up_is_a_no_op_once_already_started() -> None:
    state = GuidanceUnitState(takeoff_seen=True, next_switch_due_sim=10.0)
    result = start_power_up(state, now_sim=20.0)

    assert result is state


def test_start_power_up_is_a_no_op_once_the_sequence_has_progressed() -> None:
    """`power_up_stage > 0` alone (even with `next_switch_due_sim` reset
    to `None` by a completed sequence) must not re-start."""
    state = GuidanceUnitState(power_up_stage=1, next_switch_due_sim=None)
    result = start_power_up(state, now_sim=20.0)

    assert result is state


def test_advance_power_up_writes_the_first_switch_immediately() -> None:
    client = _RecordingAircraftClient()
    state = start_power_up(GuidanceUnitState(), now_sim=10.0)

    advanced = advance_power_up(state, now_sim=10.0, aircraft_client=_client(client))

    assert advanced.power_up_stage == 1
    assert len(client.writes) == 1
    _device, _cmd, value = client.writes[0]
    assert value == 1.0
    assert advanced.next_switch_due_sim == 10.0 + GUIDANCE_UNIT_SWITCH_DELAY_S


def test_advance_power_up_does_not_fire_before_the_delay_has_elapsed() -> None:
    client = _RecordingAircraftClient()
    state = start_power_up(GuidanceUnitState(), now_sim=10.0)
    state = advance_power_up(state, now_sim=10.0, aircraft_client=_client(client))
    assert len(client.writes) == 1

    # Not yet due -- `GUIDANCE_UNIT_SWITCH_DELAY_S` has not elapsed.
    still = advance_power_up(
        state,
        now_sim=10.0 + GUIDANCE_UNIT_SWITCH_DELAY_S / 2,
        aircraft_client=_client(client),
    )

    assert still is state
    assert len(client.writes) == 1


def test_advance_power_up_writes_all_four_switches_in_order_and_completes() -> None:
    """`[[BL-B80]]` v2: completion no longer *declares* readiness itself
    -- `sight_ready()` reads the real 960 lamp, not a sequence-completion
    latch."""
    client = _RecordingAircraftClient()
    state = start_power_up(GuidanceUnitState(), now_sim=0.0)

    t = 0.0
    for expected_stage in range(1, 5):
        state = advance_power_up(state, now_sim=t, aircraft_client=_client(client))
        assert state.power_up_stage == expected_stage
        t += GUIDANCE_UNIT_SWITCH_DELAY_S

    assert len(client.writes) == 4
    assert state.next_switch_due_sim is None
    # Readiness is independent of the power-up sequence now.
    assert sight_ready(state) is False
    assert sight_ready(replace(state, ready_observed=True)) is True

    # A true no-op once complete.
    final = advance_power_up(state, now_sim=t + 100.0, aircraft_client=_client(client))
    assert final is state
    assert len(client.writes) == 4


def test_advance_power_up_before_start_is_a_no_op() -> None:
    client = _RecordingAircraftClient()
    state = GuidanceUnitState()  # never started

    result = advance_power_up(state, now_sim=50.0, aircraft_client=_client(client))

    assert result is state
    assert client.writes == []


def test_advance_power_up_retries_on_a_failed_write(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Security plan review finding 3: a dropped write must not advance
    the stage or stall the sequence -- the same switch is retried next
    poll, which is safe because every write is an idempotent absolute
    set."""
    client = _FailingAircraftClient()
    state = start_power_up(GuidanceUnitState(), now_sim=0.0)

    with caplog.at_level(logging.WARNING):
        after_failure = advance_power_up(
            state, now_sim=0.0, aircraft_client=_client(client)
        )

    assert after_failure.power_up_stage == 0
    assert after_failure.next_switch_due_sim == 0.0
    assert client.attempts == 1
    assert any("power-up" in r.message for r in caplog.records)

    # Retried next poll, this time against a working client.
    working = _RecordingAircraftClient()
    retried = advance_power_up(
        after_failure, now_sim=0.0, aircraft_client=_client(working)
    )
    assert retried.power_up_stage == 1
    assert len(working.writes) == 1


def test_advance_power_up_uses_the_device_cmd_pairs_in_order() -> None:
    """MISSILE POWER -> CPLR DISTR -> Sight Power -> SHCHO PWR B1
    (`docs/acceptance/2026-10-17-9k113-procedures-direction.md` §3,
    explore-notes point 4)."""
    client = _RecordingAircraftClient()
    state = start_power_up(GuidanceUnitState(), now_sim=0.0)
    t = 0.0
    for _ in range(4):
        state = advance_power_up(state, now_sim=t, aircraft_client=_client(client))
        t += GUIDANCE_UNIT_SWITCH_DELAY_S

    devices = [w[0] for w in client.writes]
    cmds = [w[1] for w in client.writes]
    # device 6 (WEAP_SYS), 16 (ASP_17V), 7 (I9K113), 6 (WEAP_SYS)
    assert devices == [6, 16, 7, 6]
    assert cmds == [3028, 3015, 3001, 3030]


# --- sight_ready (`[[BL-B80]]` v2: the real 960 lamp) ----------------------


def test_sight_ready_reflects_ready_observed() -> None:
    assert sight_ready(GuidanceUnitState()) is False
    assert sight_ready(GuidanceUnitState(ready_observed=False)) is False
    assert sight_ready(GuidanceUnitState(ready_observed=True)) is True


# --- write_observ / write_weapon_safety ---------------------------------


def test_write_observ_on_writes_arg_886_device_7_value_1() -> None:
    client = _RecordingAircraftClient()
    write_observ(_client(client), on=True)
    assert client.writes == [(7, 3002, 1.0)]


def test_write_observ_off_writes_value_0() -> None:
    client = _RecordingAircraftClient()
    write_observ(_client(client), on=False)
    assert client.writes == [(7, 3002, 0.0)]


def test_write_observ_raises_on_a_failed_write() -> None:
    client = _FailingAircraftClient()
    with pytest.raises(AircraftLayerError):
        write_observ(_client(client), on=True)


def test_write_weapon_safety_armed_writes_arg_673_device_6_value_1() -> None:
    client = _RecordingAircraftClient()
    write_weapon_safety(_client(client), armed=True)
    assert client.writes == [(6, 3020, 1.0)]


def test_write_weapon_safety_safe_writes_value_0() -> None:
    client = _RecordingAircraftClient()
    write_weapon_safety(_client(client), armed=False)
    assert client.writes == [(6, 3020, 0.0)]


def test_write_weapon_safety_raises_on_a_failed_write() -> None:
    client = _FailingAircraftClient()
    with pytest.raises(AircraftLayerError):
        write_weapon_safety(_client(client), armed=True)


# --- refresh_readback ----------------------------------------------------


def test_refresh_readback_is_a_no_op_when_no_sample_yet() -> None:
    state = GuidanceUnitState()
    result = refresh_readback(state, None)
    assert result is state


def test_refresh_readback_sets_observed_fields_from_the_latest_sample() -> None:
    state = GuidanceUnitState()
    result = refresh_readback(
        state, {"observe_on": True, "weapons_armed": False, "missl_pw_on": True}
    )
    assert result.observ_observed is True
    assert result.weapon_safety_observed is False


def test_refresh_readback_leaves_fields_unchanged_when_keys_are_missing() -> None:
    state = GuidanceUnitState(observ_observed=True, weapon_safety_observed=False)
    result = refresh_readback(state, {})
    assert result.observ_observed is True
    assert result.weapon_safety_observed is False


def test_refresh_readback_sets_the_three_lamp_fields() -> None:
    """`[[BL-B80]]` v2: 898 (Л5 gyro alignment), 960 (READY), 962 (launch
    permission), real readbacks, no timer."""
    state = GuidanceUnitState()
    result = refresh_readback(
        state,
        {"align_lamp": True, "ready_lamp": False, "launch_perm_lamp": True},
    )
    assert result.align_observed is True
    assert result.ready_observed is False
    assert result.launch_perm_observed is True


def test_refresh_readback_leaves_lamp_fields_unchanged_when_absent() -> None:
    """An `Export.lua` predating the three lamps must not be read as "the
    lamp is off" -- absence leaves the prior value, same posture every
    other `*_observed` field in this class already takes."""
    state = GuidanceUnitState(
        align_observed=True, ready_observed=True, launch_perm_observed=False
    )
    result = refresh_readback(state, {"observe_on": True})
    assert result.align_observed is True
    assert result.ready_observed is True
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


def test_guidance_unit_state_is_constructed_in_exactly_one_place_in_logger_py() -> None:
    """`ConsolePerceptionRunner`'s `field(default_factory=GuidanceUnitState)`
    is the plan's named single construction site -- grepped, not counted
    by eye, per the `BL-B71` lesson the plan explicitly transfers here
    (plan's "Construction-site check"). A `default_factory=ClassName`
    dataclass field never spells out a literal `ClassName(` call -- the
    machinery calls it -- so this checks for the factory reference itself,
    not a call-shaped substring (unlike the sibling test below, which
    checks `sight_effector.py` never calls this constructor directly)."""
    text = (_SRC / "logger.py").read_text()
    hits = re.findall(r"default_factory=GuidanceUnitState\b", text)
    assert len(hits) == 1, (
        f"expected exactly one `default_factory=GuidanceUnitState` "
        f"construction site in logger.py, found {len(hits)}"
    )
    # And no *literal* construction call anywhere in logger.py either --
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
