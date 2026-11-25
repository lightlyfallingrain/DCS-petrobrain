---
name: tier-ranges-is-the-choke-point
description: body-layer's whole optic ladder (eye/binocular/9K113 raise-or-not decisions) reads only tier_ranges() output — a new condition multiplier belongs there, not in per-decision branches
type: feedback
---

`body-layer/src/perception/visibility.py`'s `tier_ranges()` is the single function every
"is it worth raising this instrument" decision in `belief/optic_policy.py`
(`improvement_window_m`, `location_gain_for`, `sight_look_optic`, `sight_can_still_improve`, and
two more call sites) reads, plus `check_visibility()`'s own gate. None of these decisions has its
own threshold logic — they all derive "worth it" purely from comparing `tier_ranges()` outputs for
two optics.

**Why this matters for planning:** any new per-condition multiplier (light level BL-B124, and the
weather/rain factor BL-B22 still owes) belongs as a parameter on `tier_ranges()` itself, threaded
through to its ~7 call sites, never as a bespoke "if dusk, skip binoculars" branch somewhere in the
decision logic. Once the multiplier shrinks a tier's achievable range toward zero, the existing
ladder stops raising that instrument on its own — no new branch needed, and the behaviour composes
with every other multiplier already in the chain (optic.presence_range_mult etc.) instead of
fighting it.

**How to apply:** before designing a new "Petrovich should prefer instrument X under condition Y"
feature, check whether it can be expressed as a `tier_ranges()` input instead of a policy branch —
it almost certainly can, because every existing branch in `optic_policy.py` is already economics
over `tier_ranges()`, not a hand-written preference order. This closed BL-B124's alignment doc open
question ("should he lean on the 9K113 and skip binocular glances that cannot help") with no new
code at all — it falls out once light factor is threaded through.

Separately: body-layer's existing emitter bypass (`perception/emitters.py`'s `BURNING`/`FIRING`
kinds) already ignores range/light gates and already reaches `PLAYER_BUBBLE_RADIUS_M` — so "a unit
giving off light should be visible at night regardless of range" (BL-B124's light-sources half)
needed **zero** changes to the existing two emitter kinds. Only genuinely new light sources
(missile/rocket launch, explosion) needed new emitter kinds. Worth checking, for any future "X
should reveal itself regardless of normal gates" ask, whether the emitter mechanism already covers
it before assuming new plumbing is needed.
