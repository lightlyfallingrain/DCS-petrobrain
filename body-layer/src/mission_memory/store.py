"""`MissionMemory` -- the in-memory append-only store, plan Decision 4's
strike bookkeeping, and the Co-moving Fields table's five fields.

**The store never decides anything** (Decision 4): a strike is proposed by
whichever admission rule (`admission.py`) writes the replacement entry,
naming the entry it supersedes via `strikes=<seq>`. This module only
records that decision and keeps the derived indices consistent.

**`append()` is the single construction site for a *live* `Entry`.**
Every `seq`/mark-index/strike-bookkeeping invariant in the plan's Co-moving
Fields table is enforced here, in one place, under one lock -- appends
come from the poll thread, reads from the REPL/brain thread, and two
fields updating between a reader's two reads is the failure the lock
prevents. `entries.decode_entry` is the one other place an `Entry` is ever
constructed, and only to rebuild a historical entry already on disk, never
to mint a new `seq` or mark index -- see its own docstring."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import replace

from mission_memory.entries import (
    SCHEMA_VERSION,
    Entry,
    EntryKind,
    EntryPosition,
    MarkPayload,
    Payload,
    PhaseInfo,
    Provenance,
    SeenHow,
)


class MissionMemory:
    """Holds every entry appended this sortie, plus the derived indices
    `admission.py`/`marks.py` and a future query surface need: `struck_by`
    (seq -> the seq that struck it), and `latest_live_seq` (contact id ->
    the newest unstruck entry naming it, O(1), so the admission rules'
    material-change check never scans the log -- the plan's own "Risks"
    section names this as the one thing that must never move onto the poll
    thread's critical path as an O(n) scan)."""

    def __init__(self) -> None:
        self._entries: list[Entry] = []
        self._next_seq = 1
        self._next_mark_index = 1
        self._seqs: set[int] = set()
        self._struck_by: dict[int, int] = {}
        self._latest_live: dict[str, int] = {}
        self._lock = threading.Lock()
        #: Set by `log.MissionMemoryLogWriter.write` via `logger.py`'s
        #: wiring -- `None` (the default) means every append simply holds
        #: in memory, which is what every Stage 1 test exercises.
        self._sink: Callable[[Entry], None] | None = None

    def set_sink(self, sink: Callable[[Entry], None] | None) -> None:
        """Wire (or clear) the JSONL sink every subsequent `append` writes
        through. Separate from `__init__` so a store can be built before
        its log path is known (mirrors every other writer-injection
        pattern in this codebase, e.g. `CrewConsole.speech_log_sink`)."""
        self._sink = sink

    def reset_for_new_mission(self) -> None:
        """Give a clean slate on a genuine DCS mission (re)start (`BL-15`
        Stage 1): so nothing from the previous mission can be recalled in
        this one. Re-invokes `__init__` on this same object, then restores
        the one field that must survive -- the open `MissionMemoryLogWriter`
        sink, same mechanism as `belief.contacts.ContactStore.reset_for_
        new_mission`'s "re-run the constructor" pattern, see that method's
        own docstring. `_next_seq`/`_next_mark_index` restart at 1 inside
        whatever log file is still open (the plan's own named risk -- a
        future debrief tool reading that file across a restart would see
        two entries with `seq=1`); full per-mission log re-rolling is a
        separate, not-yet-decided follow-up, not this method's job."""
        sink = self._sink
        self.__init__()  # type: ignore[misc]
        self.set_sink(sink)

    @property
    def entries(self) -> list[Entry]:
        """Every entry appended so far, insertion order. A read-only
        view -- callers must not mutate the returned list."""
        with self._lock:
            return list(self._entries)

    @property
    def struck_by(self) -> dict[int, int]:
        """`{struck_seq: striking_seq}`, built incrementally by `append`.
        A read-only view -- callers must not mutate the returned dict.
        `rebuild_struck_by` below is the same mapping, computed from
        scratch by replaying `entries` alone -- the two must always agree;
        that agreement is what `tests/test_mission_memory_store.py`'s
        replay test checks."""
        with self._lock:
            return dict(self._struck_by)

    def is_struck(self, seq: int) -> bool:
        with self._lock:
            return seq in self._struck_by

    def latest_live_seq(self, belief_ref: str) -> int | None:
        """The newest entry naming `belief_ref`, or `None` if none exists
        yet. By construction (every admission rule that replaces an entry
        also strikes it, naming the new entry's own `strikes`) this is
        always the newest *unstruck* entry for that subject too -- see the
        Co-moving Fields table's own "must hold true" column."""
        with self._lock:
            return self._latest_live.get(belief_ref)

    def latest_entry(self, belief_ref: str) -> Entry | None:
        """`latest_live_seq(belief_ref)`'s own `Entry`, or `None` -- the
        read `admission.py`'s material-change check uses to compare a
        contact's current belief against what was last written.

        **Not O(1)**: the seq lookup itself is, but resolving it to the
        `Entry` object walks `_entries` from the end. Acceptable at this
        plan's own estimated volumes (`~3600` entries in a worst-case
        two-hour sortie, "Risks & Unknowns") -- if the log ever grows large
        enough for this to matter, add a `seq -> Entry` index alongside
        `_latest_live` rather than widening this method's contract."""
        with self._lock:
            seq = self._latest_live.get(belief_ref)
            if seq is None:
                return None
            for entry in reversed(self._entries):
                if entry.seq == seq:
                    return entry
            return None

    def append(
        self,
        *,
        kind: EntryKind,
        provenance: Provenance,
        t_sim: float,
        phase: PhaseInfo | None,
        pos: EntryPosition | None,
        seen: SeenHow | None,
        belief_ref: str | None,
        strikes: int | None,
        payload: Payload,
        t_wall: float | None = None,
    ) -> Entry:
        """Append one new entry and return it. `strikes`, when given, must
        name an existing, not-yet-struck `seq` -- a second strike of one
        entry is a bug in the calling admission rule, not a chain, and is
        rejected rather than silently layered (Co-moving Fields table,
        `_struck_by` row).

        `kind="mark"` entries get their `payload.index` **overwritten**
        here from `_next_mark_index`, regardless of what the caller passed
        -- the single place that counter is allowed to move, and the only
        way a mark index is ever minted (see `entries.MarkPayload`'s own
        docstring)."""
        with self._lock:
            if strikes is not None:
                if strikes not in self._seqs:
                    raise ValueError(
                        f"strikes={strikes!r} does not name an existing entry"
                    )
                if strikes in self._struck_by:
                    raise ValueError(
                        f"entry {strikes!r} is already struck by "
                        f"{self._struck_by[strikes]!r} -- a second strike "
                        "is a bug in the caller, not a chain"
                    )

            seq = self._next_seq
            self._next_seq += 1
            self._seqs.add(seq)

            if kind == "mark":
                mark_payload = payload
                assert isinstance(mark_payload, MarkPayload)
                payload = replace(mark_payload, index=self._next_mark_index)
                self._next_mark_index += 1

            entry = Entry(
                schema=SCHEMA_VERSION,
                seq=seq,
                kind=kind,
                provenance=provenance,
                t_sim=t_sim,
                t_wall=t_wall if t_wall is not None else time.time(),
                phase=phase,
                pos=pos,
                seen=seen,
                belief_ref=belief_ref,
                strikes=strikes,
                iff=None,
                payload=payload,
            )
            self._entries.append(entry)
            if strikes is not None:
                self._struck_by[strikes] = seq
            if belief_ref is not None:
                self._latest_live[belief_ref] = seq
            sink = self._sink
        # The sink write happens outside the lock -- file I/O should never
        # hold up a reader on another thread, and the entry is already
        # fully decided and appended by the time it runs.
        if sink is not None:
            sink(entry)
        return entry


def rebuild_struck_by(entries: list[Entry]) -> dict[int, int]:
    """`MissionMemory._struck_by`, recomputed from scratch by replaying
    `entries` alone, in order -- what a debrief tool does, since it only
    ever has the JSONL file, never a live `MissionMemory` instance."""
    struck_by: dict[int, int] = {}
    for entry in entries:
        if entry.strikes is not None:
            struck_by[entry.strikes] = entry.seq
    return struck_by
