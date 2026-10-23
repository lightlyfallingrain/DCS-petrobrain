"""Pure-function tests for `belief.effector_engine` -- `plans/
effector-sequences/plan.md` Stage 2, D1/D3/D4/D8/D9/R12. No live DCS/
aircraft-layer needed -- every write goes through a fake
`AircraftLayerClient` double, same posture as `test_sight_effector.py`.

Real-poll-loop integration tests (the takeoff edge, mission restart,
the startup-error banner/audio line) live in `test_logger.py` instead --
this file is only the engine's own transition logic against hand-built
`SequenceFile`/`EffectorDef` fixtures, not markdown parsing or wiring."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.effector_engine import (
    AIRCRAFT,
    EFFECTOR_CONDITION_READBACK_WAIT_S,
    EFFECTOR_SEQUENCE_STEP_DELAY_S,
    PETROVICH_ROLE,
    EffectorRunState,
    EffectorTrigger,
    advance,
    fire_trigger,
)
from belief.effector_registry import EffectorDef
from belief.effector_sequences import Condition, SequenceFile, SwitchRow, WaitRow


class _FakeAircraftClient:
    """Records every cockpit-switch write. `fail_effectors`, mutated
    directly by a test between `advance` calls, names which curated
    effector *names* the next write(s) to their arg should fail for --
    tracked by `(device, cmd)` pair since that is what `write_cockpit_
    switch` actually receives."""

    def __init__(self) -> None:
        self.writes: list[tuple[int, int, float]] = []
        self.fail_device_cmds: set[tuple[int, int]] = set()

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        if (device, cmd) in self.fail_device_cmds:
            raise AircraftLayerError("simulated failure")
        self.writes.append((device, cmd, value))


def _client(fake: _FakeAircraftClient) -> AircraftLayerClient:
    return cast(AircraftLayerClient, fake)


_MISSILE_POWER = EffectorDef(
    name="missile_power",
    source_element="MISSILE-POWER-PTR",
    device=6,
    cmd=3028,
    arg=773,
    values={"on": 1.0, "off": 0.0},
)
_CPLR_DISTR = EffectorDef(
    name="cplr_distr",
    source_element="CPLR-DISTR-PTR",
    device=16,
    cmd=3015,
    arg=761,
    values={"on": 1.0, "off": 0.0},
    unverified=True,
)
_SIGHT_POWER = EffectorDef(
    name="sight_power",
    source_element="SIGHT-POWER-PTR",
    device=7,
    cmd=3001,
    arg=885,
    values={"on": 1.0, "off": 0.0},
)
_SCHO_PWR_B1 = EffectorDef(
    name="scho_pwr_b1",
    source_element="SCHO-PWR-PTR",
    device=6,
    cmd=3030,
    arg=955,
    values={"on": 1.0, "off": 0.0},
)
_OBSERV = EffectorDef(
    name="observ",
    source_element="OBSERVE-PTR",
    device=7,
    cmd=3002,
    arg=886,
    values={"on": 1.0, "off": 0.0},
)
_WEAPON_SAFETY = EffectorDef(
    name="weapon_safety",
    source_element="WEAPON-SAFETY-PTR",
    device=6,
    cmd=3020,
    arg=673,
    values={"armed": 1.0, "safe": 0.0},
)

_REGISTRY = {
    "missile_power": _MISSILE_POWER,
    "cplr_distr": _CPLR_DISTR,
    "sight_power": _SIGHT_POWER,
    "scho_pwr_b1": _SCHO_PWR_B1,
    "observ": _OBSERV,
    "weapon_safety": _WEAPON_SAFETY,
}

_TAKEOFF_ROWS = (
    SwitchRow(
        condition=None,
        effector="missile_power",
        value="on",
        petrovich_says="",
        comment="",
    ),
    SwitchRow(
        condition=None, effector="cplr_distr", value="on", petrovich_says="", comment=""
    ),
    SwitchRow(
        condition=None,
        effector="sight_power",
        value="on",
        petrovich_says="",
        comment="",
    ),
    SwitchRow(
        condition=None,
        effector="scho_pwr_b1",
        value="on",
        petrovich_says="",
        comment="",
    ),
)


def _sequence(trigger: EffectorTrigger, rows: tuple[object, ...]) -> SequenceFile:
    return SequenceFile(
        aircraft=AIRCRAFT,
        petrovich_role=PETROVICH_ROLE,
        trigger=trigger.value,
        rows=rows,  # type: ignore[arg-type]
        source_path=Path("fake.md"),
    )


_SEQUENCES = {
    (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.TAKEOFF.value): _sequence(
        EffectorTrigger.TAKEOFF, _TAKEOFF_ROWS
    ),
    (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.OBSERV_ON.value): _sequence(
        EffectorTrigger.OBSERV_ON,
        (
            SwitchRow(
                condition=None,
                effector="observ",
                value="on",
                petrovich_says="",
                comment="",
            ),
        ),
    ),
    (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.OBSERV_OFF.value): _sequence(
        EffectorTrigger.OBSERV_OFF,
        (
            SwitchRow(
                condition=None,
                effector="observ",
                value="off",
                petrovich_says="",
                comment="",
            ),
        ),
    ),
    (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.WEAPONS_ARM.value): _sequence(
        EffectorTrigger.WEAPONS_ARM,
        (
            SwitchRow(
                condition=None,
                effector="weapon_safety",
                value="armed",
                petrovich_says="",
                comment="",
            ),
        ),
    ),
    (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.WEAPONS_SAFE.value): _sequence(
        EffectorTrigger.WEAPONS_SAFE,
        (
            SwitchRow(
                condition=None,
                effector="weapon_safety",
                value="safe",
                petrovich_says="",
                comment="",
            ),
        ),
    ),
}


# --- fire_trigger (D1) -------------------------------------------------------


def test_fire_trigger_starts_immediately_when_idle() -> None:
    state = EffectorRunState()
    state = fire_trigger(state, EffectorTrigger.TAKEOFF, now_sim=10.0)

    assert EffectorTrigger.TAKEOFF in state.runs
    cursor = state.runs[EffectorTrigger.TAKEOFF]
    assert cursor.row_index == 0
    assert cursor.next_due_sim == 10.0
    assert state.fire_order == (EffectorTrigger.TAKEOFF,)


def test_fire_trigger_marks_pending_when_already_running() -> None:
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=10.0)
    state = fire_trigger(state, EffectorTrigger.TAKEOFF, now_sim=11.0)

    assert state.pending[EffectorTrigger.TAKEOFF] is True
    # The running cursor itself is untouched by the second fire.
    assert state.runs[EffectorTrigger.TAKEOFF].next_due_sim == 10.0


def test_fire_trigger_second_pending_fire_is_a_noop() -> None:
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=10.0)
    state = fire_trigger(state, EffectorTrigger.TAKEOFF, now_sim=11.0)
    again = fire_trigger(state, EffectorTrigger.TAKEOFF, now_sim=12.0)

    assert again == state


def test_different_triggers_queue_independently() -> None:
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=10.0)
    state = fire_trigger(state, EffectorTrigger.OBSERV_ON, now_sim=10.0)

    assert set(state.runs) == {EffectorTrigger.TAKEOFF, EffectorTrigger.OBSERV_ON}
    assert state.fire_order == (EffectorTrigger.TAKEOFF, EffectorTrigger.OBSERV_ON)


# --- cold takeoff: writes all four, in order, spaced ------------------------


def test_cold_takeoff_writes_four_switches_in_order_with_spacing() -> None:
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)
    readback = {"773": 0.0, "761": 0.0, "885": 0.0, "955": 0.0}

    now = 0.0
    for _ in range(4):
        state = advance(state, now, readback, _client(client), _SEQUENCES, _REGISTRY)
        now += EFFECTOR_SEQUENCE_STEP_DELAY_S

    assert client.writes == [
        (6, 3028, 1.0),
        (16, 3015, 1.0),
        (7, 3001, 1.0),
        (6, 3030, 1.0),
    ]
    assert EffectorTrigger.TAKEOFF not in state.runs
    assert state.commanded_values == {
        "missile_power": "on",
        "cplr_distr": "on",
        "sight_power": "on",
        "scho_pwr_b1": "on",
    }


# --- R12: implicit self-check -----------------------------------------------


def test_second_takeoff_with_everything_already_on_writes_nothing() -> None:
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)
    readback = {"773": 1.0, "761": 1.0, "885": 1.0, "955": 1.0}

    state = advance(state, 0.0, readback, _client(client), _SEQUENCES, _REGISTRY)

    assert client.writes == []
    assert EffectorTrigger.TAKEOFF not in state.runs
    assert state.commanded_values == {}


def test_air_start_with_switches_already_on_writes_nothing() -> None:
    """Same mechanism as the second-takeoff case -- the engine cannot
    and need not tell a warm air start apart from a repeat takeoff; the
    observed readback is all it ever looks at (R4/R5)."""
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)
    readback = {"773": 1.0, "761": 1.0, "885": 1.0, "955": 1.0}

    state = advance(state, 0.0, readback, _client(client), _SEQUENCES, _REGISTRY)

    assert client.writes == []


def test_one_switch_off_among_four_on_writes_exactly_one() -> None:
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)
    # cplr_distr (761) is the only one still off.
    readback = {"773": 1.0, "761": 0.0, "885": 1.0, "955": 1.0}

    now = 0.0
    for _ in range(4):
        state = advance(state, now, readback, _client(client), _SEQUENCES, _REGISTRY)
        now += EFFECTOR_SEQUENCE_STEP_DELAY_S

    assert client.writes == [(16, 3015, 1.0)]
    assert EffectorTrigger.TAKEOFF not in state.runs
    assert state.commanded_values == {"cplr_distr": "on"}


def test_unknown_readback_waits_then_writes_on_timeout() -> None:
    """R12: an implicit self-check whose own readback never arrives
    writes once `EFFECTOR_CONDITION_READBACK_WAIT_S` has elapsed --
    the opposite outcome from an explicit `condition`'s timeout."""
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=100.0)

    # First call: readback entirely absent, starts the wait clock.
    state = advance(state, 100.0, None, _client(client), _SEQUENCES, _REGISTRY)
    assert client.writes == []

    # Still under the wait threshold.
    state = advance(
        state,
        100.0 + EFFECTOR_CONDITION_READBACK_WAIT_S - 1.0,
        None,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == []

    # Past the threshold: writes anyway.
    state = advance(
        state,
        100.0 + EFFECTOR_CONDITION_READBACK_WAIT_S + 1.0,
        None,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == [(7, 3002, 1.0)]
    assert EffectorTrigger.OBSERV_ON not in state.runs


# --- explicit condition cells: opposite timeout outcome ----------------------


def test_explicit_condition_unknown_readback_skips_on_timeout() -> None:
    """Unlike the implicit self-check above, an explicit `condition`'s
    unknown-readback timeout *skips* the row rather than writing it
    (D3, unchanged by R12)."""
    client = _FakeAircraftClient()
    gated_sequences = dict(_SEQUENCES)
    gated_sequences[(AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.OBSERV_ON.value)] = (
        _sequence(
            EffectorTrigger.OBSERV_ON,
            (
                SwitchRow(
                    condition=Condition(effector="sight_power", op="=", value="on"),
                    effector="observ",
                    value="on",
                    petrovich_says="",
                    comment="",
                ),
            ),
        )
    )
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    # "sight_power" (885) is never present in readback -- condition stays unknown.
    readback = {"886": 0.0}

    state = advance(state, 0.0, readback, _client(client), gated_sequences, _REGISTRY)
    state = advance(
        state,
        EFFECTOR_CONDITION_READBACK_WAIT_S + 1.0,
        readback,
        _client(client),
        gated_sequences,
        _REGISTRY,
    )

    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON not in state.runs
    assert state.commanded_values == {}


def test_explicit_condition_known_false_skips_immediately_no_wait() -> None:
    client = _FakeAircraftClient()
    gated_sequences = dict(_SEQUENCES)
    gated_sequences[(AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.OBSERV_ON.value)] = (
        _sequence(
            EffectorTrigger.OBSERV_ON,
            (
                SwitchRow(
                    condition=Condition(effector="sight_power", op="=", value="on"),
                    effector="observ",
                    value="on",
                    petrovich_says="",
                    comment="",
                ),
            ),
        )
    )
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    readback = {"886": 0.0, "885": 0.0}  # sight_power is off -> condition false

    state = advance(state, 0.0, readback, _client(client), gated_sequences, _REGISTRY)

    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON not in state.runs


# --- D8: wait rows -----------------------------------------------------------


def test_wait_row_overrides_the_gap_for_one_transition() -> None:
    client = _FakeAircraftClient()
    waiting_sequences = dict(_SEQUENCES)
    waiting_sequences[(AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.TAKEOFF.value)] = (
        _sequence(
            EffectorTrigger.TAKEOFF,
            (
                SwitchRow(
                    condition=None,
                    effector="missile_power",
                    value="on",
                    petrovich_says="",
                    comment="",
                ),
                WaitRow(wait_s=3.0),
                SwitchRow(
                    condition=None,
                    effector="observ",
                    value="on",
                    petrovich_says="",
                    comment="",
                ),
            ),
        )
    )
    readback = {"773": 0.0, "886": 0.0}
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    state = advance(state, 0.0, readback, _client(client), waiting_sequences, _REGISTRY)
    assert client.writes == [(6, 3028, 1.0)]

    # The WaitRow is reached exactly at the ordinary 1s step delay (no
    # intervening poll) and sets its *own* 3s gap from there -- so the
    # second switch must not fire before t=1.0+3.0=4.0.
    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S,
        readback,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0)]

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S + 2.9,
        readback,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0)]

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S + 3.0,
        readback,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0), (7, 3002, 1.0)]


