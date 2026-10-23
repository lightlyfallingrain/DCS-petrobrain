"""The sequence-file execution engine -- `plans/effector-sequences/plan.md`
Stage 2, D1/D3/D4/D8/D9/D10/D11/R12. Replaces BL-B66's hand-coded
power-up/OBSERV/weapons-safety write blocks (`belief.sight_effector`'s
now-deleted sequencing half) with a small state machine that walks a
loaded `effector_sequences.SequenceFile`'s rows, driven once per poll by
`logger.py`.

**One queue per trigger (D1).** Each `EffectorTrigger` has at most one
*running* cursor (`EffectorRunState.runs[trigger]`) and one *pending*
re-fire flag (`.pending[trigger]`). `fire_trigger` starts a trigger that
is idle immediately (same poll); firing one that is already running
marks it pending (a second fire while already pending is a no-op, D1);
different triggers queue independently.

**Two distinct per-row gates, not one (R12/D3).** An explicit
`condition` cell (a genuine cross-switch dependency) is evaluated first,
if present: unknown readback waits up to
`EFFECTOR_CONDITION_READBACK_WAIT_S`, then **skips** the row. Once that
gate passes (or there was none), the engine runs its own *implicit*
self-check against the row's own effector -- "is this switch already at
the value this row would write?" (R12, user 2026-10-23: *"I'd expect the
code to check that switch is already in set position, so no action."*).
A known match **skips**; a known mismatch proceeds to write; an unknown
readback waits the same `EFFECTOR_CONDITION_READBACK_WAIT_S`, but then
**writes** instead of skipping -- the opposite outcome from the explicit
condition's timeout, because an absolute-value write is harmless even if
the switch secretly already had that value, whereas skipping a
cross-switch *dependency* on no information would risk firing a row
whose precondition was never actually confirmed.

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
sequence collapsing in one tick)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Final

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.effector_registry import EffectorDef
from belief.effector_sequences import EffectorTrigger, SequenceFile, SwitchRow, WaitRow

logger = logging.getLogger(__name__)

#: `EffectorTrigger` is declared in `effector_sequences.py` (merged
#: 2026-10-23 -- see that module's docstring); listing it here tells
#: `mypy --strict` this import is a deliberate re-export, not an unused
#: one, so `from belief.effector_engine import EffectorTrigger`
#: (`logger.py`, tests) keeps working unchanged.
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

#: How long a row with an unknown readback waits before the engine gives
#: up on the readback ever arriving this run (D3/R12) -- long enough to
#: survive a brief telemetry gap, short enough that a genuinely-missing
#: feed (an old aircraft-layer predating the `args` map) does not stall
#: a sequence indefinitely. An explicit `condition` row **skips** on
#: timeout; an implicit self-check row **writes** on timeout (R12) --
#: see the module docstring for why those differ.
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


def _matches(effector_def: EffectorDef, raw: float, value_name: str) -> bool:
    """`True` iff the observed raw value `raw` is within half the
    smallest inter-value gap of the named value `value_name`'s own raw
    number (plan: "Readback value matching")."""
    target = effector_def.values[value_name]
    return abs(raw - target) < _half_gap(effector_def.values)


def _raw_value_for(
    effector_def: EffectorDef, readback: Mapping[str, float] | None
) -> float | None:
    """The observed raw value for `effector_def`'s own arg, from the
    `args` map `GET /cockpit_switch/latest` now carries (plan R7/Stage 2:
    `schema.cockpit_switch.CockpitSwitchState.to_api_dict`'s `"args"`
    key, `{"773": <raw>, ...}`). `None` -- never a value -- when
    `readback` itself is absent (no sample yet, or a collector predating
    the `args` map) or does not carry this particular arg."""
    if readback is None:
        return None
    return readback.get(str(effector_def.arg))


@dataclass(frozen=True, slots=True)
class _RunCursor:
    """One trigger's progress through its own `SequenceFile.rows`.
    Replaced wholesale, never mutated -- same discipline as
    `GuidanceUnitState`. The two `*_waiting_since_sim` fields are
    deliberately separate (not one shared field): an explicit
    `condition` gate and the implicit self-check gate on the *same* row
    can each need their own independent "how long have I been waiting"
    clock, and conflating them would mean the self-check's timer
    silently inherits a stale value left over from the condition gate
    resolving earlier in a previous poll."""

    row_index: int
    next_due_sim: float
    condition_waiting_since_sim: float | None = None
    self_waiting_since_sim: float | None = None


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
    (`advance` filters it down to live triggers every call)."""

    runs: Mapping[EffectorTrigger, _RunCursor] = field(default_factory=dict)
    pending: Mapping[EffectorTrigger, bool] = field(default_factory=dict)
    commanded_values: Mapping[str, str] = field(default_factory=dict)
    fire_order: tuple[EffectorTrigger, ...] = ()


def fire_trigger(
    state: EffectorRunState, trigger: EffectorTrigger, now_sim: float
) -> EffectorRunState:
    """Starts `trigger` running this poll if it is idle (cursor at row
    0, due now -- `advance` may execute its first row the same poll);
    marks it `pending` if it is already running (D1); a fire while
    already pending is a logged no-op, since a second pending copy adds
    nothing beyond re-evaluating conditions once the run restarts."""
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


def _sequence_for(
    trigger: EffectorTrigger,
    sequences: Mapping[tuple[str, str, str], SequenceFile],
) -> SequenceFile | None:
    return sequences.get((AIRCRAFT, PETROVICH_ROLE, trigger.value))


