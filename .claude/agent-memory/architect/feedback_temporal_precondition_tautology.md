---
name: feedback-temporal-precondition-tautology
description: A trigger precondition like "A not seen this poll" written as last_seen < now is true of every match against stored state; define "out of view" as a perceived window (BL-B111)
metadata:
  type: feedback
---

When a plan says "remembered thing X, not currently seen", **write the predicate against a window, not
against `now`**. `a.last_seen_sim < now_sim` is true of every gate match by construction, because any
stored candidate was last seen at an earlier poll. In BL-B111 it fired on 18 of 18 continuous-tracking
gate matches, broke two existing `test_contacts.py` tests, and cost an Implementer pass that had to
revert the call site. The fix was `now - last_seen > FOCUS_DWELL_S`, meaning "not seen within the
current look": 0 of 18 eligible, and identical to the model in all 144 harness cells.

**Why:** a harness that only ever constructs long gaps (6 s, 700 s) cannot reveal a tautological
precondition. The plan's numbers looked right while the condition did no work at all.

**How to apply:** for any temporal precondition in a plan, name the *shortest* gap the trigger must
**not** fire on (here: consecutive 1 s polls) as well as the gaps it must fire on. Then check the
existing tests that construct the short gap, `grep` for gate-path sequences without
`continues_observation_id`, before handing the plan to the Implementer. Prefer an existing perceived
window (`FOCUS_DWELL_S`, `OBSERVED_WINDOW_S`) over a poll-loop cadence, which belief does not own.
Related: [[feedback-verify-state-not-the-account-of-it]].
