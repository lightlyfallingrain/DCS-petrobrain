---
name: tautological-trigger-precondition
description: before wiring a "fires when X was not true this poll" trigger into ingest, check whether X is nearly always false by construction -- run it against the existing suite, not just new tests
metadata:
  type: feedback
---

On `BL-B111` (expected-area look), the plan's trigger precondition "A was
not seen this poll" was implemented as `a.last_seen_sim < now_sim`. This is
true of nearly *every* ordinary gate-path match by construction -- a passing
candidate's own `last_seen_sim` is always from a strictly earlier poll than
the percept now being matched against it. Wired into `ContactStore.ingest`
exactly as specified, it intercepted every gate-path reacquisition, not only
a genuine "out of view" case, and broke two existing `test_contacts.py`
tests (`test_slow_directional_drift_...`, `test_position_runaway_...`) that
deliberately construct a same-object sequence of gate-path (not continuity)
reacquisitions to isolate the spatial gate's own robustness.

**Why:** in real flight this is rare (continuity resolves ordinary
reacquisition, leaving the gate for genuine gaps/foundings -- confirmed by
`association_over_time.py`'s own module docstring: "this gate is now the
exception path, not the common case"). But a *unit test* exercising the gate
in isolation has no reason to carry continuity, so the same code path that
is rare in flight is the *only* path a gate-focused test takes -- the new
trigger fires on literally every one of its reacquisitions.

**How to apply:** before wiring a trigger whose precondition is phrased as
"X was not true recently" / "not seen right now" / "not in the current
look", ask whether the underlying field (`last_seen_sim`, `last_observed_sim`,
etc.) is *always* satisfying that precondition by the time the code reaches
this branch at all -- i.e. whether the precondition is tautological given
how the caller already filtered its candidates. Then run the new wiring
against the *existing* suite, not just newly-written tests, before
considering it done -- a regression here is invisible to a plan's own
measured numbers (which model the mechanism, not the code) and invisible to
new tests (which test the new behaviour, not whether old tests still pass).

**What I did instead of patching around it**: reverted the `ingest` call
site, left a dated comment explaining the finding and pointing at
`plans/<feature>/implementation.md`, and reported it as the central
escalation point rather than guessing at a narrower trigger or silently
rewriting the two existing tests. Per root `CLAUDE.md`'s "Escalation Rules",
"existing tests must be rewritten rather than extended" needs explicit
sign-off, not a unilateral implementer call.

See [[circular-import-from-lazy-annotations]] for a second, related finding
from the same session (an import cycle `mypy` did not catch because of
`from __future__ import annotations`).
