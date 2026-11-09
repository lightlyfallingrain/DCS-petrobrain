# Expected-area check — explore notes

Follow-on to `[[BL-B108]]` (merged 9e4b7115). BL-B108 left one accepted gap: a group held only in
mission memory/belief (out of view) and a new sighting 1.5 km nearer on the same bearing, seen
through a different optic, merge into one contact 0–86% of the time (worst: far group glassed at
4.5–5 km, near group then seen by eye, far first). Range numbers alone cannot separate them
honestly. The user's answer: settle it the way a crewman would, by looking where the remembered
group should be.

The two sections below are copied verbatim from `plans/relative-distance-grouping/explore-notes.md`.

## Memory-only fold, real rate 0–86%: user's answer (verbatim, 2026-11-01)

Told: the shipped model folds the memory-only cross-optic case up to 86% (far group glassed at
4.5–5 km, out of view, near group 1.5 km closer then seen by eye), not the 67% first quoted.
Options: (1) accept; (2) binocular 0.85; (3) re-look along the whole bearing on raising binoculars.

> *"3 but not whole bearing. Check the expected locations/area. That's what I'd do, look around the
> area a bit and that would tell me if a unit I see is the same one.*
>
> *Like: looking ahead, I see couple of dots. I raise binoculars to take a look. That becomes group
> A, I believe it's 4.5 km away, and I see it's right of village near a river. In a moment I fly
> over a ridge I was approaching low and then can see some more units ahead. They are also near the
> river, but a bit different side of the village. Naked eye look immedeiately tells group A has 3
> dots and this new group B has 2 dots and that they are separate. Raising the binoculars, I first
> check the near group that is B and then A. That gives me information on both and a clear visual
> that they are not the same group.*
>
> *Counter example. In the above example I fly over the ridge and spot more contancts between group
> A and the village. Looking with binoculars I see that they all are group A units, just spread
> wide. I check group B and see that it is separate."*

Reading (main loop, to confirm with the user):

- Same-or-different is settled by **looking where the remembered group should be**, not by the
  range numbers alone. A focused look at A's expected area (not the whole bearing): A seen there
  → the new sighting is a different group; A not there → it may be A.
- Cues a real observer uses, beyond range: **position relative to a visible landmark** (right of
  the village, by the river), **dot count / composition** (3 vs 2), and the glass look at each.
- Order: near group first, then A.
- Counter-example: units spread between A and the village are A's, found by glassing them — group
  membership by neighbour gap (goal-check Q2) still applies.

## Follow-on answers (user, verbatim, 2026-11-01)

Asked: (1) merge now or hold; (2) what the new sighting is before the check; (3) A's area empty
when checked; (4) village/river as evidence; (5) dot count as a cue.

> *"1 - merge current, then continue with this*
> *2 - less noise is better, callout when verdict is known*
> *3 - if unit composition matches A's and the distance is believable for A's movement speed,
> consider A has moved. Otherwise it's a different group.*
> *4 - for a player looking at group the surrounding terrain features act as anchors and help tell
> where the units are and tell one group from another. If that would help in deterministic code,
> sure, let's do it. But if the effect is minor, then let's not spend resources on it.*
> *5 - I might not see all units, depends on terrain, buildings, trees, etc. So 3 and 5 units could
> be same, could be different. 3 and 8 makes me more suspicious. Could be 3 and 5 obscured, but
> that definately deserves more attention. Etc. The more difference there is the more  suspicious
> that is."*

Reading (main loop):

- (1) Merge BL-B108 with the fence; the expected-area check is a new feature.
- (2) No callout for the new sighting until same/different is decided.
- (3) Area empty: "A moved" only if composition matches and the displacement fits A's plausible
  speed over the elapsed time; otherwise a different group.
- (4) Landmark anchoring only if it measurably helps the deterministic decision; measure before
  building.
- (5) Count difference is graded suspicion, not a verdict: partial visibility makes small
  differences weak evidence, large ones strong, and either way it raises the need to look.

## Goal-check answers (user, verbatim, 2026-11-01)

