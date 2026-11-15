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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal, TypeVar

import tuning
from belief import tools
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from mission_memory import query as mission_memory_query
from mission_memory import tools as mission_memory_tools
from mission_memory.store import MissionMemory
from perception.geometry import GeoPosition


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


# ---------------------------------------------------------------------------
# BR-2 Stage 2 (`plans/brain-tool-calls/plan.md` D2/D5) -- the brain-facing
# query-tool surface. `TOOL_SET` above is body's own tool registry, keyed
# by name/description/callable with no calling convention of its own (see
# `.claude/agent-memory/implementer/project_tool_set_has_no_dispatcher_
# yet.md`: nothing called a `ToolSpec.fn` generically before this). `
# BrainTool` is BR-2's calling convention: `invoke(ctx, args)` where `ctx`
# is bound entirely by body (`run_brain_tool`'s closure in `body.py`, D2)
# and `args` are the model's own (already-`belief.brain_reply`-validated)
# keyword values -- never a raw `ToolSpec.fn` call with model arguments.
# D5's seven query tools, one hand-written adapter each -- names are
# test-enforced to equal a `TOOL_SET` name (`test_tool_api.py`).
# `remember_location` is Stage 6, deliberately not exposed here yet (D8).
# ---------------------------------------------------------------------------

#: `plans/brain-tool-calls/plan.md` D5 -- `recall_memory`'s "near a place"
#: filter radius. Behaviour-affecting (it decides which memory entries
#: "near Gemerek" surfaces), so it goes through the tuning mechanism
#: rather than as a bare literal, per root `CLAUDE.md`'s standing rule --
#: unmeasured, a first guess pending flight evidence.
RECALL_MEMORY_NEAR_RADIUS_M: float = tuning.real(
    "belief.tool_api.RECALL_MEMORY_NEAR_RADIUS_M",
    5000.0,
    lo=500.0,
    hi=50000.0,
    status="agreed-guess",
)

#: D2's compactness rule -- a tool observation's own list is capped here,
#: with an "and N more" note for the rest, so a turn's prompt never grows
#: with the size of the contact store/memory ledger.
BRAIN_TOOL_LIST_CAP: int = 5

ParamKind = Literal[
    "str", "int", "bool", "enum", "contact_ref", "place_ref", "memory_ref"
]


@dataclass(frozen=True)
class ParamSpec:
    """One `BrainTool` parameter -- serialisable to the JSON-schema
    subset `brain-layer`'s `ToolLoopDecider` shows the model (D2), and the
    exact shape `belief.brain_reply`'s tool-call validator (D3) checks a
    model-supplied value against: type/enum/range/length per the kind
    below, and -- for the three `*_ref` kinds -- offered-this-turn
    membership (`BrainTurn.offered`), never "any id that exists"."""

    name: str
    kind: ParamKind
    required: bool = False
    choices: tuple[str, ...] = ()
    lo: int | None = None
    hi: int | None = None
    max_len: int = 40
    #: `recall_memory`'s `near` parameter only (D5: `place_ref | "ownship"`)
    #: -- the one place a `*_ref` kind's value may legally be something
    #: other than an offered handle. Kept as an explicit per-param flag
    #: rather than a special-cased parameter name, so the validator has
    #: one rule to read rather than a name to recognise.
    allow_ownship: bool = False


