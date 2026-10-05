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
exists at all.

`observation_id_to_contact_id` (public, `todo/todo.md`'s "belief vs ground
truth" logging addition) is this module's own contact-id resolution,
shared rather than duplicated: `belief_truth_log.py` needs the exact same
observation-id -> contact-id join `write_poll` below already performs, and
the user's own direction was "reuse rather than duplicate ... that pairing
belongs in one place that both read.\"
"""

from __future__ import annotations

import contextlib
import json
import sys
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
        self._path = path
        self._file: TextIO = path.open("a", encoding="utf-8")
        self._flush_every_n_polls = flush_every_n_polls
        self._polls_since_flush = 0
        #: Set by `_fail` after the first write error -- see that method.
        self._disabled = False

    def write_poll(
        self, collector: DetectionTraceCollector, store: ContactStore
    ) -> None:
        """Append `collector`'s currently-buffered records (this poll's
        gate outcomes) as JSON lines, joined against `store`'s current
        contacts, then clear `collector.records` so the next poll's
        `write_poll` call only sees that poll's own entries. Read-only
        against `store` -- never calls anything that mutates it.

        `collector.records` is cleared whether or not the write succeeded:
        a disabled writer (see `_fail`) must not let the collector's buffer
        grow without bound for the rest of the sortie."""
        if self._disabled:
            collector.records.clear()
            return

        obs_to_contact_id = observation_id_to_contact_id(store)
        try:
            for entry in collector.records:
                contact_id = None
                if entry.observation_id is not None:
                    contact_id = obs_to_contact_id.get(entry.observation_id)
                self._file.write(json.dumps(_entry_to_dict(entry, contact_id)))
                self._file.write("\n")
        except OSError as exc:
            self._fail(exc)
        finally:
            collector.records.clear()

        self._polls_since_flush += 1
        if self._polls_since_flush >= self._flush_every_n_polls:
            self.flush()

    def flush(self) -> None:
        if self._disabled:
            return
        try:
            self._file.flush()
        except OSError as exc:
            self._fail(exc)
        self._polls_since_flush = 0

    def close(self) -> None:
        """Flush and close, never raising -- `BL-11` Stage 5.

        `flush` above early-returns once the writer is disabled, so buffered
        data that cannot be written surfaces from `close()` instead. The
        poll loop calls this from its `finally:` block (`logger.py`), so an
        unguarded `OSError` here is a traceback on shutdown in exactly the
        full-disk scenario this stage exists to make legible -- and the
        `_fail` line has already said what went wrong."""
        self.flush()
        with contextlib.suppress(OSError):
            self._file.close()

    def _fail(self, exc: OSError) -> None:
        """Report one write failure, then stop writing for the rest of the
        run -- `BL-11` Stage 5.

        **A full disk mid-flight used to be invisible.** The poll loop's own
        broad `except Exception` caught the `OSError`, logged a traceback
        per poll, and carried on calling this writer, so the sortie
        continued with a truncated log and nothing said so until the file
        was read afterwards. Saying it once and disabling the writer makes
        the symptom legible without turning a debug artifact into a
        per-poll traceback storm.

        Only this writer stops. Perception, belief and speech are
        unaffected, which is the right trade: losing the trace is bad,
        losing the crew member is worse."""
        self._disabled = True
        print(
            f"detection-trace: write to {self._path} failed ({exc}); "
            f"no further trace rows will be written this run",
            file=sys.stderr,
        )


def observation_id_to_contact_id(store: ContactStore) -> dict[str, str]:
    """Every observation id any current contact has ever contributed,
    mapped to that contact's id -- rebuilt fresh from `store.contacts` on
    every call (an accepted cost for a single-sortie debug artifact, not a
    standing index; see the plan's Risks & Unknowns on volume)."""
    mapping: dict[str, str] = {}
    for contact in store.contacts:
        for observation_id in contact.contributing_observation_ids:
            mapping[observation_id] = contact.id
    return mapping


def _entry_to_dict(
    entry: DetectionTrace, contact_id: str | None
) -> dict[str, object | None]:
    """One row's JSON payload, **with `None`-valued annotation fields
    omitted** -- `BL-11` Stage 5.

    `DetectionTrace` has 25 fields and most are the optional annotations
    (motion gate, live LOS, achieved tier, cluster membership) that stay
    `None` on any candidate those stages never reached. `asdict` emitted all
    of them, which is roughly half the bytes of a 290 KB/poll artifact
    (`body-layer/research/2026-10-05-performance-review.md` finding 6).

    **An absent key means `None`** -- the same absent-not-null convention
    `belief.tools` already uses for its `facts`. Safe for the readers this
    repo has: every field one of them reads unconditionally (`object_id`,
    `object_type`, `t_sim`, `true_bearing_deg`, `true_range_m`,
    `range_threshold_m`, `threshold_bound`, `outcome`, `optic`) is
    non-optional on `DetectionTrace`, and the annotations are already read
    with `.get` by `tools/summarize_detection_trace.py`,
    `tools/eyesight_replay.py` and `.claude/skills/sortie-log-triage`.

    **`observation_id` and `contact_id` stay present even when `None`**,
    unlike every other optional field. They are the join keys -- "did this
    candidate ever become something Petrovich believed" is the question the
    whole artifact exists to answer -- and for those two an absent key
    would read as *unknown* rather than as the definite *never admitted*
    that a `null` states."""
    data: dict[str, object | None] = {
        key: value
        for key, value in asdict(entry).items()
        if value is not None and key != "cluster_member_object_ids"
    }
    data["outcome"] = entry.outcome.value
    if entry.cluster_member_object_ids is not None:
        data["cluster_member_object_ids"] = list(entry.cluster_member_object_ids)
    data["observation_id"] = entry.observation_id
    data["contact_id"] = contact_id
    return data
