"""Pure-function tests for `belief.effector_engine` -- `plans/
effector-sequences/plan.md` Stage 2 (D1/D3/D4/D8/D9/R12) and Stage 4,
S4.3/S4.7 (E1-E9: the one-shot snapshot read, `assumed_writes`,
`absolute_write`). No live DCS/aircraft-layer needed -- every write and
every read goes through a fake `AircraftLayerClient` double, same
posture as `test_sight_effector.py`.

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
    """Records every cockpit-switch write and every `read_args` request.
    `read_values` is the fake's own "ground truth" (`arg -> raw value`)
    that `read_args` serves from, keyed by the real DCS arg number (an
    `int`, unlike the wire's string keys -- this fake does the string
    conversion itself, so test bodies can stay in arg-number terms).
    `fail_reads`/`fail_device_cmds` are mutated directly by a test
    between `advance` calls to simulate a failing read/write."""

    def __init__(self) -> None:
        self.writes: list[tuple[int, int, float]] = []
        self.fail_device_cmds: set[tuple[int, int]] = set()
        self.read_values: dict[int, float] = {}
        self.fail_reads = False
        self.read_calls: list[list[int]] = []

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        if (device, cmd) in self.fail_device_cmds:
            raise AircraftLayerError("simulated write failure")
        self.writes.append((device, cmd, value))

    def read_args(self, args: list[int]) -> dict[str, float]:
        self.read_calls.append(list(args))
        if self.fail_reads:
            raise AircraftLayerError("simulated read failure")
        return {str(a): self.read_values[a] for a in args if a in self.read_values}


def _client(fake: _FakeAircraftClient) -> AircraftLayerClient:
    return cast(AircraftLayerClient, fake)


_MISSILE_POWER = EffectorDef(
    name="missile_power",
    source_element="MISSILE-POWER-PTR",
    device=6,
    cmd=3028,
    arg=773,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_CPLR_DISTR = EffectorDef(
    name="cplr_distr",
    source_element="CPLR-DISTR-PTR",
    device=16,
    cmd=3015,
    arg=761,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
    unverified=True,
)
_SIGHT_POWER = EffectorDef(
    name="sight_power",
    source_element="SIGHT-POWER-PTR",
    device=7,
    cmd=3001,
    arg=885,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_SCHO_PWR_B1 = EffectorDef(
    name="scho_pwr_b1",
    source_element="SCHO-PWR-PTR",
    device=6,
    cmd=3030,
    arg=955,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_OBSERV = EffectorDef(
    name="observ",
    source_element="OBSERVE-PTR",
    device=7,
    cmd=3002,
    arg=886,
    values={"on": 1.0, "off": 0.0},
    shape="default_2_position_tumb",
)
_WEAPON_SAFETY = EffectorDef(
    name="weapon_safety",
    source_element="WEAPON-SAFETY-PTR",
    device=6,
    cmd=3020,
    arg=673,
    values={"armed": 1.0, "safe": 0.0},
    shape="default_2_position_tumb",
)
#: A non-absolute shape (anything other than `default_2_position_tumb`)
#: -- used by the "never a blind write" tests (R12's fail-safe for an
#: unconfirmed shape).
_COVERED_BUTTON = EffectorDef(
    name="covered_button",
    source_element="COVERED-BUTTON-PTR",
    device=9,
    cmd=4001,
    arg=500,
    values={"pressed": 1.0, "released": 0.0},
    shape="default_blue_cover",
)

_REGISTRY = {
    "missile_power": _MISSILE_POWER,
    "cplr_distr": _CPLR_DISTR,
    "sight_power": _SIGHT_POWER,
    "scho_pwr_b1": _SCHO_PWR_B1,
    "observ": _OBSERV,
    "weapon_safety": _WEAPON_SAFETY,
    "covered_button": _COVERED_BUTTON,
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


def _read_args_for(
    rows: tuple[object, ...], registry: dict[str, EffectorDef]
) -> frozenset[int]:
    """Mirrors `effector_sequences._compute_read_args` for hand-built
    fixtures in this file, so a fixture's `read_args` is never typed by
    hand and drifting from its own rows."""
    args: set[int] = set()
    for row in rows:
        if isinstance(row, SwitchRow):
            args.add(registry[row.effector].arg)
            if row.condition is not None:
                args.add(registry[row.condition.effector].arg)
    return frozenset(args)


def _sequence(
    trigger: EffectorTrigger,
    rows: tuple[object, ...],
    registry: dict[str, EffectorDef] = _REGISTRY,
) -> SequenceFile:
    return SequenceFile(
        aircraft=AIRCRAFT,
        petrovich_role=PETROVICH_ROLE,
        trigger=trigger.value,
        rows=rows,  # type: ignore[arg-type]
        source_path=Path("fake.md"),
        read_args=_read_args_for(rows, registry),
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
    assert cursor.snapshot is None
    assert state.fire_order == (EffectorTrigger.TAKEOFF,)


def test_fire_trigger_marks_pending_when_already_running() -> None:
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=10.0)
    state = fire_trigger(state, EffectorTrigger.TAKEOFF, now_sim=11.0)

    assert state.pending[EffectorTrigger.TAKEOFF] is True
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


# --- E1: a read succeeds -> rows run the same poll ---------------------------


def test_e1_successful_read_runs_rows_the_same_poll() -> None:
    client = _FakeAircraftClient()
    client.read_values = {773: 0.0, 761: 0.0, 885: 0.0, 955: 0.0}
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    state = advance(state, 0.0, _client(client), _SEQUENCES, _REGISTRY)

    # The first row's write lands the very same poll the read succeeded.
    assert client.writes == [(6, 3028, 1.0)]
    assert client.read_calls == [[761, 773, 885, 955]]


def test_cold_takeoff_writes_four_switches_in_order_with_spacing() -> None:
    client = _FakeAircraftClient()
    client.read_values = {773: 0.0, 761: 0.0, 885: 0.0, 955: 0.0}
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    now = 0.0
    for _ in range(4):
        state = advance(state, now, _client(client), _SEQUENCES, _REGISTRY)
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
    # Exactly one read for the whole run (E1's own "no per-tick cost").
    assert client.read_calls == [[761, 773, 885, 955]]


# --- R12: implicit self-check -----------------------------------------------


def test_second_takeoff_with_everything_already_on_writes_nothing_one_read() -> None:
    """Plan P1/(b): "second takeoff: exactly one read_args with the four
    takeoff args, zero writes, nothing spoken"."""
    client = _FakeAircraftClient()
    client.read_values = {773: 1.0, 761: 1.0, 885: 1.0, 955: 1.0}
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    state = advance(state, 0.0, _client(client), _SEQUENCES, _REGISTRY)

    assert client.writes == []
    assert EffectorTrigger.TAKEOFF not in state.runs
    assert state.commanded_values == {}
    assert client.read_calls == [[761, 773, 885, 955]]


