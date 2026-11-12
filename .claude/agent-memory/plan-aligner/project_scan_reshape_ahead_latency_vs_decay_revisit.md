---
name: scan-reshape-ahead-latency-vs-decay-revisit
description: a scan-order plan can disclose "revisit" (decay/re-certainty) arithmetic while leaving first-detection latency for a brand-new contact unmeasured -- they are different numbers
metadata:
  type: project
---

On `BL-B110`'s expected-area-check revision (2026-11-01), the architect reshaped `SCAN_PLAN` from
two sweeps through 12 o'clock to one left→ahead→right pass, cutting ahead from two naked-eye
visits per cycle to one. The plan computed and disclosed a "worst revisit" figure (26–29 s vs the
30 s `POSITION_HALF_LIFE_S`) and treated that as the complete accounting of the cost.

That figure is about an **already-tracked** contact's certainty decaying between glass steps. It
is a different number from **first-detection latency for a brand-new contact** that appears in the
sector right after the eye has just swept past it — which, for ahead, roughly doubled (≈8 s → ≈14 s)
under the same reshape, because the old table visited 12 o'clock twice per cycle and the new one
visits it once. The plan's own Risks section named the premise ("ahead seen half as often") but
immediately answered it with the decay-revisit arithmetic, which doesn't speak to it.

The architect's mitigation ("the pilot is looking ahead himself, flanks are where Petrovich adds
value") is the right *kind* of argument — the project's own whose-job test, applied in the right
direction — but it asserts the player's attention is actually on 12 o'clock when something
appears there, which is a different claim from "the player can physically see ahead." Low-level,
fast, eyes-on-instruments flying is exactly when that assumption is weakest, and it is the one
sector most tied to evasion.

**How to apply**: whenever a plan reshapes a scan/sweep table and reports a "revisit" number,
check whether that number is decay-revisit (an existing contact losing certainty) or
first-detection latency (a new contact appearing cold) — they move independently when a sector's
visit *count* per cycle changes, not just the cycle length. A plan that discloses one and implies
it covers the other is a finding, not a pass. See [[project_staged_by_measurement_can_hide_a_scope_decision]]
for the sibling pattern (a staging decision framed as settled that was actually a scope decision).
