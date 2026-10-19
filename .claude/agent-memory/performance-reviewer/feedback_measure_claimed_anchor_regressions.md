---
name: measure-claimed-anchor-regressions
description: audio-adapter's VERB_ANCHOR_WORDS set has coincidental ties at exactly VERB_FLOOR (0.5) — a new verb can be "already admitted" before it is added; don't take an implementer's "X is now a new anchor word" framing at face value, recompute the old ratio.
metadata:
  type: feedback
---

On `feature/radio-check` (BL-B81, 2026-10-19), the implementer flagged: *"'good' became a new
verb-anchor word, so ordinary sentences starting with 'good' now cost an extra phrase-scoring
pass."* Measured directly instead of trusting the framing: `difflib.SequenceMatcher(None, "good",
"look").ratio() == 0.5`, which already clears `VERB_FLOOR` (`>= 0.5`, the check is `< VERB_FLOOR`
rejects) against the **pre-existing** `VERB_ANCHOR_WORDS` set — i.e. "good ..." already anchored
before this feature via a coincidental tie with "look", and already paid the full branch-chain +
phrase-table cost. Reconstructing the old anchor set (every `vocabulary.PHRASES` entry except the
new token) and re-timing showed the real delta for ordinary "good"-prefixed chatter was ~2.6%
(17 µs on a ~660 µs call), not a new cost class.

**Why:** `VERB_ANCHOR_WORDS` is derived from every phrasing's first word (`command_matcher.py`'s
own docstring: "a strict superset... picks up extras"), and `VERB_FLOOR` is deliberately loose
(0.5, looser than `MATCH_FLOOR`'s 0.6) because a false *reject* at the anchor is irreversible while
a false anchor just costs one scoring pass that almost always rejects anyway. That looseness means
near-misses with the *existing* set are common and easy to miss by eye — always recompute the old
ratio before accepting a "this word is now newly expensive" claim.

**How to apply:** Whenever a performance report (self-flagged by the implementer or otherwise)
claims "X is now a new anchor/trigger word, so sentences starting with X cost more," reconstruct
the pre-change set (exclude the new token's contribution) and recompute the ratio for X against it
before accepting the claim's magnitude. The direction can be right while the magnitude is wrong —
this is the project's own "measure n before scaling anything by n" rule
([[slot-branch-beats-phrase-table]] is the sibling finding: the phrase table, not the anchor gate,
is the expensive part here).
