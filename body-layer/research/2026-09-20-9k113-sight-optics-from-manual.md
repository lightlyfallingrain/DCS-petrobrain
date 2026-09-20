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

## The sight's real angular limits — SOURCED (user, 2026-09-20)

**Periscope lateral axis: ±60°. Periscope vertical axis: +20° / −15°.**

Source: the **English-language** edition of the Mi-24P manual, §3 "RADUGA-SH COMPONENTS", §3.4
"Missile Guidance Controls". **That document is not in this repository** — the Russian QuickStart
PDF that is (`docs/concept/mi-24_info/`) organises the same material as §4.6.7 and does not carry
these figures on any page searched. Supplied by the user, who located them after this note's first
version got the azimuth wrong.

This is the **field of regard for the magnified channel**: the sight head cannot be pointed outside
it, so a contact beyond ±60° azimuth or outside +20°/−15° elevation is unreachable through the
9K113 however visible it may be to the unaided eye. The cones model now has a sourced third bound,
distinct from both the optic's own field of view and the cockpit occlusion mask.

### Why the earlier mistake was plausible — worth keeping

The first version of this note read ±40° azimuth and −15°/+20° elevation off the annotations on the
ПУ ПН control-console photograph and reported them as the sight's limits. **The vertical pair was
right. The azimuth was not.**

That partial agreement is the interesting part. Had both been wrong the error would have announced
itself; instead one axis matched the real figure exactly, which is precisely the shape of evidence
that makes a wrong reading feel confirmed. The lesson is not "check your numbers" but something
narrower: **a figure printed beside a photograph of a control describes that control**, and
agreement on one axis is not evidence about the other.

The underlying reason they cannot be the same quantity is now established independently — the
manual states the operator commands an angular *rate*, not a position (see the second-pass section
below), so console deflection and head angle are different kinds of thing. Any coincidence between
them is just that.

## Control-console travel — not the sight's own limits

The ±40° azimuth and −15°/+20° elevation annotated on p.70 (Рис. 4.20) belong to the **ПУ ПН
control console** — the operator's handle, the input device — not the optical head. See the
sourced figures above for the head's own limits.

The distinction matters for the cone model. The console's handle travel and the sight head's
angular deflection need not map one to one, and the manual describes the linkage as a
*spring-centred* control: release the force and the head returns toward a rest position, which is a
rate-or-displacement control relationship rather than a direct angular mapping (p.71, items 2 and
4). Treating handle travel as a field of regard would have put a wrong bound into `optics.py` and
made it look sourced.

**Resolved:** the head's own limits are now sourced from the English edition — ±60° lateral,
+20°/−15° vertical. See the top of this note.

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

## Second pass: looking for the sight's own angular limits (2026-09-20)

The user recalls seeing the 9K113's real limits in this manual — **azimuth ±60°**, elevation not
remembered. Searched pages **66–75** (all of §4.6.7), **80–81** (§4.11, which turns out to be an
empty heading), **105–108** and **110–113** (the ПТУР employment procedure).

**The elevation limit was not found on any of them**, and the search was abandoned rather than
completed — the user located both figures in the **English-language edition** instead (§3 "RADUGA-SH
COMPONENTS", §3.4 "Missile Guidance Controls"), which states them outright. See the top of this note.

Worth recording for the next person searching this PDF: the Russian edition organises the same
material as §4.6.7 and, across every page read, never states the head's angular limits. The
equivalent English section does so in two bullet points. **Where the two editions diverge in
structure, the English one is worth checking first for a plain numeric specification** — it is not
merely a translation of the same pages.

The search turned up four things that matter more to the cones model than the limits would have.

### The operator commands an angular RATE, not an angular position

Verbatim, p.113 step 14:

> оператор управляет не угловым положением ЛВ ПН, а **угловой скоростью** ЛВ ПН … Чем сильнее
> отклонен джойстик, или чем дальше перемещена мышь, тем быстрее начинает двигаться прицельная
> марка.

This **confirms the correction made earlier today rather than merely supporting it**: the control
console's travel could never have been the sight's field of regard, because deflection sets *slew
rate*, not angle. Handle position and head position are not the same kind of quantity.

For the cones milestone this is a direct input to slice 2 rather than slice 1: **pointing the sight
somewhere costs time proportional to angular distance**, at a rate the operator chooses. A scan
model that teleports the sight between sectors would be wrong in a way the manual explicitly
describes.

### The sight has physical doors, and they are a real state

p.110 step 10 and p.72 item 3: the `НАБЛ.` switch opens the **outer doors** (наружные створки) of
the nose turret — hydraulic pressure required — and the inner doors are separately switched.
Switching `НАБЛ.` off automatically closes inner then outer, in that order.

So the state-transitions diagram's **"Observ off = close 9K113 doors"** is a real physical action
with a real sequence, not a UI nicety. A cone model that lets the magnified channel see while the
doors are shut would be wrong.

### Launch entry requires the sight line within 0.86° of the airframe axis

p.112 step 12: while the sight line is parallel to the construction axis (СГФ) or near it, a red
cue and a buzzer indicate the missile-entry condition is satisfied; **beyond 0.86° of deflection
the condition disappears.** The operator's panel lamp `РАЗРЕШ. ПУСК` states the same bound as "not
more than 1°" (p.67).

That is a *launch* constraint rather than a *seeing* constraint, and worth keeping separate: the
sight can look well off-axis, but the missile can only be fired into a narrow cone ahead.

### Magnification is toggled in flight

`LCtrl+X` switches ×3.3 ↔ ×10 (p.112–113), and the manual's own step 13 says to use **both** when
searching and identifying: search wide, identify narrow. That is a behaviour the cones design
should expect rather than picking one magnification per mode.

### Also noted

The head is **gyro-stabilised** and takes about three minutes from power-on before `ГОТОВ` lights
(p.75, p.110) — a warm-up state the model does not currently have. And the IR seeker's diaphragm
works over an 8–16 arcminute viewing angle (p.73 item 12), which is the *missile tracker's* field,
not the optical sight's, and should not be mistaken for it.
