# 9K113 sight — direction, 2026-10-15

User direction arriving in response to `plans/9k113-sight/plan.md` (architect pass, 2026-10-15) and
its five open decisions. Captured verbatim per the standing rule: the user's own words are the
specification, and paraphrasing them loses the part that decides the design. `/explore` is owed on
what remains open before an Architect amendment.

Supersedes nothing in `docs/concept/9K113.md` — that document is the user's own and is not edited
here. Where this contradicts the plan, **this wins**.

---

## §1 — The ASP-17 is not an effector. It is not touched at all.

> *"Note: ASP-17 *must not* be manipulated directly. It shows the pilot where the 9K113 is pointing,
> but that's automatic, not manual."*

**This removes a whole use case from the plan.** The plan treated "hold the crosshair so the pilot
can read the target off the ASP-17" as one of two non-ATGM uses, and placed it on the effector axis
(Axis B) because it appeared to need cockpit writes. It needs none: the ASP-17 mark follows the
9K113's pointing automatically. Whatever makes the sight point somewhere makes the mark move; there
is no separate "mark the target" action to build, and building one would be wrong.

---

## §2 — "Poor vertical understanding" is two separate things, and only one is about the sight

> *"There two separate things here really. The 9K113 itself is very precise on where it is pointing.
> However, the copilot only has azimuth reading for it, and not a precise one. See reference image I
> pulled from the manual. The 1, 3 and 6 along the bottom part of the circle refer to 10, 30 and 60
> degree offset from boresight in azimuth. Nothing at all tells the vertical offset. The copilot can
> of course judge that himself based on visually apparent angle, position of horizon etc, but there
> is no instrument reading. That is what I mean by poor horizontal understanding."*

(The closing sentence says "horizontal"; the section is headed *"poor vertical understanding"* and
every clause before it is about the vertical axis. Read as **vertical** — recorded rather than
silently corrected.)

**This answers the plan's open Decision 2, and none of the three candidate mechanisms it proposed
was right.** The plan asked whether the coarseness was in the DCS readout, the reticle, or the
difficulty of judging depression — reasoning from the optics, and correctly noting that the sourced
FOVs are symmetric so the *sight* has no asymmetry. The actual answer is upstream of the optics
entirely: **the sight is precise, the instrumentation is asymmetric.** There is an azimuth scale and
there is no elevation scale. The asymmetry is in what the crewman can *read*, not in what the
instrument can *see*.

**The reticle, as the user describes it** — the image he supplied is committed at
`docs/concept/mi-24_info/9k113-reticle-narrow-x10.png`, so this section has a durable referent:

- A bottom arc marked `1`, `3`, `6` each side of `0` — **10°, 30°, 60° azimuth offset from
  boresight**. This is the only angular readout on the instrument.
