---
name: host-specific-measurement-is-not-a-scope-verdict
description: "cannot be driven to a pass on this host" is a measurement, not a scope decision -- do not approve a branch that leaves a test deterministically failing by calling the cause "pre-existing and host-specific"
metadata:
  type: feedback
---

On `fix/connection-reporter-flaky` (`plans/connection-reporter-flaky/review.md`), my own first-pass
review approved the branch while `test_unreachable_brain_logs_one_line_without_traceback` failed
**always**, 3/3, alone and in the full suite, on this host -- both before and after the diff. I had
correctly reproduced the mechanism (a `bind()`-but-never-`listen()`-ed socket does not refuse
`connect()` instantly on this host; it blocks for the client's full 5.0s `poll_timeout_s`, past the
test's 2.0s wait) and correctly confirmed it was not caused by this diff. I then wrote "confirms
this is a pre-existing, host-specific socket-timing issue ... and not something this fix could have
addressed" and approved. That conclusion does not follow from the measurement: "not caused by this
diff" and "cannot presently be reproduced on this host" are true; "therefore out of scope" and
"therefore unfixable" are not, and the second pair is what actually went in the verdict. A test
failing deterministically on a real, in-use development host is a real defect regardless of whether
the *cause* predates the branch being reviewed -- the question a review verdict has to answer is
"does this branch leave a known-bad test red," not "did this branch cause the red."

The debugger's own first pass made the identical move (`debug.md`'s original framing, corrected in
its own later "Follow-up" section) -- two independent reviewers reached for the same false inference
from the same true measurement, which suggests the inference is the natural-sounding one, not an
isolated lapse.

**Why:** "pre-existing" answers "whose fault" (relevant to whether this diff regressed something);
it does not answer "is this acceptable to ship" (the actual question a verdict commits to). A
measurement that something is host-specific is evidence about *mechanism*, not permission to treat
the failure as outside the branch's scope -- especially when, as here, the branch's own stated
purpose was "make these tests stop failing."

**How to apply:** before writing "pre-existing" or "host-specific" as part of a verdict (not just a
diagnosis), ask the separate question explicitly: does the test pass, right now, on this host, after
this diff? If no, that is a required fix or an explicit, user-visible scope carve-out stated as such
("known to fail on this host, tracked as X, approved anyway because Y") -- never silently folded
into "not caused by this diff, therefore fine." The fix in this case was cheap once named correctly:
stop depending on the host's socket timing (inject the exception shape instead of relying on a real
refused connection) rather than accepting the test as permanently unrunnable here.

Related: [[feedback_check_the_premise_not_just_the_mechanism]] -- same shape of error (a true
measurement feeding a false downstream conclusion), different subject matter (data-model claims vs.
scope verdicts).
