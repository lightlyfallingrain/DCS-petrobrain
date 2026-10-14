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

## 15. The run claims the gaze

Settled 2026-10-14, after the Architect pass surfaced the concrete case: `_SECTOR_LEGS["left"]` is
hours `(11, 10, 9)` and contains **no 12**, so a standing `scan left` followed by `engage` would mean
**the target ahead is never looked at** — guidance running silently against an ageing belief, which
is the one circumstance that makes §4's silence a lie.

**So an attack run fixes the look on the target.** The cost is accepted: no scanning elsewhere for
the run's duration. The mechanism is already seamed for it — `ScanPlan.__post_init__` deliberately
permits a `fixed_look` alongside a commanded sector.

Note what this does *not* change: **routine reporting about everything else continues.** An attack
run must not blind the intercom to a SAM.

## 16. `silence` mutes guidance too — no exemption

Settled 2026-10-14. `silence` stays absolute, as it was deliberately built to be. Guidance is not
exempt.

The reason this costs nothing in practice: **a run cannot begin while muted**, because any command
clears silence. So the only reachable case is the pilot muting Petrovich *during* a run, which is an
instruction to stop talking, and taking it literally is the whole point of the command.

## 17. Elevation is a real boresight-relative angle — two vectors, and the discrimination test is **not** what was wanted

Asked to choose between a wide absolute gate and a *discrimination test* (speak when the nose's
elevation would put it on a different candidate), he declined the fork and specified the mechanism
instead:

> *"Elevation guidance is about target relative to boresight.*
>
> *We need two things: ownship -> target LOS vector and ownship boresight (unit) vector. Then azimuth
> guidance is the lateral angle between boresight and target LOS vectors. Vertical guidance is
> horizontal angle between ownship boresight and target LOS vector.*
>
> *Ownship boresight vector we get from DCS ownship telemetry data.*
>
> *Ownship -> target LOS vector needs ownship x,y,z and target x,y,z. Then it's a simple vector
> between them. No LOS calculation necessary since DCS will do that for us. No world elevation
> necessary since unit data has elevation.*
>
> *BTW, design approach so that fine grained elevation guidance is possible with just changing
> parameters. It may be needed, a flight will tell once there's the callouts to test."*

**So both axes are one derivation, not two mechanisms.** Form the ownship→target vector, form the
boresight unit vector, and decompose the angle between them into its lateral and vertical parts.
Azimuth guidance is the lateral component; elevation guidance is the vertical one. There is no
separate vertical model, no candidate comparison, and no second code path.

### What this corrects in the Architect's plan

The plan's finding 3 established that `Contact.last_alt_m` is set from the flat projection and its
altitude convention is `percept.ownship_at_observation.alt_m` — i.e. **the aircraft's own altitude at
the last look**, documented as not fused. That finding stands and is worth keeping: an elevation
angle read off that field reports how much the aircraft has climbed since, not where the target is.

**Its remedy does not.** The plan's answer was to take terrain MSL from
`geometry.elevation_at(conn, theatre, x, z)`, cached on the quantised position. That is now
superseded: *"No world elevation necessary since unit data has elevation."* The target's own altitude
arrives from the aircraft layer with the unit, so the vertical axis needs **no world-model query at
all** — which removes an in-loop dependency, a cache, and the `BL-B49`-shaped risk of routing
through enrichment to get it.

### Fine-grained elevation must be reachable by parameter alone

> *"design approach so that fine grained elevation guidance is possible with just changing
> parameters. It may be needed, a flight will tell once there's the callouts to test."*

This is a **structural requirement on the design, not a value**. Whatever the elevation gate starts
at, going from a coarse nudge to fine-grained guidance must be a parameter change — not a rewrite,
not a new code path, and not a second renderer. Concretely: the word thresholds and the gate are data,
the derivation is one function, and nothing in the renderer may assume the vertical axis is coarse.
The flight decides the value; the design must not decide the resolution.

## 18. Two mechanisms: world-anchored belief, and ownship-relative observation

**This is the most consequential thing in the conversation and it reaches past `BL-14`.** It arrived
in answer to a no-omniscience objection — that reading the target's DCS altitude at callout time
would make one axis of the callout omniscient while the other carried a deliberate bias — and it
dissolves the objection rather than trading against it.