# --- D9: write-failure ordering ----------------------------------------------


def test_d9_failed_on_then_off_ends_off() -> None:
    """Fire OBSERV_ON then OBSERV_OFF. While the write to `observ`
    keeps failing, neither trigger's write lands; once writes succeed
    again, both land within the same poll, in fire order, so the state
    ends at "off" -- exactly the plan's own D9 example."""
    client = _FakeAircraftClient()
    client.fail_device_cmds.add((7, 3002))  # observ's (device, cmd)

    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    state = fire_trigger(state, EffectorTrigger.OBSERV_OFF, now_sim=0.0)
    assert state.fire_order == (EffectorTrigger.OBSERV_ON, EffectorTrigger.OBSERV_OFF)

    # Readback for "observ" (886) is never supplied -- both rows' own
    # implicit self-check is waiting on an unknown readback. The wait
    # clock starts on the first poll that actually evaluates the row
    # (here, t=0, since both triggers are due immediately), so kick it
    # off first.
    state = advance(state, 0.0, None, _client(client), _SEQUENCES, _REGISTRY)
    assert client.writes == []

    # Once the wait times out each attempts its write, and the failing
    # client blocks both this same poll.
    state = advance(
        state,
        EFFECTOR_CONDITION_READBACK_WAIT_S + 1.0,
        None,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON in state.runs
    assert EffectorTrigger.OBSERV_OFF in state.runs

    # The fault clears; next poll both ON and OFF attempt again, in fire
    # order, within the same `advance` call.
    client.fail_device_cmds.clear()
    state = advance(
        state,
        EFFECTOR_CONDITION_READBACK_WAIT_S + 2.0,
        None,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )

    assert client.writes == [(7, 3002, 1.0), (7, 3002, 0.0)]
    assert state.commanded_values["observ"] == "off"
    assert EffectorTrigger.OBSERV_ON not in state.runs
    assert EffectorTrigger.OBSERV_OFF not in state.runs


# --- D4-adjacent: pending restart re-evaluates immediately -------------------


def test_pending_restart_may_execute_the_same_poll() -> None:
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    # Re-fire while running, before it has had a chance to complete.
    state = fire_trigger(state, EffectorTrigger.OBSERV_ON, now_sim=0.0)
    assert state.pending[EffectorTrigger.OBSERV_ON] is True

    readback = {"886": 0.0}
    state = advance(state, 0.0, readback, _client(client), _SEQUENCES, _REGISTRY)

    # The first run completed (one write) and the pending re-fire
    # restarted and ran again, same poll -- observed readback has not
    # changed (this fake client doesn't feed writes back into readback),
    # so the restarted run's own self-check also proceeds to write.
    assert client.writes == [(7, 3002, 1.0), (7, 3002, 1.0)]
    assert state.pending[EffectorTrigger.OBSERV_ON] is False
    assert EffectorTrigger.OBSERV_ON not in state.runs


# --- missing sequence file ----------------------------------------------------


def test_trigger_with_no_loaded_sequence_fires_into_nothing() -> None:
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.WEAPONS_ARM, now_sim=0.0)

    state = advance(state, 0.0, None, _client(client), {}, _REGISTRY)

    assert client.writes == []
    assert EffectorTrigger.WEAPONS_ARM not in state.runs
