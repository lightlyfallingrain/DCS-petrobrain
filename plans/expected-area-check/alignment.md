# Expected-area check (BL-B110) — alignment

## Goal check — 2026-11-01

**Verdict:** CONCERNS — the goal is sound and squarely Petrovich's job; four assumptions a planner
would otherwise fill silently need the user (delay bound, threats, a check that cannot be made,
what the pilot hears when A has moved).

### Why

So that **a second group on the bearing of one Petrovich already reported is told to the pilot as a
second group — and a re-sighting of the first is not reported as new** — when the first group is not
in his current look. Why that matters: today the new sighting can fold silently into the remembered
group (0–86%, `BL-B108`), and the group that disappears from the pilot's picture is **the nearer
one** — the one he is about to fly over, evade or attack.

Second "why": the user's answer is to settle it the way a crewman does — *"look around the area a
bit"* — so the verdict rests on something Petrovich **saw**, not on range arithmetic. The check is
a means; the end is a correct count and placement of groups in what the pilot hears.

### Player expectations

- **E1 — Two groups stay two.** A remembered group A, out of the current look, and a new group B
  nearer on roughly the same bearing: once the check has seen A where A was believed to be, the
  pilot hears B as a new contact, and A is not re-announced.
- **E2 — One group stays one.** If the new sighting is A (A moved, or Petrovich misjudged its
  range), the pilot hears no "new contact" for it. Units spread between A and a landmark that the
  glass look shows to be A's (the user's counter-example) join A, not a new group.
- **E3 — No callout for B until the verdict** (user Q2, *"less noise is better"*) — but the wait is
  **bounded**, and when the bound runs out the pilot still hears about B. A held callout must never
  quietly become no callout.
- **E4 — The look is a look at A's area**, not a sweep of the whole bearing, and it shows up where
  the debug/eyesight view shows where Petrovich actually looks. The user's order: the near group
  (B) first, then A.
- **E5 — Absence counts only where he could have seen.** "A is not there" is concluded only from a
  look in which A, at its expected place, was within that optic's detection range and not masked by
  terrain, trees, buildings or the cockpit. A look into a masked area says nothing about A.
- **E6 — "A has moved" only when it is believable** (user Q3): A's area seen empty, B's composition
  compatible with A's, and the displacement achievable at A's plausible speed in the elapsed time.
  Otherwise B is a different group.
- **E7 — Composition is graded suspicion** (user Q5): a small count difference is weak evidence
  (he may not see all units), a large one strong; neither alone is a verdict, and a large one is a
  reason to look, not a reason to decide.
- **E8 — The check never pre-empts something more important**: a firing/threat callout, or the
  sight while a 9K113 is in flight.

### Open assumptions

- **What triggers a check** — serves the why: only the ambiguous case — a new sighting that the
  association gate would accept as a remembered group *not seen in the same look*; would not: every
  new sighting, or every optic switch (noise, cost, and re-sweeps the user rejected as "whole
  bearing"). When A is in the same look the existing in-view path already gives 0% fold
  (`BL-B108`), so no check is needed there.
- **Which "remembered" counts** — serves: both a contact unseen this look and a group already lost
  into mission memory (user, 2026-10-31: *"keep all groups in mission memory"*); would not: only one
  of the two, leaving the other path folding.
- **How long B's callout may be held** — serves: a bound of a few seconds to roughly one look cycle,
  after which B is called out on what is known; would not: waiting for the next glass phase, which
  the existing optic policy makes reachable only at the end of a full naked-eye scan (free scan
  cycle 16 s, `perception/gaze.py`), while `CALLOUT_MAX_AGE_S` (10 s) silently drops an event that
  waits longer. Unbounded holding turns E3 into "the nearest group is never mentioned".
- **What happens when the bound runs out, or the area cannot be looked at** (masked, behind the
  field of regard, ownship turning hard) — serves: decide on what was perceived and say so; the
  default direction is the user's call (Q3). Would not: treating "could not look" as "looked and
  found empty" (E5), or waiting indefinitely.
- **Which optic does the check** — serves: whichever can actually detect A at its expected range —
  naked eye where A is within naked-eye range (the user's example: *"Naked eye look immediately
  tells group A has 3 dots and this new group B has 2"*), binoculars otherwise, and the sight when
  it is already Petrovich's home phase; would not: always binoculars, or a look with an optic that
  could not have detected A there (which then "finds it empty" falsely).
- **How big "A's expected area" is** — serves: A's believed position with its own uncertainty plus
  how far it could have moved since last seen; would not: a fixed circle. A consequence a planner
  should know: for a long-lost moving group this area grows without limit, and past the point where
  one look cannot cover it the check proves nothing — that is where it should stop being tried.
- **"Plausible speed" for E6** — serves: A's believed class and believed movement state (a group
  seen stopped vs. seen moving), from what he perceived; would not: true speed, or one global max.
  Note the two time scales: seconds after A was seen (the BL-B108 scenario, 6 s), a 1.5 km
  displacement is implausible for any ground group, so E6 resolves "different" there almost by
  itself; minutes later (mission memory) it becomes plausible and the look is what decides.
- **Composition compared** — serves: what he saw of each group (count and class as perceived);
  would not: the true unit count of A or B.
- **Terrain anchors** — serves the why only if measured to change verdicts (user Q4). Finding 4
  below explains why the effect is likely already mostly in the model.

### Findings

1. **The group that folds is the nearer one, so the hold has a real cost** — lens: Whose job /
   Crew sense
   - Assumption: holding B's callout until the verdict costs only noise.
   - In the sim: B is the nearer group (≈1.5 km nearer, 2.4–3.5 km out in the measured cases); at
     typical Mi-24 speeds a 16 s wait closes 0.5–1 km. Callouts expire after 10 s
     (`belief/callouts.py`, `CALLOUT_MAX_AGE_S`), and a glass phase can start only at the end of a
     naked-eye scan cycle (`belief/optic_policy.py` module docstring, user 2026-09-23).
   - The pilot would see: a quiet front seat while a nearer group sits in the windscreen, then
     either a late callout or none.
   - Grounded in: user Q2 (*"callout when verdict is known"*) and the existing timing constants.
   - Suggests: the hold needs a stated bound, and the check needs to happen promptly enough to fit
     it — whether it may interrupt the naked-eye scan rule is the user's call (Q1).

2. **Absence of A is evidence only where A could have been seen** — lens: World truth / Bounded
   knowledge
   - Assumption a planner might make: "looked at A's area, no detection → A is not there".
   - In the sim: ridges, trees and buildings mask ground units; the user names exactly that
     (*"I might not see all units, depends on terrain, buildings, trees"*). The BL-B108 scenario is
     itself a ridge crossing.
   - The pilot would see: Petrovich declaring "A moved" and folding B into it, because he looked
     into a valley he could not see into.
   - Grounded in: user Q5; the project's visibility/masking model already decides what he could see.
   - Suggests: "seen empty" requires A's expected place to have been visible to that look (E5);
     otherwise the check is "could not look", not "empty".

3. **At Mi-24 altitudes one look along the bearing already covers both groups** — lens: The
   envelope / Unit of action
   - Observation (geometry, not DCS lore): at 100 m AGL the depression to 3 km is ≈1.9° and to
     4.5 km ≈1.3° — 0.6° apart, inside one binocular field (≈4.25°). At 500 m it is ≈9.5° vs ≈6.3°,
     about one field. So "look at A's area" and "look at B" are frequently the same look, and that
     look puts both groups in view — the case BL-B108 already resolves (0% fold).
   - The pilot would see: no difference — which is the point. The user's "B first, then A" is two
     looks for a human; Petrovich may get both from one.
   - Suggests: the planner should not assume the check needs a separate excursion; most of the cost
     may be in *holding the decision* until a look that contains A's expected place, not in a new
     look. Where A's expected place is outside the look containing B (higher altitude, large
     bearing difference, a long-lost moving group), a second look is needed.

