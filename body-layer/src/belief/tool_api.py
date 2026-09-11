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
now the frozen surface `docs/concept/PETROBRAIN_RUNTIME.md` §3.3 names in
full.

Descriptions below are taken verbatim from `plans/body-layer/plan.md` §3.3
where that section already wrote one; the three net-new tools' descriptions
are written fresh, matching that section's plain-language style."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from belief import tools


@dataclass(frozen=True)
class ToolSpec:
    """One named tool: its brain-facing name (may differ from the
    `tools.py` function name it maps to, e.g. `poll_events` ->
    `tools.list_events`, per Decision 4), a plain-language description, and
    the callable itself."""

    name: str
    description: str
    fn: Callable[..., object]


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
            "A contact's sighting-span and lifecycle-event history, oldest first."
        ),
        fn=tools.get_contact_history,
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
]
