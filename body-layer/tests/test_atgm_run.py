"""Tests for `belief.atgm_run` -- `[[BL-B67]]` Stage 3, `plans/
bl-b67-atgm-run/plan.md`. Table-driven over the plan's own state diagram,
against synthetic `AtgmInputs` -- no DCS, no aircraft-layer, no effector
engine. See that module's own docstring for why `decide` is pure and why
`actions` never carries `say`.

Sections mirror the plan's own Stage 3 test list: range calls, launch/
impact, failure paths (`FailedLaunch`/count-drop), selection (Preparing's
first pick and Resetting's post-impact resolution), the backstop (N1),
and `family_of`/the launch-line rendering. `hold_routine`'s own tests
(the in-flight silence mechanism) live in `test_callouts.py`, where the
mechanism itself lives."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from belief.atgm_run import (
    ATAKA_MAX_RANGE_M,
    ATAKA_SPEED_MPS,
    ATGM_MAX_FLIGHT_S,
    ATGM_MIN_RANGE_M,
    ATGM_UNCONFIRMED_DROP_GRACE_S,
    SHTURM_MAX_RANGE_M,
    SHTURM_SPEED_MPS,
    AtgmInputs,
    AtgmPhase,
    AtgmRunState,
    FailedLaunch,
    Fire,
    LaunchEvent,
    SelectStation,
    decide,
    family_of,
)


def _inputs(
    *,
    now_sim: float,
    observ_observed: bool = True,
    belief_range_m: float | None = None,
    station_counts: Mapping[int, int] | None = None,
    selected_station_type_name: str | None = None,
    launch: LaunchEvent | None = None,
    failed_launch: FailedLaunch | None = None,
    missile_gone: bool = False,
    own_feed_fresh: bool = True,
    impact_sequence_running: bool = False,
) -> AtgmInputs:
    return AtgmInputs(
        now_sim=now_sim,
        observ_observed=observ_observed,
        belief_range_m=belief_range_m,
        station_counts=station_counts if station_counts is not None else {},
        selected_station_type_name=selected_station_type_name,
        launch=launch,
        failed_launch=failed_launch,
        missile_gone=missile_gone,
        own_feed_fresh=own_feed_fresh,
        impact_sequence_running=impact_sequence_running,
    )


def _tracking_state(**overrides: object) -> AtgmRunState:
    """A `Tracking` state already past Preparing's own first selection --
    station 1 selected, holding 2 rounds, no range calls spoken yet."""
    defaults: dict[str, object] = {
        "contact_id": "CONTACT_1",
        "phase": AtgmPhase.TRACKING,
        "selected_step": 1,
        "selected_step_count_last_seen": 2,
    }
    defaults.update(overrides)
    return AtgmRunState(**defaults)  # type: ignore[arg-type]


# -- Range calls (round 7, decision 1) -----------------------------------


def test_run_starting_out_of_range_says_out_then_in_range_once() -> None:
    state = _tracking_state()
    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=SHTURM_MAX_RANGE_M + 1.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
        ),
    )
    assert [s.text for s in speech] == ["Out of range."]
    assert actions == ()
    assert state.range_out_called is True
    assert state.in_range_call_pending is True
    assert state.range_calls_done is False

    # Still beyond max -- no repeat, no change.
    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=1.0,
            belief_range_m=SHTURM_MAX_RANGE_M + 1.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
        ),
    )
    assert speech == ()

    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=2.0,
            belief_range_m=SHTURM_MAX_RANGE_M - 1.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
        ),
    )
    assert [s.text for s in speech] == ["In range."]
    assert state.in_range_call_pending is False
    assert state.range_calls_done is True

    # Once done, stays done -- no repeat even if range opens back up.
    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=3.0,
            belief_range_m=SHTURM_MAX_RANGE_M + 1.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
        ),
    )
    assert speech == ()
    assert state.range_calls_done is True


def test_run_starting_in_range_says_neither() -> None:
    state = _tracking_state()
    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=SHTURM_MAX_RANGE_M - 100.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
        ),
    )
    assert speech == ()
    assert state.range_calls_done is True
    assert state.range_out_called is False
    assert state.in_range_call_pending is False


def test_pending_run_jumping_straight_to_inside_min_range_says_neither() -> None:
    """A pending run (already said "Out of range.") whose `belief_range_m`
    jumps, in a single poll, from beyond max range straight to below
    `ATGM_MIN_RANGE_M` -- the edge case the plan's own "Inside 400 m says
    nothing" (round 3, "just track") covers even though the max-bound
    latch alone would otherwise speak "In range." as a side effect of
    crossing it on the way through. The run still settles
    (`range_calls_done`), it just says nothing on the settling poll."""
    state = _tracking_state(range_out_called=True, in_range_call_pending=True)
    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=5.0,
            belief_range_m=ATGM_MIN_RANGE_M - 50.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
        ),
    )
    assert speech == ()
    assert state.in_range_call_pending is False
    assert state.range_calls_done is True


def test_second_missile_in_the_same_run_says_neither_range_call() -> None:
    """Once `range_calls_done`, a later missile's own launch -- and every
    poll after it -- never re-triggers either call, even though the
    in-flight `_maybe_range_call` branch runs again every Tracking tick
    after the reset."""
    state = _tracking_state(range_calls_done=True)
    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=10.0,
            belief_range_m=SHTURM_MAX_RANGE_M + 1.0,
            station_counts={1: 2},
            selected_station_type_name="shturm",
            launch=LaunchEvent(t_sim=10.0, type_name="shturm"),
        ),
    )
    # Only the launch line -- no range call text at all.
    assert [s.text for s in speech] == ["Shturm, 14 seconds."]
    assert state.range_calls_done is True


def test_a_fresh_atgm_run_state_has_untouched_range_latches() -> None:
    """The re-point reset itself is `body.py`'s job (a fresh
    `AtgmRunState(contact_id=...)` construction, same as Stage 1's
    existing engage-apply block) -- `decide` never mutates `contact_id`
    and has nothing of its own to reset. This pins the one thing `decide`
    *can* promise: a freshly-constructed state's latches are all at their
    dataclass defaults, so a caller that does construct fresh on re-point
    gets "resets the latches" for free, with no extra code in this
    module."""
    fresh = AtgmRunState(contact_id="CONTACT_2")
    assert fresh.range_out_called is False
    assert fresh.in_range_call_pending is False
    assert fresh.range_calls_done is False
    assert fresh.phase is AtgmPhase.PREPARING


# -- Launch and impact ----------------------------------------------------


def test_launch_while_out_of_range_says_only_the_launch_line() -> None:
    """Range calls already resolved earlier in the run (`range_calls_
    done=True`) -- the ordinary case, since range/family are known long
    before the pilot fires. A launch landing while the target has since
    drifted back out of range speaks only the launch line."""
    state = _tracking_state(range_calls_done=True)
    _state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=5.0,
            belief_range_m=SHTURM_MAX_RANGE_M + 500.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=5.0, type_name="shturm"),
        ),
    )
    assert len(speech) == 1
    assert speech[0].text.startswith("Shturm")


def test_launch_inside_min_range_says_only_the_launch_line() -> None:
    state = _tracking_state(range_calls_done=True)
    _state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=5.0,
            belief_range_m=ATGM_MIN_RANGE_M - 50.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=5.0, type_name="shturm"),
        ),
    )
    assert len(speech) == 1
    assert speech[0].text.startswith("Shturm")


def test_second_launch_while_in_flight_rebases_to_the_newest_missile() -> None:
    state = _tracking_state(range_calls_done=True)
    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=2000.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="shturm"),
        ),
    )
    assert state.phase is AtgmPhase.IN_FLIGHT
    assert state.in_flight_since_sim == 0.0
    assert state.tracked_family == "shturm"

    # A second `LaunchEvent` lands while the first is still flying -- the
    # newest is tracked (rebased), silently.
    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=3.0,
            belief_range_m=2000.0,
            station_counts={1: 0},
            launch=LaunchEvent(t_sim=3.0, type_name="ataka"),
        ),
    )
    assert speech == ()
    assert actions == ()
    assert state.phase is AtgmPhase.IN_FLIGHT
    assert state.in_flight_since_sim == 3.0
    assert state.tracked_family == "ataka"


def test_launch_and_gone_in_the_same_poll_give_both_lines_in_order() -> None:
    state = _tracking_state(range_calls_done=True)
    _state, speech, actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=SHTURM_SPEED_MPS * 1.0,  # ~1 second flight
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="shturm"),
            missile_gone=True,
        ),
    )
    assert [s.text for s in speech] == ["Shturm, 1 second.", "Impact."]
    assert actions == (Fire("atgm-impact"),)


# -- Failure paths ----------------------------------------------------------


def test_failed_launch_gives_no_speech_no_state_change_and_no_reset() -> None:
    state = _tracking_state(range_calls_done=True)
    with_failed = decide(
        state,
        _inputs(
            now_sim=5.0,
            belief_range_m=2000.0,
            station_counts={1: 2},
            failed_launch=FailedLaunch(t_sim=5.0, type_name="shturm"),
        ),
    )
    without_failed = decide(
        state,
        _inputs(now_sim=5.0, belief_range_m=2000.0, station_counts={1: 2}),
    )
    assert with_failed == without_failed
    assert with_failed[0] == state
    assert with_failed[1] == ()
    assert with_failed[2] == ()


def test_count_drop_followed_by_launch_inside_the_grace_window_gives_no_selection_before_the_launch() -> (
    None
):
    state = _tracking_state(selected_step_count_last_seen=2)
    # Count drops this poll (2 -> 1), no launch yet.
    state, speech, actions = decide(state, _inputs(now_sim=0.0, station_counts={1: 1}))
    assert speech == ()
    assert actions == ()
    assert state.unconfirmed_drop_since_sim == 0.0
    assert state.phase is AtgmPhase.TRACKING
    assert state.selected_step == 1

    # The launch's own confirmation arrives inside the grace window --
    # no selection (no `SelectStation`) happens before it.
    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=ATGM_UNCONFIRMED_DROP_GRACE_S - 0.1,
            belief_range_m=2000.0,
            station_counts={1: 0},
            launch=LaunchEvent(t_sim=ATGM_UNCONFIRMED_DROP_GRACE_S - 0.1),
        ),
    )
    assert actions == ()
    assert state.phase is AtgmPhase.IN_FLIGHT
    assert state.unconfirmed_drop_since_sim is None


def test_count_drop_with_no_launch_emptying_the_last_station_gives_no_more_missiles() -> (
    None
):
    state = _tracking_state(selected_step_count_last_seen=1)
    state, speech, actions = decide(state, _inputs(now_sim=0.0, station_counts={1: 0}))
    assert speech == ()
    assert state.unconfirmed_drop_since_sim == 0.0

    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=ATGM_UNCONFIRMED_DROP_GRACE_S,
            station_counts={1: 0},
        ),
    )
    assert [s.text for s in speech] == ["No more missiles."]
    assert actions == ()
    assert state.phase is AtgmPhase.EMPTY
    assert state.selected_step is None
    assert state.unconfirmed_drop_since_sim is None


def test_count_drop_with_no_launch_but_another_loaded_station_is_selected_silently() -> (
    None
):
    state = _tracking_state(selected_step_count_last_seen=1)
    state, _speech, _actions = decide(
        state, _inputs(now_sim=0.0, station_counts={1: 0, 2: 3})
    )
    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=ATGM_UNCONFIRMED_DROP_GRACE_S,
            station_counts={1: 0, 2: 3},
        ),
    )
    assert speech == ()  # silent station switch -- no words
    assert actions == (SelectStation(2),)
    assert state.selected_step == 2
    assert state.selected_step_count_last_seen == 3
    assert state.phase is AtgmPhase.TRACKING


def test_count_drop_that_does_not_empty_the_station_clears_the_timer_and_stays() -> (
    None
):
    """E.g. a two-round station dropping to one -- logged, but nothing
    else changes: no selection, same station."""
    state = _tracking_state(selected_step_count_last_seen=3)
    state, _speech, _actions = decide(
        state, _inputs(now_sim=0.0, station_counts={1: 2})
    )
    state, speech, actions = decide(
        state,
        _inputs(now_sim=ATGM_UNCONFIRMED_DROP_GRACE_S, station_counts={1: 2}),
    )
    assert speech == ()
    assert actions == ()
    assert state.selected_step == 1
    assert state.selected_step_count_last_seen == 2
    assert state.unconfirmed_drop_since_sim is None


# -- Backstop (Decision N1) ------------------------------------------------


def test_backstop_leaves_in_flight_silently_after_max_flight_time() -> None:
    state = _tracking_state(range_calls_done=True)
    state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=2000.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="shturm"),
        ),
    )
    assert state.phase is AtgmPhase.IN_FLIGHT

    state, speech, actions = decide(
        state,
        _inputs(now_sim=ATGM_MAX_FLIGHT_S, station_counts={1: 0}),
    )
    assert speech == ()  # silent -- Decision N1
    assert actions == (Fire("atgm-impact"),)
    assert state.phase is AtgmPhase.RESETTING
    assert state.in_flight_since_sim is None


def test_in_flight_stays_in_flight_before_the_backstop_elapses() -> None:
    state = AtgmRunState(
        contact_id="CONTACT_1", phase=AtgmPhase.IN_FLIGHT, in_flight_since_sim=0.0
    )
    state, speech, actions = decide(
        state,
        _inputs(now_sim=ATGM_MAX_FLIGHT_S - 1.0, station_counts={1: 0}),
    )
    assert speech == ()
    assert actions == ()
    assert state.phase is AtgmPhase.IN_FLIGHT


# -- Selection: Preparing's first pick -------------------------------------


def test_preparing_waits_silently_until_observ_observed() -> None:
    state = AtgmRunState(contact_id="CONTACT_1")
    state, speech, actions = decide(
        state, _inputs(now_sim=0.0, observ_observed=False, station_counts={1: 2})
    )
    assert speech == ()
    assert actions == ()
    assert state.phase is AtgmPhase.PREPARING


def test_preparing_selects_the_first_loaded_station_once_observed() -> None:
    state = AtgmRunState(contact_id="CONTACT_1")
    state, speech, actions = decide(
        state, _inputs(now_sim=0.0, observ_observed=True, station_counts={2: 1, 4: 3})
    )
    assert speech == ()
    assert actions == (SelectStation(2),)
    assert state.phase is AtgmPhase.TRACKING
    assert state.selected_step == 2
    assert state.selected_step_count_last_seen == 1


def test_preparing_with_no_atgm_loaded_says_no_more_missiles() -> None:
    state = AtgmRunState(contact_id="CONTACT_1")
    state, speech, actions = decide(
        state, _inputs(now_sim=0.0, observ_observed=True, station_counts={1: 0})
    )
    assert [s.text for s in speech] == ["No more missiles."]
    assert actions == ()
    assert state.phase is AtgmPhase.EMPTY


def test_empty_phase_is_a_steady_no_op() -> None:
    state = AtgmRunState(contact_id="CONTACT_1", phase=AtgmPhase.EMPTY)
    state, speech, actions = decide(
        state, _inputs(now_sim=100.0, observ_observed=True, station_counts={1: 5})
    )
    assert speech == ()
    assert actions == ()
    assert state.phase is AtgmPhase.EMPTY


# -- Resetting -> Selecting -> Tracking/Empty ------------------------------


def test_resetting_waits_for_the_impact_sequence_to_finish() -> None:
    state = AtgmRunState(
        contact_id="CONTACT_1", phase=AtgmPhase.RESETTING, selected_step=1
    )
    state, speech, actions = decide(
        state,
        _inputs(now_sim=0.0, station_counts={1: 1}, impact_sequence_running=True),
    )
    assert speech == ()
    assert actions == ()
    assert state.phase is AtgmPhase.RESETTING


def test_resetting_stays_on_the_selected_station_if_still_loaded() -> None:
    state = AtgmRunState(
        contact_id="CONTACT_1", phase=AtgmPhase.RESETTING, selected_step=1
    )
    state, speech, actions = decide(
        state,
        _inputs(now_sim=0.0, station_counts={1: 1}, impact_sequence_running=False),
    )
    assert speech == ()
    assert actions == ()  # same station -- no write needed
    assert state.phase is AtgmPhase.TRACKING
    assert state.selected_step == 1
    assert state.selected_step_count_last_seen == 1


def test_resetting_resolves_to_the_next_loaded_station_and_selects_it() -> None:
    state = AtgmRunState(
        contact_id="CONTACT_1", phase=AtgmPhase.RESETTING, selected_step=1
    )
    state, speech, actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            station_counts={1: 0, 3: 2},
            impact_sequence_running=False,
        ),
    )
    assert speech == ()
    assert actions == (SelectStation(3),)
    assert state.phase is AtgmPhase.TRACKING
    assert state.selected_step == 3


def test_resetting_with_nothing_loaded_says_no_more_missiles() -> None:
    state = AtgmRunState(
        contact_id="CONTACT_1", phase=AtgmPhase.RESETTING, selected_step=1
    )
    state, speech, actions = decide(
        state,
        _inputs(now_sim=0.0, station_counts={1: 0}, impact_sequence_running=False),
    )
    assert [s.text for s in speech] == ["No more missiles."]
    assert actions == ()
    assert state.phase is AtgmPhase.EMPTY
    assert state.selected_step is None


# -- `family_of` -----------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Shturm", "shturm"),
        ("9M114", "shturm"),
        ("ataka", "ataka"),
        ("9M120", "ataka"),
        (None, None),
        ("unknown_store", None),
        ("S-8KOM", None),
    ],
)
def test_family_of(name: str | None, expected: str | None) -> None:
    assert family_of(name) == expected


def test_family_of_is_case_insensitive() -> None:
    assert family_of("SHTURM") == "shturm"
    assert family_of("Ataka-V") == "ataka"


# -- The launch line --------------------------------------------------------


def test_launch_line_unknown_family_says_missile_with_no_time() -> None:
    state = _tracking_state(range_calls_done=True)
    _state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=2000.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="some_unknown_type"),
        ),
    )
    assert [s.text for s in speech] == ["Missile."]


def test_launch_line_unknown_range_says_missile_with_no_time() -> None:
    state = _tracking_state(range_calls_done=True)
    _state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=None,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="shturm"),
        ),
    )
    assert [s.text for s in speech] == ["Missile."]


def test_launch_line_speaks_the_singular_one_second() -> None:
    state = _tracking_state(range_calls_done=True)
    _state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=SHTURM_SPEED_MPS * 1.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="shturm"),
        ),
    )
    assert [s.text for s in speech] == ["Shturm, 1 second."]


def test_launch_line_speaks_the_plural_for_every_other_count() -> None:
    state = _tracking_state(range_calls_done=True)
    _state, speech, _actions = decide(
        state,
        _inputs(
            now_sim=0.0,
            belief_range_m=ATAKA_SPEED_MPS * 2.0,
            station_counts={1: 1},
            launch=LaunchEvent(t_sim=0.0, type_name="ataka"),
        ),
    )
    assert [s.text for s in speech] == ["Ataka, 2 seconds."]


# -- Tunables ---------------------------------------------------------------


def test_the_two_families_own_speed_and_range_figures_are_the_wikipedia_values() -> (
    None
):
    """Round 1: *"missile speeds, leave it, Wikipedia is good enough
    approximation"* -- pinned so a future calibration commit changing
    these is a visible, reviewed diff rather than a silent drift."""
    assert SHTURM_SPEED_MPS == 345.0
    assert SHTURM_MAX_RANGE_M == 5000.0
    assert ATAKA_SPEED_MPS == 400.0
    assert ATAKA_MAX_RANGE_M == 6000.0
    assert ATGM_MIN_RANGE_M == 400.0
