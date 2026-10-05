---
name: dcs-driven-los-review-approved
description: X-B29 DCS-driven LOS Stages 1-3 review — APPROVED clean, NaN-clamp empirical verification technique
metadata:
  type: project
---

Reviewed `feature/dcs-driven-los` tip `0200e07`, X-B29 Stages 1-3 (cone-scoped DCS LOS query,
look-direction command channel, gate 4 live-first/offline-fallback). **APPROVED**, no required fixes.

**Why:** both Security plan-review required fixes (total NaN/Inf clamp in Lua, per-frame
`dostring_in` coalescing) were correctly implemented. I did not just read the clamp — I extracted
`_safeClampInt` and ran it under a standalone `lua` interpreter against `0/0`, `math.huge`,
`-math.huge`, `nil`, a string, a table, and huge finite values, and separately ran the naive
`math.max(lo, math.min(hi, x))` idiom to confirm it really does pass NaN through unchanged (Security's
claimed bug, reproduced rather than taken on faith). The 12m terrain-tolerance boundary claim ("gate 4
never calls the offline primitive once a live verdict exists") was verified by reading
`visibility.py`'s actual `if candidate.live_los_clear is not None: ... elif not
line_of_sight_clear(...)` branch, not accepted from the implementer's note.

**How to apply:** when a plan/security-review names a specific hostile-input failure mode for a
clamp/validator (NaN passthrough, overflow, etc.), and the implementer's test suite only does
text-presence grepping rather than execution (common for this project's untested Lua Hook scripts —
see [[feedback_rendered_english_assertions_too_weak]]-adjacent pattern), reproduce the failure mode
yourself with a throwaway interpreter/script rather than trusting the static check. It is cheap (a
local `lua`/`python` one-liner) and catches the gap between "the guard code is present" and "the
guard code actually works," which a grep-for-presence test cannot distinguish.

**Secondary finding, optional not required:** this project's own convention (`aircraft-layer/
CLAUDE.md` Testing section) is that Lua Hook scripts get `luac5.1 -p` syntax-only checks and nothing
more — no execution tests exist anywhere for Lua in this codebase, DCS-dependent or not. A pure
function like `_safeClampInt` (no DCS globals) could be execution-tested without DCS, closing exactly
the gap Security asked for, but doing so would be new test infrastructure beyond the established
pattern — recorded as optional, not a blocker, consistent with the existing convention.

See also: [[project_group_cohesion_redesign_review_needs_revision]] and
[[project_los_tolerance_boundary_test_review]] for the general "run the code, don't just read it"
pattern this review continues.