Asked: the five questions in `alignment.md`, "Questions for the user". Q1 was answered by
correcting the premise it rested on (a glass phase only after the whole naked-eye scan cycle).

> *"A binocular look can start up to about 16 s after the sighting, because the eye scan finishes
> first -> actually, that should be per sector. naked eye scan of sector, then binoculars on new
> contants in sector and units that plausibly could get a better identification than existing,
> move to next sector and repeat*
> *Q2 - yes*
> *Q3 - call B as new*
> *Q4 - tell me about both*
> *Q5 - yes, check paused, 9K113 on target only"*

Reading (main loop):

- (Q1) **Scan order changes: per sector, not per cycle.** Naked-eye sweep of one sector → glass
  that sector's new contacts and the ones that could plausibly get a better identification than
  they have → next sector. This **revises the 2026-09-23 direction** that a glass phase starts
  only at the end of a naked-eye scan cycle (`belief/optic_policy.py` docstring). Consequence for
  this feature: B's verdict waits at most one sector's dwell, not a whole cycle, so the hold is
  short by construction; the expected-area look at A belongs in that same sector's glass step when
  A's area is in it.
- (Q2) Firing or threat-type B (AAA/SAM): call out at once; same/different settled after.
- (Q3) Cannot look at A's area, or the wait runs out: call B out as a new group (missing a group
  is worse than a possible duplicate).
- (Q4) Tell the pilot both: "A has moved" with its new position, and "A is no longer where it
  was" when A's area is seen empty and B is a different group.
- (Q5) During a 9K113 attack run the check is paused; the sight stays on target; B is called out
  on what is already known.

## Plan-check decisions (user, verbatim, 2026-11-01)

Asked: the four decisions after the plan and plan check (`plan.md` "Decisions", `alignment.md`
"Plan check"): (1) what a sector is (half-sweep recommended) and several looks per glass step;
(2) the visibility source / when to build the area look — recommended: ship Stages 0–2 and open a
separate roadmap entry now for a point line-of-sight query plus Stages 3–4; (3) tests rewritten
rather than extended; (4) wording for "A moved".

> *"1 - third of full scan. So basically left right and ahead. Multiple looks per glass is ok and
> expected.*
> *2 - as recommended*
> *3 - ok*
> *4 - ~"A now at...""*

Reading (main loop):

- (1) **Sector = a third of the free scan: left, ahead, right** — not the half-sweep the plan
  proposed. Several binocular looks in one glass step are expected. The plan's Stage 1 sector
  definition and its decay-coupling arithmetic must be redone for three sectors.
- (2) Ship Stages 0–2. Open a separate roadmap entry now for the point line-of-sight query and
  Stages 3–4 (the area look itself), so it is planned work; the flight duplicate count sets its
  priority, not whether it happens.
- (3) The five full-cycle lockout tests and the exact-100% fold test are rewritten.
- (4) Wording when A is judged moved: approximately *"A now at …"* — neutral, which also covers
  the "misranged" case Petrovich cannot tell apart.

## Plan re-check answers (user, verbatim, 2026-11-02)

Asked: (1) the sweep order left → ahead → right, or literal "left, right, ahead"; (2) ahead glassed
once per cycle (worst first notice of a new threat dead ahead ~14 s instead of ~8 s), or a second
ahead visit per cycle; (3) Decision 5, glass budget 4 s per step, or (b) 12 s per cycle shared
across the steps.

> *"1,2 - I meant regions, not order. For order, always start from ahead and sweep to left/right
> alternating. That way direction of flight is checked more often.*
> *3 - four is too short. Binoculars should be used to look closer when there is good probability
> that using them brings a benefit - detection, classification or identification. There's no use
> raising them on contacts where additional information is not available at current distance.
> Then when binoculars are used, it's better to not limit the time too tightly. The 12 s sounds
> ok."*

Reading (main loop):

- (1, 2) "Left right and ahead" named the **regions**, not an order. **Order: start ahead, then
  alternate sides** — read as ahead → left → ahead → right, repeating, so ahead is swept twice per
  cycle. This reverses the plan's "ahead once per cycle" call.
