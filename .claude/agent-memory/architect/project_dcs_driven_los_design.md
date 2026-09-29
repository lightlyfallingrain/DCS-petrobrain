---
name: project_dcs_driven_los_design
description: X-B29 (DCS-driven LOS) plan's key architectural finding — the no-omniscience boundary splits where a live per-unit LOS feed can be consumed, and the "fix" it was pitched as already shipped
metadata:
  type: project
---

Plan: `plans/dcs-driven-los/plan.md` (2026-09-29).

**The load-bearing finding**: `geometry.line_of_sight_clear` has two callers in body-layer —
`visibility.py::check_visibility` gate 4 (has a `WorldObjectCandidate` with real DCS identity,
pre-no-omniscience-boundary) and `belief/contacts.py::tick`'s engagement term (only has a
`Contact`'s belief-estimated `GeoPosition`, no DCS object id — `Contact` structurally cannot carry
one). A live, DCS-unit-keyed LOS feed can only ever be joined at the first call site. The second
stays on world-model's offline `sample_grid`-based primitive forever, by invariant, not by choice.
Any future plan that touches LOS should check which of these two call sites it means — "line of
sight" is not one thing in this codebase, it's these two, with different reachable data.

**Effort/value catch**: the debug report this was pitched as fixing
(`plans/missed-aaa-detection/debug.md`) already has a shipped mitigation — `_TERRAIN_TOLERANCE_M =
12.0` in `world-model/src/query/line_of_sight.py`, merged before this plan was written. Always
check whether the bug a new plan cites as motivation is still open before sizing the plan's value
around it — read the target file's current state, not the debug report's "not applied" framing at
the top, which can go stale the moment a later commit lands the fix.

**Join-key precedent worth reusing whenever a new aircraft-layer feed needs to correlate against
`/world_objects/latest`**: use `unit_name` (`Unit:getName()` / `UnitName`), never `object_id` (the
`LoGetWorldObjects` `pairs()` key, explicitly flagged unconfirmed for cross-poll stability).
`naked_eye_source.py::_resolve_velocity_by_object_id` already established this for the unit-velocity
feed (`plans/movement-detection/plan.md` Decision 1) — join by `unit_name`, compute a skew between
the two feeds' own `dcs_model_time_s`, drop to `None` past a threshold. New cross-feed joins should
copy that shape rather than re-derive it.

**Coordinator correction mid-task, worth remembering as a pattern**: an investigator's "X has no
route at all" can overstate what was actually tested. The Windows session confirmed two specific
calls (`world.searchObjects`, `land.isVisible`) exclude trees; the user separately supplied
observational evidence (F10 map tree rendering, per-tree collision, AI Petrovich's 9K113 blocked by
trees) that the *engine* holds tree geometry and at least one shipped path tests LOS against it. The
honest framing is "no exposed scripting-API call has been found yet," not "unavailable" — and the
plan should name concrete next probes (here: characterise `Controller.isTargetDetected`/
`getDetectedTargets` even though it's the wrong shape, and try `land.getIP` into canopy) rather than
closing the question or building a permanent workaround that assumes it's closed.
