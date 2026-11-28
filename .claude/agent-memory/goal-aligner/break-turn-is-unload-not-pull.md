---
name: break-turn-is-unload-not-pull
description: Mi-24 break turn why got wrong in the 2026-11-20 goal check — E5 expected collective to come in with the bank; user flies a break with LESS collective, nose low, height spent
metadata:
  type: feedback
---

The 2026-11-20 BL-16 goal check (E5) derived "back-cyclic and collective come in promptly and in
proportion" for a break from the lift-vector framing (more bank → more lift needed → more
collective). That was wrong for the Mi-24 in DCS: the 2026-11-28 sortie failed precisely because
collective went full up chasing height at 60°+ bank (nose rose against full forward cyclic, 213 →
81 km/h, then −52° pitch, below the floor). The user's own technique (explore-notes "LV-2
re-explore", 2026-11-28): bank 30–60°, pedal with bank, nose ≈ −10°, collective **20–30 % of lever
travel lower**; speed and rotor are kept, height is the currency.

**Why:** a level-turn physics derivation ("hold height, so add lift") answered a question the pilot
does not ask; the why of a break is escape with energy kept, and height is what a pilot spends.

**How to apply:** for any manoeuvre goal, ask what the pilot *spends* and what he *keeps* before
deriving control expectations from physics; a "hold everything" expectation for an aggressive
manoeuvre is a signal to ask. Also check, on any "fallback/degraded" behaviour, that the existing
caps (e.g. ordinary `max_turn_bank_deg` 20°) do not silently reduce it to the ordinary case.
Related: [[break-rollout-height]] (pending user answer, 2026-11-28 goal check Q1).