def test_one_switch_off_among_four_on_writes_exactly_one() -> None:
    client = _FakeAircraftClient()
    client.read_values = {773: 1.0, 761: 0.0, 885: 1.0, 955: 1.0}
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    now = 0.0
    for _ in range(4):
        state = advance(state, now, _client(client), _SEQUENCES, _REGISTRY)
        now += EFFECTOR_SEQUENCE_STEP_DELAY_S

    assert client.writes == [(16, 3015, 1.0)]
    assert EffectorTrigger.TAKEOFF not in state.runs
    assert state.commanded_values == {"cplr_distr": "on"}


# --- E2: read fails then succeeds / fails >= 5s -------------------------------


def test_e2_read_fails_then_succeeds_before_timeout_writes_once_it_arrives() -> None:
    client = _FakeAircraftClient()
    client.fail_reads = True
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=100.0)

    state = advance(state, 100.0, _client(client), _SEQUENCES, _REGISTRY)
    assert client.writes == []

    state = advance(
        state,
        100.0 + EFFECTOR_CONDITION_READBACK_WAIT_S - 1.0,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON in state.runs

    client.fail_reads = False
    client.read_values = {886: 0.0}
    state = advance(
        state,
        100.0 + EFFECTOR_CONDITION_READBACK_WAIT_S - 0.5,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == [(7, 3002, 1.0)]
    assert EffectorTrigger.OBSERV_ON not in state.runs


def test_e2_implicit_self_check_writes_absolute_after_timeout() -> None:
    """A read that never succeeds: an absolute-position effector's row
    writes once `EFFECTOR_CONDITION_READBACK_WAIT_S` elapses (R12) --
    the opposite outcome from an explicit `condition`'s timeout."""
    client = _FakeAircraftClient()
    client.fail_reads = True
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=100.0)

    state = advance(state, 100.0, _client(client), _SEQUENCES, _REGISTRY)
    state = advance(
        state,
        100.0 + EFFECTOR_CONDITION_READBACK_WAIT_S - 1.0,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == []

    state = advance(
        state,
        100.0 + EFFECTOR_CONDITION_READBACK_WAIT_S + 1.0,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )
    assert client.writes == [(7, 3002, 1.0)]
    assert EffectorTrigger.OBSERV_ON not in state.runs


def test_e2_explicit_condition_unknown_readback_skips_on_timeout() -> None:
    """Unlike the implicit self-check above, an explicit `condition`'s
    unknown-readback timeout *skips* the row (D3, unchanged by R12)."""
    client = _FakeAircraftClient()
    client.fail_reads = True
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

    state = advance(state, 0.0, _client(client), gated_sequences, _REGISTRY)
    state = advance(
        state,
        EFFECTOR_CONDITION_READBACK_WAIT_S + 1.0,
        _client(client),
        gated_sequences,
        _REGISTRY,
    )

    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON not in state.runs
    assert state.commanded_values == {}


def test_e2_non_absolute_unknown_readback_skips_with_warning() -> None:
    """A non-absolute shape (`_COVERED_BUTTON`) never blind-writes on an
    unknown self-check readback, unlike an absolute one."""
    client = _FakeAircraftClient()
    client.fail_reads = True
    sequences = {
        (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.OBSERV_ON.value): _sequence(
            EffectorTrigger.OBSERV_ON,
            (
                SwitchRow(
                    condition=None,
                    effector="covered_button",
                    value="pressed",
                    petrovich_says="",
                    comment="",
                ),
            ),
        )
    }
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)

    state = advance(state, 0.0, _client(client), sequences, _REGISTRY)
    state = advance(
        state,
        EFFECTOR_CONDITION_READBACK_WAIT_S + 1.0,
        _client(client),
        sequences,
        _REGISTRY,
    )

    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON not in state.runs


def test_explicit_condition_known_false_skips_immediately_no_wait() -> None:
    client = _FakeAircraftClient()
    client.read_values = {886: 0.0, 885: 0.0}  # sight_power off -> condition false
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

    state = advance(state, 0.0, _client(client), gated_sequences, _REGISTRY)

    assert client.writes == []
    assert EffectorTrigger.OBSERV_ON not in state.runs


# --- E3: a wait row -> a second read -----------------------------------------


def test_e3_wait_row_triggers_a_second_read() -> None:
    client = _FakeAircraftClient()
    client.read_values = {773: 0.0, 886: 0.0}
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
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    state = advance(state, 0.0, _client(client), waiting_sequences, _REGISTRY)
    assert client.writes == [(6, 3028, 1.0)]
    assert client.read_calls == [[773, 886]]

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0)]  # still waiting out the WaitRow

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S + 3.0,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0), (7, 3002, 1.0)]
    # A second, independent read after the wait row.
    assert client.read_calls == [[773, 886], [773, 886]]


