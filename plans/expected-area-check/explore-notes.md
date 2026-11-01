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
