---
name: closing-a-required-fix-needs-the-same-independence-as-finding-it
description: Re-reviewing a fix for a required finding (BL-16 LV-2 breaks) -- confirmed closure by re-deriving the implementer's own numeric claims from first principles and mutating the fix, not by re-reading the diff and trusting the new numbers.
metadata:
  type: feedback
---

BL-16 LV-2 (breaks), `review-lv2.md` required fix 1: the break's bank/rate cap was built correctly
but, as first shipped, almost never bound -- the heading-rate step reused the ordinary
`omega_heading` (0.3), whose critically-damped peak rate (`err*omega/e`) is independent of any
ceiling above it. The fix pass added a break-only `break_omega_heading` (1.0 rad/s). Re-reviewing
the fix, I did not just read the new comment/plan/card numbers and check they were internally
consistent with each other (they were) -- I independently re-derived both load-bearing numeric
claims from first principles: a bare Python simulation of the idealized shaper confirmed the
peak-rate formula at both the old and new bandwidth (9.95/33.1 deg/s), and a direct
`law_turn_rate_at_bank(60, v)` computation at the three card speeds matched the claimed cap figures
(29.21/19.47/14.02 deg/s) exactly. I also mutated the fix itself (commented out the one line
reading `break_omega_heading`) and confirmed the new test class went red for the stated reason
rather than trusting the implementer's own reported counterfactual.

**Why:** the first pass's own finding was exactly this kind of error -- a plausible-looking,
internally-consistent set of numbers (plan, comment, card all agreeing) that was wrong because
nobody had closed the loop through the real mechanism. A fix pass that corrects three documents to
agree with each other is not evidence the documents now agree with the code; only re-deriving the
numbers independently (not reading them) and mutating the mechanism catches a fix pass that fixed
the *documentation* consistency but not the *underlying* claim. The fix pass here held up under
both checks, but the checks were what made "APPROVED" more than a second read of the same prose.

**How to apply:** when closing a review's own required fix, re-run the same rigor that found the
problem in the first place -- independent first-principles numeric checks and a mutation of the
*new* mechanism, not just confirming the plan/comment/card now read consistently with each other.
See also [[clamp-structural-vs-measured-residual]] (a related but distinct trap: matching a
formula's structural property vs. its absolute figure against a research doc).

A second, smaller judgment call from the same pass: a ~5-10 deg roll-out overshoot appeared as a
side effect of the fix. It was accepted as a known, bounded, disclosed plant-lag artifact (not a
shaper defect) rather than flagged as a new required fix, because (a) the idealized shaper's own
reference was independently confirmed to have zero overshoot at any bandwidth, pointing the
residual at the toy plant's bank-lag model specifically, not the control law; (b) it was bounded
and tested (≤2 zero-crossings); and (c) it was disclosed in three places and named on the
acceptance card's own watch line. A first-cut tunable constant with a bounded, disclosed,
test-covered residual is a card-watches-it item, not a blocker -- don't require a mechanism (a
lookahead/anticipation term) to be built before a first-cut tuning constant can ship.