4. **Terrain anchors probably add little in deterministic code** — lens: Purpose
   - In the model: BL-B108 made the range error stable per view and shared by nearby things. That
     is the deterministic form of "right of the village": two things near each other carry the same
     error, so their *relative* placement is already good. An anchor would add information only
     where that sharing breaks — across optics and across time, i.e. exactly the memory-only case.
   - Grounded in: user Q4 (*"if the effect is minor, then let's not spend resources on it"*) and
     the BL-B108 explore notes (*"also surrounding terrain features help judge the relative
     distances"*), which BL-B108 modelled as shared error.
   - Suggests: build without anchors; measure the residual fold rate first, as the user asked.

5. **An empty check is news about A too** — lens: Crew sense / Bounded knowledge
   - Assumption a planner might make: the check decides only what B is.
   - The pilot would see: if B is judged different and A's area was seen empty, Petrovich still
     "holds" A at a place he has just looked at and found empty — and would report it there on a
     `report`.
   - Suggests: after a "different" verdict with A's area seen empty, A's belief should reflect "not
     at last known position". What the pilot hears about that is Q4.

6. **Whose job — passes.** Telling one group from two is detection and identification, the core
   of Petrovich's job (root `CLAUDE.md`). The pilot benefits directly: the right number of groups,
   in the right places, to evade or attack. Would he notice? Yes — as a group he was never told
   about (today) or as a duplicate "new contact" (the opposite failure).

**Non-obvious vignette walked.** A group of one (A: one vehicle, glassed at 4.7 km). Ownship
descends into a valley; A is masked. Three minutes later, B — one vehicle — is seen by eye at
3.2 km on A's bearing, still from the valley. A's area is masked (Finding 2: "could not look").
Composition 1 vs 1 matches, 1.5 km in 3 min is plausible for a vehicle. Under E6 as worded, B
would be folded into A without A ever having been looked for — the user's "consider A has moved"
was stated for *A's area empty when checked*, not for *not checkable*. That gap is Q3.

### Questions for the user

1. **How long may Petrovich hold a new group's callout while he checks** — a few seconds, or until
   his next binocular look even if that means finishing the current naked-eye scan first (up to
   ~16 s)? Or may this check interrupt the scan the way it doesn't today?
2. **If the new group is firing, or is a threat type (AAA/SAM), is it called out immediately**,
   and the same/different question settled afterwards?
3. **If he cannot look at A's area** (masked by terrain, out of view, you are turning hard) **or
   the wait runs out: call B out as a new group, or stay silent?** (Missing a group vs. a possible
   duplicate.)
4. **When he decides A has moved, does he tell you** (*"that group has moved, now two o'clock,
   3 km"*), or just update silently? And if A's area is seen empty but B is a different group, does
   he say A is gone from where it was?
5. **During a 9K113 attack run, is the check suspended** — nothing pulls the sight off the target —
   with B called out on what is known?
