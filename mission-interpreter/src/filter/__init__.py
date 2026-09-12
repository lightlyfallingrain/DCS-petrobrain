"""The author-only-knowledge boundary (concept doc's central invariant,
`CLAUDE.md`: "must filter out mission-author-only knowledge... before it
reaches the crew layer").

Takes MI-1's raw parsed tree (`miz.tree.RawMission`) and produces a
"crew-available" filtered version (`crew_available.CrewAvailableMission`)
that drops `Group.hidden`/`hiddenOnPlanner`/`hiddenOnMFD` groups and
`lateActivation` groups entirely -- their existence must not appear
anywhere in the filtered output. `trigrules.py` parses `trigrules`' raw
`predicate`-string tree directly (Decision 1a) for research/debugging
purposes only; raw `trigrules` data is never surfaced in the crew-available
output this package produces.

**Explicitly out of scope: `mission["trig"]`** (`RawMission.trig_raw`).
Per the plan's Decision 5, this newly-discovered generated-Lua-source table
is not parsed or filtered here -- it is a documented gap, not an oversight.
The architect's reasoning (see `plans/mission-interpreter/plan.md` Decision
5): `trig` looks like a Mission-Editor-compiled/flattened artifact of
`trigrules` (same predicates, same DictKey cross-references), not an
independent authoring surface, so the residual exposure of leaving it
unfiltered is bounded to a `trigrules`-correctness bug, not a `trig`-
specific leak -- as long as `trig_raw` itself is never copied into a
crew-available output. This is not a permanent closure: before this
filter's output is trusted for actual play (not just schema validation), a
dedicated investigator pass on `trig` vs. `trigrules` runtime authority is
still owed (see Decision 5's own "not blocking, not closed" framing).
"""

from filter.crew_available import CrewAvailableMission, filter_crew_available

__all__ = ["CrewAvailableMission", "filter_crew_available"]
