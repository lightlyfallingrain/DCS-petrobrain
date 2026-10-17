"""The documented, enumerable BL-5 tool surface -- `plans/bl5-tool-api/
plan.md`. `belief.tools` has always had these twelve functions (nine since
BL-2/BL-4, three new as of this milestone); what was missing was the actual
artifact a brain-layer prototype or a future transport can read to answer
"what tools exist and what do they do" without grepping `tools.py`'s
docstrings. `TOOL_SET` is that artifact: a `name -> description -> callable`
registry, deliberately **transport-agnostic** (Decision 1 -- no HTTP this
milestone; the registry is what a thin HTTP/RPC adapter would wrap later,
not a replacement for one).

**This is provisional scaffolding, not a frozen contract.** Per the plan's
Second-Order Effect note, the tool-set freeze point is BL-6, not BL-5 --
BL-5a's `say`/`ask_player` and BL-6's `scan_area`/`get_task_status`/
`cancel_task` (`plans/bl6-commands-inspect-adapt/plan.md`) are expected to
extend `TOOL_SET`, not be blocked by it. With BL-6 landed, `TOOL_SET` is
now the frozen surface `plans/body-layer/plan.md` §3.3 names in
full.

Descriptions below are taken verbatim from `plans/body-layer/plan.md` §3.3
where that section already wrote one; the three net-new tools' descriptions
are written fresh, matching that section's plain-language style.

**BL-7** (`plans/bl7-mission-phase-relevance/plan.md`) considered and
rejected adding a `get_mission_phase` tool here: current mission phase is a
single global value, a strict id-less subset of what `get_situation`
already returns, so it was folded into `get_situation`'s facts payload
instead (`facts["mission_phase"]`) -- `TOOL_SET` itself is unchanged by
that milestone.

**BL-8 (`plans/bl8-mission-memory/plan.md` Decision 5) takes `TOOL_SET`
15 -> 17, and does both halves BL-7's precedent might seem to argue
against in one move.** `get_contact_history` is folded rather than given
a sibling -- but that is not this milestone repeating BL-7's reasoning,
it is the same reasoning reaching the opposite conclusion for a different
shape of question: BL-7's mission phase was *"a strict id-less subset of
what `get_situation` already returns"* -- redundant information, so
folding it cost nothing. A contact's mission-memory chain is not a subset
of its sighting/event history; it is the *same question* ("what do we know
about this contact's history") with the *same key* (`contact_id`), so
giving it a second tool would be the duplication, not the fold. Where BL-7
found a subset it declined a tool; here `get_contact_history_with_memory`
below folds a second source answering the identical question under the
identical key.

That reasoning has no purchase on the two genuinely new tools,
`recall_memory`/`remember_location`: a mark, or a group belief has
forgotten entirely, has no live contact id to key on at all, so there is
no existing tool's question for either to be a subset of. Mission memory
is, in the explore conversation's own words, *"the third queryable store
beside belief and the world model"* -- a store that answers questions
belief cannot answer, not a view onto one it already can. Reuse where it
is a subset (the fold); extend where it is a new store (the two new
tools). `mission_memory/` is this project's second deliberate, documented
extension of the BL-6 freeze, after BL-7 chose not to be the first."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from belief import tools
from belief.contacts import ContactStore
from mission_memory import query as mission_memory_query
from mission_memory import tools as mission_memory_tools
from mission_memory.store import MissionMemory


@dataclass(frozen=True)
class ToolSpec:
    """One named tool: its brain-facing name (may differ from the
    `tools.py` function name it maps to, e.g. `poll_events` ->
    `tools.list_events`, per Decision 4), a plain-language description, and
    the callable itself."""

    name: str
    description: str
    fn: Callable[..., object]


def _history_sort_key(entry: dict[str, object]) -> float:
    """`tools.get_contact_history`'s own private sort key, duplicated here
    rather than imported: it is one line, and importing a private name
    across a module boundary for one line is the wrong kind of DRY --
    the same judgement `implementation.md`'s point 5 already made for
    `marks._mark_position` versus `admission._build_entry_position`."""
    value = entry.get("start_sim", entry.get("t_sim", 0.0))
    assert isinstance(value, float)
    return value


def get_contact_history_with_memory(
    store: ContactStore, memory: MissionMemory, contact_id: str
) -> list[dict[str, object]]:
    """The `get_contact_history` fold (Decision 5): `tools.
    get_contact_history`'s belief-side sighting/event history, merged with
    this contact's mission-memory chain (`mission_memory.query.chain_for`)
    into one oldest-first ordering. Each memory entry is tagged
    `"type": "memory"` so a caller can tell the two sources apart the same
    way it already tells `"sighting"` from `"event"`; its own `struck_by`
    (from `chain_for`) carries the strike state the fold's description
    promises. An unknown `contact_id` returns `[]` for both halves, same
    as `tools.get_contact_history` alone -- this function adds a second
    source, it does not change the unknown-id behaviour of the first."""
    history = tools.get_contact_history(store, contact_id)
    chain = mission_memory_query.chain_for(memory, contact_id)
    for memory_entry in chain:
        memory_entry["type"] = "memory"
    merged = history + chain
    merged.sort(key=_history_sort_key)
    return merged


TOOL_SET: list[ToolSpec] = [
    ToolSpec(
        name="get_contacts",
        description=(
            "List current contacts, most-recently-seen first, optionally "
            "filtered to 'visible' or 'watched'."
        ),
        fn=tools.get_contacts,
    ),
    ToolSpec(
        name="describe_contact",
        description="Everything currently known about one contact, by id.",
        fn=tools.describe_contact,
    ),
    ToolSpec(
        name="get_contact_history",
        description=(
            "A contact's sighting-span and lifecycle-event history, oldest "
            "first, folded with its mission-memory chain (BL-8) -- entries "
            "marked 'memory' carry their own strike state."
        ),
        fn=get_contact_history_with_memory,
    ),
    ToolSpec(
        name="find_contact",
        description=("Search contacts by perceived classification text (e.g. 'T-72')."),
        fn=tools.find_contact,
    ),
    ToolSpec(
        name="set_attention",
        description=(
            "Mark a contact's direct attention level (ignore/normal/watch/priority)."
        ),
        fn=tools.set_attention,
    ),
    ToolSpec(
        name="watch_area",
        description=(
            "Register a watched area (a center position + radius, "
            "optionally a sector) that raises the effective attention of "
            "any contact inside it."
        ),
        fn=tools.watch_area,
    ),
    ToolSpec(
        name="get_attention_state",
        description=(
            "A contact's direct attention mark alongside its effective "
            "attention (which an AttentionArea may raise above the direct "
            "mark)."
        ),
        fn=tools.get_attention_state,
    ),
    ToolSpec(
        name="acknowledge_event",
        description="Mark one event acknowledged, by id.",
        fn=tools.acknowledge_event,
    ),
    ToolSpec(
        name="poll_events",
        description="List unacknowledged lifecycle/classification events.",
        fn=tools.poll_events,
    ),
    ToolSpec(
        name="find_place",
        description=(
            "Look up a named place in the world model by text (settlement, "
            "named place, airfield, or navaid). Matching is a plain "
            "substring match, not fuzzy -- a name like 'the LZ' or 'the "
            "ridge to the west' will not resolve."
        ),
        fn=tools.find_place,
    ),
    ToolSpec(
        name="get_situation",
        description=(
            "An aggregate sitrep: contact counts, the highest-attention "
            "contact, unacknowledged event count, and a one-line summary "
            "of our own position."
        ),
        fn=tools.get_situation,
    ),
    ToolSpec(
        name="describe_our_position",
        description=(
            "Our own current position, plus nearby world-model semantic "
            "facts (settlements, roads, water, ridges/valleys)."
        ),
        fn=tools.describe_our_position,
    ),
    ToolSpec(
        name="scan_area",
        description=(
            "Ask Petrovich to search, and report whether something "
            "relevant is subsequently found in a named area (a center "
            "position + radius, optionally a sector). This does NOT aim "
            "Petrovich at that area -- he decides where to look, this only "
            "scopes which of his own findings count as satisfying the "
            "request. A later 'failed' status means nothing was confirmed "
            "by the deadline, never that the area was confirmed empty."
        ),
        fn=tools.scan_area,
    ),
    ToolSpec(
        name="get_task_status",
        description=(
            "The current status of a scan_area task (pending/succeeded/"
            "failed/cancelled), by id. 'failed' means nothing was "
            "confirmed by the deadline -- never 'confirmed empty', since "
            "Petrovich's search was never aimed at the requested area."
        ),
        fn=tools.get_task_status,
    ),
    ToolSpec(
        name="cancel_task",
        description=(
            "Cancel a still-pending scan_area task, by id, and stop "
            "watching the area it registered."
        ),
        fn=tools.cancel_task,
    ),
    # BL-8 (`plans/bl8-mission-memory/plan.md`) -- the second deliberate
    # extension of the BL-6 freeze, after BL-7 chose not to be the first.
    ToolSpec(
        name="recall_memory",
        description=(
            "Read the mission-memory notepad: entries newest-first, "
            "optionally filtered by kind, by a radius around a position, "
            "and by current-only (default) versus include-struck. For "
            "marks, dropped contacts, and anything else belief can no "
            "longer answer for."
        ),
        fn=mission_memory_tools.recall_memory,
    ),
    ToolSpec(
        name="remember_location",
        description=(
            "Have Petrovich mark a location in mission memory, the way a "
            "pilot 'mark here'/'mark target' voice command does -- "
            "anchor='ownship' (default) marks our own current position; "
            "anchor='target' marks the given contact_id's believed "
            "position and requires contact_id."
        ),
        fn=mission_memory_tools.remember_location,
    ),
]
