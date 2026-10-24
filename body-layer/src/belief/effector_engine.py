"""The sequence-file execution engine -- `plans/effector-sequences/plan.md`
Stage 2 (D1/D3/D4/D8/D9/D10/D11/R12) and Stage 4 (S4.3, "readback by
need"). Replaces BL-B66's hand-coded power-up/OBSERV/weapons-safety
write blocks (`belief.sight_effector`'s now-deleted sequencing half)
with a small state machine that walks a loaded `effector_sequences.
SequenceFile`'s rows, driven once per poll by `logger.py`.

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
    like every other field here."""

    runs: Mapping[EffectorTrigger, _RunCursor] = field(default_factory=dict)
    pending: Mapping[EffectorTrigger, bool] = field(default_factory=dict)
    commanded_values: Mapping[str, str] = field(default_factory=dict)
    fire_order: tuple[EffectorTrigger, ...] = ()
    assumed_writes: Mapping[int, tuple[float, float]] = field(default_factory=dict)


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


def _sequence_for(
    trigger: EffectorTrigger,
    sequences: Mapping[tuple[str, str, str], SequenceFile],
) -> SequenceFile | None:
    return sequences.get((AIRCRAFT, PETROVICH_ROLE, trigger.value))


def _effective_value(
    arg: int,
    cursor: _RunCursor,
    assumed_writes: Mapping[int, tuple[float, float]],
) -> float | None:
    """The value a row sees for arg `arg` (plan S4.3's own rule): an
    `assumed_writes` entry written at `sim >= cursor.snapshot_sim` wins
    over the snapshot (a write this run or an earlier trigger made this
    poll, or a previous poll, settled before this snapshot was taken);
    otherwise the snapshot's own reading; otherwise unknown (`None`).
    `cursor.snapshot_sim` is only `None` while `cursor.snapshot` is also
    `None`, so this is never called in that state (the caller always
    attempts a read first)."""
    assumed = assumed_writes.get(arg)
    if (
        assumed is not None
        and cursor.snapshot_sim is not None
        and assumed[1] >= cursor.snapshot_sim
    ):
        return assumed[0]
    if cursor.snapshot is not None:
        return cursor.snapshot.get(str(arg))
    return None


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
    zero writes in one call). Called once per poll by `logger.py`,
    unconditionally -- a true no-op when no trigger is running.

    **No `readback` parameter** (Stage 4) -- each cursor's own one-shot
    `client.read_args(...)` call is this function's only source of
    cockpit state; see the module docstring's "Each run carries a
    snapshot" section."""
    runs = dict(state.runs)
    pending = dict(state.pending)
    commanded_values = dict(state.commanded_values)
    assumed_writes = dict(state.assumed_writes)
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

            if row.condition is not None:
                cond_def = registry.get(row.condition.effector)
                if cond_def is None:
                    # Validated away at load time; unreachable in
                    # practice. Fail closed by skipping, never writing
                    # on an unresolvable condition.
                    cursor = replace(cursor, row_index=cursor.row_index + 1)
                    continue
                cond_raw = _effective_value(cond_def.arg, cursor, assumed_writes)
                if cond_raw is None:
                    # D3: unknown -> skip, unconditionally -- the wait
                    # already happened once, at the run-level read above.
                    cursor = replace(cursor, row_index=cursor.row_index + 1)
                    continue
                matches = _matches(cond_def, cond_raw, row.condition.value)
                satisfied = matches if row.condition.op == "=" else not matches
                if not satisfied:
                    cursor = replace(cursor, row_index=cursor.row_index + 1)
                    continue

            effector_def = registry.get(row.effector)
            if effector_def is None:
                # Also validated away at load time; fail closed the same
                # way as an unresolvable condition effector above.
                cursor = replace(cursor, row_index=cursor.row_index + 1)
                continue

            # R12: the implicit self-check -- is this row's own effector
            # already at the value this row would write?
            self_raw = _effective_value(effector_def.arg, cursor, assumed_writes)
            if self_raw is not None and _matches(effector_def, self_raw, row.value):
                cursor = replace(cursor, row_index=cursor.row_index + 1)
                continue
            if self_raw is None and not effector_def.absolute_write:
                # Never a blind write on an unverified-absolute shape --
                # a toggle/press could land the wrong way with no
                # information to go on.
                logger.warning(
                    "effector %r (arg %d, shape %r) has no readback; "
                    "skipping row for trigger %s (never a blind write "
                    "on an unconfirmed-absolute shape)",
                    row.effector,
                    effector_def.arg,
                    effector_def.shape,
                    trigger,
                )
                cursor = replace(cursor, row_index=cursor.row_index + 1)
                continue

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
            assumed_writes[effector_def.arg] = (value, now_sim)
            cursor = replace(
                cursor,
                row_index=cursor.row_index + 1,
                next_due_sim=now_sim + EFFECTOR_SEQUENCE_STEP_DELAY_S,
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
        assumed_writes=assumed_writes,
    )