- (3) **4 s per step is rejected; Decision 5 goes to (b), a 12 s budget per cycle.** Looks should
  not be cut short. The bound on binocular time is to come mainly from **selectivity**: raise
  them only when a look is likely to add detection, classification or identification at the
  current distance, not on contacts where nothing more is visible from here.
- Consequence to settle in the plan: four sector visits (10 legs, 20 s of eye sweep) plus up to
  12 s of glassing puts the worst flank revisit past the 30 s position half-life. The plan must
  say how that is handled and what the pilot would notice.

## Mission density, optics priority, approach speed, stationary units (user, verbatim, 2026-11-02)

Told: plan re-check 2 ALIGNED; Decision 6 (≤ 2 s overrun of the 30 s position half-life in a full
12 s glass window) proceeding on the default.

> *"The missions I fly are not super busy. There's groups here and there, but not like a real
> frontline with hundreds or thousands of units. Rather a handful of groups a few km apart,
> typically. Larger missions have more units and groups, but still spread around. Therefore
> priority is a) knowing where the groups are b) iff c) classification. Scanning and optics usage
> should serve these goals.*
>
> *While the Hind can fly 250 km/h, when approaching suspected enemy locations it's wise to
> approach carefully and slower so that Petrovich has time to scan without us flying headfirst
> into danger.*
>
> *For the overrun - ok.*
> *Tracking vs estimated. Again, the unit movement should be considered. Stationary unit can be
> expected to remain stationary. Therefore even if no one looked at it for 30s it's not likely to
> have moved."*

Reading (main loop):

- **Density:** a handful of groups a few km apart is the design case; busy-window worst cases are
  rare in the missions flown.
- **Priority for scanning and optics: (a) where the groups are, (b) IFF, (c) classification.**
  Checked against the code (2026-11-02): the binocular gate `can_still_improve` admits a contact
  only on the classification ladder (next tier reachable at the believed range); it never admits a
  look for **position** (a). IFF (b) is not modelled: every contact is `UNKNOWN`, BL-B12 deferred
  (infer from type vocabulary and terrain control, never DCS truth). `choose_look` orders by
  watched count, coverage, then nearest.
- **Approach speed:** careful, slower approach to suspected enemy is the expected tactic; scan
  timing should be judged at that speed, not at 250 km/h.
- **Decision 6: ANSWERED, "ok".**
- **Tracked vs estimated must consider movement.** `certainty_of` is time-only (30 s → estimated,
  120 s → lost) whatever the contact's motion; position covariance already grows per class
  (`plausible_speed_mps`, 0 for entrenched). A stationary unit unseen for 30 s should not read as
  less certain in position.

## Location looks, stationary-unit entry, approach profile (user, verbatim, 2026-11-02)

Asked: (1) binocular looks for **position** (a group whose range rests on the naked eye only),
ranked before classification — in Stage 1 or a separate entry; (2) open a separate entry for
motion-aware tracked/estimated/lost.

> *"1 - do in stage 1*
> *2 - own item, queue after this*
>
> *Careful approach speed might be ~100 km/h and could include sideways movement and circling to
> keep safe distance"*

Reading (main loop):

- (1) **Stage 1 gains location looks**: a contact/group whose position rests only on the naked eye
  is worth a binocular look for position; look choice ranks position before classification (IFF
  not modelled, BL-B12).
- (2) Opened as `[[BL-B112]]`, queued after BL-B110.
- **Approach profile for sizing scan timing:** ~100 km/h, with sideways flight and circling at a
  safe distance. Sectors are body-relative, so while circling the ground under each sector rotates;
  a group can move from one sector to another between sweep and glass step.

## Decision 7 and the refined priority (user, verbatim, 2026-11-02)