@dataclass(frozen=True)
class ToolObservation:
    """What a `BrainTool.invoke` call hands back to the brain turn -- D2's
    "compact, model-facing projection": a one-line `summary` (never a raw
    `x`/`z`, never more than `BRAIN_TOOL_LIST_CAP` items spelled out), the
    handles this call introduced (added to `BrainTurn.offered`), and,
    for a `find_*` call that returned two or more candidates,
    `candidate_texts` -- handle -> that candidate's own short identifying
    text, which is exactly what `belief.brain_reply`'s ambiguity-evidence
    rule (D3) needs to reuse `_validate_pick`'s existing substring test
    against, the same way `belief.utterance.ReferenceCandidate.why` already
    serves `_validate_pick` on the BR-1 path."""

    summary: str
    handles: tuple[str, ...] = ()
    candidate_texts: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolContext:
    """Bound entirely by body, never accepted from the wire (D2) -- the
    closure `body.py`'s `_run_brain_tool_fn` builds reads `store`/
    `enrichment` *live* off the running `ConsolePerceptionRunner`, the same
    "never capture, always read live" rule `_mark_here_fn` already follows,
    and passes `now_sim` fresh per call.

    `place_positions` is this turn's own place-handle -> resolved-position
    cache, populated by `_find_place_adapter` and read by
    `_recall_memory_adapter`'s `near` resolution -- it lets one tool call's
    result be used as another's input without ever putting a coordinate on
    the wire to the model (D2's "no exposed parameter is a coordinate"):
    the model only ever says `near="PLACE_7"`, never a position. Mutable
    (unlike most dataclasses in this codebase) because it accumulates
    within one turn's own rounds; a fresh `ToolContext` is built by
    `body.py` for each round, so nothing here is ever shared *across*
    turns."""

    store: ContactStore
    enrichment: EnrichmentContext | None
    memory: MissionMemory
    now_sim: float
    place_positions: dict[str, GeoPosition] = field(default_factory=dict)


@dataclass(frozen=True)
class BrainTool:
    """One tool the brain may call -- D2's calling convention. `name` must
    equal a `TOOL_SET` entry's `name` (test-enforced, `test_tool_api.py`):
    this is a second, narrower surface over the same underlying functions,
    not a parallel naming scheme."""

    name: str
    params: tuple[ParamSpec, ...]
    invoke: Callable[[ToolContext, Mapping[str, object]], ToolObservation]


_T = TypeVar("_T")


def _cap(items: list[_T], limit: int = BRAIN_TOOL_LIST_CAP) -> tuple[list[_T], int]:
    """D2's cap, shared by every adapter below: the first `limit` items,
    plus how many were left off (0 if none)."""
    return items[:limit], max(0, len(items) - limit)


def _and_more(count: int) -> str:
    return "" if count == 0 else f", and {count} more"


def _find_contact_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    """`plans/brain-tool-calls/performance-review.md`'s required fix:
    `tools.find_contact`'s own `limit` truncates *before* enrichment, so
    this adapter enriches only the `BRAIN_TOOL_LIST_CAP` contacts it will
    actually show. The unenriched call (`enrichment` omitted) is the total
    admitted count for the "and N more" note -- cheap, since it skips
    `_add_enrichment_facts`'s world-model work entirely, and counted before
    either call truncates."""
    text = str(args["text"])
    total = len(tools.find_contact(ctx.store, text, ctx.now_sim))
    shown = tools.find_contact(
        ctx.store, text, ctx.now_sim, ctx.enrichment, limit=BRAIN_TOOL_LIST_CAP
    )
    extra = max(0, total - len(shown))
    if not shown:
        return ToolObservation(summary="no matching contacts")
    handles: list[str] = []
    candidate_texts: dict[str, str] = {}
    lines: list[str] = []
    for result in shown:
        cid = str(result["facts"]["id"])
        text_line = str(result["summary"])
        handles.append(cid)
        candidate_texts[cid] = text_line
        lines.append(f"{cid}: {text_line}")
    summary = "; ".join(lines) + _and_more(extra)
    return ToolObservation(
        summary=summary,
        handles=tuple(handles),
        candidate_texts=candidate_texts if len(handles) >= 2 else {},
    )


def _list_contacts_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    """Same fix as `_find_contact_adapter` above, for `tools.get_contacts`."""
    filter_arg = args.get("filter")
    contact_filter = None if filter_arg is None else str(filter_arg)
    total = len(tools.get_contacts(ctx.store, ctx.now_sim, contact_filter))  # type: ignore[arg-type]
    shown = tools.get_contacts(
        ctx.store,
        ctx.now_sim,
        contact_filter,  # type: ignore[arg-type]
        ctx.enrichment,
        limit=BRAIN_TOOL_LIST_CAP,
    )
    extra = max(0, total - len(shown))
    if not shown:
        return ToolObservation(summary="no contacts")
    handles: list[str] = []
    lines: list[str] = []
    for result in shown:
        cid = str(result["facts"]["id"])
        handles.append(cid)
        lines.append(f"{cid}: {result['summary']}")
    return ToolObservation(
        summary="; ".join(lines) + _and_more(extra), handles=tuple(handles)
    )


