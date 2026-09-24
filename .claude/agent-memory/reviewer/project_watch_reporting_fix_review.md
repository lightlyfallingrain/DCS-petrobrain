---
name: watch-reporting-fix-review
description: Review of a single follow-up fix commit (7f4f24d) answering Performance/Security findings on watch-reporting — how to check a hysteresis-vs-no-hysteresis gate asymmetry
metadata:
  type: project
---

Reviewed `7f4f24d` on `feature/watch-reporting` in isolation — the "review of the fix" step for
a new project workflow rule (`AGENTS.md`, "A change request from Security or Performance
Reviewer re-enters the loop"): a fix answering a Security/Performance finding goes
Implementer → Reviewer → DoD, treated as ordinary new code, not re-litigated by the review that
asked for it. APPROVED, no required fixes; see `plans/watch-reporting/fix-review.md`.

**Technique worth reusing**: when a fix adds a short-circuit/skip branch that also resets some
piece of dwell/bookkeeping state (here: `contact.los_masked_since_sim = None` on the new
range/alt skip path in `ContactStore.tick`'s engagement block), check whether every *other* gate
feeding the same `and` condition has the same protection against noise-driven flapping. Here
`range_ok` has `ENGAGEMENT_LEAVING_HYSTERESIS` (1.5x widening while already engaged) precisely
to stop range-edge noise from flapping the gate; `alt_ok` has none. That asymmetry is real and
newly-consequential (before the fix, LOS ran unconditionally every tick so dwell was continuous
regardless of gate state; after, any `alt_ok` flip discards it) — but tracing the consequence
through the dwell's own semantics (`los_ok = masked_for_s < LOS_MASK_CONFIRM_S`) showed
discarding the dwell only ever delays clearing an engagement/danger state, never drops one
early. Fail-safe direction, so downgraded to an optional refinement rather than a required fix.
**The check that matters: don't stop at "the gates are asymmetric" — trace which direction the
reset biases the final boolean.** An asymmetry that biases toward under-reporting a threat is a
required fix; one that biases toward over-reporting (staying cautious longer) usually isn't.

Also found (optional, not required): in `_run_crew_text_poll_loop`'s new whole-body guard, a
mid-iteration exception between `_poll_f10_commands` (which can already have incremented
`crew_console.commands_handled` via `handle_command`) and the `commands_handled != commands_before`
check silently drops that cycle's `lower_binoculars` call — `commands_before` is loop-local and
recomputed fresh next iteration, so the delta is lost with no retry. Cosmetic (one missed optic
cue), and strictly better than pre-fix (same exception used to kill the thread outright), so not
a blocker — but the general pattern (`try` guard wraps a "dispatch A, then derive a side effect
from A's delta" pair) is worth a second look whenever a broad guard is added around code that
already had this shape.
