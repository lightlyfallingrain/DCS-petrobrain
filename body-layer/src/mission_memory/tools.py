"""The two new brain-facing tool functions -- plan Decision 5 --
`recall_memory` and `remember_location`. This is the module that imports
`belief` on this package's one allowed direction (Decision 1) so that
`belief/tool_api.py` -- the sole importer of `mission_memory` on the
other side of that boundary -- can register these two as ordinary
`ToolSpec` entries without any other module inside `belief/` gaining a
dependency on this package.

**`remember_location` is not `marks.mark_here`/`marks.mark_target` with a
new name wrapped around them -- it dispatches to whichever one `anchor`
asks for.** The pilot's voice path reaches the two forms separately
(`crew_console._handle_mark_here`/`_handle_mark_target`, each via its own
injected closure, per `plans/bl8-mission-memory/implementation.md`'s point
1); the brain names its target explicitly (`contact_id`) rather than
relying on `crew_console`'s own "currently selected target" notion
(`_active_attack_target_task`), since the brain has no such pilot-UI
concept of a selection -- it already knows which contact it means."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.mission_phase import MissionPhaseInfo
from mission_memory import marks, query
from mission_memory.admission import to_phase_info
from mission_memory.entries import EntryKind, MarkAnchor
from mission_memory.query import entry_to_dict
from mission_memory.store import MissionMemory
from perception.geometry import GeoPosition
from perception.source import OwnshipState


def recall_memory(
    memory: MissionMemory,
    *,
    kind: EntryKind | None = None,
    center: GeoPosition | None = None,
    radius_m: float | None = None,
    include_struck: bool = False,
) -> list[dict[str, object]]:
    """The brain-facing `recall_memory` tool (Decision 5): the notepad
    read -- a thin pass-through to `query.recall_memory`, kept as its own
    function here (rather than registering `query.recall_memory` directly
    in `TOOL_SET`) so the brain-facing surface is this module and not a
    second, parallel entry point into the read-only query layer."""
    return query.recall_memory(
        memory,
        kind=kind,
        center=center,
        radius_m=radius_m,
        include_struck=include_struck,
    )


def remember_location(
    memory: MissionMemory,
    ownship: OwnshipState,
    contacts: ContactStore,
    now_sim: float,
    *,
    anchor: MarkAnchor = "ownship",
    contact_id: str | None = None,
    theatre: str | None = None,
    phase: MissionPhaseInfo | None = None,
    enrichment: EnrichmentContext | None = None,
    label: str | None = None,
) -> dict[str, object] | None:
    """The brain-facing `remember_location` tool (Decision 5): the same
    commanded-mark path the pilot's voice command reaches, under one name
    with an `anchor` switch -- `anchor="ownship"` (the default) calls
    `marks.mark_here`; `anchor="target"` calls `marks.mark_target` against
    `contact_id`, which is then required (`ValueError` if omitted -- a
    caller error in how the tool was invoked, not a missing-input case the
    tool itself can answer the way `mark_target`'s unknown-id case can).

    Returns `None` for an unknown `contact_id` under `anchor="target"`,
    exactly mirroring `marks.mark_target`'s own "no such contact" case --
    never raises for that one. The returned dict is `query.entry_to_dict`'s
    shape with `struck_by=None` (a just-written entry cannot yet be
    struck), the same per-entry shape `recall_memory` returns, so a caller
    reading both tools' results does not have to learn two shapes."""
    phase_info = to_phase_info(phase)
    if anchor == "target":
        if contact_id is None:
            raise ValueError("anchor='target' requires contact_id")
        entry = marks.mark_target(
            memory,
            contacts,
            contact_id,
            now_sim,
            theatre=theatre,
            phase=phase_info,
            enrichment=enrichment,
            label=label,
        )
    else:
        entry = marks.mark_here(
            memory,
            ownship,
            now_sim,
            theatre=theatre,
            phase=phase_info,
            enrichment=enrichment,
            label=label,
        )
    if entry is None:
        return None
    return entry_to_dict(entry)
