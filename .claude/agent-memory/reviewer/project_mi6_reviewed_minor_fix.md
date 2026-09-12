---
name: mi6-reviewed-minor-fix
description: MI-6 runtime compilation reviewed; one required fix on Tagged[str] | None collapsing rejected-vs-never-asked states.
metadata:
  type: project
---

MI-6 (`mission-interpreter/src/runtime/compact.py`/`compile.py`) reviewed 2026-09-12 against
`plans/mi6-runtime-compilation/plan.md` (`48a2f5c`). Verdict: APPROVED WITH MINOR FIXES.

Core invariants held: epistemic status survives player confirmation (only `confidence` is raised,
`epistemic_status` never upgraded), all four `player_intent` question-id reconciliation paths
(`ownship`/`purpose`/`task`/`threat_{index}`) genuinely match MI-5's `questions.py`/`console.py`
shape, `compile.py` is a pure mapping with zero model/world-model calls, `current_phase`/
`priorities`/`intended_plan` correctly absent per the plan's resolved decisions.

Required fix: `purpose`/`task` fields (`Tagged[str] | None`) collapse "MI-4 never guessed" and
"MI-4 guessed, player explicitly rejected it" into the same bare `None` — real information loss
for a future BL-7 consumer (a rejected guess is an active correction, not mere absence of data).
Root cause: the plan's own prose ("clears to `None` with `epistemic_status` `UNKNOWN`") implied a
`Tagged` wrapper distinct from bare `None`-for-never-populated, but the plan's field-type listing
in the same doc declared a bare-`None`-compatible type — an internal plan inconsistency the
Implementer correctly flagged rather than silently resolving, but then picked the reading that
loses the distinction. Recommended fix: `Tagged[str | None]` (always-wrapped, matching every other
field on the dataclass) so rejection carries non-empty `basis=(..., "player:rejected")` while
never-asked keeps `basis=()`.

**Pattern to watch for in future reviews**: any "reject/clear a guess back to unknown" reconciliation
that uses a plain `None`/absent-value sentinel for the cleared state — check whether that sentinel
is now indistinguishable from a completely different provenance state (never-had-data vs.
actively-corrected). This project's epistemic-tagging convention ([[reviewer's mi4/mi5 memories]])
exists precisely to keep these states distinct; a bare optional collapses them back together.