def _describe_contact_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    contact_id = str(args["contact_ref"])
    result = tools.describe_contact(ctx.store, contact_id, ctx.now_sim, ctx.enrichment)
    if result is None:
        return ToolObservation(summary=f"{contact_id}: no such contact")
    return ToolObservation(
        summary=f"{contact_id}: {result['summary']}", handles=(contact_id,)
    )


def _get_contact_history_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    contact_id = str(args["contact_ref"])
    entries = get_contact_history_with_memory(ctx.store, ctx.memory, contact_id)
    if not entries:
        return ToolObservation(
            summary=f"{contact_id}: no history", handles=(contact_id,)
        )
    recent = entries[-BRAIN_TOOL_LIST_CAP:]
    extra = max(0, len(entries) - len(recent))
    lines = [_describe_history_entry(entry) for entry in recent]
    summary = f"{contact_id}: " + "; ".join(lines) + _and_more(extra)
    return ToolObservation(summary=summary, handles=(contact_id,))


def _describe_history_entry(entry: dict[str, object]) -> str:
    """One `get_contact_history_with_memory` row, compactly -- no `pos`
    (every row that carries one is a memory-chain fold entry, and position
    is a coordinate, D2's "no raw x/z")."""
    kind = entry.get("type")
    if kind == "sighting":
        return f"seen by {entry.get('source')}"
    if kind == "event":
        return f"{entry.get('kind')}"
    if kind == "memory":
        return _describe_memory_entry(entry)
    return str(kind)


def _describe_memory_entry(entry: dict[str, object]) -> str:
    """A mission-memory entry dict (`mission_memory.query.entry_to_dict`'s
    shape), compactly and with no coordinates -- used by both the history
    fold above and `_recall_memory_adapter` below."""
    mem_kind = entry.get("kind")
    payload = entry.get("payload")
    parts = [str(mem_kind)]
    if isinstance(payload, dict) and mem_kind == "mark":
        label = payload.get("label")
        if label:
            parts.append(f"'{label}'")
    pos = entry.get("pos")
    if isinstance(pos, dict):
        landmark = pos.get("landmark")
        if landmark:
            parts.append(str(landmark))
    if entry.get("struck_by") is not None:
        parts.append("struck")
    return ", ".join(parts)


def _memory_entry_handle(entry: dict[str, object]) -> str:
    """`MARK_<index>` for a mark entry (matching the spoken "mark one"
    numbering, `MarkPayload.index`), `MEM_<seq>` for every other kind."""
    if entry.get("kind") == "mark":
        payload = entry.get("payload")
        if isinstance(payload, dict):
            index = payload.get("index")
            if isinstance(index, int):
                return f"MARK_{index}"
    return f"MEM_{entry.get('seq')}"


def _find_place_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    if ctx.enrichment is None:
        return ToolObservation(summary="world model not available")
    text = str(args["text"])
    results = tools.find_place(ctx.enrichment, text)
    shown, extra = _cap(list(results))
    if not shown:
        return ToolObservation(summary="no matching place")
    handles: list[str] = []
    candidate_texts: dict[str, str] = {}
    lines: list[str] = []
    for result in shown:
        facts = result["facts"]
        feature_id = facts.get("feature_id")
        name = str(facts.get("name"))
        handle = (
            f"PLACE_{feature_id}"
            if feature_id is not None
            else f"PLACE_{abs(hash(name)) % 100000}"
        )
        position = facts.get("position")
        if isinstance(position, dict):
            dcs = position.get("dcs")
            if isinstance(dcs, dict):
                ctx.place_positions[handle] = GeoPosition(
                    x=float(dcs["x"]), z=float(dcs["z"]), alt_m=0.0
                )
        handles.append(handle)
        text_line = str(result["summary"])
        candidate_texts[handle] = text_line
        lines.append(f"{handle}: {text_line}")
    return ToolObservation(
        summary="; ".join(lines) + _and_more(extra),
        handles=tuple(handles),
        candidate_texts=candidate_texts if len(handles) >= 2 else {},
    )


