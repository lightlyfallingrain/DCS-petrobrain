---
name: los-hook-statics-round2-approved
description: Round-2 APPROVED; a pcall's loss-of-candidates risk is bounded by whether the guarded call can fail open and whether the chunk can yield.
metadata:
  type: project
---

`fix/los-hook-statics` round 2 (2026-10-06), reviewed `928a2c6` (brief named `5ec13eb`; the delta was
a stray config commit the orchestrator later moved to `main`). APPROVED, no required fixes.

**The technique that settled the round's one real question.** The brief asked whether an *uncounted*
`pcall` site can distort a measurement, when a sibling site got a counter. Do not answer it by
severity intuition. Answer it per site, from the control flow:

1. **Does the guarded call fail open or fail closed?** `unit:getID()`'s failure path is
   `if (not okI) or playerId == nil or uid ~= playerId then consider(...)` — it *admits*. A site that
   fails open cannot lose a candidate, so it needs no counter however often it fails. Check the
   `or`-chain, not the `pcall`.
2. **Can the enclosing scope yield between enumeration and use?** The DCS mission-scripting chunk runs
   synchronously inside one `net.dostring_in` with no yield, so nothing enumerated can die mid-loop. A
   `grp:getUnits()` that errors was therefore handed over already invalid — and a dead group has no
   live units whether it errors or returns `{}`, so counting it recovers nothing. This collapses a
   scary-sounding "many small groups could bleed candidates" into "needs an engine bug".
3. **Is a systematic failure already inferable from fields on the same line?** Here yes: a blanket
   unit-side failure makes `statics_in_bubble == objects_in_bubble`. A free cross-check beats a new
   counter.
4. **Then ask what the counted site has that the others lack.** `coalition.getGroups` has a real
   mechanism (API absent/erroring per side — the same thing that motivated `staticEnumFailures`),
   loses a whole side, and is *not* inferable, because a side with no units is legitimate.

**Also found, and it is this role's recurring pattern:** the counter's comment justified the
granularity by "comparability with `staticEnumFailures` (also per side, max 3)" — true, aesthetic, and
not what makes the choice right. Correct conclusion, non-load-bearing reason. Same window: a
"deliberately duplicated, do not tidy" ruling was recorded in `implementation.md` while the Lua's own
declaration comment said the pair "mirrors" the chunk's defaults — i.e. the file where the next reader
meets it pointed the opposite way, and the round had just added two worked splices three lines below.
**Where a ruling is recorded decides whether it holds.**

**Splice boundary check, cheap and worth repeating:** when a constant moves from a re-typed literal to
a `string.format`-spliced one, do not reason about the comparison — paste the generated prefix into a
Lua interpreter and run the boundary (`10000.0`, `9999.9999`, `10000.0001`, and `10000 == 10000.0`).
Confirmed inclusive-at-boundary and numerically identical in one command.

Left as optional rather than required: no automated test defends either constant splice
(`tests/test_line_of_sight_hook_lua.py` is five text assertions over the Lua and already guards the
sibling `SET_LOOK_TEMPLATE` splice, so the idiom exists). Ruled a maintenance-regression risk, not a
runtime one, and round 1 had shipped the cap splice the same way — so requiring it would be a round
trip that does not affect the pilot's flight. See [[project_los_hook_statics_review]].
