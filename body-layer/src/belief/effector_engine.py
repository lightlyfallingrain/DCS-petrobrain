"""The sequence-file execution engine -- `plans/effector-sequences/plan.md`
Stage 2 (D1/D3/D4/D8/D9/D10/D11/R12) and Stage 4 (S4.3, "readback by
need"). Replaces BL-B66's hand-coded power-up/OBSERV/weapons-safety
write blocks (`belief.sight_effector`'s now-deleted sequencing half)
with a small state machine that walks a loaded `effector_sequences.
SequenceFile`'s rows, driven once per poll by `body.py`.

**One queue per trigger (D1).** Each `EffectorTrigger` has at most one
*running* cursor (`EffectorRunState.runs[trigger]`) and one *pending*
re-fire flag (`.pending[trigger]`). `fire_trigger` starts a trigger that
is idle immediately (same poll); firing one that is already running
marks it pending (a second fire while already pending is a no-op, D1);
different triggers queue independently.

**Each run carries a snapshot (Stage 4, S4.3), read once per run start
and once again after each `WaitRow`.** `advance` takes no `readback`
parameter any more -- a cursor whose `snapshot is None` makes its own
synchronous `client.read_args(...)` call for exactly its own sequence
file's `read_args` set (`SequenceFile.read_args`, computed at load time:
every switch row's effector arg, union every explicit condition's
effector arg). A failed read holds the trigger (other triggers still
advance) and retries next poll; after
`EFFECTOR_CONDITION_READBACK_WAIT_S` of failures the run gives up and
treats every arg as unknown (`snapshot = {}`) rather than stalling
forever.

**Two distinct per-row gates, not one (R12/D3), resolved against the
snapshot plus `assumed_writes` (below) once the snapshot exists -- no
per-row waiting any more.** An explicit `condition` cell (a genuine
cross-switch dependency) is evaluated first, if present: unknown ->
**skip** the row (D3). Once that gate passes (or there was none), the
engine runs its own *implicit* self-check against the row's own
effector -- "is this switch already at the value this row would
write?" (R12). A known match **skips**; a known mismatch **writes**; an
unknown readback **writes only if the effector's own `shape` is
confirmed as an absolute set** (`EffectorDef.absolute_write`) -- an
absolute write is harmless even if the switch secretly already had that
value, whereas writing *any other* shape on no information risks a
toggle/press landing the wrong way, so that case **skips with a
WARNING** instead (never a blind write).

**Assumed success (D3 revision, option B).** Every successful write
records `(raw_value, now_sim)` into `EffectorRunState.assumed_writes[arg]`
-- visible to *every* currently-running trigger's row resolution, not
only the writer's own, and only once its own `sim >=
cursor.snapshot_sim` (the `>=`, not `>`: two triggers can see one write's
UDP and another's read land in the same Export frame, so a same-poll
write must be visible to a same-poll read). This is what lets a second
takeoff see the first takeoff's own switch states without rereading
DCS, and what makes writing the same switch twice in one file correct
(the second row sees the first row's own write, not the stale snapshot).

**D9 ordering, across triggers, within one poll.** `advance` processes
every currently-running trigger in **fire order** (the order
`fire_trigger` most recently *started* it running -- `EffectorRunState.
fire_order`), and once a write to effector `E` fails this poll, no later
row in this same `advance` call that would also write `E` is attempted
-- it waits for the next poll instead, so a later trigger's write to the
same switch can never land ahead of an earlier trigger's still-failing
one. At most one *write* happens per trigger per poll (parity with
today's one-switch-per-poll power-up spacing) -- the one exception
being a trigger that completes and immediately restarts from a pending
re-fire (D1: "same poll's advance may execute it"), which may write
once for the run that just finished and once more for the one that
restarts. Any number of rows may be *skipped* in the same poll (D1's
queueing and R12's self-check both rely on a whole already-satisfied
sequence collapsing in one tick).

**A row's own `petrovich-says` line is reported when the row completes
(`[[BL-B119]]`) -- written successfully, or found already at its target
value (R12's self-check skip counts as a completion too, pilot
decision: the line confirms the state is as commanded either way).** A
row skipped for a failed explicit condition, an unknown/no-readback
effector, or a failed write awaiting retry says nothing. This module
stays pure: `EffectorRunState.spoken` carries this call's own lines, in
execution order (row order within a trigger, fire order across
triggers) -- `advance` never calls speech itself; `body.py` drains
`spoken` into `CrewConsole`'s own speech path once each. An empty
`petrovich-says` cell reports nothing. `spoken` is replaced wholesale
every call (including with `()` when nothing completed), the same
`replace()`-only discipline as every other field here, so a mission
reset drops it exactly like `assumed_writes`.

**A second kind of run, for a single rule-originated write (`[[BL-17]]`
D20, `plans/speech-rules/plan.md` Stage 3d).** `EffectorRunState.
ad_hoc_runs` holds a single target `(effector, value, says)` per
caller-minted request id, started by `request_write` (mirrors `fire_
trigger`'s own "start if idle" shape). The actual per-target execution
-- condition check, the implicit self-check, the `absolute_write` gate,
the write itself, bookkeeping, the spoken line -- is `_execute_switch_
row`, extracted from the trigger-run loop below so both kinds of run
call the *same* function: not a second write path. `advance` processes
`ad_hoc_runs` in a second pass, after the trigger-run loop, sharing
`assumed_writes`/`commanded_values`/`failed_effectors`/`spoken` with it
in the same call, so a rule-originated write and a sequence-row write to
the same effector in the same poll still respect D9's same-poll
collision rule. Unlike a sequence row -- which simply moves on to its
next row forever once it cannot resolve a non-absolute effector's
unknown readback -- an ad hoc run is a command the pilot explicitly
asked for, so that case is kept and retried with a fresh read next poll
rather than silently abandoned (a deliberate, documented departure from
the sequence-row behaviour the two passes otherwise share verbatim). A
write failure (an exception from `client.write_cockpit_switch`, or a
same-poll D9 collision) is held and retried next poll exactly like a
sequence row's own failed write -- no line is spoken either way, and the
run retries indefinitely (U24: this is a real, acknowledged tension with
the rule engine's own "always say something" culture, not resolved
here)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Final, Literal

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.effector_registry import EffectorDef
from belief.effector_sequences import (
    Condition,
    EffectorTrigger,
    SequenceFile,
    SwitchRow,
    WaitRow,
)

logger = logging.getLogger(__name__)

#: `EffectorTrigger` is declared in `effector_sequences.py` (merged
#: 2026-10-23 -- see that module's docstring); listing it here tells
#: `mypy --strict` this import is a deliberate re-export, not an unused
#: one, so `from belief.effector_engine import EffectorTrigger`
#: (`body.py`, tests) keeps working unchanged.
__all__ = ["EffectorTrigger"]

#: The aircraft/role this runtime always runs as -- "Role mismatch ->
#: sequence does not run. Only Mi-24P / copilot exist now" (explore-
#: notes, "Carried from the concept, unchanged"). Not derived from
#: anywhere else; a second aircraft/role is a later milestone's problem.
AIRCRAFT: Final[str] = "Mi-24P"
PETROVICH_ROLE: Final[str] = "copilot"


#: Minimum seconds between successive writes *within one trigger's own*
#: sequence -- renamed from `belief.sight_effector.
#: GUIDANCE_UNIT_SWITCH_DELAY_S` (D10); same value, same reasoning (the
#: measured ~3-frame/~0.1s DCS switch-animation ramp plus margin). A
#: `tuning.toml` still naming the old key gets this module's own "unknown
#: key" warning, same as any other renamed/removed tunable.
EFFECTOR_SEQUENCE_STEP_DELAY_S: Final[float] = tuning.real(
    "belief.effector_engine.EFFECTOR_SEQUENCE_STEP_DELAY_S",
    1.0,
    lo=0.5,
    hi=5.0,
    status="derived",
)

#: How long a run waits, per snapshot (Stage 4: once at run start, once
#: again after each wait row), for `client.read_args` to succeed before
#: giving up on the readback ever arriving and treating every arg as
#: unknown -- long enough to survive a brief collector/Export.lua gap,
#: short enough that a genuinely-down aircraft layer does not stall a
#: sequence indefinitely. A failed explicit `condition` row **skips** on
#: timeout; a failed implicit self-check row **writes** on timeout only
#: if the effector's own shape is a confirmed absolute set -- see the
#: module docstring for why those differ. **Cross-key coupling (root
#: `CLAUDE.md`'s third tuning trap): this value is compared against
#: `logger.WATCH_ARGS_RESEND_S`'s own retry cadence for the *continuous*
#: feed in spirit only (the two tunables gate unrelated reads), but
#: lowering this one toward its `lo` narrows the margin a one-shot read
#: has to recover from a single lost UDP datagram before the run gives
#: up and starts writing on no information.**
EFFECTOR_CONDITION_READBACK_WAIT_S: Final[float] = tuning.real(
    "belief.effector_engine.EFFECTOR_CONDITION_READBACK_WAIT_S",
    5.0,
    lo=1.0,
    hi=30.0,
    status="derived",
)

#: Half the smallest gap between an effector's named values, used when
#: there are fewer than two distinct values to compute a real gap from
#: (never happens for any shipped effector -- every one has at least an
#: on/off or armed/safe pair -- but `EffectorDef.values` is not typed to
#: forbid it). Matches the pre-existing two-position switch threshold
#: (`_SWITCH_ON_THRESHOLD` in aircraft-layer's `schema.cockpit_switch`).
_FALLBACK_HALF_GAP: Final[float] = 0.5


def _half_gap(values: Mapping[str, float]) -> float:
    """Half the smallest gap between an effector's distinct named raw
    values (plan: "Readback value matching"). `_FALLBACK_HALF_GAP` when
    there are fewer than two distinct values to take a gap between."""
    distinct = sorted(set(values.values()))
    if len(distinct) < 2:
        return _FALLBACK_HALF_GAP
    return min(b - a for a, b in pairwise(distinct)) / 2.0


def _speak_text(text: str) -> str:
    """Sentence-cases a completed row's own `petrovich-says` cell
    (`[[BL-B119]]`, plan: "the pilot wrote the words, the code only
    normalises punctuation/case") -- matching the fixed phrasing it
    replaces (`"Observ on."`, `"Weapons armed."`): capitalises the first
    character and appends a period if the cell did not already end in
    terminal punctuation. The cell is already quote/whitespace-stripped
    by `effector_sequences._strip_petrovich_says` at parse time."""
    if not text:
        return text
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    return text


def _matches(effector_def: EffectorDef, raw: float, value_name: str) -> bool:
    """`True` iff the observed raw value `raw` is within half the
    smallest inter-value gap of the named value `value_name`'s own raw
    number (plan: "Readback value matching")."""
    target = effector_def.values[value_name]
    return abs(raw - target) < _half_gap(effector_def.values)


@dataclass(frozen=True, slots=True)
class _RunCursor:
    """One trigger's progress through its own `SequenceFile.rows`.
    Replaced wholesale, never mutated -- same discipline as
    `GuidanceUnitState`.

    `snapshot`/`snapshot_sim` (Stage 4, S4.3) are the one-shot read taken
    at run start and re-taken after each `WaitRow`; `snapshot is None`
    means "a read is owed before the next row can be evaluated".
    `read_first_attempt_sim` latches the sim time of the *first* failed
    read attempt this snapshot cycle, so the run knows how long it has
    been waiting without a second field -- cleared whenever a read
    succeeds or the snapshot is reset by a `WaitRow`."""

    row_index: int
    next_due_sim: float
    snapshot: Mapping[str, float] | None = None
    snapshot_sim: float | None = None
    read_first_attempt_sim: float | None = None


@dataclass(frozen=True, slots=True)
class _AdHocEffectorCursor:
    """One rule-originated single-target write (D20), keyed by a
    caller-minted request id in `EffectorRunState.ad_hoc_runs` --
    mirrors `_RunCursor`'s own read/write progress fields, minus
    `row_index` (there is exactly one target, never a sequence of
    rows). `status` is introspection only (plan: "nothing reads it yet
    ... a future `--print-rules`-style debug dump") -- `advance` sets
    it, nothing branches on it; `"succeeded"` is never actually observed
    on a *stored* cursor, since a successful run is removed from `ad_hoc_
    runs` rather than kept with that status, but it is part of the same
    closed vocabulary the plan names."""

    effector: str
    value: str
    says: str | None
    next_due_sim: float
    status: Literal["pending", "succeeded", "failed_write", "failed_no_readback"] = (
        "pending"
    )
    snapshot: Mapping[str, float] | None = None
    snapshot_sim: float | None = None
    read_first_attempt_sim: float | None = None


@dataclass(frozen=True, slots=True)
class EffectorRunState:
    """All of this engine's own sequencing state -- `replace()`-only,
    **one construction site**: the `field(default_factory=
    EffectorRunState)` on `logger.ConsolePerceptionRunner`, re-run by
    mission reset (D11). `commanded_values` is the plan's "What moves,
    what stays" replacement for `GuidanceUnitState.observ_commanded`/
    `weapon_safety_commanded` -- keyed by curated effector name, holding
    the value name of the most recent *successful* write (D9: a failed
    write never updates it). `fire_order` is internal bookkeeping for
    D9's "in fire order" rule -- the order `fire_trigger` most recently
    *started* each currently-running trigger; a trigger with no entry in
    `runs` is idle and plays no part in `fire_order`'s own ordering
    (`advance` filters it down to live triggers every call).

    `assumed_writes` (Stage 4, S4.3) is `{arg: (raw_value, sim_written)}`
    -- every successful write across every trigger, read by every
    running cursor's own row resolution (see the module docstring's
    "Assumed success" section). Dropped wholesale on mission reset (D11),
    like every other field here.

    `spoken` (`[[BL-B119]]`) is this call's own completed-row lines, in
    execution order -- replaced wholesale every `advance` call (`()`
    when nothing completed this poll), never accumulated across calls.
    `body.py` is the only reader; see the module docstring's own
    paragraph on it.

    `ad_hoc_runs` (`[[BL-17]]` D20) is every pending rule-originated
    single-target write, keyed by the caller-minted request id `request_
    write` was given -- see the module docstring's own paragraph on this
    second kind of run."""

    runs: Mapping[EffectorTrigger, _RunCursor] = field(default_factory=dict)
    pending: Mapping[EffectorTrigger, bool] = field(default_factory=dict)
    commanded_values: Mapping[str, str] = field(default_factory=dict)
    fire_order: tuple[EffectorTrigger, ...] = ()
    assumed_writes: Mapping[int, tuple[float, float]] = field(default_factory=dict)
    spoken: tuple[str, ...] = ()
    ad_hoc_runs: Mapping[str, _AdHocEffectorCursor] = field(default_factory=dict)


def fire_trigger(
    state: EffectorRunState, trigger: EffectorTrigger, now_sim: float
) -> EffectorRunState:
    """Starts `trigger` running this poll if it is idle (cursor at row
    0, due now, snapshot `None` -- `advance` reads before executing any
    row, same poll if the read succeeds immediately); marks it `pending`
    if it is already running (D1); a fire while already pending is a
    logged no-op, since a second pending copy adds nothing beyond
    re-evaluating conditions once the run restarts."""
    if trigger in state.runs:
        if state.pending.get(trigger, False):
            logger.debug("trigger %s fired while already pending; no-op (D1)", trigger)
            return state
        new_pending = dict(state.pending)
        new_pending[trigger] = True
        return replace(state, pending=new_pending)

    new_runs = dict(state.runs)
    new_runs[trigger] = _RunCursor(row_index=0, next_due_sim=now_sim)
    new_fire_order = (*(t for t in state.fire_order if t != trigger), trigger)
    return replace(state, runs=new_runs, fire_order=new_fire_order)


def request_write(
    state: EffectorRunState,
    request_id: str,
    name: str,
    value: str,
    says: str | None,
    now_sim: float,
) -> EffectorRunState:
    """Starts a rule-originated single-target effector write (`[[BL-17]]`
    D20) -- mirrors `fire_trigger`'s own "start if idle" shape, but keyed
    by a caller-minted `request_id` (`body.py`'s own injected closure
    mints a fresh one per dispatch) rather than an `EffectorTrigger`:
    there is no sequence file or trigger behind an ad hoc write.

    **A second request for the same effector while one is already
    pending, at the *same* value, is a no-op** (plan's own Stage 3d test
    list) -- the same-effector check is against `ad_hoc_runs`' own
    `.effector` values, not `request_id`: two distinct dispatches (e.g.
    the pilot repeating a command before the first write has resolved)
    naturally mint two distinct ids even when they name the same switch,
    so a plain `request_id in state.ad_hoc_runs` check would never
    actually catch the case this mirrors (`fire_trigger`'s own "fire
    while already running" is keyed by the trigger itself, the
    equivalent "target" concept here).

    **A second request naming a *different* value replaces the pending
    one** (Stage 3d review Required Fix 2) -- this project's existing
    "latest wins, nothing lost" convention for exactly this kind of
    arbitration (U21; `AiPilotWheelGoal`'s own outstanding-flight-goal
    rule, `body-layer/CLAUDE.md`). The plan's own test-list wording only
    ever considered the same-value case, which mirrors `fire_trigger`'s
    D1 because a trigger carries no value of its own; an ad hoc write
    does, and a pilot's most recent instruction must not silently lose
    to an earlier one still in flight (the switch would otherwise settle
    at the *first* value while Petrovich eventually speaks the second
    request's own confirmation line for a value that was never
    reached)."""
    existing_id = next(
        (
            request_id_in_flight
            for request_id_in_flight, ad_hoc in state.ad_hoc_runs.items()
            if ad_hoc.effector == name
        ),
        None,
    )
    new_ad_hoc_runs = dict(state.ad_hoc_runs)
    if existing_id is not None:
        if state.ad_hoc_runs[existing_id].value == value:
            logger.debug(
                "ad hoc write to effector %r already pending at the same "
                "value; no-op (mirrors D1)",
                name,
            )
            return state
        logger.debug(
            "ad hoc write to effector %r already pending at a different "
            "value (%r); replacing with the latest request (%r) -- "
            "latest wins (U21)",
            name,
            state.ad_hoc_runs[existing_id].value,
            value,
        )
        del new_ad_hoc_runs[existing_id]
    new_ad_hoc_runs[request_id] = _AdHocEffectorCursor(
        effector=name, value=value, says=says, next_due_sim=now_sim
    )
    return replace(state, ad_hoc_runs=new_ad_hoc_runs)


def _sequence_for(
    trigger: EffectorTrigger,
    sequences: Mapping[tuple[str, str, str], SequenceFile],
) -> SequenceFile | None:
    return sequences.get((AIRCRAFT, PETROVICH_ROLE, trigger.value))


def _effective_value(
    arg: int,
    snapshot: Mapping[str, float] | None,
    snapshot_sim: float | None,
    assumed_writes: Mapping[int, tuple[float, float]],
) -> float | None:
    """The value a row/request sees for arg `arg` (plan S4.3's own rule;
    generalised from a `_RunCursor` to a bare `snapshot`/`snapshot_sim`
    pair by D20, so `_execute_switch_row` can share it between
    `_RunCursor` and `_AdHocEffectorCursor`): an `assumed_writes` entry
    written at `sim >= snapshot_sim` wins over the snapshot (a write this
    run or an earlier trigger/request made this poll, or a previous
    poll, settled before this snapshot was taken); otherwise the
    snapshot's own reading; otherwise unknown (`None`). `snapshot_sim` is
    only `None` while `snapshot` is also `None`, so this is never called
    in that state (every caller always attempts a read first)."""
    assumed = assumed_writes.get(arg)
    if assumed is not None and snapshot_sim is not None and assumed[1] >= snapshot_sim:
        return assumed[0]
    if snapshot is not None:
        return snapshot.get(str(arg))
    return None


_RowResult = Literal[
    "condition_unresolved",
    "self_matched",
    "unknown_readback",
    "blocked",
    "write_failed",
    "written",
]


@dataclass(frozen=True, slots=True)
class _RowOutcome:
    """What `_execute_switch_row` decided for one target. The two
    callers below read `result` differently -- see each one's own
    comment at its call site; this type and `_execute_switch_row` itself
    do not know or care which kind of run called them."""

    result: _RowResult
    spoken: str | None = None


def _execute_switch_row(
    effector_def: EffectorDef,
    value_name: str,
    says_text: str,
    condition: Condition | None,
    condition_def: EffectorDef | None,
    snapshot: Mapping[str, float] | None,
    snapshot_sim: float | None,
    assumed_writes: dict[int, tuple[float, float]],
    commanded_values: dict[str, str],
    failed_effectors: set[str],
    now_sim: float,
    client: AircraftLayerClient,
) -> _RowOutcome:
    """One target's actual execution (`[[BL-17]]` D20) -- condition check
    -> the implicit self-check (R12) -> the `absolute_write` gate ->
    `client.write_cockpit_switch` -> `assumed_writes`/`commanded_values`
    update -> an optional spoken line. Extracted from `advance`'s own
    per-row loop so the trigger-run sequence-row pass and the ad hoc pass
    below call the *same* function -- not a second write path.
    `condition`/`condition_def` are always `None` for an ad hoc target
    (D20: "a single target", no condition). `effector_def`'s own
    resolution, and the condition's own resolution when one exists, are
    always the caller's job -- this function takes no `registry` of its
    own. `assumed_writes`/`commanded_values`/`failed_effectors` are
    mutated in place on a successful write, the same engine-wide
    bookkeeping discipline as before this extraction."""
    if condition is not None:
        if condition_def is None:
            # Validated away at load time for a sequence file;
            # unreachable in practice. Fail closed by skipping, never
            # writing on an unresolvable condition.
            return _RowOutcome("condition_unresolved")
        cond_raw = _effective_value(
            condition_def.arg, snapshot, snapshot_sim, assumed_writes
        )
        if cond_raw is None:
            # D3: unknown -> skip, unconditionally.
            return _RowOutcome("condition_unresolved")
        matches = _matches(condition_def, cond_raw, condition.value)
        satisfied = matches if condition.op == "=" else not matches
        if not satisfied:
            return _RowOutcome("condition_unresolved")

    # R12: the implicit self-check -- is this target's own effector
    # already at the value this row/request would write?
    self_raw = _effective_value(
        effector_def.arg, snapshot, snapshot_sim, assumed_writes
    )
    if self_raw is not None and _matches(effector_def, self_raw, value_name):
        # `[[BL-B119]]`: found already in position still counts as
        # completing (pilot decision -- the line confirms the state is
        # as commanded either way).
        return _RowOutcome(
            "self_matched", spoken=_speak_text(says_text) if says_text else None
        )
    if self_raw is None and not effector_def.absolute_write:
        # Never a blind write on an unverified-absolute shape -- a
        # toggle/press could land the wrong way with no information to
        # go on.
        logger.warning(
            "effector %r (arg %d, shape %r) has no readback; skipping "
            "(never a blind write on an unconfirmed-absolute shape)",
            effector_def.name,
            effector_def.arg,
            effector_def.shape,
        )
        return _RowOutcome("unknown_readback")

    if effector_def.name in failed_effectors:
        # D9: a write to this same effector already failed this poll (an
        # earlier trigger/request in fire order); hold here and retry
        # next poll rather than risk landing out of order.
        return _RowOutcome("blocked")

    value = effector_def.values[value_name]
    try:
        client.write_cockpit_switch(effector_def.device, effector_def.cmd, value)
    except AircraftLayerError:
        logger.warning(
            "effector %r write failed; retrying next poll",
            effector_def.name,
            exc_info=True,
        )
        failed_effectors.add(effector_def.name)
        return _RowOutcome("write_failed")

    commanded_values[effector_def.name] = value_name
    assumed_writes[effector_def.arg] = (value, now_sim)
    # `[[BL-B119]]`: the row/request completed by a successful write.
    return _RowOutcome("written", spoken=_speak_text(says_text) if says_text else None)


def advance(
    state: EffectorRunState,
    now_sim: float,
    client: AircraftLayerClient,
    sequences: Mapping[tuple[str, str, str], SequenceFile],
    registry: Mapping[str, EffectorDef],
) -> EffectorRunState:
    """Advances every currently-running trigger by at most one write
    each, in fire order (D9), evaluating as many skip-only rows as apply
    first (D1/R12 can collapse an entire already-satisfied sequence into
    zero writes in one call), then every pending `EffectorRunState.
    ad_hoc_runs` entry (`[[BL-17]]` D20). Called once per poll by
    `body.py`, unconditionally -- a true no-op when nothing is running.

    **No `readback` parameter** (Stage 4) -- each cursor's own one-shot
    `client.read_args(...)` call is this function's only source of
    cockpit state; see the module docstring's "Each run carries a
    snapshot" section.

    **Returned state's own `spoken` is this call's completed-row lines
    only** (`[[BL-B119]]`), not an accumulation across calls -- see the
    module docstring's own paragraph and `EffectorRunState.spoken`'s
    field docstring."""
    runs = dict(state.runs)
    pending = dict(state.pending)
    commanded_values = dict(state.commanded_values)
    assumed_writes = dict(state.assumed_writes)
    spoken: list[str] = []
    failed_effectors: set[str] = set()

    order = [t for t in state.fire_order if t in runs]
    for trigger in order:
        cursor: _RunCursor | None = runs[trigger]
        sequence = _sequence_for(trigger, sequences)
        if sequence is None:
            logger.debug(
                "trigger %s fired but no sequence file is loaded for it", trigger
            )
            del runs[trigger]
            pending.pop(trigger, None)
            continue

        rows = sequence.rows
        while cursor is not None:
            if cursor.row_index >= len(rows):
                if pending.get(trigger, False):
                    pending[trigger] = False
                    cursor = _RunCursor(row_index=0, next_due_sim=now_sim)
                    continue
                cursor = None
                break
            if now_sim < cursor.next_due_sim:
                break

            if cursor.snapshot is None:
                try:
                    values = client.read_args(sorted(sequence.read_args))
                except AircraftLayerError:
                    if cursor.read_first_attempt_sim is None:
                        cursor = replace(cursor, read_first_attempt_sim=now_sim)
                        break
                    if (
                        now_sim - cursor.read_first_attempt_sim
                        < EFFECTOR_CONDITION_READBACK_WAIT_S
                    ):
                        break
                    logger.warning(
                        "no switch readback for trigger %s after %.1fs; "
                        "treating every arg as unknown",
                        trigger,
                        EFFECTOR_CONDITION_READBACK_WAIT_S,
                    )
                    cursor = replace(cursor, snapshot={}, read_first_attempt_sim=None)
                    continue
                cursor = replace(
                    cursor,
                    snapshot=values,
                    snapshot_sim=now_sim,
                    read_first_attempt_sim=None,
                )
                # Falls through into row evaluation this same poll
                # (plan E1: "a read succeeds -> rows run the same poll").

            row = rows[cursor.row_index]
            if isinstance(row, WaitRow):
                cursor = replace(
                    cursor,
                    row_index=cursor.row_index + 1,
                    next_due_sim=now_sim + row.wait_s,
                    snapshot=None,
                    snapshot_sim=None,
                    read_first_attempt_sim=None,
                )
                continue

            assert isinstance(row, SwitchRow)

            effector_def = registry.get(row.effector)
            if effector_def is None:
                # Validated away at load time; unreachable in practice.
                # Fail closed by skipping, never writing on an
                # unresolvable effector.
                cursor = replace(cursor, row_index=cursor.row_index + 1)
                continue

            condition_def = (
                registry.get(row.condition.effector)
                if row.condition is not None
                else None
            )
            outcome = _execute_switch_row(
                effector_def=effector_def,
                value_name=row.value,
                says_text=row.petrovich_says,
                condition=row.condition,
                condition_def=condition_def,
                snapshot=cursor.snapshot,
                snapshot_sim=cursor.snapshot_sim,
                assumed_writes=assumed_writes,
                commanded_values=commanded_values,
                failed_effectors=failed_effectors,
                now_sim=now_sim,
                client=client,
            )
            if outcome.result in ("blocked", "write_failed"):
                # D9: a write to this same effector already failed this
                # poll (an earlier trigger in fire order), or this row's
                # own write just failed -- hold this row at the same
                # index and retry next poll rather than risk landing out
                # of order.
                break
            if outcome.spoken:
                spoken.append(outcome.spoken)
            cursor = replace(
                cursor,
                row_index=cursor.row_index + 1,
                next_due_sim=(
                    now_sim + EFFECTOR_SEQUENCE_STEP_DELAY_S
                    if outcome.result == "written"
                    else cursor.next_due_sim
                ),
            )
            # Deliberately `continue`, not `break`: the "one write per
            # trigger per poll" cap (parity with today's power-up
            # spacing) falls out naturally from `next_due_sim` now being
            # in the future after a real write, which the loop's own
            # due-time check catches on the very next iteration --
            # *except* when this write was the sequence's last row and a
            # pending re-fire is waiting, whose fresh cursor is due
            # `now_sim` immediately (Co-moving Fields: "same poll's
            # advance may execute it"). Breaking here unconditionally
            # would defer that legitimate immediate restart to next poll
            # instead.
            continue

        if cursor is None:
            runs.pop(trigger, None)
        else:
            runs[trigger] = cursor

    # `[[BL-17]]` D20: rule-originated single-target effector writes, a
    # second pass over `EffectorRunState.ad_hoc_runs` sharing `assumed_
    # writes`/`commanded_values`/`failed_effectors`/`spoken` with the
    # trigger-run pass above in this same call -- never a second write
    # path (same `_execute_switch_row`); see the module docstring's own
    # paragraph on this second kind of run.
    new_ad_hoc_runs: dict[str, _AdHocEffectorCursor] = {}
    for request_id, ad_hoc in state.ad_hoc_runs.items():
        if now_sim < ad_hoc.next_due_sim:
            new_ad_hoc_runs[request_id] = ad_hoc
            continue

        ad_hoc_effector_def = registry.get(ad_hoc.effector)
        if ad_hoc_effector_def is None:
            # Validated against this same registry at `effector.write`
            # dispatch time (`rules.actions._write_effector`); unreachable
            # in practice. Drop it rather than retry forever on a name
            # that can never resolve.
            continue

        snapshot = ad_hoc.snapshot
        snapshot_sim = ad_hoc.snapshot_sim
        if snapshot is None:
            try:
                values = client.read_args([ad_hoc_effector_def.arg])
            except AircraftLayerError:
                if ad_hoc.read_first_attempt_sim is None:
                    new_ad_hoc_runs[request_id] = replace(
                        ad_hoc, read_first_attempt_sim=now_sim
                    )
                    continue
                if (
                    now_sim - ad_hoc.read_first_attempt_sim
                    < EFFECTOR_CONDITION_READBACK_WAIT_S
                ):
                    new_ad_hoc_runs[request_id] = ad_hoc
                    continue
                logger.warning(
                    "no switch readback for ad hoc write %r (effector %r) "
                    "after %.1fs; treating as unknown",
                    request_id,
                    ad_hoc.effector,
                    EFFECTOR_CONDITION_READBACK_WAIT_S,
                )
                snapshot = {}
                snapshot_sim = now_sim
                ad_hoc = replace(
                    ad_hoc,
                    snapshot=snapshot,
                    snapshot_sim=snapshot_sim,
                    read_first_attempt_sim=None,
                )
            else:
                snapshot = values
                snapshot_sim = now_sim
                ad_hoc = replace(
                    ad_hoc,
                    snapshot=snapshot,
                    snapshot_sim=snapshot_sim,
                    read_first_attempt_sim=None,
                )

        ad_hoc_outcome = _execute_switch_row(
            effector_def=ad_hoc_effector_def,
            value_name=ad_hoc.value,
            says_text=ad_hoc.says or "",
            condition=None,
            condition_def=None,
            snapshot=snapshot,
            snapshot_sim=snapshot_sim,
            assumed_writes=assumed_writes,
            commanded_values=commanded_values,
            failed_effectors=failed_effectors,
            now_sim=now_sim,
            client=client,
        )
        if ad_hoc_outcome.result in ("self_matched", "written"):
            if ad_hoc_outcome.spoken:
                spoken.append(ad_hoc_outcome.spoken)
            # Done -- not carried into `new_ad_hoc_runs`.
            continue
        if ad_hoc_outcome.result == "unknown_readback":
            # D20: unlike a sequence row (which simply moves on to its
            # next row forever once it cannot resolve a non-absolute
            # effector's unknown readback), a rule-originated write is a
            # command the pilot explicitly asked for -- kept and retried
            # with a fresh read next poll rather than silently abandoned.
            new_ad_hoc_runs[request_id] = replace(
                ad_hoc,
                status="failed_no_readback",
                snapshot=None,
                snapshot_sim=None,
            )
            continue
        # "blocked" or "write_failed": hold at the current snapshot and
        # retry next poll -- D9's same-poll collision rule applies here
        # too, via the `failed_effectors` set shared with the trigger-run
        # pass above.
        new_ad_hoc_runs[request_id] = replace(ad_hoc, status="failed_write")

    new_fire_order = tuple(t for t in state.fire_order if t in runs)
    return replace(
        state,
        runs=runs,
        pending=pending,
        commanded_values=commanded_values,
        fire_order=new_fire_order,
        assumed_writes=assumed_writes,
        spoken=tuple(spoken),
        ad_hoc_runs=new_ad_hoc_runs,
    )