def _describe_our_position_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    del args  # no parameters
    if ctx.enrichment is None:
        return ToolObservation(summary="world model not available")
    result = tools.describe_our_position(ctx.enrichment)
    return ToolObservation(summary=str(result["summary"]))


def _recall_memory_adapter(
    ctx: ToolContext, args: Mapping[str, object]
) -> ToolObservation:
    kind_arg = args.get("kind")
    include_struck = bool(args.get("include_struck", False))
    near = args.get("near")
    center: GeoPosition | None = None
    radius_m: float | None = None
    if near is not None:
        near_str = str(near)
        if near_str == "ownship":
            if ctx.enrichment is None:
                return ToolObservation(summary="world model not available")
            ownship = ctx.enrichment.ownship
            center = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
        else:
            center = ctx.place_positions.get(near_str)
            if center is None:
                return ToolObservation(
                    summary=f"{near_str}: not a known place this turn"
                )
        radius_m = RECALL_MEMORY_NEAR_RADIUS_M
    entries = mission_memory_tools.recall_memory(
        ctx.memory,
        kind=kind_arg,  # type: ignore[arg-type]
        center=center,
        radius_m=radius_m,
        include_struck=include_struck,
    )
    shown, extra = _cap(list(entries))
    if not shown:
        return ToolObservation(summary="nothing in memory matches")
    handles: list[str] = []
    candidate_texts: dict[str, str] = {}
    lines: list[str] = []
    for entry in shown:
        handle = _memory_entry_handle(entry)
        text_line = _describe_memory_entry(entry)
        handles.append(handle)
        candidate_texts[handle] = text_line
        lines.append(f"{handle}: {text_line}")
    return ToolObservation(
        summary="; ".join(lines) + _and_more(extra),
        handles=tuple(handles),
        candidate_texts=candidate_texts if len(handles) >= 2 else {},
    )


BRAIN_TOOLS: tuple[BrainTool, ...] = (
    BrainTool(
        name="find_contact",
        params=(ParamSpec(name="text", kind="str", required=True, max_len=40),),
        invoke=_find_contact_adapter,
    ),
    BrainTool(
        name="get_contacts",
        params=(
            ParamSpec(
                name="filter", kind="enum", choices=("all", "visible", "watched")
            ),
        ),
        invoke=_list_contacts_adapter,
    ),
    BrainTool(
        name="describe_contact",
        params=(ParamSpec(name="contact_ref", kind="contact_ref", required=True),),
        invoke=_describe_contact_adapter,
    ),
    BrainTool(
        name="get_contact_history",
        params=(ParamSpec(name="contact_ref", kind="contact_ref", required=True),),
        invoke=_get_contact_history_adapter,
    ),
    BrainTool(
        name="find_place",
        params=(ParamSpec(name="text", kind="str", required=True, max_len=40),),
        invoke=_find_place_adapter,
    ),
    BrainTool(
        name="describe_our_position",
        params=(),
        invoke=_describe_our_position_adapter,
    ),
    BrainTool(
        name="recall_memory",
        params=(
            ParamSpec(
                name="kind",
                kind="enum",
                choices=("group", "air_defence", "attack_run", "mark", "fired_on"),
            ),
            ParamSpec(name="near", kind="place_ref", allow_ownship=True),
            ParamSpec(name="include_struck", kind="bool"),
        ),
        invoke=_recall_memory_adapter,
    ),
)

#: Name -> `BrainTool`, for `belief.brain_reply`'s validator and
#: `belief.crew_console`'s dispatch -- both need O(1) lookup, not a scan.
BRAIN_TOOLS_BY_NAME: dict[str, BrainTool] = {tool.name: tool for tool in BRAIN_TOOLS}


def _param_spec_to_dict(param: ParamSpec) -> dict[str, object]:
    return {
        "name": param.name,
        "kind": param.kind,
        "required": param.required,
        "choices": list(param.choices),
        "lo": param.lo,
        "hi": param.hi,
        "max_len": param.max_len,
    }