def test_e3_wait_row_old_snapshot_mutation_would_use_stale_state() -> None:
    """*Mutation* (plan E3): if the wait row did not reset the snapshot,
    the post-wait row would see the pre-wait reading of `observ` (0.0,
    i.e. off) rather than re-reading it -- harmless here since the
    engine never reads `observ`'s own pre-wait value for this row
    (there is no condition on it), but demonstrated via the read-call
    count: a correct implementation issues a second `read_args` call."""
    client = _FakeAircraftClient()
    client.read_values = {773: 0.0, 886: 0.0}
    waiting_sequences = {
        (AIRCRAFT, PETROVICH_ROLE, EffectorTrigger.TAKEOFF.value): _sequence(
            EffectorTrigger.TAKEOFF,
            (
                SwitchRow(
                    condition=None,
                    effector="missile_power",
                    value="on",
                    petrovich_says="",
                    comment="",
                ),
                WaitRow(wait_s=1.0),
                SwitchRow(
                    condition=None,
                    effector="observ",
                    value="on",
                    petrovich_says="",
                    comment="",
                ),
            ),
        )
    }
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)
    # t=0: first read + write; next_due_sim=1.0 (the row's own step delay).
    state = advance(state, 0.0, _client(client), waiting_sequences, _REGISTRY)
    # t=2.0: >= 1.0, so the WaitRow itself is now reached and processed
    # (resetting the snapshot, next_due_sim=2.0+1.0=3.0) -- no second
    # read yet, since the row *after* the wait has not been reached.
    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S + 1.0,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert len(client.read_calls) == 1
    # t=3.0: the wait has elapsed; the post-wait row triggers the second
    # read.
    state = advance(
        state,
        2 * EFFECTOR_SEQUENCE_STEP_DELAY_S + 1.0,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert len(client.read_calls) == 2


# --- E4: assumed_writes beats an older snapshot, loses to a newer one -------


def test_e4_assumed_write_beats_older_snapshot_same_poll() -> None:
    """Trigger A writes 886=1 and trigger B's read returns 886=0 in the
    same poll; B must see 1 (the `>=` rule, not `>`)."""
    client = _FakeAircraftClient()
    client.read_values = {886: 0.0}

    sequences = {
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
                    # A genuine cross-switch dependency on the same arg,
                    # purely to observe what B's own condition resolution
                    # saw -- not a realistic sequence, a test probe.
                    condition=Condition(effector="observ", op="=", value="on"),
                    effector="weapon_safety",
                    value="armed",
                    petrovich_says="",
                    comment="",
                ),
            ),
        ),
    }
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    state = fire_trigger(state, EffectorTrigger.OBSERV_OFF, now_sim=0.0)

    state = advance(state, 0.0, _client(client), sequences, _REGISTRY)

    # A's write landed; B's condition (observ = on) sees A's assumed
    # write, not its own stale snapshot (886=0.0) -> B's row proceeds.
    assert (6, 3028, 1.0) not in client.writes  # sanity: not a missile_power test
    assert client.writes == [(7, 3002, 1.0), (6, 3020, 1.0)]


