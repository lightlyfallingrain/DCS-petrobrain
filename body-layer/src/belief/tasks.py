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
`ContactStore.tick`'s own replay-determinism guarantee."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from belief.attention import AttentionArea, area_contains
from belief.contacts import ContactStore

#: Only one kind exists this milestone -- `scan_area`'s trigger-and-check
#: lifecycle. A `Literal` (not a bare `str`) so a future second kind is a
#: type-checked, additive change, not a silent string-typo risk.
TaskKind = Literal["scan_area"]

#: `"pending"` is the only mutable state; the other three are terminal --
#: once set, `tick`/`TaskStore.cancel` never touch that task again.
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
    area too" (the plan's Decision 3) can read `task.area.id` directly."""

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
        """Mark a still-`pending` task `cancelled`. Returns whether
        `task_id` was found -- a task already resolved (`succeeded`/
        `failed`) or already `cancelled` is left untouched either way (its
        terminal status is not overwritten), but the lookup still reports
        `True` since the id genuinely exists; only an unknown id returns
        `False`, mirroring `ContactStore.remove_area`'s own "unknown id"
        convention. Does not touch `task.area` -- removing the
        `AttentionArea` a cancelled task registered is `tools.cancel_task`'s
        job (it also needs the `ContactStore`, which this store does not
        hold), per the plan's Decision 3."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status == "pending":
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
            matching = [
                contact.id
                for contact in store.contacts
                if contact.last_seen_sim > task.created_sim
                and area_contains(task.area, contact.last_position)
            ]
            if matching:
                task.status = "succeeded"
                task.result_contact_ids = matching
            elif now_sim >= task.deadline_sim:
                task.status = "failed"

    def _new_task_id(self) -> str:
        self._next_task_number += 1
        return f"{_TASK_ID_PREFIX}_{self._next_task_number}"
