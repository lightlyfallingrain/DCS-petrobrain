---
name: bl13-round3-selective-freshness-approved
description: BL-13 round 3 (Security required fix) APPROVED; a purely-additive diff settles a regression list mechanically, and an honesty marker's own failure mode is a false age.
metadata:
  type: project
---

`feature/bl13-crew-query-path`, `6ec99f1..153efc0`, one commit. Reviewer-on-the-fix after a
Security change request. **APPROVED, no required fixes.**

**Zero deletions in a diff is evidence, and cheap.** The whole round-3 diff was 612 insertions and
**0 deletions**. That single `git diff --numstat` settled most of the "what must not have
regressed" list — `decay.py` untouched, `_is_air_defence` untouched, Decision D's exclusion and
Q2's regression byte-unchanged, zero existing tests modified — without reading a line. Run
`--numstat` before inspecting a regression list; an additive diff collapses it.

**The non-droppability of a clause is a mutation question, not a reading question.** The claim was
"appended in every budget candidate, therefore non-droppable". Reading the loop supports it; what
*proves* it is gating the append behind `with_deferral` and getting **5 failed** including the
security-measured scene — i.e. the finding reproduced by the perturbation and absent without it.
Re-running only the counterfactual that reproduces the original finding is the minimum for a
fix-review; here the selectivity-guard one (3 failed, trade-test red for the stated reason) was
worth the second run, because a guard no test defends is a comment.

**An honesty marker's own failure mode is a *new* false claim.** The user's phrase *"a couple
minutes old"* was true at the 119 s scene he saw, but the stale window opens at 16 s — so the
literal phrase would have hedged a 20-second-old contact with a two-minute claim, worse than the
silence it replaced. The fix rounded to minute rungs instead. **Verify such a ladder by
brute-forcing its whole reachable range against the real constants**, not at the three ages the
test picked: here 16.1 s → 160 s at 0.1 s steps against `OBSERVED_WINDOW_S` = 16 /
`LOST_THRESHOLD_S` = 120 gave flips at 30.1 / 90.0 / 150.1 and no false rung.

**The `parent_class_of` vs `profile_for` split is this module's standing trap, now load-bearing
twice.** `profile_for` keyword-matches *type* names, so `profile_for("OP_SRSAM").op_class` is
`OP_GROUPSOMETHING` while `parent_class_of("OP_SRSAM")` is `OP_SRSAM`. Any `AIR_DEFENSE_OP_CLASSES`
membership test on a *class*-level belief must go through the lattice walk, or it is silently dead
with every test green (`BL-B47`). Measure both in the reviewed tree rather than trusting a report
that says it was checked.

**A never-dropped clause changes what a word-budget constant means.** Two never-dropped clauses
plus a 28-vs-25-word overrun is fine against the existing "a too-long pointer beats no answer"
floor; but if `REPORT_SUMMARY_MAX_WORDS` is halved to the ~13 its own comment anticipates, the
pointer alone fills it and the constant becomes a budget on the *droppable tail* only. Recorded in
`plans/crew-query-path/review.md` as the input to plan Q3 rather than left to whoever lowers the
number.

Smaller finding worth keeping: a collective fallback subject (*"The air defence is…"*) can hedge a
*fresh* tier when three tiers are in scope with mixed staleness. Over-hedging is the safe
direction, so it was left optional — but "the safe direction" is the reason, and it should be
stated rather than assumed.
