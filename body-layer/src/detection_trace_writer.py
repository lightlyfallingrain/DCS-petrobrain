"""`DetectionTraceWriter` -- BL-9's belief join (`plans/
bl9-debug-visualization/plan.md`).

**This is the one module in the codebase deliberately allowed to hold both
ground truth and belief at once.** `perception.detection_trace.
DetectionTrace` is ground truth (candidate geometry, gate outcome, achieved
tier) by construction, same footing as `perception.source.Observation`;
`belief.contacts.Contact` is what Petrovich actually believes. Joining them
is real, but it is **read-only and one-directional**: this module reads
`ContactStore.contacts` (already a public property, the same read
`belief.tools.get_contacts` already performs) to resolve which `Contact`
an admitted object's `Observation.id` ended up in, via `Contact.
contributing_observation_ids` (already public, already exists for BL-2's
own history tooling) -- it never writes anything back. No ground-truth
field is ever passed into `ContactStore.ingest`, `Percept`, or any
`Contact` field; the structural boundary `belief/percept.py` already
enforces is untouched.

`perception/` gains no import of `belief/` from this change (this module
sits beside `logger.py`, not inside either package); `belief/` gains no
import of this module or of `detection_trace.py` -- the no-omniscience
invariant holds for Petrovich exactly as before. Deliberately kept a
single, narrow, read-only file, since it is the one place this permission
exists at all."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

from belief.contacts import ContactStore
from perception.detection_trace import DetectionTrace, DetectionTraceCollector

#: How many polls' worth of records to buffer before flushing to disk --
#: favors "a few polls" over "as rarely as possible" (plan Risks &
#: Unknowns: an unclean exit loses at most this many polls' data). Not a
#: user-facing setting; see `plans/bl9-debug-visualization/
#: implementation.md` for this being one of the plan's two flagged-open
#: decisions, picked rather than confirmed.
DEFAULT_FLUSH_EVERY_N_POLLS = 5


class DetectionTraceWriter:
    """Appends one JSON line per `DetectionTrace` record to `path`,
    buffering a few polls' worth before flushing (never the poll loop's own
    critical path -- disk I/O only happens at `write_poll`/`flush`/`close`
    call points, never inside `perception/`)."""

    def __init__(
        self,
        path: Path,
        flush_every_n_polls: int = DEFAULT_FLUSH_EVERY_N_POLLS,
    ) -> None:
        self._file: TextIO = path.open("a", encoding="utf-8")
        self._flush_every_n_polls = flush_every_n_polls
        self._polls_since_flush = 0

    def write_poll(
        self, collector: DetectionTraceCollector, store: ContactStore
    ) -> None:
        """Append `collector`'s currently-buffered records (this poll's
        gate outcomes) as JSON lines, joined against `store`'s current
        contacts, then clear `collector.records` so the next poll's
        `write_poll` call only sees that poll's own entries. Read-only
        against `store` -- never calls anything that mutates it."""
        observation_id_to_contact_id = _observation_id_to_contact_id(store)
        for entry in collector.records:
            contact_id = None
            if entry.observation_id is not None:
                contact_id = observation_id_to_contact_id.get(entry.observation_id)
            self._file.write(json.dumps(_entry_to_dict(entry, contact_id)))
            self._file.write("\n")
        collector.records.clear()

        self._polls_since_flush += 1
        if self._polls_since_flush >= self._flush_every_n_polls:
            self.flush()

    def flush(self) -> None:
        self._file.flush()
        self._polls_since_flush = 0

    def close(self) -> None:
        self.flush()
        self._file.close()


def _observation_id_to_contact_id(store: ContactStore) -> dict[str, str]:
    """Every observation id any current contact has ever contributed,
    mapped to that contact's id -- rebuilt fresh from `store.contacts` on
    every call (an accepted cost for a single-sortie debug artifact, not a
    standing index; see the plan's Risks & Unknowns on volume)."""
    mapping: dict[str, str] = {}
    for contact in store.contacts:
        for observation_id in contact.contributing_observation_ids:
            mapping[observation_id] = contact.id
    return mapping


def _entry_to_dict(entry: DetectionTrace, contact_id: str | None) -> dict[str, object]:
    data = asdict(entry)
    data["outcome"] = entry.outcome.value
    data["cluster_member_object_ids"] = (
        list(entry.cluster_member_object_ids)
        if entry.cluster_member_object_ids is not None
        else None
    )
    data["contact_id"] = contact_id
    return data
