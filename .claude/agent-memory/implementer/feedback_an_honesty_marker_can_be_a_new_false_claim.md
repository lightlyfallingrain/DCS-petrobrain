---
name: an-honesty-marker-can-be-a-new-false-claim
description: A hedge quoted from the user was true only at the age they were shown; reusing it verbatim at every age would have been a fresh lie.
metadata:
  type: feedback
---

**When a user hands you the exact wording for a hedge, check the range of inputs it will be spoken
over before using it verbatim. A hedge that is false at some ages is worse than the unqualified
sentence it replaced.**

**Why:** BL-13's selective freshness marker (`plans/crew-query-path/security.md` required fix 1).
The user chose the option whose own words were *"the SAM is a couple minutes old"*, and the task
said to prefer that register. But they were shown a scene at ~119 s; the staleness window is one
scan cycle (16 s) and in-scope belief runs to `LOST_THRESHOLD_S` (120 s), so the same phrase would
have been spoken about a contact seen **twenty seconds ago**. The whole point of the marker is
honesty, so a false age claim in an honesty marker is a strictly worse outcome than the flat
present-tense sentence the security finding objected to. Fixed by rounding to minutes
(`round(ago_s / 60)`) and keeping their phrase for the rung where it is true.

**How to apply:** whenever you are given a phrase to speak — a hedge, a confidence word, a
magnitude, a direction — enumerate the input range the call site will actually feed it, not the one
example you were shown. The rungs fell out of arithmetic rather than named thresholds, which also
satisfied a "no new constant" constraint for free; prefer that shape over a table of boundaries.

Related: [[feedback_verify_keyword_vocab_against_real_strings]] (same failure in the other
direction — a vocabulary assumed rather than checked), and
[[project_bl13_selective_freshness_marker]] for the mechanics of this fix.
