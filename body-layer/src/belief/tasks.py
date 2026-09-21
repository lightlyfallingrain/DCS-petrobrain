"""`PendingIntent`/`TaskStore` -- BL-6 (`plans/bl6-commands-inspect-adapt/
plan.md`), the belief-side half of `scan_area`'s command lifecycle.

Unchanged in shape from the plan's original (pre-live-investigation)
premise, per the plan's "What stayed the same" section: a `PendingIntent`
is created when a scan is requested, and `tick` decides whether it has
`succeeded` (a `belief.contacts.Contact` inside the task's area was
observed after the task was created), `failed` (nothing confirmed by
`deadline_sim`), or is still `pending`. This module has **no DCS I/O** --
the live trigger that (per the plan's newer half) actually makes Petrovich
search lives one layer up, in `console.py`'s `scan-area` handler, the same
place BL-2.5 wired the overlay push rather than inside `tools.py`.

**Epistemic caveat, carried at every read site (`tools.get_task_status`'s
own docstring repeats this for the brain-facing surface):** a `failed`
task means "nothing confirmed by the deadline," never "confirmed empty."
Since the effector cannot aim Petrovich (see the plan's "What this plan
does NOT attempt"), a real search can genuinely miss a real target inside
the task's area through no fault of this module's logic -- `tick` has no
way to distinguish that from "nothing was there" or "the trigger never
actually fired." `PendingIntent`/`TaskStore` must never be read as if
`failed` were a stronger claim than that.

**Success check, mirroring `ContactStore.tick`'s own reuse of
`belief.attention.area_contains`:** a task succeeds the moment *any*
contact's `last_position` falls inside `task.area` (`area_contains`) with
`last_seen_sim` strictly after `task.created_sim` -- i.e. a contact
observed *after* the scan was requested, not a contact that merely
happens to already be sitting in that area from before. `HybridPerceptionSource`
already gates on real detections, so this check is exactly the "did
something relevant appear here" reasoning the plan's "What stayed the
same" section describes, unchanged by which effector (if any) triggered
the search.

**Idempotence.** Calling `tick` repeatedly with the same `now_sim` is a
no-op after the first call for any task already resolved (`succeeded`/
`failed`/`cancelled`) -- `tick` only ever touches `pending` tasks, mirroring
`ContactStore.tick`'s own replay-determinism guarantee.

**Ownship-anchored areas are a moving patch of view, not ground
(`plans/f10-command-vocabulary/plan.md` D1-D3).** A `scan_area` task
created over a relative-sector area (`ahead`/`left`/`right`/`full`) does
not judge contacts against a fixed circle frozen at command-time ownship
position -- its success predicate genuinely means "was a contact seen
inside the sector at *some* tick since the task was created," because the
sector itself tracks ownship's nose via `logger.py`'s per-tick
`ContactStore.reproject_relative_areas` call. That is a different
predicate from the fixed-ground-area case, where "inside the area" has one
fixed meaning for the task's whole life -- and it has a structural
consequence here too: `PendingIntent.area` is captured *once*, at
task-creation time (see its own docstring), while `reproject_relative_areas`
replaces the *store's* entry with a new frozen object (`dataclasses.
replace`) rather than mutating it in place, so a captured reference goes
stale the moment the first reprojection after task creation happens. `tick`
therefore never reads `task.area` directly for its containment check -- it
re-resolves the *live* area by id first (`ContactStore.get_area
(task.area.id)`), falling back to the captured reference only if that id is
no longer registered.

That fallback is reachable, just not from anything a scan command does.
`tools.cancel_task` cancels the task before removing its area, so the id
stays live for as long as that task is pending -- but `cancel_task` is not
the only way an area leaves the store. `tools.unwatch_area` (reached from
`belief.console`'s `unwatch-area <id>` developer command) calls
`ContactStore.remove_area` directly with no task awareness at all, and will
happily strip the area out from under a still-`pending` scan task. The
fallback then degrades to the captured reference, which for an
ownship-anchored area means an unprojected one: a permissive circle at the
position ownship held when the scan was ordered. That is exactly the
too-permissive completion check this id-resolution exists to prevent, so
the degradation is graceful only in the sense that it does not crash.

Do not tighten `unwatch_area` into task-awareness on this note alone --
it is a pre-existing `--console`-only debug path, and no F10 or crew-text
command can reach it. It is written down because the honest statement is
"reachable from one debug command, with a known bad-but-bounded outcome",
not "cannot happen".

Two views of the same object silently drifting apart is a recurring failure
mode in this codebase (see NOTES.md) -- the fallback above is a safety net,
not the intended path, and must never be relied on to paper over an
invariant violation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from belief.attention import AttentionArea, area_contains
from belief.contacts import ContactStore

#: Only one kind exists this milestone -- `scan_area`'s trigger-and-check
#: lifecycle. A `Literal` (not a bare `str`) so a future second kind is a
#: type-checked, additive change, not a silent string-typo risk.
TaskKind = Literal["scan_area"]

#: **`"cancelled"` is the only true terminal state (cones 2C sortie fix,
#: `docs/concept/STATE_TRANSITIONS.md`'s "Modes" section).** `tick` still
#: only ever touches a `"pending"` task (its own docstring, unchanged) --
#: but `"succeeded"`/`"failed"` are no longer terminal to `TaskStore.cancel`:
#: a `scan_area` task is a standing *mode*, not a one-shot job, so finding
#: something (`"succeeded"`) or timing out (`"failed"`) is an event about
#: what the search has (not) confirmed, never the end of the mode. Only an
#: explicit cancel, or a newer scan command superseding it (`logger.
#: _active_gaze`'s own "most recently created" tie-break), ends it. See
#: `TaskStore.cancel`'s own docstring for the fix this replaced.
TaskStatus = Literal["pending", "succeeded", "failed", "cancelled"]

#: `TaskStore`-minted `PendingIntent.id` prefix, distinct in shape from
#: every other id space in `belief.contacts`/`belief.attention`
#: (`CONTACT_*`/`EVENT_*`/`AREA_*`) for the same reason those are kept
#: distinct from each other -- a task id never collides with a contact,
#: event, or area id.
_TASK_ID_PREFIX = "TASK"


@dataclass
class PendingIntent:
    """One outstanding (or resolved) `scan_area` request. `area` is the
    `belief.attention.AttentionArea` `tools.scan_area` registered alongside
    this task -- the same object, not a copy, so `cancel_task`'s "remove the
    area too" (the plan's Decision 3) can read `task.area.id` directly.

    **`task.area.id` is the only field of this reference safe to read
    directly once the task exists.** For an ownship-anchored area,
    `ContactStore.reproject_relative_areas` replaces the *store's* entry
    with a new object on every telemetry tick, and this captured reference
    is never updated to match -- so `task.area.center`/`.wedge_deg` can be
    silently stale. Any containment check (`area_contains`) must resolve
    the live area via `ContactStore.get_area(task.area.id)` first; see
    `TaskStore.tick` and this module's own docstring."""

    id: str
    kind: TaskKind
    area: AttentionArea
    created_sim: float
    deadline_sim: float
    reason: str
    status: TaskStatus = "pending"
    result_contact_ids: list[str] = field(default_factory=list)


