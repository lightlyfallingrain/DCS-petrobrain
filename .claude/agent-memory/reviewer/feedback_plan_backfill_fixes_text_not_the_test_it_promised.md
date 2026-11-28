---
name: plan-backfill-fixes-text-not-the-test-it-promised
description: An implementer "confirmed by grep" that a plan-aligner finding was backfilled into the plan text -- check whether the TEST the backfill promised was actually written, not just that the sentence exists
metadata:
  type: feedback
---

On BL-16 M3 (terrain floor/look-ahead, `plans/flight-lift-vector/plan.md`), `plan-aligner`'s plan
check found three gaps where the plan still read as the pre-answer recommendation instead of the
user's actual decision (U22 "every climb trades speed," not "terrain only"). One of the three
fixes was a **Tests-section addition**: a named toy-plant case for an ordinary, non-terrain
altitude climb through capped authority, asserting `v_ref` yields toward the speed-give floor —
explicitly because, without it, "a regression to 'terrain only' fails [no] test."

The implementer's own summary said: *"Cross-checked plan-aligner's... all three findings... were
already backfilled into plan.md by the tip commit before this build started — confirmed by grep,
not assumed."* That check (grepping the plan text) is real and was done correctly. But a backfilled
**plan sentence promising a test** is not the same claim as **the test existing** — and the second
half was never checked, by the implementer or by this role's first pass. The test was never
written; nothing in the "Deviations from the plan, disclosed" section named the gap either.

**Why this slipped past**: the implementer's grep answered "is the plan text current," which reads
as settling the whole finding because the finding's own wording ("Tests section has no explicit
assertion...") sounds like a plan-authoring problem. It is actually a two-part finding — fix the
plan's words, AND build what the corrected words now promise — and only the first half got a
grep-backed confirmation.

**How to apply**: whenever an implementation summary says a plan-aligner/reviewer finding was
"already fixed in the plan" before the build started, check what KIND of fix the finding asked
for. If it asked for a **Tests-section addition**, grep the actual test files for the named
mechanism (constant name, function name) under an assertion, not just confirm the plan prose
reads correctly — a plan sentence and a test are different deliverables, and only one of them
shows up in a diff of `plan.md`.
