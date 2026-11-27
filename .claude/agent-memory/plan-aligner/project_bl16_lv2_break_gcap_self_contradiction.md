---
name: bl16-lv2-break-gcap-self-contradiction
description: BL-16 LV-2 amendment (breaks) — a design constant's own justification was contradicted by the plan's own next paragraph; worth checking adjacent prose, not just the number.
metadata:
  type: project
---

BL-16 LV-2 amendment (`plans/flight-lift-vector/plan.md`, 2026-11-27, break_max_bank_deg): the plan
picked 65° "deliberately a touch above" the user's own "~2 G momentarily" figure (60° = 2.0 G exactly,
65° ≈ 2.37 G), justified by "the rate-cap... not this angle alone, is what actually bounds the load in
practice." The very next subsection ("Effect, by speed") showed the cap **binds continuously at every
card speed** (120/180/250 km/h all need more bank than 65° for the commanded rate) — meaning the break
flies *at* 65° (2.37 G) for several seconds every time, which is the opposite of what the justification
claimed. Caught only by reading the design-constant paragraph and the very next paragraph together and
doing the arithmetic (`1/cos(φ)`, `atan(ω·V/g)`) myself rather than trusting either sentence alone.

**Why this matters generally:** a plan can disclose a gain as a "first cut, measured on the card" (this
project's standard posture, usually fine) while also writing a self-contradicting justification for why
the chosen value is safe. The "first cut" disclosure does not excuse checking whether the stated
reasoning for the specific value actually holds — those are two different things. This was a genuine
Finding, not covered by the project's usual "first cut, card measures" allowance, because the
contradiction was *internal to the plan's own two paragraphs*, not a question the card could settle.

**How to apply:** when a plan names a design constant "a touch above/below" a user-stated figure with an
explicit reason ("X, not Y, is what actually bounds this"), check that reason against the plan's own
very next subsection before accepting it — the two are often adjacent and the contradiction is visible
without any code read, just arithmetic on numbers the plan itself supplies.

See also [[project_bl_b124_hybrid_channel_unaddressed]] for a different pattern (a module map gap)
caught the same way — reading everything the plan says about one mechanism, not just its header claim.
