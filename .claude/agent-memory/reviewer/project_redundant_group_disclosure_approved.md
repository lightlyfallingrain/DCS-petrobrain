---
name: redundant-group-disclosure-approved
description: fix/redundant-group-disclosure reviewed APPROVED clean — how the restated merge-echo predicate and the "fully-covered early return" were independently verified
metadata:
  type: project
---

`fix/redundant-group-disclosure` (b09f270/4d81c43) reviewed APPROVED, no required fixes. Silences
a `belief.groups.Group`'s first disclosure when every current member's content already reached the
pilot (directly or via merge-echo suppression); speaks only the unreported remainder in the partial
case. User direction settled the design: "for now, no 'those are together', prioritize less
speaking."

**Verification techniques worth reusing:**

- Disabling just `never_spoken_fully_covered` (forcing it `False`) did **not** make the
  all-already-reported test fail — it degenerates into the `never_spoken_partially_covered` path
  with zero unreported members, which independently returns `None` too. The two branches are
  behaviourally redundant in that one case; to actually falsify the mechanism I had to zero out
  `already_reported_now` itself (the shared input both branches read), which did make all four
  named tests fail with the exact expected diffs. **When a fix has an "early return" branch that
  looks load-bearing, check whether a fallback branch produces the same result before trusting the
  early-return's own test as proof of it** — see [[feedback_regression_test_empirical_check]].
- Verified the restated merge-echo predicate (`CalloutScheduler._already_reported_member_ids`
  branch 2) is character-for-character identical to `_render_event`'s own `CONTACT_DETECTED`
  suppression condition by reading both call sites side by side, not trusting the docstring's claim
  of "identical." It held. Flagged the lack of a drift-guard test as optional, not required — see
  [[feedback_regression_test_empirical_check]].
- Rebuilt `main`'s baseline test count via `git archive main | tar -x` into scratch rather than
  trusting the implementer's quoted 1409/4 — reproduced exactly.

See also [[project_contact_report_flood_review]] (the sibling fix this one builds on, same
"restated not shared" predicate-duplication pattern one layer down).