class TaskStore:
    """Holds every `PendingIntent` ever created, mirroring `belief.contacts.
    ContactStore`'s own store-mints-the-id shape (`_new_contact_id` etc.)."""

    def __init__(self) -> None:
        self._tasks: dict[str, PendingIntent] = {}
        self._next_task_number = 0

    @property
    def tasks(self) -> list[PendingIntent]:
        """Every task, insertion order. A read-only view -- callers must not
        mutate the returned list."""
        return list(self._tasks.values())

    def create(
        self,
        kind: TaskKind,
        area: AttentionArea,
        created_sim: float,
        deadline_sim: float,
        reason: str,
    ) -> PendingIntent:
        """Mint a new `PendingIntent`, minting its `id` the same way
        `ContactStore._new_contact_id`/`_new_event_id`/`_new_area_id` mint
        theirs. Returns the stored task, including its minted `id`, so a
        caller (`tools.scan_area`) can report it back."""
        task = PendingIntent(
            id=self._new_task_id(),
            kind=kind,
            area=area,
            created_sim=created_sim,
            deadline_sim=deadline_sim,
            reason=reason,
        )
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> PendingIntent | None:
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Mark `task_id` `cancelled`, regardless of its current status.
        Returns whether `task_id` was found -- mirrors `ContactStore.
        remove_area`'s own "unknown id" convention. Does not touch
        `task.area` -- removing the `AttentionArea` a cancelled task
        registered is `tools.cancel_task`'s job (it also needs the
        `ContactStore`, which this store does not hold), per the plan's
        Decision 3.

        **Cones 2C sortie fix.** This used to leave a task already resolved
        (`succeeded`/`failed`) untouched -- its terminal status was never
        overwritten, only reported as found. That was the second half of
        the sortie's "watch closest -> flew past -> cancel task -> 'nothing
        to stop'"-shaped bug: `tick` resolves a `scan_area` task the moment
        any contact appears in its area, so a task could become
        uncancellable within seconds of being issued, while `logger.
        _active_gaze` (which used to honour only `"pending"` tasks) had
        already, silently, reverted to free scan. A `scan_area` task is a
        standing mode (`TaskStatus`'s own docstring, `docs/concept/
        STATE_TRANSITIONS.md`): `"succeeded"`/`"failed"` say what the
        search has (not) confirmed, never that the mode ended, so cancel
        must still be able to end it from either state. Idempotent on an
        already-`"cancelled"` task -- no functional change, same as
        before."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = "cancelled"
        return True

    def tick(self, store: ContactStore, now_sim: float) -> None:
        """Resolve every still-`pending` task as of `now_sim`, driven purely
        by `now_sim` (never wall clock, preserving BL-0's replay
        determinism) -- see the module docstring for the success/timeout
        rule and the idempotence guarantee."""
        for task in self._tasks.values():
            if task.status != "pending":
                continue
            # Resolve the live area by id rather than trusting `task.area`
            # directly -- see `PendingIntent.area`'s docstring and this
            # module's own docstring on why a captured reference can be
            # stale for an ownship-anchored area.
            area = store.get_area(task.area.id) or task.area
            matching = [
                contact.id
                for contact in store.contacts
                if contact.last_seen_sim > task.created_sim
                and area_contains(area, contact.last_position)
            ]
            if matching:
                task.status = "succeeded"
                task.result_contact_ids = matching
            elif now_sim >= task.deadline_sim:
                task.status = "failed"

    def _new_task_id(self) -> str:
        self._next_task_number += 1
        return f"{_TASK_ID_PREFIX}_{self._next_task_number}"
