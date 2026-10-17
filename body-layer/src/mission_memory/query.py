"""The in-flight read surface the brain-facing tools call -- plan
Decision 5. This is the read half of the package: every function here is
pure over an already-built `MissionMemory`, holds no tuning constants, and
constructs no `Entry` (`tests/test_mission_memory_store.py`'s
`test_admission_and_marks_never_construct_entry_directly`-style grep test
is extended to this module too).

**No `belief` import.** Unlike `admission.py`/`marks.py` (which read a
live `ContactStore` to decide what is worth writing), a query over
already-written entries needs nothing from `belief` at all -- `Entry.pos`/
`Entry.belief_ref`/`Entry.kind` already carry everything a filter needs.
`perception.geometry.GeoPosition` is imported for the radius filter's
`center` parameter, the same "outside `belief/` but not `belief` itself"
import `marks.py` already established for its own position arguments.

**Strike state is a store-level read, never a field on `Entry`** (Decision
4: the file is never mutated, so a struck entry cannot be marked in place).
Every dict this module returns therefore carries its own `struck_by`
looked up from `MissionMemory.struck_by` at query time, not from the
entry."""

from __future__ import annotations

import math
from collections.abc import Mapping

from mission_memory.entries import Entry, EntryKind, encode_entry
from mission_memory.store import MissionMemory
from perception.geometry import GeoPosition


def entry_to_dict(
    entry: Entry, struck_by: Mapping[int, int] | None = None
) -> dict[str, object]:
    """One entry rendered for a brain-facing tool result: `encode_entry`'s
    JSON-safe shape plus `struck_by` (the seq that struck this entry, or
    `None` if it is still live) -- the one field `encode_entry` cannot
    carry, since it belongs to the store, not the entry (Decision 4).
    `struck_by=None` (the default) is correct for a just-appended entry
    that cannot yet have been struck by anything, e.g. `tools.
    remember_location`'s own return value."""
    data = encode_entry(entry)
    data["struck_by"] = None if struck_by is None else struck_by.get(entry.seq)
    return data


def chain_for(memory: MissionMemory, belief_ref: str) -> list[dict[str, object]]:
    """Every entry naming `belief_ref`, oldest first, each carrying its own
    strike state -- the memory chain `belief.tool_api`'s `get_contact_history`
    fold (Decision 5) merges into the belief-side sighting/event history,
    and the same building block `recall_memory` below reuses for its own
    per-entry dicts."""
    struck_by = memory.struck_by
    entries = [entry for entry in memory.entries if entry.belief_ref == belief_ref]
    return [entry_to_dict(entry, struck_by) for entry in entries]


def recall_memory(
    memory: MissionMemory,
    *,
    kind: EntryKind | None = None,
    center: GeoPosition | None = None,
    radius_m: float | None = None,
    include_struck: bool = False,
) -> list[dict[str, object]]:
    """The notepad read (Decision 5): entries newest-first, optionally
    filtered by `kind`, by a radius around `center`, and by
    `include_struck` (default `False` -- current-only, the common case for
    "what do we know now"; a struck entry is history, not standing fact,
    and `recall_memory(include_struck=True)` is how a caller deliberately
    asks for that history instead).

    `center`/`radius_m` are a matched pair -- passing one without the
    other is a caller error (`ValueError`), never a silently-ignored
    partial filter. An entry with no position (`pos is None`, e.g. a
    `fired_on` entry) never matches a radius filter, since there is
    nothing to measure a distance from."""
    if (center is None) != (radius_m is None):
        raise ValueError("center and radius_m must be given together or not at all")

    struck_by = memory.struck_by
    matches: list[Entry] = []
    for entry in memory.entries:
        if not include_struck and entry.seq in struck_by:
            continue
        if kind is not None and entry.kind != kind:
            continue
        if center is not None and radius_m is not None:
            if entry.pos is None:
                continue
            distance_m = math.hypot(entry.pos.x - center.x, entry.pos.z - center.z)
            if distance_m > radius_m:
                continue
        matches.append(entry)

    matches.sort(key=lambda entry: entry.seq, reverse=True)
    return [entry_to_dict(entry, struck_by) for entry in matches]
