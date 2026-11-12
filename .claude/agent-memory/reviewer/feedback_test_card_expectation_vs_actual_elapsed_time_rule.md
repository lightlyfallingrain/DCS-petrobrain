---
name: test-card-expectation-vs-actual-elapsed-time-rule
description: When a plan keeps one time-based transition (e.g. "lost" stays purely elapsed-time) while making another time-based transition distance/growth-based, check every test-card scenario's literal wait-time against the unchanged rule too, not only the changed one.
metadata:
  type: feedback
---

BL-B112 (motion-aware contact certainty) deliberately kept `LOST_THRESHOLD_S` purely elapsed-time
(the user's own "use current implementation" answer) while making the tracked/estimated boundary
growth-distance-based. `test-card.md`'s Case 1 told the tester to wait "several minutes (well past
the old ~2-minute 'estimated' window)" for a fixed SAM site and then expected it to **still be in
working memory, not lost** — contradicting the very rule the plan explicitly kept unchanged, and
contradicting a passing unit test
(`test_immobile_contact_still_goes_lost_at_the_lost_threshold`) that proves the opposite.

**Why this slipped through implementation and self-review**: the plan's prose about the *new*
growth-based hedge is easy to internalise ("fixed site never hedges"), and it is tempting to
generalise that into "fixed site is never bothered by time at all" when writing the human-facing
test card — but the plan kept a *second*, separate elapsed-time rule untouched, and the card's
author (reasoning from the feature's own headline, not from both rules) wrote an expectation for
the untouched rule that was simply wrong.

**Why:** this is exactly the class of defect "player-facing correctness is yours alone" (reviewer.md)
was written for — a test card is what the user flies against, and a wrong expectation in it
produces either a false bug report (behaviour is correct, tester thinks it's broken) or a false
pass (tester doesn't notice the card's own internal contradiction and skips the check).

**How to apply:** whenever a plan changes one time-based lifecycle boundary but explicitly keeps a
sibling one (lost/eviction/expiry, a second half-life, a second threshold) unchanged, check every
test-card scenario that waits "long enough" against *both* rules, not just the one that changed.
Grep the plan for the unchanged rule's own name (here, `LOST_THRESHOLD_S`) and cross-check its
value against every "wait N minutes" instruction in the card. A passing unit test proving the
unchanged rule's boundary (here, `test_immobile_contact_still_goes_lost_at_the_lost_threshold`) is
the fastest way to settle which expectation is right when the card and the plan disagree.