> *"It sounds like we may need two mechanisms. There's the belief where the unit is* on the map*.
> That is what we have now.*
>
> *Then there's "I'm looking at it, I can tell where it is relative to ownship" and that not not a
> question of where is it in world, it's a ownship relative observation. That is what we need for
> guidance.*
>
> *I (or Petrovich) could be wrong about the world position by a lot and still see the unit plainly
> at bearing 355, 1.5 km and be able to guide to it exactly because we look at it and see it's
> relative position. (At some much later stage we may build ownship world position ambihuity as
> well, but that's much later. This is pre-GPS are aircraft after all, we might get lost, but still
> see units and world outside the aircraft and how it is* relative to ownship*.)"*

### The distinction

| | question it answers | error model | what uses it |
|---|---|---|---|
| **world-anchored belief** (today's `PositionBelief`) | *where is this unit on the map* | `BEARING_SIGMA_DEG = 3.0`, `RANGE_FRACTIONAL_SIGMA = 0.17`, plus a per-object systematic bias at `SYSTEMATIC_BIAS_FRACTION = 0.4` of single-look sigma that **never averages out** | reporting, grouping, memory, world-feature references |
| **ownship-relative observation** (new) | *where is it relative to me, right now* | direct — not mediated by the map at all | **attack-run guidance** |

**Why the relative one is more accurate, and it is not that Petrovich knows more:** most of the
world-position error is *ownship's own* error, and in a relative observation it cancels. A crewman
watching a vehicle can align the aircraft with it far better than he can state its azimuth in
degrees. `BEARING_SIGMA_DEG = 3.0` is a model of **stating** a bearing — its own docstring says it is
*"the crewman's own pointing precision, not anything DCS reports"*, bounded between the optical
resolution floor and the 15° clock half-bucket. It is the right model for *"ground, two o'clock, two
kilometres"* and the wrong one for *"come left"* while looking straight at the thing.

**His pre-GPS framing is the proof the two are independent**: an Mi-24P crew can be badly lost — wrong
about where they are on the map by a lot — and still guide a gun run exactly, because the guidance
never passes through the map. Ownship world-position ambiguity is explicitly **deferred to much
later**, and this design does not block it: when it arrives it degrades the world-anchored belief and
leaves the relative channel untouched, which is the correct coupling.

### What this changes in the plan

- **Guidance derives from the relative observation, never from `Contact.last_position`** while the
  target is being looked at. The attack run fixes the gaze (§15), so during a run that is the normal
  state rather than a lucky one.
- **The cluster-bias-anchor risk evaporates for guidance.** The bias is hashed off
  `min(member.object_id)` of the cluster (`naked_eye_source.py:957`, a documented limitation), so a
  mid-run membership change — destroying one vehicle of a group, exactly when a re-attack happens —
  shifts the *world-anchored* believed position by the bias delta. At 300 m a 20 m shift is 3.8°,
  enough to fire a spurious *"come left"*. **Guidance never reads that channel while looking**, so
  the risk applies to reporting, not to the run.
- **§7's fallback becomes a clean second tier rather than a special case.** Looking → relative
  observation. Lost sight → project from world-anchored belief against ownship position, inheriting
  ~1.2° azimuth / ~0.4° elevation of bias-driven error at 1 km (computed from the constants above).
  Both are inside the proposed 5° band, and silence keeps meaning one thing. *"Last known position.
  If target is moving, projected position"* is exactly this tier.
- **Guidance gets *more* accurate as the run develops** — the opposite of what reading map belief
  would have produced.
- **No world-model elevation query, and no live truth read into belief.** §17's mechanism stands;
  the invariant objection is answered by the channel being a genuine relative perception rather than
  a map lookup.

### The reading being planned against, stated as an assumption

*"guide to it exactly because we look at it"* is read as: **v1 treats the relative direction as exact
while the look holds**, with the noise term present as a parameter fixed at zero so a value can be
given later without a rewrite — the same structural requirement as §17's fine-grained elevation.
Pilot pointing error stays the pilot's, consistent with ballistics staying his. If a small error was
meant from the start, this is the line to correct.

### Scope note

This is a **new perception datum**, not a reinterpretation of an existing one, so it is scope the
earlier stages did not carry. It is also mechanically *simpler* than the world-anchored path — the
aircraft layer already publishes unit `x`/`y`/`z` and ownship position plus attitude, so the relative
vector is a subtraction and a frame rotation. What it must carry is a **bound**: it exists only while
the target is actually being looked at with line of sight clear, which is what makes it a perception
rather than a map read.

## 19. Lost sight is spoken as a qualifier on the guidance, not as an event

> *"When lost sight -> "right/left, obstructed"."*

**This refines §7 rather than contradicting it.** §7 said *"Say nothing"*, and that still holds for
the thing it was about: **losing the target is not announced as an event** — there is no *"lost
contact"*, no interruption, no change of task. What changes is that the ongoing guidance callout
**carries a qualifier**: `"right, obstructed"` / `"left, obstructed"`.

**Why this is better than the alternative that was about to be chosen.** The Architect pass had found
that guiding on projected belief while circling carries ~3.9° of error at 1σ (see §20), against a
5° lined-up band — so a silent switch between channels could move the aim point ~4° and fire a
spurious *"come left"* at an aircraft the pilot had not moved. The proposed fix was to restrict the
fallback to coarse words so a 4° shift would produce no utterance. **The user's answer is better: one
word tells the pilot which channel he is hearing.** The transition becomes *observable* without being
*announced*, silence keeps meaning exactly one thing, and the pilot can discount the precision
himself rather than the system pretending to a precision it does not have.

Note what his own example also does: it drops the magnitude word. Not *"come right, obstructed"* or
*"a bit right, obstructed"* — just **direction plus the qualifier**. So the obstructed register is
inherently the coarse one, which is the same outcome the coarse-register restriction was reaching
for, arrived at by vocabulary instead of by a rule.

**Both axes carry the qualifier** — confirmed 2026-10-14. His example gave only azimuth; the
Architect pass extended it to the vertical (*"higher, obstructed"* / *"lower, obstructed"*) as its
own inference and flagged it as such, and the extension was put to him and confirmed. The reason it
matters rather than being symmetry for its own sake: a bare *"lower"* during an obstructed stretch
would sound like it came from a live look, so marking one axis and not the other would make half of
each callout silently more confident than the other half.

## 20. Relative direction is exact while the look holds

> *"Relative direction while he's looking at it -> exact."*

Confirms §18's stated assumption. `RELATIVE_DIRECTION_SIGMA_DEG = 0.0`, present as a parameter so a
value can be given later with no rewrite (§17's structural requirement), and **pilot pointing error
stays the pilot's** — consistent with ballistics staying his.

For scale, so the zero is a decision rather than an oversight: at 1 km, 1° of pointing error is 17 m
of cross-track against a 5° band, so a non-zero sigma would be felt as occasional chatter near the
band edge.

## 21. Why a finished angle cannot be carried — three reasons, and the third reaches another subproject

The Architect pass established that the crew loop polls at 1.0 s and a 45° bank turn at 220 km/h
yaws at `g·tan45/V` = **9.2°/s**, so an azimuth frozen at the observing poll is ~9° stale one poll
later — nearly twice the lined-up band. Hence the datum carries an ownship-frame **offset**, re-rotated
against current attitude each poll. The user added three things that reframe what that means:

> *"1 - it takes some time to speak the words, so any update is a couple of second old by the time I
> hear it. 2 - angle changes fast when turning in for attack run. When the target is in 12 o'clock
> sector, also the ownship movements become more gentle. 3 - this could be a good reason to separate
> telemetry updates to different frequency than world object updates. The target position is not
> going to change by that much, but ownship angles might change quickly."*

**1. Speech latency bounds the useful precision.** A callout is already a couple of seconds old by
the time it is heard, so precision beyond that is spent on nothing. This is an argument against
chasing freshness past a point, and it belongs next to the cadence rule (§10): *what* is said should
be worth saying by the time it arrives.

**2. The register and the dynamics co-vary, so the design self-balances.** Angular rate is highest
during turn-in — which is exactly the o'clock phase, where the words are 30° buckets and 9° of
staleness is immaterial. Once the target is in the 12 o'clock sector the movements are gentle, which
is exactly where the words become fine. **The phase where precision matters is the phase where the
geometry is calm.** This is why the poll split below is an optimisation rather than a prerequisite,
and it should be stated in the plan so nobody treats the 9.2°/s figure as a blocker.

**3. Ownship telemetry and world objects should update at different rates** — and this corrects a
filed assumption. `aircraft-layer/ROADMAP/AC-B3.md` ("Split the export throttle", raised 2026-09-09)
proposes exactly this and dismisses it as *"Not urgent — no measured FPS cost yet to react to… a pure
export-cost/latency tradeoff, **not a belief-quality one**."* Attack-run guidance is the first
consumer for which attitude freshness **is** a quality driver, so that last clause no longer holds
and `AC-B3` has its first real motivation.

**But the binding constraint is not where `AC-B3` puts it.** Aircraft-layer already exports at 5 Hz
(`EXPORT_INTERVAL_S = 0.2`); **body-layer polls everything once a second in one loop**
(`logger.py`'s `_DEFAULT_POLL_INTERVAL_S = 1.0`, one `run_once()` polling ownship telemetry and then
every source). So attitude reaching the guidance layer is ≤1 s old *regardless of export rate*, and
splitting the export throttle alone would deliver none of this.

## 22. The fast lane is **selective**, not a global rate change

> *"for body layer poll rate, we should have a selective more frequent poll: ownship telemetry and
> currect target data. Not all world objects, just ownship and current target. Could be that 5 Hz.
> We'll need both anyway for 9K113 missile guidance to be precise."*

**This supersedes §21 point 3's framing** (and the "both sides must split" reading recorded above).
The shape is not *telemetry fast, world objects slow*. It is a **fast lane carrying exactly two
things — ownship telemetry and the currently selected target — at perhaps 5 Hz**, with bulk world
objects left on their own slower rate.

**Why this is tidier than the general split:**

- **It is attack-run-scoped by construction.** A "current target" exists only while one is selected,
  so the lane turns on with the run and off with it. No global rate change, and no cost at all when
  not attacking.
- **It needs no aircraft-layer change to start.** World objects are *already* published at 5 Hz;
  body-layer's 1 Hz poll is the only throttle between that and guidance. So a body-side selective
  fast poll gets 5 Hz target data today. `AC-B3` becomes a prerequisite only *if* it lands and slows
  bulk world objects for FPS — at which point the selected target needs its own fast publication on
  the aircraft side too. **The dependency runs that way round, not the other.**
- **It has a second consumer already named**: *"We'll need both anyway for 9K113 missile guidance to
  be precise."* The 9K113 run requires the copilot to hold the sight on the target for the missile's
  whole flight, so continuous precise tracking is a known future requirement rather than speculative
  scope. The lane is therefore a **reusable seam**, not an attack-run optimisation.

**The constraint that decides whether this is buildable at all:** the fast lane **cannot** be the
poll loop running five times faster. `BL-B26`'s measured worst tick is **1,579 ms** and
`group_salient_ids` alone is ~300 ms of every poll, so a 5 Hz full perception tick is not merely
expensive — it is impossible. The lane has to be a narrow path refreshing only ownship attitude and
the selected target's relative-direction datum: no clustering, no group reconciliation, no
enrichment, no callout scheduling. That is exactly what the re-rotation design consumes, so it
should fall out cleanly, but it is the part to verify rather than assume.

**File, do not build.** Not in `BL-14`'s scope.

## 23. One voice: guidance waits for the readback, plus a 1 s gap

> *"Petrovich can only speak one thing at a time. The first guidance callout will have to wait until
> the attack command readback is done. Add a 1s delay after that also."*

Arrived while the Stage 4–5 fix was under review, and it **settles a question that was about to be
answered by reasoning instead of by direction**. The Stage 4–5 review had found that
`drain_attack_run` recorded a callout as spoken even when channel occupancy suppressed the print, so
the cadence baseline sat at a value never heard. The fix suppresses the print, keeps the previous
baseline, and re-offers on the next free tick. The open question was whether the ~5 s occupancy of
`engage`'s own readback was itself a problem.

**It is not.** Waiting is the correct behaviour: one voice, one utterance at a time, and the first
guidance callout queues behind the readback by design. What would have been a defect is the callout
being *lost* rather than *delayed* — which is exactly what the review caught.

**And there is a new requirement**: a **1 s delay after the readback completes** before guidance may
speak.

**The gap belongs in the audio path, not in the attack run** — settled the same day, once the
placement question was put to him:

> *"The 1s audio gap could live in the audio path. It's failry natural for humans to pause shortly
> between utterances, that makes the transition to next topic clear. Simple solution, after every
> spoken audio, add 1s delay before anything new is accepted. Expection: urgent -tagged items. It'd
> also be good to have a feedback channel to body/brain of when speaking (=audio playback) has
> stopped."*

So it is **not** a fourth attack-run constant. It is a property of speaking, applied after every
utterance, with urgent lines exempt — which is also the more honest model: a pause is how a person
marks the transition to a new topic. Filed as `audio-adapter/ROADMAP/AA-B5.md`, with the
playback-stopped feedback channel, and `aircraft-layer/ROADMAP/AC-B6.md` for the collector half.
**Not `BL-14`'s work.**

**It is also ~80% already built, in the wrong layer.** `belief/callouts.py` has
`INTER_UTTERANCE_GAP_S = 0.75`, applied by `CalloutScheduler.note_reply` when it extends
`busy_until_sim`, and `drain_attack_run`'s occupancy gate already waits on it. So the delta to the
requested second is 0.25 s, not a missing mechanism — found by the Stage 4–5 fix review looking for
an existing general mechanism before scoping a new one. What is genuinely missing is the *feedback
channel*: today the gap is applied to a word-count **estimate** (`SPEECH_RATE_WPS = 2.5`, whose own
comment says "Uncalibrated — needs a live sortie"), and every occupancy decision in the crew layer
keys on that guess.

## 24. Losing line of sight speaks the remembered position — it does not go silent

> *"If LOS broke, we use remembered position. "<where>, obstructed""*

**This closes the question §23 left open, and it closes it the other way from the staging's
assumption.** The worry was that with guidance barred until readback + 1 s, the first guidance
evaluation lands **≥6 s after `engage`** — three times tier 1's `ATTACK_RUN_RELATIVE_MAX_AGE_S` of
2.0 s — so if line of sight broke during the readback the pilot's first experience of the feature
would be **silence**. The review reproduced exactly that: correct tier-1 silence, by design rather
than by defect.

**But silence is not what he wants there.** Losing sight means guidance continues from the
*remembered* position, in the obstructed register (§19) — `"<where>, obstructed"`. Note the slot:
**`<where>`**, so the whole positional vocabulary is available in the obstructed form, not only a
bare direction.

**The staging consequence, which is the point of recording this here**: `BL-14`'s Stage 5 was
planned as the acceptance sortie with tier 2 arriving in Stage 6. Under this direction, **Stage 5
alone is knowingly wrong in a case the pilot will hit on the very first run** — and flying it would
teach him that the feature goes quiet when a vehicle slips behind a berm. So the acceptance sortie
must cover **Stages 5, 6 and 7** together: tier 2's obstructed register, and the projection that
makes "remembered position" correct for a *moving* target (§7's own *"If target is moving, projected
position"*).

That is not scope creep. It is the staging being built on an assumption — that silence was an
acceptable intermediate state — which this direction removes.

### `"lined up, obstructed"`

Asked what `"lined up"` should say while obstructed — the one vocabulary case §4 and §19 together do
not settle, since silence already means *inside both gates* and the qualifier means *this is
remembered*, and a lined-up-but-obstructed run is both at once:

> *"lined up, obstructed"*

**So the qualifier simply composes.** The obstructed register is the coarse tier-1 utterance with
`", obstructed"` appended — `"right, obstructed"`, `"lower, obstructed"`, `"lined up, obstructed"`.
One rule rather than a per-utterance table, which is also why it was worth asking rather than
inventing: a derived answer would plausibly have chosen silence (treating lined-up as the absence of
a correction) and thereby hidden the channel change that §19 exists to make audible.

It is spoken **once** on entering the lined-up state, then silence, mirroring tier 1's
`"lined up"`-then-silence. The case this settles cleanly: a run lined up in tier 1 that loses sight
while still lined up now says `"lined up, obstructed"` rather than going quiet — the qualifier
appearing is the observable in the lined-up case exactly as in the correcting case.

And the symmetric case, confirmed immediately after:

> *"yes, re-speak it once on regaining sight"*

So regaining sight while still lined up speaks a bare `"lined up"` once, then silence. **The general
rule, which is worth stating as a rule rather than as four cases: a tier change always produces
exactly one utterance, in the register of the tier being entered.** Correcting or lined up, entering
tier 2 or returning to tier 1 — one line, then the normal change-driven cadence resumes.

The reason this is not politeness: **the qualifier's presence or absence is the only observable that
distinguishes a live look from a remembered position**, and an observable nobody speaks is not one.
Without the return utterance the pilot could learn that belief had gone stale but never that it had
gone live again.

---

## Still open

Two values remain deliberately unset and belong to a sortie, not to analysis: the **lined-up azimuth
band** (§5) and the **change threshold** that drives cadence (§10). Both are agreed guesses in this
project's usual sense — one named constant each, one place, stated as an assumption, tuned from
flying. The Architect's proposed values are 5.0° and 3.0°, with their bounds reasoned in
`plans/attack-run/plan.md`.

Related: `body-layer/ROADMAP/BL-14.md`, `docs/concept/Attacking target.md` (his spec, 2026-10-11),
`plans/brain-layer/explore-notes.md` §"Attack run (user-raised, 2026-09-24)",
`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` (the attention tiers, and the
per-unit-resolution gap this direction routes around for stepping).
