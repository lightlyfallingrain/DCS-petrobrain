# The 9K113 sight's real optics — from the DCS Mi-24P manual

**Date:** 2026-09-20 · **Source:** `docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf`,
§4.6.7 "Пульты и объекты комплекса УРВ 9К113", pages 68–71 (Russian)

Found while wiring that PDF into the project's reference surface. It answers, with published
figures, two things the detection-cones slice 1 plan had recorded as **placeholders** and one
question the roadmap had flagged as "verify before building" — and it produced one over-claim,
corrected below, which is recorded rather than quietly deleted.

## Magnification: ×3.3 and ×10, switchable

The прибор наведения (ПН, guidance unit) has a magnification selector — handle position A gives
**×3.3**, position B gives **×10** (p.68, Рис. 4.17 item 1). So the sight is **two optics, not
one**, and the cones design needs both: a wide mode and a narrow one, with whatever field of view
each implies.

**This lands close to an assumption already in the code.** `visibility.py`'s
`BINOCULAR_RANGE_MULTIPLIER` is ×4 — a deliberate modelling choice for "what a crew member sees
through binoculars", owned by this project rather than transcribed from DCS. The sight's low
setting is ×3.3. That is near enough that today's calibrated behaviour is approximately *the sight
at its wide setting*, which is worth knowing before anyone reasons about what the current numbers
represent.

## Control-console travel — NOT the sight's own limits

**Corrected 2026-09-20 by the user, who spotted the over-claim before it propagated.** An earlier
version of this note reported ±40° azimuth and −15°/+20° elevation as *the 9K113 sight's slew
limits*. They are not. They are the annotated travel of the **ПУ ПН control console** — the
operator's handle (p.70, Рис. 4.20, "missile control console") — which is the input device, not the
optical head.

The distinction matters for the cone model. The console's handle travel and the sight head's
angular deflection need not map one to one, and the manual describes the linkage as a
*spring-centred* control: release the force and the head returns toward a rest position, which is a
rate-or-displacement control relationship rather than a direct angular mapping (p.71, items 2 and
4). Treating handle travel as a field of regard would have put a wrong bound into `optics.py` and
made it look sourced.

**The 9K113's own angular limits are in this manual** — the user confirms they are there — but not
on the pages read so far. Until they are found and cited, the cone model has **no sourced field of
regard for the sight**, and should say so rather than substituting these numbers.

The lesson generalises past this note: a figure printed next to a photograph of a control describes
*that control*, and the temptation to read it as the system's limit is exactly the kind of
plausible-but-wrong claim a citation makes durable.

## Stadiametric ranging: calibrated for a 2.5 m target, marks at 1000 m and 5000 m

The reticle's дальномерные штрихи are published precisely (p.70, Рис. 4.19):

> **"50"** indicates a range of **5000 m** when a target **2.5 m tall** fits between the horizontal
> stroke and the bottom of the "50" mark, touching both lines.
> **"10"** indicates **1000 m** under the same rule.

Reticle geometry is given in mils — 0.5, 2, 2.5, 5, 10 and 13 mil markings.

**This verifies the roadmap's open assumption.** The range-uncertainty entry said the 9K113's
stadiametric aide is "useful to ~5 km, verify before building". Verified: the scale is explicitly
calibrated to 5000 m, and the reference target height is 2.5 m — which is a real number for the
model rather than a guess, and close to the 7 m vehicle length the vision calibration used for a
different axis.

It also confirms the shape the range work was planning: **using the sight should narrow the belief**
rather than merely reword the callout, because the sight genuinely supplies a measurement the naked
eye cannot.

## Filters — relevant to the conditions backlog, not to slice 1

Two filters are modelled (p.68, items 2 and 5):

- an **orange filter** for haze and low target contrast — i.e. the aircraft itself carries a
  mitigation for exactly the conditions the "Detection under real world conditions" backlog entry
  describes. Worth remembering when that work starts: the crew is not helpless in haze, and
  modelling only the degradation would be half the picture.
- a **green filter** protecting against laser illumination.

## What this does not settle

The **field of view in degrees** at each magnification is not stated in these pages — only the
magnifications and the slew limits. The reticle mil markings bound the *visible* angular extent
indirectly (13 mil ≈ 0.74°) but that is the reticle's extent, not the eyepiece's. If slice 1 needs
a real FOV figure rather than a placeholder, that is a further question for the manual's optical
sections or for measurement in the sim.
