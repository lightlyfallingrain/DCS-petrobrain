---
name: project-pcall-degradation-without-counter
description: A pcall added for graceful degradation shipped without a paired failure counter, converting a loud failure into a silent one — 1st occurrence at DoD, watch for a 2nd.
metadata:
  type: project
---

`fix/los-hook-statics` (BL-11 Stage 4, Reviewer Required Fix 1): wrapping `coalition.getGroups`/
`grp:getUnits()`/`unit:isExist()`/`unit:getID()` in `pcall` so a per-side enumeration failure
degrades to "fewer candidates" instead of losing the whole poll is the right behaviour — but on its
own it also converts a previously *loud* failure (an uncaught error, logged by the caller) into a
*silent* one, with nothing distinguishing "fewer candidates because fewer were really there" from
"fewer candidates because an enumeration call failed". The fix needed a dedicated counter
(`unitEnumFailures`) mirroring one that already existed for the sibling statics path
(`staticEnumFailures`).

**Why: an isolated agent-memory file was already written about this exact case** in
`reviewer/MEMORY.md` ("pcall-without-a-counter lesson") during this feature's own review round —
so the lesson was learned once, locally, by the role that found it. The question for DoD is whether
this is a one-off or a category: "a `pcall` added for degradation ships without the counter that
would make the degradation observable."

**How to apply:** when reviewing a feature that adds `pcall`-wrapped graceful degradation to an
enumeration/collection loop, check whether a counter for the degraded case shipped in the same
commit — not whether the `pcall` itself is correct. If this recurs on a second, unrelated feature,
promote to a `project_recurring_*` memory and flag it as a pattern worth catching earlier (Architect
or plan-review stage), per the dod role's own "recurring fix" instruction.
