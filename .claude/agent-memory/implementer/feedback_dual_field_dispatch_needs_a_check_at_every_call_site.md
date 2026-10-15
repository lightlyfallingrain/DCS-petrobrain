---
name: feedback_dual_field_dispatch_needs_a_check_at_every_call_site
description: Fixing a "current field doesn't read the target field" defect — add the check at the dispatch site that calls the phase's own body, not inside the body, and enumerate every other dispatch branch for the same shape before reporting done.
metadata:
  type: feedback
---

`BL-B64` Stage 2 review, Pass 2: `decide()`'s `state.phase is OpticPhase.SIGHTING` dispatch called
`_decide_sighting` unconditionally, so a pilot's "Observ off" (which writes `OpticState.home_phase`
alone, one poll lagged) was invisible until the sight's own internal stop conditions fired — see
[[feedback_diverged_dual_field_state_untested]] (reviewer memory) for the defect itself.

**Where the fix belongs**: at the *dispatch* site (`decide()`'s own `if state.phase is
OpticPhase.SIGHTING:` branch), not inside the phase's own body (`_decide_sighting`). The dispatch
site is what decides whether to call the body at all; putting the check there means the body's own
precondition ("only called while the two fields agree") can become *true by construction* rather
than merely documented. After this fix, `_decide_sighting`'s docstring claim that it is "only ever
called while `home_phase is SIGHTING` too" went from false-but-assumed to true-and-enforced — the
same sentence, but now checkable by reading `decide()`'s dispatch rather than by trusting the
docstring.

**The systematic check the review asked for, and why it's cheap**: enumerate every dispatch branch
in the function and say, for each, whether it reads the "target" field and whether it should. In
this case `SEARCHING`/`GLASSING` deliberately do *not* read `home_phase` — entering OBSERV is
specified to never abandon an in-progress naked-eye/binocular activity, and existing tests
(`TestObservOn`) already pin that. Only `SIGHTING` needed the read. Writing that table out (one row
per branch, "reads it? should it?") took a few minutes and turned "I fixed the one bug named in the
review" into "I checked the other five places the same shape could recur and five of them are
correct by design, not by oversight" — the second claim is what the review is actually asking to
see, and it's one `grep`-and-read away once you already have the function open.

**Test shape that actually exercises the fix**: build the diverged state directly
(`OpticState(phase=TARGET_MODE, home_phase=OTHER_MODE, ...)`), both idle and mid-activity (an active
look with non-empty pending marks), and step the pure decision function. Don't rely on "set it, then
decide, then set it again" sequences — those still agree at the moment `decide()` is called unless
you deliberately leave them apart, which is exactly the state every pre-existing test in this
codebase failed to construct.