def advance(
    state: EffectorRunState,
    now_sim: float,
    readback: Mapping[str, float] | None,
    client: AircraftLayerClient,
    sequences: Mapping[tuple[str, str, str], SequenceFile],
    registry: Mapping[str, EffectorDef],
) -> EffectorRunState:
    """Advances every currently-running trigger by at most one write
    each, in fire order (D9), evaluating as many skip-only rows as apply
    first (D1/R12 can collapse an entire already-satisfied sequence into
    zero writes in one call). Called once per poll by `logger.py`,
    unconditionally -- a true no-op when no trigger is running."""
    runs = dict(state.runs)
    pending = dict(state.pending)
    commanded_values = dict(state.commanded_values)
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

            row = rows[cursor.row_index]
            if isinstance(row, WaitRow):
                cursor = replace(
                    cursor,
                    row_index=cursor.row_index + 1,
                    next_due_sim=now_sim + row.wait_s,
                    condition_waiting_since_sim=None,
                    self_waiting_since_sim=None,
                )
                continue

            assert isinstance(row, SwitchRow)

            if row.condition is not None:
                cond_def = registry.get(row.condition.effector)
                if cond_def is None:
                    # Validated away at load time; unreachable in
                    # practice. Fail closed by skipping, never writing
                    # on an unresolvable condition.
                    cursor = replace(
                        cursor,
                        row_index=cursor.row_index + 1,
                        condition_waiting_since_sim=None,
                        self_waiting_since_sim=None,
                    )
                    continue
                cond_raw = _raw_value_for(cond_def, readback)
                if cond_raw is None:
                    if cursor.condition_waiting_since_sim is None:
                        cursor = replace(cursor, condition_waiting_since_sim=now_sim)
                        break
                    if (
                        now_sim - cursor.condition_waiting_since_sim
                        < EFFECTOR_CONDITION_READBACK_WAIT_S
                    ):
                        break
                    logger.warning(
                        "condition effector %r (arg %d) has no readback "
                        "after %.1fs; skipping row for trigger %s",
                        row.condition.effector,
                        cond_def.arg,
                        EFFECTOR_CONDITION_READBACK_WAIT_S,
                        trigger,
                    )
                    cursor = replace(
                        cursor,
                        row_index=cursor.row_index + 1,
                        condition_waiting_since_sim=None,
                        self_waiting_since_sim=None,
                    )
                    continue
                matches = _matches(cond_def, cond_raw, row.condition.value)
                satisfied = matches if row.condition.op == "=" else not matches
                if not satisfied:
                    cursor = replace(
                        cursor,
                        row_index=cursor.row_index + 1,
                        condition_waiting_since_sim=None,
                        self_waiting_since_sim=None,
                    )
                    continue

            effector_def = registry.get(row.effector)
            if effector_def is None:
                # Also validated away at load time; fail closed the same
                # way as an unresolvable condition effector above.
                cursor = replace(
                    cursor,
                    row_index=cursor.row_index + 1,
                    condition_waiting_since_sim=None,
                    self_waiting_since_sim=None,
                )
                continue

            # R12: the implicit self-check -- is this row's own effector
            # already at the value this row would write?
            self_raw = _raw_value_for(effector_def, readback)
            if self_raw is not None and _matches(effector_def, self_raw, row.value):
                cursor = replace(
                    cursor,
                    row_index=cursor.row_index + 1,
                    condition_waiting_since_sim=None,
                    self_waiting_since_sim=None,
                )
                continue
            if self_raw is None:
                if cursor.self_waiting_since_sim is None:
                    cursor = replace(cursor, self_waiting_since_sim=now_sim)
                    break
                if (
                    now_sim - cursor.self_waiting_since_sim
                    < EFFECTOR_CONDITION_READBACK_WAIT_S
                ):
                    break
                # R12: unlike the explicit-condition timeout above, an
                # unknown self-readback *writes* rather than skips -- an
                # absolute-value write is harmless even if the switch
                # secretly already had that value.
                logger.warning(
                    "effector %r (arg %d) has no readback after %.1fs; "
                    "writing anyway for trigger %s",
                    row.effector,
                    effector_def.arg,
                    EFFECTOR_CONDITION_READBACK_WAIT_S,
                    trigger,
                )

            if row.effector in failed_effectors:
                # D9: a write to this same effector already failed this
                # poll (an earlier trigger in fire order); hold this row
                # at the same index and retry next poll rather than risk
                # landing out of order.
                break

            value = effector_def.values[row.value]
            try:
                client.write_cockpit_switch(
                    effector_def.device, effector_def.cmd, value
                )
            except AircraftLayerError:
                logger.warning(
                    "effector %r write failed (trigger %s); retrying next poll",
                    row.effector,
                    trigger,
                    exc_info=True,
                )
                failed_effectors.add(row.effector)
                break

            commanded_values[row.effector] = row.value
            cursor = replace(
                cursor,
                row_index=cursor.row_index + 1,
                next_due_sim=now_sim + EFFECTOR_SEQUENCE_STEP_DELAY_S,
                condition_waiting_since_sim=None,
                self_waiting_since_sim=None,
            )
            # Deliberately `continue`, not `break`: the "one write per
            # trigger per poll" cap (parity with today's power-up
            # spacing) falls out naturally from `next_due_sim` now being
            # in the future, which the loop's own due-time check catches
            # on the very next iteration -- *except* when this write was
            # the sequence's last row and a pending re-fire is waiting,
            # whose fresh cursor is due `now_sim` immediately (Co-moving
            # Fields: "same poll's advance may execute it"). Breaking
            # here unconditionally would defer that legitimate immediate
            # restart to next poll instead.
            continue

        if cursor is None:
            runs.pop(trigger, None)
        else:
            runs[trigger] = cursor

    new_fire_order = tuple(t for t in state.fire_order if t in runs)
    return replace(
        state,
        runs=runs,
        pending=pending,
        commanded_values=commanded_values,
        fire_order=new_fire_order,
    )