def serialize_tool(tool: BrainTool) -> dict[str, object]:
    """One `BrainTool` -> the JSON-schema subset `brain-layer` mirrors
    into Ollama's native `tools` (D1's measured form) -- module
    independence: this process never imports `brain-layer/` code, and
    `brain-layer` never imports this one, so the wire carries the whole
    shape rather than either side assuming the other's Python types."""
    return {"name": tool.name, "params": [_param_spec_to_dict(p) for p in tool.params]}


#: Serialised once at import time -- the tool set does not change within a
#: process, so every brain turn's escalation payload reuses this same
#: tuple rather than re-serialising it per round (also keeps the prompt's
#: tool block byte-stable across rounds, R3's KV-cache-reuse point).
BRAIN_TOOL_SPECS: tuple[dict[str, object], ...] = tuple(
    serialize_tool(tool) for tool in BRAIN_TOOLS
)


# ---------------------------------------------------------------------------
# BR-2 Stage 3 (`plans/brain-tool-calls/plan.md` D5) -- the explicit,
# opt-in `handle_command` allowlist. A token not listed here is excluded
# by construction (U2's weapons/sight tokens, every flight token, and
# anything BL-16 adds later, all without a denylist anyone has to
# remember) and gets `unable FIXED_COMMAND_ONLY` (`belief.brain_reply.
# _validate_turn_command`). `name` is test-enforced to equal a
# `belief.crew_console.DISPATCHED_COMMAND_TOKENS` member -- this module
# cannot import `crew_console` to check that itself (the import runs the
# other way), so `test_crew_console.py` carries the check.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrainCommand:
    """One `handle_command` token the brain may dispatch directly, once
    `belief.brain_reply._validate_turn_command` has validated the final
    that names it. `takes_target` is the whole slot schema this stage
    needs: every allowlisted command takes at most one optional `target`
    (a `contact_ref` handle, resolved by the model through a tool call
    first -- D5: "the model never fills descriptor/clock slots when it
    has a resolved id") or no slot at all. `report`'s own richer
    phrasebook slots (`descriptor`/`clock`/`sector`/`relative`/`band`) are
    deliberately **not** exposed yet -- a place slot is Stage 4's own job
    ("A place slot... mapped onto the existing sector/radius filter
    shapes"), and the other four are free-text/enum slots a resolved
    target already makes redundant for every acceptance-set case this
    stage covers. A brain-dispatched `report` is a plain whole-scene
    report today, the same answer `report_all` already gives -- kept as
    its own token (not folded into `report_all`) so Stage 4 can widen
    *this* command's schema without re-adding it to the allowlist."""

    name: str
    takes_target: bool
    #: One-line meaning for the brain-facing command-notes block
    #: (`brain-layer/src/tool_loop_prompts.py`'s `_command_block`,
    #: rendered from this field rather than hand-written prose the two
    #: sides could drift from -- the research note's own open follow-up).
    meaning: str


