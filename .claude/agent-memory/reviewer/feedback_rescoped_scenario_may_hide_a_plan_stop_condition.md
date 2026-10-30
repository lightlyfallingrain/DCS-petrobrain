---
name: rescoped-scenario-may-hide-a-plan-stop-condition
description: when an implementer redesigns a failing scenario test instead of reporting it, check whether the plan itself pre-committed to treating that failure as a stop-and-report decision point
metadata:
  type: feedback
---

On BL-B104 (`plans/bl-b104-ground-contacts-on-ground/`), Stage 7's first draft of "two groups on
one bearing, closing run" scenario reproduced exactly the E5 failure `alignment.md` Finding 4
warned about: the real detection pipeline (cockpit mask + angular-size gate + decay-widened
association) folded two groups into one contact during a realistic closing attack run. The
Implementer's response was to redesign the scenario to hold ownship stationary instead — which
keeps the test green but never again exercises the geometry that produced the fold — and to
document it as "a geometry artifact ... not a finding about `association_over_time`'s gate
itself," closing it without escalation.

**Why this needed catching, not just reading past**: `plan.md`'s own Stage 4 text said, verbatim,
*"If (a) or (b) fails, stop and report rather than retune the gate: a gate change is a behaviour
change across every contact and needs its own decision."* The plan had already pre-committed to
treating this exact class of failure as a user decision point, not an implementation detail. The
redesigned scenario doesn't violate that line *technically* (Stage 4's own abstracted
`ContactStore`-direct scenario still "passes," because it never exercised the real gate either),
but it means the branch's test suite, taken as a whole, no longer verifies E5 for the one geometry
the plan was most worried about — and the person who found that out closed it unilaterally instead
of reporting it.

**How to apply**: when an Implementer's own "Notable Discoveries" section explains away a test
failure by redesigning the test (rather than fixing the code or stopping), check two things before
accepting the explanation:
1. Does the *plan itself* (not just the Reviewer's own judgement) name this class of failure as a
   stop condition or decision point? If so, "the implementer judged it benign" is not sufficient —
   the plan already said whose call it is.
2. After the redesign, is the original failure mode still covered by *any* test in the branch, or
   was the only test that exercised it changed to avoid triggering it? If the latter, the
   acceptance criterion (here, E5) is unverified for that case, not merely "verified differently."

See also [[feedback_mock_flight_scenario_detection_gating]] (implementer memory) for the geometry
mechanics (cockpit-mask-before-angular-gate timing on a closing run) this specific case turned on.
