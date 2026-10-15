---
name: feedback_verify_fresh_construction_sites_by_grep_not_count
description: when an implementer claims "I checked there is no third fresh-construction site that drops a new persistent field", verify by grepping all construction sites of that dataclass across src/, and mutate the two already-fixed sites to confirm the tests actually catch the regression
metadata:
  type: feedback
---

Found reviewing `BL-B64` Stage 1b/§15a (`plans/9k113-sight/plan.md`) in
`body-layer/src/belief/optic_policy.py`. The implementer's own account (and a new
implementer-memory entry, `feedback_decide_fresh_dataclass_construction_drops_fields.md`)
flagged that `decide()` has branches that construct `OpticState(...)` fresh rather than
via `dataclasses.replace(state, ...)`, which silently drops any new field not named in
the fresh call. They found and fixed two such branches (`SEARCHING`, `GLASSING`) and
claimed to have checked there was no third.

**How this was verified rather than accepted:**
1. `grep -n "OpticState(" src/belief/optic_policy.py` and `grep -rn "OpticState(" src/`
   (whole tree) — confirmed exactly two fresh-construction call sites exist in `src/`,
   both already fixed. This is the cheap half and should always be done — a claim of
   "no third" is a `grep`, not a re-read of the whole file.
2. **Mutation, not just reading, on the two fixed sites.** Temporarily deleted the two
   carry-forward kwargs and re-ran the two tests pinning the carry-forward
   (`TestOpticStateActualAimCarriesForward`) — both failed immediately with the exact
   defect described. This is the load-bearing half: a test *named* for an invariant can
   still be vacuous (e.g. asserting something that was never going to be false given the
   rest of the fixture). Only the red confirms the green means something.

**How to apply:** whenever a fix is described as "found by enumerating every
construction/call site of X, not just the ones the task pointed at" (the recurring
"enumerate the containing unit" lesson this role already tracks for exception handlers
and guard sets), re-run that enumeration yourself with `grep` rather than trusting the
count, and mutate at least one of the already-fixed sites to confirm the pinning test
is not vacuous. Both checks are cheap (one `grep`, one temporary edit + test run) and
together they are the difference between "the implementer says they checked" and
"verified."

See also `[[feedback_every_guard_entry_needs_a_failing_counterfactual]]` — same principle,
applied here to dataclass construction sites instead of a guard/exemption set.