#: D5's initial set, in the plan's own order. **Every `report_clock_*`/
#: `report_bearing_*` member is the *real* token set this project's
#: `handle_command` actually dispatches, not the plan prose's "1..12"/
#: "north/south/east/west" shorthand**: `belief.crew_console.
#: _CLOCK_REPORT_TOKENS` only ever covers the nine forward hours (no
#: 5/6/7 -- Petrovich cannot see behind the aircraft, the same
#: no-omniscience reason `_CLOCK_SCAN_TOKENS` excludes them), and `_
#: BEARING_REPORT_TOKENS` is the full eight-point compass, not four. Both
#: verified against `crew_console.py` directly (`test_crew_console.py`
#: asserts the match) rather than copied from the plan's illustrative
#: wording.
BRAIN_COMMANDS: tuple[BrainCommand, ...] = (
    BrainCommand(
        name="report",
        takes_target=False,
        meaning="a whole-scene report (no place slot yet, Stage 4)",
    ),
    BrainCommand(name="report_all", takes_target=False, meaning="report everything"),
    BrainCommand(
        name="report_clock_8",
        takes_target=False,
        meaning="report at the 8 o'clock",
    ),
    BrainCommand(
        name="report_clock_9", takes_target=False, meaning="report at the 9 o'clock"
    ),
    BrainCommand(
        name="report_clock_10", takes_target=False, meaning="report at the 10 o'clock"
    ),
    BrainCommand(
        name="report_clock_11", takes_target=False, meaning="report at the 11 o'clock"
    ),
    BrainCommand(
        name="report_clock_12", takes_target=False, meaning="report at the 12 o'clock"
    ),
    BrainCommand(
        name="report_clock_1", takes_target=False, meaning="report at the 1 o'clock"
    ),
    BrainCommand(
        name="report_clock_2", takes_target=False, meaning="report at the 2 o'clock"
    ),
    BrainCommand(
        name="report_clock_3", takes_target=False, meaning="report at the 3 o'clock"
    ),
    BrainCommand(
        name="report_clock_4", takes_target=False, meaning="report at the 4 o'clock"
    ),
    BrainCommand(
        name="report_bearing_n", takes_target=False, meaning="report to the north"
    ),
    BrainCommand(
        name="report_bearing_ne",
        takes_target=False,
        meaning="report to the north-east",
    ),
    BrainCommand(
        name="report_bearing_e", takes_target=False, meaning="report to the east"
    ),
    BrainCommand(
        name="report_bearing_se",
        takes_target=False,
        meaning="report to the south-east",
    ),
    BrainCommand(
        name="report_bearing_s", takes_target=False, meaning="report to the south"
    ),
    BrainCommand(
        name="report_bearing_sw",
        takes_target=False,
        meaning="report to the south-west",
    ),
    BrainCommand(
        name="report_bearing_w", takes_target=False, meaning="report to the west"
    ),
    BrainCommand(
        name="report_bearing_nw",
        takes_target=False,
        meaning="report to the north-west",
    ),
    BrainCommand(
        name="where_is_it",
        takes_target=True,
        meaning="give a positional update on a target, resolved via a tool first",
    ),
    BrainCommand(
        name="follow",
        takes_target=True,
        meaning="watch a resolved target (binoculars up)",
    ),
    BrainCommand(
        name="select_target",
        takes_target=True,
        meaning="select a resolved target for an attack run",
    ),
    BrainCommand(
        name="drop_target", takes_target=False, meaning="drop the current target"
    ),
    BrainCommand(
        name="mark_here", takes_target=False, meaning="mark our own current position"
    ),
    BrainCommand(
        name="mark_target",
        takes_target=True,
        meaning="mark a resolved target's position (or the current target if none given)",
    ),
    BrainCommand(
        name="watch_nearest", takes_target=False, meaning="watch the nearest contact"
    ),
    BrainCommand(
        name="watch_nearest_air_defence",
        takes_target=False,
        meaning="watch the nearest air-defence contact",
    ),
    BrainCommand(name="cancel_task", takes_target=False, meaning="cancel every task"),
    BrainCommand(
        name="cancel_scan", takes_target=False, meaning="cancel the pending scan task"
    ),
    BrainCommand(
        name="cancel_watch", takes_target=False, meaning="cancel the watch task"
    ),
)

#: Name -> `BrainCommand`, for `belief.brain_reply`'s validator.
BRAIN_COMMANDS_BY_NAME: dict[str, BrainCommand] = {
    command.name: command for command in BRAIN_COMMANDS
}


def serialize_command(command: BrainCommand) -> dict[str, object]:
    """One `BrainCommand` -> the wire shape `brain-layer`'s command-notes
    block reads (`tool_loop_prompts._command_block`) -- `token` rather
    than `name`, matching `BrainReply.token`'s own wire field name."""
    return {
        "token": command.name,
        "takes_target": command.takes_target,
        "meaning": command.meaning,
    }


#: Serialised once at import time, same reasoning as `BRAIN_TOOL_SPECS`
#: above -- a process-lifetime-fixed tuple, not re-serialised per round.
BRAIN_COMMAND_SPECS: tuple[dict[str, object], ...] = tuple(
    serialize_command(command) for command in BRAIN_COMMANDS
)