def test_e4_per_run_assumed_writes_mutation_would_isolate_them() -> None:
    """*Mutation*: per-run (not engine-wide) `assumed_writes` -- a second
    trigger would never see the first's write, and its condition would
    read as unknown (skip) instead of satisfied. Demonstrated by the
    same fixture as the test above: a per-run implementation is
    falsified by `weapon_safety`'s row being skipped rather than
    written."""
    client = _FakeAircraftClient()
    client.read_values = {886: 0.0}
    sequences = {
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
                    condition=Condition(effector="observ", op="=", value="on"),
                    effector="weapon_safety",
                    value="armed",
                    petrovich_says="",
                    comment="",
                ),
            ),
        ),
    }
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    state = fire_trigger(state, EffectorTrigger.OBSERV_OFF, now_sim=0.0)
    state = advance(state, 0.0, _client(client), sequences, _REGISTRY)
    # The real (engine-wide) implementation writes both this poll.
    assert len(client.writes) == 2


# --- E5: a file writing the same switch twice ---------------------------------


def test_e5_file_writing_the_same_switch_on_then_off_both_write() -> None:
    client = _FakeAircraftClient()
    client.read_values = {886: 0.0}
    sequences = {
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
                SwitchRow(
                    condition=None,
                    effector="observ",
                    value="off",
                    petrovich_says="",
                    comment="",
                ),
            ),
        )
    }
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)

    state = advance(state, 0.0, _client(client), sequences, _REGISTRY)
    assert client.writes == [(7, 3002, 1.0)]

    state = advance(
        state, EFFECTOR_SEQUENCE_STEP_DELAY_S, _client(client), sequences, _REGISTRY
    )
    # The second row sees the first row's own write (1.0), not the
    # stale snapshot (0.0) -- so it correctly writes "off" rather than
    # skipping on a self-check that reads its own earlier write as the
    # ambient state (R12's "second row sees the first row's own write").
    assert client.writes == [(7, 3002, 1.0), (7, 3002, 0.0)]


# --- E6: D9, a failed write leaves assumed_writes unchanged ------------------


def test_e6_failed_write_leaves_assumed_writes_unchanged_retries_next_poll() -> None:
    client = _FakeAircraftClient()
    client.read_values = {886: 0.0}
    client.fail_device_cmds.add((7, 3002))
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)

    state = advance(state, 0.0, _client(client), _SEQUENCES, _REGISTRY)
    assert client.writes == []
    assert state.assumed_writes == {}
    assert EffectorTrigger.OBSERV_ON in state.runs

    client.fail_device_cmds.clear()
    state = advance(
        state, EFFECTOR_SEQUENCE_STEP_DELAY_S, _client(client), _SEQUENCES, _REGISTRY
    )
    assert client.writes == [(7, 3002, 1.0)]
    assert 886 in state.assumed_writes


