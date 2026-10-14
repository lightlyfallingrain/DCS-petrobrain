---
name: tier-qualifier-as-text-suffix-avoids-tier-aware-cadence
description: BL-14 Stage 6 pattern -- append a degraded-mode qualifier as the last step of rendering so a change-driven cadence rule needs no tier-aware branch
metadata:
  type: project
---

When a speech renderer has a change-driven cadence rule that compares the *rendered text* against
the last-spoken text (not a decomposed tuple of inputs), a degraded-mode qualifier (e.g. BL-14's
`", obstructed"` for tier 2) should be appended as the very last step, after whatever the normal
branches would have produced, uniformly across every branch (including an otherwise-untouched
case like `"lined up"`).

**Why.** The qualifier's presence/absence then becomes part of the compared string, so a tier
transition in either direction is automatically "a text change" and the cadence rule re-fires with
zero additional code. No tier-aware branch is needed in the cadence function itself. This was
confirmed end-to-end with two full-sequence tests (`test_decide_lined_up_tier_transition_speaks_
once_each_way`, `test_decide_tier_transition_speaks_the_qualifier_without_flipping_direction` in
`body-layer/tests/test_attack_run.py`) rather than assumed from reading the code -- worth doing
for any future "two registers of the same utterance" design, since the alternative (a tier-aware
early-return in the cadence check) is the first thing that looks necessary and is not.

**Related, same feature:** `perception/naked_eye_source.py` emits an `Observation` every poll a
cluster is *admitted*, regardless of whether that poll's sightline is clear -- `live_los_clear`
gates only the `relative_direction` field, not emission. Combined with `Contact.record`/
`from_percept` overwriting `last_percept` wholesale (never folding), this means a contact's
`last_percept.relative_direction` can flip from present to `None` poll-to-poll on a contact that
has not moved or disappeared. Any module that wants to remember something derived from a past
`relative_direction` (BL-14's remembered target altitude) must carry that memory on its own state
object, updated whenever the derivation last succeeded -- it cannot rely on `Contact.last_percept`
still holding it later.
