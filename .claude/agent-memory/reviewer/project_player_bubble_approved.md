---
name: project_player_bubble_approved
description: player-bubble (feature/player-bubble, 6e3a2b7) reviewed APPROVED clean — the "forward-hemisphere" no-op claim and velocity-join-before-filter pattern worth re-checking on similar future features
metadata:
  type: project
---

`feature/player-bubble` (10 km computation-scope radius, `association.filter_player_bubble()`)
reviewed APPROVED, no required fixes. [[provenance_confidence_pattern]]-adjacent but not that
pattern — this is a pure geometric pre-filter with no provenance/confidence fields at all.

**Two things worth re-checking next time a similar "X is a behavioural no-op for channel Y" claim
appears in an implementation.md:**

1. **"Forward-hemisphere only" was imprecise but not wrong in outcome.** `association.RANGE_CAP_M`
   (5000 m) is actually an *unconditional* range cap applied before, and independently of, a
   separate forward-hemisphere bearing check (`if candidate_range_m > RANGE_CAP_M: continue` runs
   first, no bearing involved) — it is not itself "forward-hemisphere" anything. The implementer's
   doc called it that anyway. Luckily this error is conservative: because the real check is
   omnidirectional and strictly tighter than the new 10 km bubble, the stated conclusion (bubble is
   a no-op for this channel) held *more* strongly than the flawed reasoning implied, not less. Read
   the actual gate code (`association.py` `associate()`'s loop) rather than trusting a docstring's
   characterization of what an existing constant's scope is — a wrong characterization can still
   accidentally support a true conclusion, which makes it easy to wave through unless you read the
   code directly.
2. **Per-candidate upstream work before a new early-filter isn't always eliminated by "earliest
   point" claims.** `naked_eye_source.poll()`'s velocity-resolution join (`_resolve_velocity_by_
   object_id`) runs over *all* raw objects before `filter_player_bubble()`, so out-of-bubble units
   still get a velocity resolved this poll. Pre-existing architecture, not introduced by this
   feature, and cheap (a hash join) — judged not worth a required fix, but this is the same shape
   of question as [[feedback_verify_pipeline_wiring_not_just_module]]'s class of check: always ask
   what runs on the *full* candidate list before the new filter's call site, not just what runs
   after it.

Checks run clean from a fresh `.venv` built against Python 3.14 (no upper pin in body-layer's
`requires-python = ">=3.11"`) — 1379 passed, 4 xfailed, matching the claimed 1367/4 baseline + 12.
