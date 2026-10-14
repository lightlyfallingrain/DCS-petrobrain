# Attack-run guidance: alignment only, and stepping is keyed on line of sight — user direction, 2026-10-14

**Captured during the `/explore` as it was said**, per the standing direction of 2026-10-05. This is
design direction on cockpit behaviour for `BL-14`, and it **reverses the register the 2026-09-24
notes and `docs/concept/Attacking target.md` described**. The user's own words are the
specification.

Context: he was shown a worked table of a paper run-in — Mi-24P at 220 km/h, 120 m AGL, rolling in
from 3 km with 8° of initial heading error, pilot correcting at ~1.2°/s, a callout every 2 s — in
both candidate registers (o'clock/km, and boresight-relative degrees). The table made three things
visible: azimuth error is gone within ~6 s, both registers then collapse to a range countdown, and
the run is 23 callouts in 45 s.

---

## His words, verbatim

> *"No degree down and neither range beyond the initial report. Alignment is what matters. When
> attack run starts from a fairly close distance or there's terrain to navigate then the alignment
> is the important part and the time to weapon release might be short.*
>
> *Stepping: step through believed contacts. The important part is the LOS direction, what unit is
> next left/right from the current LOS. Because it changes as/if we circle the contacts. Or the
> contacts move."*

---

## What is decided

### 1. The guidance register is **alignment**, not position

**Struck from the design:**

- **No "N degrees down".** It is very nearly pure altitude-over-range, which the pilot can see out
  of the window and read off his own instruments. It was computable, which is not the same as
  useful — the table above is what exposed that.
- **No range countdown.** Range is reported **once**, in the initial report, and then not again.

**What remains is azimuth alignment.** The content of an attack run is whether the nose is on the
target, and nothing else.

### 2. The reason, and it changes the shape rather than trimming the wording

> *"When attack run starts from a fairly close distance or there's terrain to navigate then the
> alignment is the important part and the time to weapon release might be short."*

The paper run-in assumed a clean 3 km roll-in over open ground, which is the case where a range
countdown has room to be useful and alignment is settled early. **The real case is the opposite**: a
run begun close in, or threading terrain, where the seconds before release are few and the only
question that can still be answered in time is *am I pointed at it*. A design fitted to the open-ground
case optimises the wrong end of the run.

### 3. Stepping walks **believed contacts**, ordered by current line of sight

> *"step through believed contacts … what unit is next left/right from the current LOS"*

This settles the question left open on 2026-10-13 — whether `step right` has to walk the *world*
(and therefore wait for attention-driven per-unit resolution, which does not exist) or may walk the
belief store. **It walks the belief store.** `BL-14` is therefore not gated on the resolution
mechanism for its stepping half.

**And the ordering is not a list.** The next unit is the next one **left or right of the current
line of sight**, evaluated now:

> *"Because it changes as/if we circle the contacts. Or the contacts move."*

So the order is **angular around the current LOS bearing from ownship's present position**, recomputed
at each press — not an ordering fixed at selection time. Circling the target group reorders it, and so
does the units moving. An implementation that sorts once and indexes into the result is wrong in
exactly the case the pilot is most likely to be in: a pylon turn around a target group.

---

## 4. Silence means aligned — design A, chosen

He was shown two readings of the above as mock transcripts of a close-in run (1200 m, 12° off,
correcting at ~2°/s):

- **A — speak only the error.** Petrovich says the azimuth correction, says *"lined up"* once, and
  is then **silent while the nose stays on the target**. Five or six utterances across a whole run.
- **B — error, then a periodic confirm** (*"on it"* every couple of seconds). Never ambiguous,
  spends the channel saying nothing new.

> *"A"*

**Chosen: A.** Silence is the signal that the aircraft is pointed correctly. This is consistent with
every quieting decision of the last month rather than an exception to them, and it is what makes an
attack run affordable on the intercom at all — the paper run-in's 23 callouts in 45 s was the
problem, and this is the answer to it.

## 5. "Lined up" is a tolerance band, not zero — and crosswind is the reason

> *"we'll need a constant for what is considered lined up, since a small deviation from 0 is
> accepted and even expected side wind requires a little sideways offset. We'll tune the value
> later."*

**A non-zero azimuth error is the correct state, not a tolerated one.** In a crosswind the aircraft
must be crabbed for the weapon to track where it is pointed, so demanding azimuth error ≈ 0 would
have Petrovich calling a correctly-flown run misaligned and talking through the seconds before
release — the precise failure that design A exists to avoid.

So there is a constant, its value is **deliberately unsettled**, and it is tuned from flying rather
than derived. Treat it the way this project treats every other agreed guess: one named constant, one
place, a stated assumption rather than a measurement, and the sortie decides it. (Compare the
cohesion constants — `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` and the 500 m installation cap.)

## 6. The register switch is **sector-based**, not range-based

> *"Use the mechanism described for attack run call-outs: o'clock positions until target is at 12
> o'clock sector, then degrees left/right."*

Both registers survive, and the switch point is defined by **where the target is, not how far away
it is**:

| target's bearing | register | example |
|---|---|---|
| outside the 12 o'clock sector | **o'clock** | *"11 o'clock"* |
| inside the 12 o'clock sector | **degrees left/right** | *"4 left"* |
| inside the lined-up band (§5) | **silence**, after one *"lined up"* | — |

One clock hour is 30°, so the 12 o'clock sector is the ±15° wedge about the nose. This is a cheaper
and more defensible rule than the range threshold the earlier notes implied, and it falls out of the
vocabulary the pilot already uses rather than needing a second calibration: the register changes at
the moment o'clock stops being able to express the error.

## 7. Losing the target does not interrupt the run, and is not announced

> *"On losing target, use last known position. If target is moving, projected position. Say
> nothing."*

Asked what he should say when the target goes behind a ridge mid-run, the answer was that **the
question is wrong**: the run does not degrade and nothing is announced. Guidance continues against
**believed** position — last known if the target was stopped, **projected** if it was moving — and
the pilot is not told, because being told two seconds before release is worse than useless when he
can see the target himself.

**This keeps silence unambiguous**, which design A needs: silence means *you are pointed at where
the target is believed to be*, and that sentence stays true whether or not Petrovich currently has
eyes on it. It also makes the attack run the first consumer of position belief's own projection — and
makes [[the movement-keyed uncertainty direction]]
(`docs/acceptance/2026-10-13-position-uncertainty-direction.md`) matter here rather than only in
association: *"if unit is not moving, it is expected not to move"* is precisely the distinction
between "last known" and "projected" that this guidance now has to make.

## 8. Terrain is a reference, and only until aligned

> *"Terrain: a good reference, say if close by terrain feature. Only until aligned, then stop."*

So the 2026-09-24 notes' *"edge of forest"* survives, with a bound neither note had: a terrain
reference is **acquisition** help, not run help. It is spoken while the pilot is still finding and
turning onto the target, and **stops at `"lined up"`** — once the nose is on it, naming the treeline
is noise, and the channel goes quiet per §4.

## 9. The vocabulary is qualitative, not numeric — and vertical comes back

**This reverses the reading that §6's sector rule implied**, and it is the sharpest correction of
the conversation:

> *"actually, 'come right/left', 'a bit left/right' is much better than degrees and numbers.
> O'clock numbers are good because it tells me a concrete reference that is easy to understand.*
>
> *In same way '[little] higher/lower' (as reference to boresight) would actually be useful. With a
> certain gate when aligned is considered true."*

**The principle, stated in his own terms: a number earns its place only when it names a concrete
reference the pilot already reads.** O'clock does — it is a direction he can point at. "4 degrees
right" does not; it is a measurement he would have to convert. So:

| error | what he says |
|---|---|
| outside the 12 o'clock sector | o'clock — *"2 o'clock"* (§6) |
| inside the sector, large | *"come left"* / *"come right"* |
| inside the sector, small | *"a bit left"* / *"a bit right"* |
| inside the lined-up band | one *"lined up"*, then silence |

**And the vertical axis is back, qualitatively.** §1 struck *"15 degrees down"* and that still
stands — the *number* was pure altitude-over-range and told the pilot what he can see. But
*"higher"* / *"a little lower"*, **relative to the boresight**, is a correction he can act on
directly, which is a different thing from a measurement. It needs its own gate, as he says, so
**aligned is a conjunction: inside the azimuth band *and* inside the elevation band.**

## 10. Cadence is driven by change, not by a clock

> *"Cadence: when there is change."*

There is no tick. A callout is emitted when the error has **changed enough to be worth saying**, which
means a steady run is silent by construction rather than by a suppression rule layered on top of a
timer. The threshold is one more constant in the §5 class — stated assumption, one place, tuned from
flying.

**The known risk, recorded rather than designed around**: a slow steady drift produces small
per-tick changes and could stay under the threshold while the aggregate error grows. Whether that
happens in the air is a sortie question; the cheap guard if it does is to compare against the error
at the last *spoken* callout rather than the previous sample.

## 11. The elevation gate is wide — and its purpose is **which unit**, not how well aimed

> *"Elevation gate can be wide. It's there to make me aim at the correct unit, not wrong one."*

**This reframes the vertical axis rather than just sizing a constant.** It was raised as a precision
question — would a tight gate fight the pilot's deliberate ballistic offset (nose held high to loft
rockets, §9's open item). The answer makes precision beside the point: *"higher"* / *"lower"* exists
so the pilot aims at the **right target**, not so he aims well. Two vehicles along nearly the same
bearing but at different ranges, or on ground at different heights, are separated vertically, and
that is the confusion the vertical word resolves.

**Consequences that follow directly, and should not be re-derived:**

- The gate is **wide on purpose**, so the ballistic-offset conflict dissolves: a lofted nose stays
  inside it and Petrovich says nothing.
- It is **not** a fine-aim instrument, so no accuracy requirement attaches to it. Ballistics remain
  the pilot's, exactly as the 2026-09-24 note says.
- Its real acceptance test is a **discrimination** test, not an alignment one: two units close in
  bearing and separated in elevation, and whether the pilot ends up on the one he selected.

## 12. "Missed, aim higher" is dropped — a DCS limitation, not a deferral

> *"Missed, aim guidance. Drop as not possible with DCS limitations."*

The damage/firing probes established that gun rounds are **not** objects in `LoGetWorldObjects`
(rockets are), so nothing gives the impact point relative to the target, and no cockpit cue supplies
it either. **Aim correction after a miss is therefore out of the design**, not parked for later:
there is no channel to build it on, and recording it as deferred would invite someone to re-plan it
every time this document is read.

**What this does not strike** — flagged because the sentence is about *aim guidance* specifically:
hit and damage *state* remains reachable (`getLife()` per unit, `SHOOTING_START`, and fire as the
terminal visible state), so *"hit"* / *"on fire"* / *"destroyed"* are a separate question from aim
correction. Whether they are in `BL-14`'s scope at all is the open item below.

## 13. Scope: guidance only. Damage reporting is not in this milestone

Settled by direct choice at the end of the conversation: **`BL-14` is selection, stepping, alignment
guidance and end conditions, and stops there.** It stays inside body-layer and needs no new
aircraft-layer channel, which is what makes it flyable sooner.

**The consequence to state plainly, because his own spec says otherwise**: *"If target is destroyed
(on fire is enough), attack run stops automatically"* **cannot be built in this milestone** — the
damage channel it needs is probe-answered but unbuilt. So in `BL-14` a run ends **only** on the
pilot's command (`disengage` / `stop attack` / `abort`, or dropping the target, or the existing
cancel path). Petrovich never says *"destroyed"*, and the automatic stop does not exist. That is a
known gap against the spec, chosen deliberately, not an oversight — and it is the first thing to
revisit once a damage channel exists.

## 14. The weapon token is accepted but never required

> *"Allow weapon token, but do not require it. Nothing consumes it yet, but it will become important
> later."*

So the grammar admits `engage <what> <where> [guns|rockets|missiles]` and **nothing reads the
weapon** — every part of the vocabulary settled above (o'clock, come left/right, higher/lower, both
gates) is weapon-independent. Accepting it now means the grammar does not have to change when
something does consume it; requiring it now would be a slot with no consumer, which is the shape
`BL-13`'s own findings warn about.

---

## Still open, for a later pass

Nothing blocking a plan. Two values are deliberately unset and belong to a sortie, not to analysis:
the **lined-up azimuth band** (§5), the **elevation gate** (§11, wide), and the **change threshold**
that drives cadence (§10). All three are agreed guesses in this project's usual sense — one named
constant each, one place, stated as an assumption, tuned from flying.

Related: `body-layer/ROADMAP/BL-14.md`, `docs/concept/Attacking target.md` (his spec, 2026-10-11),
`plans/brain-layer/explore-notes.md` §"Attack run (user-raised, 2026-09-24)",
`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` (the attention tiers, and the
per-unit-resolution gap this direction routes around for stepping).
