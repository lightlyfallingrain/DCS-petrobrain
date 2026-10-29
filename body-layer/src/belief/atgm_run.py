"""The ATGM run's own per-poll state and "when" (`[[BL-B67]]`,
`plans/bl-b67-atgm-run/plan.md`). Stage 1 built the run skeleton that ties
the run's lifecycle to `belief.attack_run.AttackRunState` (`body.py`'s one
construction site, the engage-apply block). **Stage 3 adds the "when"
itself** -- `decide`, the state machine (Preparing -> Tracking -> InFlight
-> Resetting -> Selecting -> Tracking/Empty), the range latches, the
missile-family profiles, and the in-flight hold's own trigger (`belief.
callouts.CalloutScheduler.tick`'s `hold_routine` keyword lives in that
module, not here -- see its docstring).

**Pure function plus one frozen dataclass; no I/O**, modelled on `belief.
attack_run.decide`/`belief.optic_policy.decide`: `decide(state, inputs) ->
(new_state, speech, actions)`. `speech` is a tuple because one poll can
carry two lines in order (a missile whose flight ends the same poll it
launches: *"Shturm, 1 second."* then *"Impact."*). `actions` is `Fire`/
`SelectStation` only -- `say` is not an action here, it is the `speech`
tuple, matching `attack_run.decide`'s own `(state, speech)` shape rather
than root `CLAUDE.md`'s "Behaviour as actions and params" table taken
over-literally; that table names `say(text)` as a *kind* of thing this
run does, not a instruction that every "when" function must route speech
through its own `actions` return. `body.py`'s poll loop (Stage 7) is the
executor for both: `fire`/`select_station` through `effector_engine`,
`say` through the existing `CrewConsole._print`/scheduler path.

**Against synthetic events, by design** (Stage 3's own scope). Nothing in
this module imports `perception.own_weapons` (Stage 5, not built) or
`effector_sequences.EffectorTrigger` (Stage 6's own new members,
`ATGM_IMPACT`/`ATGM_RUN_END`, not added yet) -- `LaunchEvent`/
`FailedLaunch` are declared here as the input shape Stage 5's real
`OwnWeaponTracker` will eventually produce (plan: `OwnWeaponEvents(launch,
failed_launch, missile_gone, own_feed_fresh, t_sim)`), and `Fire.trigger`
is a plain string (`"atgm-impact"`) rather than the not-yet-existing enum
member, so this module has nothing to import from either future stage.
Stage 6/7 wire the real producer and the real trigger enum in; this
module's own shape does not change when they do.

A companion state beside `runner.attack_run_state`, never a replacement
and never a field on `AttackRunState`: that state is reset wholesale on
every re-point (`attack_run.py`'s `decide`, "Resets `state` to fresh the
moment `contact.id` differs from `state.last_contact_id`"), which would
silently drop a weapon field -- the recurring stale-state shape,
`.claude/agent-memory/dod/project_recurring_stale_state_on_transition.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Final

import tuning
from belief.speech import (
    OutgoingSpeech,
    render_atgm_launch,
    render_impact,
    render_no_more_missiles,
    render_range_state,
)

#: Shturm (9M114) cruise speed -- Wikipedia figure, round 1's own *"missile
#: speeds, leave it, Wikipedia is good enough approximation"* -- used only
#: to turn a believed range into the launch-line flight-time word
#: (`"Shturm, N seconds."`). Not re-derived from `db_weapons*.lua`, per the
#: same round's explicit supersession of the entry's earlier caution.
SHTURM_SPEED_MPS: Final[float] = tuning.real(
    "belief.atgm_run.SHTURM_SPEED_MPS", 345.0, lo=200.0, hi=500.0, status="agreed-guess"
)
#: Shturm's own max engagement range -- same Wikipedia source, the family
#: profile's `_FAMILY_MAX_RANGE_M` entry the range calls compare belief
#: range against.
SHTURM_MAX_RANGE_M: Final[float] = tuning.real(
    "belief.atgm_run.SHTURM_MAX_RANGE_M",
    5000.0,
    lo=1000.0,
    hi=8000.0,
    status="agreed-guess",
)
#: Ataka (9M120) cruise speed -- same source and caveat as `SHTURM_
#: SPEED_MPS`.
ATAKA_SPEED_MPS: Final[float] = tuning.real(
    "belief.atgm_run.ATAKA_SPEED_MPS", 400.0, lo=200.0, hi=600.0, status="agreed-guess"
)
#: Ataka's own max engagement range -- same source and caveat as `SHTURM_
#: MAX_RANGE_M`.
ATAKA_MAX_RANGE_M: Final[float] = tuning.real(
    "belief.atgm_run.ATAKA_MAX_RANGE_M",
    6000.0,
    lo=1000.0,
    hi=10000.0,
    status="agreed-guess",
)
#: The shared minimum range below which the range calls say nothing at all
#: (round 3: *"just track"*) -- one constant, not per-family, since both
#: families share the same 400 m figure.
ATGM_MIN_RANGE_M: Final[float] = tuning.real(
    "belief.atgm_run.ATGM_MIN_RANGE_M", 400.0, lo=0.0, hi=2000.0, status="agreed-guess"
)
#: How long Tracking waits, after the selected station's payload count
#: falls with no `LaunchEvent` to explain it, before treating the drop as
#: a jettison/failed launch rather than a shot still leaving the rail --
#: the payload feed and the Hook's firing-events drain reach body-layer by
#: different paths at different times, so a launch that really did happen
#: can still show up a poll or two after its own count drop. Unmeasured; a
#: stated guess, not a probe result (round 8 did not require probing it).
ATGM_UNCONFIRMED_DROP_GRACE_S: Final[float] = tuning.real(
    "belief.atgm_run.ATGM_UNCONFIRMED_DROP_GRACE_S",
    3.0,
    lo=0.5,
    hi=10.0,
    status="judgement",
)
#: The backstop: how long InFlight waits for a confirmed launch's `missile_
#: gone` before giving up silently (Decision N1, round 8: *"after 25 s
#: leave the flight silently... log an error"*). Derived from the slower
#: family's own max range/speed (Ataka: 6,000 m / 400 m/s = 15 s) plus
#: margin, not measured -- by 25 s the missile is physically gone
#: regardless of what the feed says.
ATGM_MAX_FLIGHT_S: Final[float] = tuning.real(
    "belief.atgm_run.ATGM_MAX_FLIGHT_S", 25.0, lo=10.0, hi=60.0, status="derived"
)

#: Family name -> cruise speed, keyed by `family_of`'s own two return
#: values. One dict rather than a per-family `if`, so a third family
#: later is one line here and one line in `_FAMILY_MAX_RANGE_M`, not a
#: third `if` branch threaded through every caller.
_FAMILY_SPEED_MPS: Final[Mapping[str, float]] = {
    "shturm": SHTURM_SPEED_MPS,
    "ataka": ATAKA_SPEED_MPS,
}
#: Family name -> max engagement range, same shape and reason as `_FAMILY_
#: SPEED_MPS`.
_FAMILY_MAX_RANGE_M: Final[Mapping[str, float]] = {
    "shturm": SHTURM_MAX_RANGE_M,
    "ataka": ATAKA_MAX_RANGE_M,
}
#: Loose, case-insensitive substring hints `family_of` matches against --
#: a stand-in for `atgm.toml`'s own DCS-store-name-confirmed table (Stage
#: 5/6, Q1/Q6), which supersedes this once Stage 0's sortie answers the
#: real store/type names. Until then this is every caller's best guess,
#: covering both the plain family word and the DCS missile designation.
_FAMILY_NAME_HINTS: Final[Mapping[str, str]] = {
    "shturm": "shturm",
    "9m114": "shturm",
    "ataka": "ataka",
    "9m120": "ataka",
}


def family_of(type_or_store_name: str | None) -> str | None:
    """`"shturm"` / `"ataka"` / `None` -- the one place this module turns
    a raw DCS type/store name into a family. `None` in (unknown station,
    or a store name that matches neither hint) gives `None` out, never a
    guess: the launch line's own "no invented number" rule (Stage 3 task
    list) depends on this function being honest about not knowing."""
    if type_or_store_name is None:
        return None
    lowered = type_or_store_name.lower()
    for hint, family in _FAMILY_NAME_HINTS.items():
        if hint in lowered:
            return family
    return None


class AtgmPhase(str, Enum):
    """Where the run is, mirroring the plan's own `stateDiagram-v2`
    exactly (`Refused` is not a member here -- it is spoken and the run
    never starts, so no `AtgmRunState` is ever constructed for it,
    `belief.crew_console._handle_engage`'s own gate, Stage 1)."""

    PREPARING = "preparing"
    TRACKING = "tracking"
    IN_FLIGHT = "in_flight"
    RESETTING = "resetting"
    #: Reachable only *within* one `decide` call -- see `decide`'s own
    #: docstring on why `AtgmRunState.phase` never holds this value once
    #: `decide` returns. Kept as a named phase (rather than inlined) for
    #: the one-to-one match with the plan's own diagram, which a future
    #: reader will have open beside this file.
    SELECTING = "selecting"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class LaunchEvent:
    """One confirmed launch (`S_EVENT_SHOT`, ours, a guided weapon object
    that exists) -- Stage 5's real shape (`perception.own_weapons.
    OwnWeaponTracker`) will carry more than this; `decide` only ever reads
    `type_name`. `None` means the event arrived with no identifiable
    type -- `family_of(None)` is `None`, so the launch line falls back to
    `"Missile."` rather than inventing a family."""

    t_sim: float
    type_name: str | None = None


@dataclass(frozen=True, slots=True)
class FailedLaunch:
    """A `S_EVENT_SHOT` for us with no weapon object (round 7, decision 4:
    *"that's probably failed launch then. Log it and treat as not
    launched."*). `decide` does not even branch on this field -- "treat as
    not launched" means the state machine does nothing with it at all; the
    caller (`body.py`, Stage 7) logs the raw event directly to the sight
    trace/belief-truth log, never through `decide`'s return. Carried on
    `AtgmInputs` only so Stage 5's producer and this module agree on the
    shape before either Stage 7 or the perception tracker exists."""

    t_sim: float
    type_name: str | None = None


@dataclass(frozen=True, slots=True)
class Fire:
    """Start an effector sequence run (`belief.effector_engine.
    fire_trigger`) -- `trigger` is a plain string, not `effector_
    sequences.EffectorTrigger`, because Stage 6 has not added `"atgm-
    impact"`/`"atgm-run-end"` to that enum yet (see module docstring).
    Stage 7 maps this string onto the real enum member once it exists;
    until then this is a complete, typed description of what should
    happen, just not yet wired to anything that executes it."""

    trigger: str


@dataclass(frozen=True, slots=True)
class SelectStation:
    """Turn the pylon-select knob to `step` (`belief.effector_engine.
    write_effector`, Stage 6) -- `step` is the knob position (1-8, per
    `switch-reference.md`'s `SHSCHO-KNOB-PTR` row), never the payload
    array index directly; whether the two coincide is Stage 0's own open
    question (Q3), not this module's problem."""

    step: int


#: `decide`'s own action union -- `Fire`/`SelectStation` only. `say` is
#: not a member (module docstring).
AtgmAction = Fire | SelectStation


@dataclass(frozen=True, slots=True)
class AtgmInputs:
    """One poll's worth of inputs to `decide`, synthetic for Stage 3 --
    nothing here is read from a live DCS feed yet; Stage 4/5/6/7 wire real
    producers in behind these same names, unchanged.

    `station_counts` is step -> ATGM count on that station, the knob-step
    keying `_resolve_station_selection`/the Preparing/Resetting/Tracking
    branches all share. `selected_station_type_name` is the *currently
    selected* station's store/type name, read only while no missile has
    launched yet this run (`_current_family` prefers `AtgmRunState.
    tracked_family`, set from `LaunchEvent.type_name` at the moment of
    launch, the instant one exists) -- this is the "else the selected
    station's store name" half of the plan's own `missile_family` state
    param.

    `launch`/`failed_launch`/`missile_gone` are this poll's own events,
    `None`/`False` when nothing happened. `own_feed_fresh` is carried for
    Stage 5's eventual producer and for completeness against the plan's
    own state-param list, but Stage 3's backstop (`_in_flight_tick`)
    deliberately does **not** consult it -- round 8, N1's own wording is
    *"after 25 s leave the flight silently... by 25 s the missile is
    physically gone, whatever the feed says"* -- the flight-elapsed timer
    alone is the backstop's one trigger, both for "the Hook stopped
    reporting" and for "the flight genuinely ran long"; a separate feed-
    staleness trigger would fire earlier than the user's own 25 s figure
    for the first cause and is not asked for.

    `impact_sequence_running` mirrors `EffectorRunState.runs` holding
    `"atgm-impact"` (Stage 6) -- `True` while the wait(1s)+reset press/
    release sequence is still in progress; Resetting waits on it rather
    than on a fixed delay of its own, so a slow/retried effector write
    never races the knob being turned before the reset actually landed."""

    now_sim: float
    observ_observed: bool
    belief_range_m: float | None
    station_counts: Mapping[int, int]
    selected_station_type_name: str | None = None
    launch: LaunchEvent | None = None
    failed_launch: FailedLaunch | None = None
    missile_gone: bool = False
    own_feed_fresh: bool = True
    impact_sequence_running: bool = False


@dataclass(frozen=True, slots=True)
class AtgmRunState:
    """The ATGM run's own state, carried on `body.ConsolePerceptionRunner`
    beside `attack_run_state` -- replaced wholesale each poll, never
    mutated, the same replay-determinism discipline every other state on
    that class already follows. `None` on the runner means "no ATGM run
    engaged" -- the same convention `attack_run_state` itself uses.

    `phase` is never observed as `AtgmPhase.SELECTING` once `decide`
    returns -- see that enum member's own docstring. `selected_step_
    count_last_seen` is `Tracking`'s own fall-detection baseline (the
    poll-to-poll comparison that arms `unconfirmed_drop_since_sim`), kept
    separate from `station_counts` itself (which lives on `AtgmInputs`,
    not here, since it is this poll's fresh reading, not something to
    remember)."""

    contact_id: str
    phase: AtgmPhase = AtgmPhase.PREPARING
    selected_step: int | None = None
    selected_step_count_last_seen: int | None = None
    in_flight_since_sim: float | None = None
    tracked_family: str | None = None
    range_out_called: bool = False
    in_range_call_pending: bool = False
    range_calls_done: bool = False
    unconfirmed_drop_since_sim: float | None = None


def _resolve_station_selection(
    selected_step: int | None, station_counts: Mapping[int, int]
) -> int | None:
    """Stay on `selected_step` while it still holds an ATGM; otherwise the
    next loaded step after it, cyclic by ascending step number; `None`
    (no loaded station at all) if none remain. `selected_step=None` (the
    run's first-ever selection, Preparing's own call) behaves as "pick the
    lowest loaded step" -- there is nothing to stay on yet."""
    loaded = sorted(step for step, count in station_counts.items() if count > 0)
    if not loaded:
        return None
    if selected_step is not None and selected_step in loaded:
        return selected_step
    if selected_step is None:
        return loaded[0]
    for step in loaded:
        if step > selected_step:
            return step
    return loaded[0]


def _current_family(state: AtgmRunState, inputs: AtgmInputs) -> str | None:
    """The plan's own `missile_family` state param: the launch event's
    type name once one exists (`state.tracked_family`, set at the
    Preparing/Tracking -> InFlight transition and never cleared mid-run),
    else the selected station's store name, resolved fresh every poll
    (the pilot can re-select a different loaded station before firing,
    so this must not cache)."""
    if state.tracked_family is not None:
        return state.tracked_family
    return family_of(inputs.selected_station_type_name)


def _maybe_range_call(
    state: AtgmRunState, inputs: AtgmInputs
) -> tuple[AtgmRunState, OutgoingSpeech | None]:
    """Round 7's range-call rule, "per run": the first poll `belief_range_
    m` and the family are both known decides everything -- beyond the
    family's max range says "Out of range." once and arms `in_range_call_
    pending`; within it says nothing and the run is immediately `range_
    calls_done` (never spoke "In range." because it never needed to). A
    pending run's own first poll back at or inside max range says "In
    range." once. Both latches are one-way: once `range_calls_done` is
    `True` it stays `True` for the rest of the run, including every later
    missile (`AtgmRunState`'s own docstring; Co-moving Fields table)."""
    if state.range_calls_done:
        return state, None
    family = _current_family(state, inputs)
    if family is None or inputs.belief_range_m is None:
        return state, None
    max_range_m = _FAMILY_MAX_RANGE_M.get(family)
    if max_range_m is None:
        return state, None
    if not state.range_out_called and not state.in_range_call_pending:
        if inputs.belief_range_m > max_range_m:
            new_state = replace(
                state, range_out_called=True, in_range_call_pending=True
            )
            return new_state, render_range_state(in_range=False)
        new_state = replace(state, range_calls_done=True)
        return new_state, None
    if state.in_range_call_pending and inputs.belief_range_m <= max_range_m:
        new_state = replace(state, in_range_call_pending=False, range_calls_done=True)
        return new_state, render_range_state(in_range=True)
    return state, None


def _render_launch_line(
    family: str | None, belief_range_m: float | None
) -> OutgoingSpeech:
    """`"<Family>, N second(s)."` when both the family and a believed
    range are known and the family has a declared speed; `"Missile."`
    (no time) otherwise -- Stage 3's own task list: "an unknown family
    gives 'Missile.' with no time (no invented number)." Extended the same
    way for an unknown *range*, which the plan's prose does not name
    explicitly but whose only consistent treatment, under the same "no
    invented number" rule, is the identical fallback."""
    if family is None or belief_range_m is None:
        return render_atgm_launch(None, None)
    speed_mps = _FAMILY_SPEED_MPS.get(family)
    if speed_mps is None:
        return render_atgm_launch(None, None)
    seconds = max(0, round(belief_range_m / speed_mps))
    return render_atgm_launch(family, seconds)


def _preparing_tick(
    state: AtgmRunState, inputs: AtgmInputs
) -> tuple[AtgmRunState, tuple[OutgoingSpeech, ...], tuple[AtgmAction, ...]]:
    """Preparing -> Tracking/Empty, gated on `observ_observed` (the
    stateDiagram's "OBSERV observed on, station selected"). Waits silently
    -- no speech, no action -- every poll OBSERV is not yet observed on;
    `belief.crew_console.drain_atgm_engage` (Stage 1) already said "Observ
    on, wait." and fired the switch once, at run start, so there is
    nothing left for this function to say while it waits."""
    if not inputs.observ_observed:
        return state, (), ()
    resolved = _resolve_station_selection(None, inputs.station_counts)
    if resolved is None:
        new_state = replace(state, phase=AtgmPhase.EMPTY)
        return new_state, (render_no_more_missiles(),), ()
    new_state = replace(
        state,
        phase=AtgmPhase.TRACKING,
        selected_step=resolved,
        selected_step_count_last_seen=inputs.station_counts.get(resolved, 0),
    )
    return new_state, (), (SelectStation(resolved),)


def _tracking_drop_check(
    state: AtgmRunState, inputs: AtgmInputs
) -> tuple[AtgmRunState, tuple[OutgoingSpeech, ...], tuple[AtgmAction, ...]]:
    """Tracking's own count-drop-without-launch bookkeeping -- only
    reached by `decide` when this same poll carries **no** `LaunchEvent`
    (a launch always wins, handled by the caller before this function is
    even called). Arms `unconfirmed_drop_since_sim` the first poll the
    selected station's count reads lower than last poll's; once `ATGM_
    UNCONFIRMED_DROP_GRACE_S` has elapsed with still no launch, resolves
    the drop: a station that still shows ammo just clears the timer and
    keeps tracking (a partial drop, nothing to select), one that reads
    empty goes to the next loaded station (silently) or "No more
    missiles." (round 7/4's own wording, reused here for the jettison
    case the plan explicitly folds into the same rule)."""
    selected_step = state.selected_step
    current_count = (
        inputs.station_counts.get(selected_step, 0) if selected_step is not None else 0
    )
    if state.unconfirmed_drop_since_sim is None:
        last_seen = state.selected_step_count_last_seen
        if last_seen is not None and current_count < last_seen:
            new_state = replace(state, unconfirmed_drop_since_sim=inputs.now_sim)
            return new_state, (), ()
        new_state = replace(state, selected_step_count_last_seen=current_count)
        return new_state, (), ()

    elapsed = inputs.now_sim - state.unconfirmed_drop_since_sim
    if elapsed < ATGM_UNCONFIRMED_DROP_GRACE_S:
        return state, (), ()

    # Grace window elapsed with no launch -- logged (Stage 7's own job,
    # reading the raw count-drop, not through this return) as "count drop
    # without launch."
    if current_count > 0:
        new_state = replace(
            state,
            unconfirmed_drop_since_sim=None,
            selected_step_count_last_seen=current_count,
        )
        return new_state, (), ()
    resolved = _resolve_station_selection(selected_step, inputs.station_counts)
    if resolved is None:
        new_state = replace(
            state,
            phase=AtgmPhase.EMPTY,
            selected_step=None,
            selected_step_count_last_seen=None,
            unconfirmed_drop_since_sim=None,
        )
        return new_state, (render_no_more_missiles(),), ()
    if resolved == selected_step:
        new_state = replace(
            state,
            unconfirmed_drop_since_sim=None,
            selected_step_count_last_seen=inputs.station_counts.get(resolved, 0),
        )
        return new_state, (), ()
    new_state = replace(
        state,
        selected_step=resolved,
        selected_step_count_last_seen=inputs.station_counts.get(resolved, 0),
        unconfirmed_drop_since_sim=None,
    )
    return new_state, (), (SelectStation(resolved),)


def _in_flight_tick(
    state: AtgmRunState, inputs: AtgmInputs, *, already_in_flight: bool
) -> tuple[AtgmRunState, tuple[OutgoingSpeech, ...], tuple[AtgmAction, ...]]:
    """InFlight -> Resetting, on either a confirmed `missile_gone`
    ("Impact.") or the backstop (Decision N1: silently, after `ATGM_MAX_
    FLIGHT_S`, no speech, Stage 7's own ERROR log -- not this function's
    job to log, only to decide). Either way fires the reset sequence
    (`Fire("atgm-impact")`) -- the wait(1s)+Radiation-Reset press/release
    the knob is never turned before (Resetting waits on `impact_sequence_
    running`, not a fixed delay, see `AtgmInputs`'s own docstring).

    `already_in_flight` (`decide`'s own flag, `False` the very poll this
    phase was *just* entered) distinguishes a genuine second `LaunchEvent`
    -- the pilot got a second missile off the rail before the first one's
    flight ended -- from `decide`'s own first call into this function
    right after the Preparing/Tracking block moved the phase here this
    same poll (which must not re-read `inputs.launch` as a second launch
    of itself). A true second launch rebases the flight to the newest
    missile (`in_flight_since_sim`/`tracked_family` both reset) and stops
    -- no speech (the in-flight silence rule governs a second launch
    exactly as it governs everything else this phase holds), and no
    `missile_gone`/backstop check this same poll (which missile a `gone`
    arriving in the same batch would refer to is ambiguous, and no test
    or user decision asks for a guess)."""
    if state.in_flight_since_sim is None:
        return state, (), ()
    if already_in_flight and inputs.launch is not None:
        family = family_of(inputs.launch.type_name)
        new_state = replace(
            state, in_flight_since_sim=inputs.now_sim, tracked_family=family
        )
        return new_state, (), ()
    backstop = (inputs.now_sim - state.in_flight_since_sim) >= ATGM_MAX_FLIGHT_S
    if not inputs.missile_gone and not backstop:
        return state, (), ()
    new_state = replace(state, phase=AtgmPhase.RESETTING, in_flight_since_sim=None)
    speech = (render_impact(),) if inputs.missile_gone else ()
    return new_state, speech, (Fire("atgm-impact"),)


def _resetting_tick(
    state: AtgmRunState, inputs: AtgmInputs
) -> tuple[AtgmRunState, tuple[OutgoingSpeech, ...], tuple[AtgmAction, ...]]:
    """Resetting -> Selecting -> Tracking/Empty, all in the one poll the
    reset sequence finishes (`impact_sequence_running` turns `False`) --
    `Selecting` is never the value `decide` returns (`AtgmPhase.SELECTING`
    docstring); this function resolves straight through it, same
    selection rule `_tracking_drop_check`'s own empty-station branch and
    `_preparing_tick`'s first selection share (`_resolve_station_
    selection`)."""
    if inputs.impact_sequence_running:
        return state, (), ()
    resolved = _resolve_station_selection(state.selected_step, inputs.station_counts)
    if resolved is None:
        new_state = replace(
            state,
            phase=AtgmPhase.EMPTY,
            selected_step=None,
            selected_step_count_last_seen=None,
        )
        return new_state, (render_no_more_missiles(),), ()
    if resolved == state.selected_step:
        new_state = replace(
            state,
            phase=AtgmPhase.TRACKING,
            selected_step_count_last_seen=inputs.station_counts.get(resolved, 0),
        )
        return new_state, (), ()
    new_state = replace(
        state,
        phase=AtgmPhase.TRACKING,
        selected_step=resolved,
        selected_step_count_last_seen=inputs.station_counts.get(resolved, 0),
    )
    return new_state, (), (SelectStation(resolved),)


def decide(
    state: AtgmRunState, inputs: AtgmInputs
) -> tuple[AtgmRunState, tuple[OutgoingSpeech, ...], tuple[AtgmAction, ...]]:
    """One poll of the ATGM run's own "when" -- `(new_state, speech,
    actions)`. See module docstring for the shape and why `actions` never
    carries `say`.

    **Range calls and launch detection both apply while Preparing or
    Tracking** (the plan's own wording, "Range calls" section: "the first
    poll in Tracking *or Preparing*"; the stateDiagram's own `Preparing
    -> InFlight: LaunchEvent, same` edge) -- handled together in this
    function's first block so a launch arriving on the very poll Preparing
    would otherwise have resolved a station selection pre-empts that
    selection entirely (the physical missile left the rail; which station
    this run *would* have picked next is moot). A `FailedLaunch` this same
    poll changes nothing by construction (`FailedLaunch`'s own docstring)
    -- this function does not even read `inputs.failed_launch`.

    **A launch and its own flight ending can land in the same poll's
    inputs** (a very short flight, or a poll gap) -- handled by *not*
    returning early after the Preparing/Tracking block: if that block just
    moved `new_state.phase` to `IN_FLIGHT`, the `IN_FLIGHT` branch below
    still runs this same call, against the *same* `inputs.missile_gone`,
    producing both lines in order ("Shturm, 1 second." then "Impact.").
    The same fall-through covers Resetting -> Selecting -> Tracking
    landing back in a state this function does not re-enter (`elif`, not a
    second `if`) -- Resetting's own resolution already lands on `TRACKING`/
    `EMPTY` directly, never back through `IN_FLIGHT`.

    **A second `LaunchEvent` while already `IN_FLIGHT`** (this poll's
    phase was `IN_FLIGHT` *before* this call, not just-entered by the
    block above) is `_in_flight_tick`'s own `already_in_flight` branch,
    not this function's -- `just_launched` is the one piece of
    information `_in_flight_tick` cannot derive from `state`/`inputs`
    alone (both a just-entered and an already-standing `IN_FLIGHT` have
    `in_flight_since_sim is not None`), so `decide` tracks it locally and
    passes `already_in_flight=not just_launched` through."""
    speech: list[OutgoingSpeech] = []
    actions: list[AtgmAction] = []
    new_state = state
    just_launched = False

    if new_state.phase in (AtgmPhase.PREPARING, AtgmPhase.TRACKING):
        new_state, range_call = _maybe_range_call(new_state, inputs)
        if range_call is not None:
            speech.append(range_call)

        if inputs.launch is not None:
            family = family_of(inputs.launch.type_name)
            new_state = replace(
                new_state,
                phase=AtgmPhase.IN_FLIGHT,
                in_flight_since_sim=inputs.now_sim,
                tracked_family=family,
                unconfirmed_drop_since_sim=None,
            )
            speech.append(_render_launch_line(family, inputs.belief_range_m))
            just_launched = True
        elif new_state.phase is AtgmPhase.PREPARING:
            new_state, s, a = _preparing_tick(new_state, inputs)
            speech.extend(s)
            actions.extend(a)
        else:
            new_state, s, a = _tracking_drop_check(new_state, inputs)
            speech.extend(s)
            actions.extend(a)

    if new_state.phase is AtgmPhase.IN_FLIGHT:
        new_state, s, a = _in_flight_tick(
            new_state, inputs, already_in_flight=not just_launched
        )
        speech.extend(s)
        actions.extend(a)
    elif new_state.phase is AtgmPhase.RESETTING:
        new_state, s, a = _resetting_tick(new_state, inputs)
        speech.extend(s)
        actions.extend(a)

    return new_state, tuple(speech), tuple(actions)
