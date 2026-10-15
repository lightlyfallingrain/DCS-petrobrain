---
name: feedback-emitter-visibility-fix-pass-confirmed-by-mutation
description: both emitter-visibility required fixes (closed Percept.emitter_kind, falsifiable group-salience window) verified correct on re-review by independently re-running the mutations rather than trusting the implementer's pasted red/green -- also caught that this review's own cited "~5.4-9.3 km" window was wrong
metadata:
  type: feedback
---

Fix-pass re-review of `feature/emitter-visibility` commit `607ba78` (addressing
[[feedback_provenance_is_not_a_free_pass_across_percept_boundary]] and
[[feedback_group_salience_noninteraction_test_units_too_far_to_falsify]]). Both fixes held up —
but only because each was independently mutated again rather than accepted from the implementer's
account:

- **Fix 1**: re-added `provenance: str | None` to `Percept` directly (a mutation the implementer's
  own report did not perform — they only added two new unit tests) and confirmed
  `test_percept_has_no_truth_carrying_field` fails. Grepped for every `Percept(` construction site
  and every non-`Observation` `.provenance` read to confirm the mapping really is the only path —
  the implementer's report asserted this but a grep is one command and removes the need to trust it.
- **Fix 2**: re-ran the exact mutation at the exact call site
  (`naked_eye_source.py`'s `salient_ids = group_salient_ids(...)` line), got the same `assert 2 == 1`
  failure, reverted, confirmed green by `git diff --stat` being empty rather than "looks the same."
  Separately computed `angular_separation_rad` between the two fixture positions directly, since
  "the cross-offset prevents clustering" is a claim a test passing does not, by itself, distinguish
  from "the units happen to cluster into one candidate that then independently satisfies the
  assertion."

**The more important finding: my own first-pass review cited a wrong number.** Required Fix #2 said
the discriminating window was "~5.4–9.3 km." Recomputing `size_m / LOWRES_ANGULAR_RADIUS_RAD` and
`size_m / RESOLUTION_ANGULAR_RADIUS_RAD` directly from the running constants gives 2333–5469 m. The
5.4 km half was right (rounding `RESOLUTION_ANGULAR_RADIUS_RAD`'s range); the 9.3 km half was a
different, unrelated calibration rung lifted from an adjacent docstring paragraph (a different
target, near the atmospheric limit, explicitly flagged in that same docstring as not usable to bound
this threshold) — i.e. the same failure mode [[project_vision_calibration_research_doc_error]]
warns about, except this time the citation was in my own review rather than in research being
reviewed.

**Why:** a reviewer's own prose is exactly as fallible as an implementer's, and citing a specific
numeric threshold without running the formula creates a wrong "ground truth" the next reader (here,
the implementer, correctly) has to override. The implementer flagged the discrepancy explicitly
instead of silently matching the wrong figure or silently fixing it without comment — the right
move, and worth reinforcing: when a round-2 pass finds the round-1 reviewer was the one who cited a
number wrong, say so in the review file itself, in place, rather than leaving a stale figure for
whoever reads the file next.

**How to apply:** when writing a required fix that depends on a numeric threshold/window, compute it
from the cited constants before writing the fix, not from an adjacent docstring's prose description
of roughly where a boundary lies. Doubly true across two review rounds — the second round's job
includes re-checking the first round's own arithmetic, not just the fix.