Asked: Decision 7 — a binocular range fix is overwritten by the next naked-eye look ((a) a new look
never leaves the belief less certain; (b) build on today's model; (c) leave location looks out);
whether binoculars give a much better sense of range; Decisions 8 (location before
classification) and 9 (look follows its contact) as defaults.

> *"Option a*
>
> *I'll rephrase the first priority: detection and therefore rough estimate of position is first
> priority. Exact position is not even needed for all units.*
>
> *Refined priority:*
> *1 detection and rough location (the further away we are, the more imprecise the location is
> allowed to be. At close distances a more specific location can and should be obtained)*
> *2 IFF, though that needs expected enemy territory and unit identification (eg. T-72 vs
> leopard)*
> *3 classification*
> *4 exact location (for enemy units especially and mission target units or anything the player
> asks for)"*

Reading (main loop):

- **Decision 7: (a).**
- **Priority 1 is detection with a rough position**, served by the scan itself. The allowed
  position error grows with range; close in, a tighter position can and should be obtained.
- **Priority 2, IFF,** needs expected enemy territory and identification to unit type (T-72 vs
  Leopard). Not modelled (BL-B12); until then, identification to type is what serves it.
- **Priority 3, classification.**
- **Priority 4, exact location** — only for enemy units, mission targets, or what the player asks
  about; not for every unit.
- So **Decision 8 reverses**: a look for exact position ranks after classification, and is limited
  to those contacts, except where the rough position is worse than the range-scaled allowance
  (that is priority 1). Binocular range-sense question not answered.

Follow-up (user, verbatim, 2026-11-02), answering whether binoculars give a much better sense of
range:

> *"Binoculars range sense - keep the current."*

So `BINOCULAR_RANGE_SIGMA_SCALE` stays 0.7 (plan Decision 11).

## Plan re-check 3 answers (user, verbatim, 2026-11-03)

Asked: (1) drop the 250 m floor so the rough-location fence is 0.2 · R throughout; (2) "anything
the player asks for" read as watched contacts, one-off queries later via the brain layer; (3) the
circling sector-edge blind spot as a test-card watch item, own entry only if noticed. Each with a
recommendation.

> *"go with recommendations"*

Reading (main loop): all three recommendations taken; also read as the go to build (Stages 0a, 0,
1, then 2).

## Stage 2 decision (user, verbatim, 2026-11-03)

Asked, after Stages 0a/0/1 merged: hold Stage 2 (call a new group out at once) until the
long-gap stationary false-trigger (7-15% at 120 s, 25-27% at 600 s, gate ~10%) is fixed and
re-measured, or build it now. Also recommended moving `[[BL-B111]]` up.

> *"Stage 2 -> Hold it until the stationary-group case is fixed."*

Reading (main loop): Stage 2 is not built until a fix brings the stationary binocular→unaided
long-gap cells under the ~10% gate in Stage 0's harness. Next is an architect pass on that fix
only. BL-B111 ordering not answered; it stays where it is.

## Decision 12 (user, verbatim, 2026-11-09)

Asked: (a) one-sided trigger (B must read nearer than A; same-group split 3-6%, a farther group
still folds as today), (b) stricter two-sided threshold, (c) duplicate gate raised to ~20%.
Recommended (a).

> *"go with (a)"*

Reading (main loop): Stage 1b goes to implementation. Stage 2 still held until Stage 1b's
acceptance grid (including the ground cells) passes.

## Same-optic fold finding: measure first (user, verbatim, 2026-11-09)

Asked, after Stage 1b stopped on the BL-B108 `u_u` fence (same group, naked eye twice, 3 km,
4 s: 83-86% fold with the harness fixed, not 100%): (1) measure the same-optic case widely
first, then decide fix vs. fence correction; (2) lower the guarantee to ~85% and continue.
Recommended (1).

> *"measure first"*

Reading (main loop): a test-only same-optic ensemble sweep (ranges x gaps x optics x class,
fixed harness), results to the user before any fence or fold code changes. Stage 2 still held.

## Same-optic fold defect: fix first (user, verbatim, 2026-11-09)

Asked, after the same-optic sweep (u_u ~90%, b_b ~95% fold, flat over gap; Covariance2D.inverse
determinant floor fires on 7% of u_u gate evaluations, S indefinite): fix as a bug on its own
branch before Stage 2, re-measure, then set the BL-B108 fences to the measured rate.

> *"do as recommended"*

Branch: `fix/same-optic-gate-indefinite` (from main). Stage 2 held until it merges and the
residual rate is back with the user.
