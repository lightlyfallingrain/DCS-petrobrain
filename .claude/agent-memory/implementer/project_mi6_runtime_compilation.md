---
name: mi6-runtime-compilation
description: MI-6 (last planned MI stage) compaction module — field-type ambiguity in the plan, PlaceMatch.name key, ownship-candidates-always-empty confirmation
metadata:
  type: project
---

MI-6 (`mission-interpreter/src/runtime/{compact,compile}.py`) compiles the full
`MissionUnderstanding` into the compact `RuntimeMissionUnderstanding` (`current_mission`). Pure
deterministic mapping, no model/world-model call. Substantive work is folding MI-5's
`player_intent` answers back into `ownship`/`purpose`/`task`/`expected_threats` (nothing upstream
does this — `console.run` only appends to `player_intent`).

- **Field-type vs. prose mismatch in a locked plan**: plan text said rejecting a low-confidence
  purpose/task should "clear the compact field to `None` with `epistemic_status` `UNKNOWN`," but
  the plan's own declared field type is `Tagged[str] | None` (outer `None` already means "never
  populated"), not `Tagged[str | None]` (which could carry an `UNKNOWN` status distinct from
  never-asked). Implemented the literal type signature (whole field -> `None`), noted the
  resulting "never asked" vs. "asked and rejected" collapse as a discovery, did not silently
  redesign the type to fix it. When a locked plan's prose and its own declared type disagree,
  prefer the declared type and flag the discrepancy rather than guessing which one is "more right."
- **`WorldRef.name_matches[i]["name"]`** is the correct key for a place name — confirmed by
  reading `world-model/src/query/search.py`'s `PlaceMatch.name: str` field directly, not just
  trusting the mission-interpreter-side plan's description of the wire shape (that side declares
  it as a raw untyped `dict[str, Any]` on purpose, see `world_enrich/schema.py`'s `WorldRef`
  docstring, so cross-check the actual producer schema before keying into it).
- `player_intent/questions.py`'s `_ownship_candidates` really is always empty (verified by
  reading, not from memory/plan-summary alone) — the `ownship` question is always `kind="free_text"`
  in this codebase today. Reconciliation code still checks `isinstance(answer.parsed, str)`
  defensively since a future `"choice"` answer would also be a `str` (the matched option) and
  needs no code change.
- `mission-interpreter/CLAUDE.md`'s Structure section was missing a `src/player_intent/` (MI-5)
  bullet entirely when this stage started — added it alongside the new `src/runtime/` bullet
  rather than leaving the gap; worth checking for similarly-missing Structure bullets before
  assuming a subproject's CLAUDE.md Structure section is fully current.