def test_d9_failed_on_then_off_ends_off() -> None:
    """Fire OBSERV_ON then OBSERV_OFF. While the write to `observ`
    keeps failing, neither trigger's write lands; once writes succeed
    again, both land within the same poll, in fire order, so the state
    ends at "off" -- exactly the plan's own D9 example."""
    client = _FakeAircraftClient()
    client.read_values = {886: 1.0}  # on, so the self-check does not skip "on"
    client.fail_device_cmds.add((7, 3002))

    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    state = fire_trigger(state, EffectorTrigger.OBSERV_OFF, now_sim=0.0)
    assert state.fire_order == (EffectorTrigger.OBSERV_ON, EffectorTrigger.OBSERV_OFF)

    state = advance(state, 0.0, _client(client), _SEQUENCES, _REGISTRY)
    assert client.writes == []

    state = advance(
        state, EFFECTOR_SEQUENCE_STEP_DELAY_S, _client(client), _SEQUENCES, _REGISTRY
    )
    # OBSERV_ON's own self-check still reads "on" (1.0) from the fresh
    # snapshot, so it skips with no write at all; OBSERV_OFF's self-check
    # sees "on", differs, and attempts to write -- the failing client
    # blocks it.
    assert client.writes == []
    assert EffectorTrigger.OBSERV_OFF in state.runs

    client.fail_device_cmds.clear()
    state = advance(
        state,
        2 * EFFECTOR_SEQUENCE_STEP_DELAY_S,
        _client(client),
        _SEQUENCES,
        _REGISTRY,
    )

    assert client.writes == [(7, 3002, 0.0)]
    assert state.commanded_values["observ"] == "off"
    assert EffectorTrigger.OBSERV_ON not in state.runs
    assert EffectorTrigger.OBSERV_OFF not in state.runs


# --- E7: SequenceFile.read_args includes condition effectors -----------------


def test_e7_read_args_includes_condition_effector() -> None:
    rows = (
        SwitchRow(
            condition=Condition(effector="sight_power", op="=", value="on"),
            effector="observ",
            value="on",
            petrovich_says="",
            comment="",
        ),
    )
    seq = _sequence(EffectorTrigger.OBSERV_ON, rows)
    assert seq.read_args == frozenset({885, 886})


# --- E8: absolute_write is true only for default_2_position_tumb ------------


def test_e8_absolute_write_true_only_for_default_2_position_tumb() -> None:
    assert _MISSILE_POWER.absolute_write is True
    assert _COVERED_BUTTON.absolute_write is False


# --- D8: wait rows (Stage 2 regression, still true under Stage 4) ------------


def test_wait_row_overrides_the_gap_for_one_transition() -> None:
    client = _FakeAircraftClient()
    client.read_values = {773: 0.0, 886: 0.0}
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
    state = fire_trigger(EffectorRunState(), EffectorTrigger.TAKEOFF, now_sim=0.0)

    state = advance(state, 0.0, _client(client), waiting_sequences, _REGISTRY)
    assert client.writes == [(6, 3028, 1.0)]

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0)]

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S + 2.9,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0)]

    state = advance(
        state,
        EFFECTOR_SEQUENCE_STEP_DELAY_S + 3.0,
        _client(client),
        waiting_sequences,
        _REGISTRY,
    )
    assert client.writes == [(6, 3028, 1.0), (7, 3002, 1.0)]


# --- D4-adjacent: pending restart re-evaluates immediately -------------------


def test_pending_restart_may_execute_the_same_poll() -> None:
    client = _FakeAircraftClient()
    client.read_values = {886: 0.0}
    state = fire_trigger(EffectorRunState(), EffectorTrigger.OBSERV_ON, now_sim=0.0)
    state = fire_trigger(state, EffectorTrigger.OBSERV_ON, now_sim=0.0)
    assert state.pending[EffectorTrigger.OBSERV_ON] is True

    state = advance(state, 0.0, _client(client), _SEQUENCES, _REGISTRY)

    # The first run completed (one write) and the pending re-fire
    # restarted and ran again, same poll -- but its own fresh read's
    # `snapshot_sim` equals `now_sim` (both 0.0), so the first run's
    # `assumed_writes` entry (also written at sim 0.0) wins over the
    # fake client's unmoved `read_values` (`>=`, not `>`): the restarted
    # run's own self-check sees the switch already on and skips. One
    # write in total, not two -- D1's "same poll's advance may execute
    # it" plus R12's self-check plus `assumed_writes` together collapse
    # a same-poll restart into no additional write.
    assert client.writes == [(7, 3002, 1.0)]
    assert state.pending[EffectorTrigger.OBSERV_ON] is False
    assert EffectorTrigger.OBSERV_ON not in state.runs


# --- missing sequence file ----------------------------------------------------


def test_trigger_with_no_loaded_sequence_fires_into_nothing() -> None:
    client = _FakeAircraftClient()
    state = fire_trigger(EffectorRunState(), EffectorTrigger.WEAPONS_ARM, now_sim=0.0)

    state = advance(state, 0.0, _client(client), {}, _REGISTRY)

    assert client.writes == []
    assert EffectorTrigger.WEAPONS_ARM not in state.runs


# --- D11: mission reset drops assumed_writes too -----------------------------


def test_mission_reset_drops_assumed_writes() -> None:
    assert EffectorRunState().assumed_writes == {}