- `x10` marks the magnification (the narrow mode).
- Two bracket marks annotated `⊥10` and `⊥50` at upper left — the stadiametric scale the user calls
  "the distance tool" below. *(The 10/50 are inferred to be target-size references in metres; this
  reading is mine, not the user's, and is unverified.)*
- A vertical ladder of `+` ticks above and below centre, and a horizontal row either side. **The
  user's account says these carry no elevation *reading*** — so they are aiming/lead marks, not a
  scale a crewman could report an angle from.

---

## §3 — Azimuth is not exact either, and the belief is built by cross-reference, not by readout

> *"Azimuth is not exact either, though there is that indicator. So the way it works for the copilot
> is that he combines the knowledge of azimuth with what he sees through the scope and then uses
> landmarks to understand where the targets are."*

So even on the axis that *has* an instrument, the instrument alone does not produce the belief. It
is one input among three: the coarse azimuth reading, the view itself, and the landmarks in it.

---

## §4 — The worked example, in full, because the procedure is the specification

> *"Exaample. Using 9K113 wide I see something right of village at about 10 degrees left azimuth.
> Using the distance tool I can see that they are >5km away. I switch to the narrow mode to see the
> units better and classify/identify is possible. I use narrow to see more detail and wide to see
> more surrounding. Them using naked eye or binoculars I combine my understaning from 9K133 view
> with where I am, what is in that direction and how it matches with what I saw about where the
> units are. That creates the belief of unit location. That goes to memory."*

Read as a sequence, this is: **wide to find → stadiametric range → narrow to classify → wide again
for surroundings → naked eye or binoculars to tie it to the world → belief → memory.** The wide and
narrow modes are not a quality setting, they are two different jobs, and the crewman moves between
them repeatedly within one observation.

Note what carries the position: **not the sight.** The sight gives direction, a coarse range and an
identification. The *location* comes from matching that against ownship position and what is known
to be in that direction — which is exactly this project's existing landmark/semantic-position
machinery, not something new.

> *"Now, that was a human usage example. While not directly translatable to code through code not
> actually seeing through the scope, we should use that principle and simplify it enough that it
> becomes sensible to implement and performative enough to actually use. Simplification is
> expected."*

**Simplification is explicitly authorised.** The procedure above is the principle to preserve, not a
specification to reproduce step for step.

---

## §5 — Staging: perception first, then effectors, then the ATGM run. Confirmed.

> *"Lets start with that, that let's us test the behaviour. We'll then add actually manipulating the
> systems in cockpit. Only then can we add the ATGM attack run."*

This confirms the plan's own central recommendation (Axis A → Axis B → ATGM) and answers its open
Decision 1: **a perception-only 9K113 is acceptable as an interim**, and the reason given is
testability — it is the stage that lets the behaviour be flown.

Three entries, in order, not one feature.

---

## §6 — OBSERV: commanded on, then autonomous within

> *"Let's start with*
> *- OBSERV ON only on pilot command*
> *- if OBSERV is ON, then Petrovich can use the 9K113 autonomously, like he uses binoculars."*

This answers the plan's open Decision 3, and it does so by **splitting the question the plan could
not answer**. The plan asked whether autonomous OBSERV was in scope and recommended deferring it
pending an `/explore`. The answer is that *entering* the mode is always the pilot's call, and
*within* the mode the sight behaves like an optic Petrovich already owns.

**That second clause is the load-bearing one**: "like he uses binoculars" means the existing optic
policy — dwell, scan, the rate limit that makes an instrument unusable under manoeuvre — applies to
the 9K113 as another optic, rather than needing its own attention model. It makes the 9K113 a new
entry in a mechanism that exists, which is a far smaller build than the plan assumed.

---

## §7 — The player bubble needs an exception, and this is new

> *"9K113, especially in narrow FOV mode can detect targets further than 10 km away. So, when OBSERV
> is ON, we need an extra cone of player bubble. In the direction 9K113 is pointing at, with the FOV
> it has, a cone up to 20 km must pass units into detection logic."*

**Not in the plan at all.** The plan established that the sight's *perception* could reach ~8 km and
treated that as a body-layer matter. This says the constraint binds a layer further out: units
beyond the player bubble are not exported at all, so no amount of body-layer capability can perceive
something DCS never sent.

Shape of the requirement, in the user's terms:

| | |
|---|---|
| when | OBSERV is ON |
| direction | wherever the 9K113 is currently pointing |
| width | the sight's own FOV (wide or narrow, as selected) |
| depth | **up to 20 km** |
| effect | those units pass into detection logic |

**Answered in the same conversation — the cone is body-layer only, and no probe is needed:**

> *"whether DCS hands us units at 20 km at all -> it does, that's been verified earlier. DCS can
> export *every* unit in the whole mission. That is why we built the bubble, to not calculate each
> and every unit and distances where they do not matter at all."*

So the export side needs no change and `AC-B3` is not involved. `PLAYER_BUBBLE_RADIUS_M = 10000.0`
(`body-layer/src/perception/association.py:116`) is purely a **cost filter of our own choosing**, and
its own comment already said so — *"a decision about what is worth computing, taken on the pilot's
own judgement… it is a number to revisit, not a law"*, with DCS's own culling radius explicitly left
unestablished. This direction establishes it: there is no culling to work around.

**What that makes the work:** a directional exemption to a filter we own, in one function, in
body-layer. The cost question is the only real one left — the cone admits more candidates into the
per-tick distance work the bubble exists to avoid, and narrow mode's reach is what makes the
exemption worth having (the measured multipliers put narrow presence at ~13.6 km for a 7 m vehicle
and ~19.4 km for a 10 m one, so 20 km is close to where the sight genuinely runs out, not a round
number).

---

## §8 — Both FOVs are simulated from the start, and the sight is slow to move

> *"both. We simulate the percetion in any case, so we can first build the simulation and then add
> the cockpit instrument manipulation. Do not that the 9K113 via cokcpit manipulation *takes time to
> move* so we cannot expect instant alignment with anything."*

(«Do not that» read as «Do note that».)

**This resolves the FOV question without a fiction.** The perception simulation is being built
*regardless* of whether the cockpit switches move, so both modes exist in the model from the start
and Axis B later makes the real switches follow. Petrovich is not pretending to use a mode he
cannot select; the model is simply ahead of the effectors, which is the same relationship
`BINOCULAR_OPTIC` already has with a cockpit that has no binoculars in it.

**The slew-time constraint is new and is not in the plan.** The sight takes real time to move, so
**nothing may assume instant alignment** — not the perception stage and not, later, the ATGM run.
Worth building into the simulation *now* rather than when the effectors land, because a perception
model that snaps instantly would produce behaviour Axis B could never reproduce, and the difference
would surface as a regression rather than as a known gap.

> *"Swithing between wide and narrow should use similar logic to naked eye and binocular usage. That
> is quite analogous example, the 9K113 just has a longer "reach", can see further, though also a
> much more limited FOV."*

So wide↔narrow is the **same mechanism** as naked eye↔binoculars, not a new one. The axis is
reach-versus-field, exactly as it already is for binoculars; the 9K113 simply sits further along it.

## §9 — The 9K113 has its own timing, unlike the other optics

> *"This also leads to 9K113 usage following different timing schedule than the naked eye and
> binoculars. When using 9K113 we typically use if for a longer period of time. Maybe take eyes of
> if for a quick glance around and then continue with the sight."*

**The mechanism is shared, the constants are not.** `optic_policy`'s existing dwell/scan machinery
applies, but the 9K113's dwell is *long* and its interruptions are brief glances away that return to
the sight — the opposite shape from binoculars, which are a short raised-to-the-eyes act between
periods of naked-eye scanning. With the sight, the sight is the baseline and the naked eye is the
interruption.

## §10 — Vertical: nothing about the sight's own angle, everything about the world

> *"No, not about the 9K113 elevation angle. Distance yes, target world reference yes - like your on
> the ridge example. So, things that can be perceived about where the target is in world, not about
> 9K113 angle."*

The dividing line is **what the crewman could know versus what the instrument would have to tell
him**. He has no elevation readout (§2), so no elevation angle is ever spoken. He *can* see that the
target is on a ridge, in a valley, behind a treeline — that is world knowledge, reached by
cross-reference, and it is already this project's existing semantic-position machinery.

> *"We do know the approximate azimuth offset so that can be used in callouts as well as attack run
> guidance. But then the already existing system there is perfectly fine: o'clock's until 12 o'clock
> sector and then left/right guidance."*

**No new guidance register.** `BL-14`'s existing scheme — o'clock positions until the target is in
the 12 o'clock sector, then qualitative left/right — covers the sight too. The approximate azimuth
offset feeds it; nothing about the sight needs its own vocabulary.

## §11 — The stadiametric measurement is an act with a cost, and a group is measured once

> *"Yes, but let's just use a time constant for that. Let's say it takes 2s to measure distance."*

> *"Note that if I'm looking at a group, I don't need to measure the distance to each unit, I'll just
> get the middle one and then use that for group position. Then if I need to know an individual units
> distance, I can use the stadiametric on that one. Use case for that would usually be attack run, to
> know when we are in ATGM range."*

**Two things fall out, and the second is the one that saves work.** Ranging costs ~2 s of the
crewman's attention, like the existing eyes-away costs. And **a group is ranged once, at its middle
unit, with that range standing for the whole group** — so the per-unit ranging cost the obvious
implementation would incur does not arise. Per-unit ranging is a deliberate, occasional act with a
named use case: knowing whether a specific unit is inside ATGM range during an attack run.

> *"An acceptable first phase implementation is that distance measurement is instant, though not
> perfect. The stadiametric scale is still just a visual aid, id does not give excat answers."*

**First phase: instant but imprecise.** The 2 s cost can come later; what must be right from the
start is that the answer is **approximate**. This is a `BL-B55` matter — the sight's range error is
better than the naked eye's but is not a laser's, and modelling it as exact would be a worse error
than modelling it as free.

---

## What this leaves open

- **The two remaining plan decisions** — the missile word, and the launch-callout interim — are both
  superseded in part by the 2026-10-15 missile-data addendum
  (`body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`) and belong to the ATGM stage,
  which §5 places last. Not urgent.
- **What the sight's range error actually is** (§11). "Approximate, better than the naked eye, not a
  laser" is the shape; the number is not set, and it is `BL-B55`'s to establish.
- **The cone's per-tick cost** (§7) — the only remaining question on the player-bubble exemption,
  now that the export side is known not to be involved.
- **Whether slew time is modelled in the perception stage or deferred with the effectors** (§8). The
  direction says alignment is never instant; it does not say which stage owns that.
