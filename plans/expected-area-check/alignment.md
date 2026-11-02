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

## Plan check — 2026-11-01

**Verdict:** CONCERNS — Stage 2 (the recommended ship) delivers the headline ("two groups stay
two") honestly and the trigger math is sound. But the plan's own Decision 2, recommendation (c),
means **BL-B110 as merged will not build the mechanism the user described** ("look around the
area a bit and that would tell me") at all — E4–E7 are deferred indefinitely behind a future
duplicate count from flight, not a date. That gap is disclosed in the plan's own text, not hidden,
but it needs the user's explicit sign-off before Stage 2 ships under this entry's title, not an
auto-advance.

| expectation | stage | status |
|---|---|---|
| E1 (two groups stay two) | 2 | met — trigger catches most cases; 0–26% residual disclosed, Stage 0 tunes it before Stage 2 ships |
| E2 (one group stays one) | 2 (partial) / 4 | **contradicted** for 4–10% of cross-optic same-group re-sightings under Stage 2 alone — a real re-sighting is wrongly founded as a new contact; the plan states this trade explicitly, and only Stage 4's `relocate` removes it |
| E3 (no callout until verdict, bounded) | 2 | met — Q3 collapses "verdict" to "cannot tell → new" with zero hold, so the bound is trivially satisfied; the *real* bounded hold (checking first) is Stage 4 only |
| E4 (the look is at A's area, debug-visible, B first) | 3–4, conditional | **missing** under the recommended ship — no look at A's area occurs at all in Stages 0–2; see Finding 1 |
| E5 (absence counts only where visible) | 3, conditional | **missing** under Stages 0–2 — there is no "seen empty" concept without a look |
| E6 ("moved" only if believable) | 4, conditional | **missing** under Stages 0–2 — no "moved" verdict is ever reached; B is simply founded distinct |
| E7 (composition as graded suspicion) | 4, conditional | **missing** under Stages 0–2 — composition is never consulted |
| E8 (never pre-empts a threat/9K113) | N/A in 0–2 (vacuous) / 4 | met — no hold exists yet to interrupt in Stage 2; Stage 4's table has explicit Q2/Q5 rows |

### Findings

1. **Four of eight expectations are deferred with no date, behind a decision the plan's own
   recommendation answers "not yet."** — lens: Whose job / Crew sense
   - Assumption a planner might make: "staged by measurement" means the full behaviour arrives
     later as a matter of course.
   - In the sim: Decision 2 recommends (c) — ship Stages 0–2, fly, count duplicates with
     `sortie-log-triage`, and only then decide whether to build the look at all. Nothing commits
     to building it; a quiet flight with few duplicates is itself a reason never to revisit it.
   - The pilot would see: the headline defect (a nearer group swallowed into a remembered one)
     goes away, which is real value. But the crew behaviour the user described in his own worked
     example — "I raise binoculars... I first check the near group that is B and then A" — never
     happens. Petrovich never looks at A's believed place, never says "that group has moved," and
     never uses dot-count suspicion the way the user walked through it. The mechanism asked for
     is absent, not merely delayed by a known interval.
   - Grounded in: the goal check's own Why ("the verdict rests on something Petrovich **saw**, not
     on range arithmetic") and the plan's point 2 under "what the measurement says" (the look
     "cannot change what the pilot hears" without a visibility source it does not yet have).
   - Suggests: this is not a defect in the plan — Decision 2 surfaces it correctly, and the
     architect-memory file this merge carries states the reasoning plainly. The gap is that
     Decision 2's framing ("if the duplicates matter") lets the user approve a path that silently
     closes the loop on E4–E7 without separately registering that they are choosing not to build
     the thing they described, for now, on a trigger (a sortie-log count) that may never fire. When
     this plan is taken to the user, Decision 2 should be asked as two questions, not one: (i) ship
     Stages 0–2 now — presumably yes; (ii) is "fly and count duplicates" an acceptable way to
     decide whether E4–E7 (the look, "moved," composition) are ever built, or should a follow-on
     entry for Stages 3–4 be opened now regardless of what flights show. Either answer is fine; the
     plan should not let a recommendation phrased as a staging choice read as a staging choice
     when it is actually a scope choice.

2. **Q1's sector reading is a defensible choice, correctly left open rather than asserted** — lens:
   Grounded in / Purpose
   - The user's words ("per sector... naked eye scan of sector, then binoculars... move to next
     sector and repeat") name no grain. The plan reads sector as half of `SCAN_PLAN`
     (`(12,11,10,9)`/`(12,1,2,3)`, 8 s each, two sectors) — confirmed against the actual
     `SCAN_PLAN` tuple in `gaze.py`, which already splits that way. That is one honest reading, not
     the only one: a literal "sector" at the grain of a single o'clock hour is equally consistent
     with the user's sentence, and is exactly the alternative Decision 1 names and rejects — for an
     engineering reason (decay-coupling overflow past 30 s), not because it was checked against
     what the user meant by "sector."
   - Suggests: fine as a recommendation, correctly exposed as Decision 1 rather than built
     silently. Carry it into that question explicitly: confirm the grain, not just the mechanism.

### Questions for the user

1. Decision 2: if you choose (c) — ship Stages 0–2, fly, count duplicates — do you want that count
   to be the only thing that decides whether the expected-area look, the "moved" verdict and
   composition suspicion (E4–E7) ever get built, or should a follow-on entry for Stages 3–4 be
   opened now regardless of what flights show?
2. Decision 1: does "per sector" mean the half-sweep grain the plan proposes (8 s, two sectors), or
   the finer o'clock-hour grain it considered and rejected for the decay-coupling reason?

## Plan re-check — 2026-11-01

**Verdict:** CONCERNS — the revision resolves both prior concerns cleanly (the "no date" scope
gap and the sector-grain ambiguity), the three-sector reading matches the user's words, and the
math underneath Decision 5 checks out. Two things earn a question before this ships, both
introduced by the revision itself rather than carried over: a scan-order choice the user's own
sentence does not settle, and a real, quantifiable detection-latency cost in the one sector where
Petrovich's job matters most — and the plan's mitigation for it rests on an assumption the plan
does not check.

| expectation | stage | status |
|---|---|---|
| E1 (two groups stay two) | 2 | met — unchanged from prior check |
| E2 (one group stays one) | 2 (partial) / BL-B111 | contradicted for 4–10% cross-optic false-split under BL-B110 alone, same as before — but now scheduled with a date (BL-B111 opened now, not conditional on flight counts), not deferred indefinitely |
| E3 (no callout until verdict, bounded) | 2 | met — unchanged |
| E4 (look at A's area, debug-visible, B first) | BL-B111 Stage 4 | missing in BL-B110 (unchanged), but now scheduled rather than contingent — resolves the prior top finding |
| E5 (absence counts only where visible) | BL-B111 Stage 3 | missing in BL-B110, scheduled in BL-B111 (point LOS query, fails closed) |
| E6 ("moved" only if believable) | BL-B111 Stage 4 | missing in BL-B110, scheduled in BL-B111 |
| E7 (composition as graded suspicion) | BL-B111 Stage 4 | missing in BL-B110, scheduled in BL-B111 |
| E8 (never pre-empts a threat/9K113) | BL-B111 Stage 4 rows | met where it will exist — Q2/Q5 rows present in the BL-B111 design |

### Findings

1. **Prior top finding is resolved: E4–E7 now have a date, not a trigger.** — lens: Whose job /
   Crew sense
   - The earlier concern was that Decision 2(c) let a quiet flight silently cancel the mechanism
     the user actually described. Decision 2 as answered (*"as recommended"*) opens `BL-B111` now,
     unconditionally; the flight duplicate count sets its priority, not its existence
     (`BL-B111.md`, "opened now so that a quiet flight cannot quietly cancel it"). That is exactly
     the fix the prior check asked for.

2. **The three-sector reading matches the user's words plainly.** — lens: Grounded in
   - *"Third of full scan. So basically left right and ahead"* names three regions and the plan's
     partition (`left` 9–10, `ahead` 11–12–1, `right` 2–3) is a literal thirds split, confirmed
     against the actual `SECTOR_WEDGE_DEG` constants. No reading judgment is needed here, unlike
     the prior half-sweep guess.

3. **The scan *order* (left → ahead → right) is the architect's own reading, not the user's
   words, and is now a cadence the pilot will listen for.** — lens: Grounded in / Crew sense
   - The user's sentence lists the sectors as *"left right and ahead"* — left, then right, then
     ahead, if read as a sequence. The plan instead orders the sweep left → ahead → right, with a
     stated geometric reason (one continuous windscreen sweep, one flick back from 3 to 9, instead
     of three flicks). That reason is sound on its own terms, but it answers a question the user's
     sentence probably wasn't posing ("which three regions" vs. "in what order"), the same shape of
     gap the half-sweep reading had last time — and this time it is not surfaced as a Decision, it
     is stated as settled.
   - The pilot would notice: Stage 5's own test card is *"free scan, listening for the left → ahead
     → right rhythm"* — the order is meant to be audible, which is exactly why a wrong guess here
     costs a re-card, not just a renumber.
   - Suggests: a one-line confirmation costs nothing and the plan is already in the habit of
     asking rather than assuming (Decision 1 is the model for this). Ask it alongside Decision 5
     below rather than shipping it as a given.

4. **Reshaping the ahead sector to one visit per cycle doubles the worst-case time to first
   notice a new threat dead ahead, and the plan's stated mitigation is unverified.** — lens:
   Whose job / The envelope
   - In the sim: today's table visits 12 o'clock twice per ~16 s cycle (legs at position 0 and 4,
     ≈8 s apart). The reshaped table visits the ahead block once per 14 s cycle. For a contact that
     appears in the ahead sector immediately after the eye has just swept past it, the worst-case
     wait before the naked eye passes that bearing again goes from ≈8 s to ≈14 s — a ≈75% increase,
     and distinct from the 26–29 s "worst revisit" figure the plan computes, which is about an
     *already-tracked* contact's certainty decaying between glass steps, not about *first* noticing
     something new. The plan's own Risks section states the premise ("12 o'clock is seen once per
     cycle instead of twice") but the arithmetic it follows up with (`_ACQUISITION_RETENTION_
     WINDOW_S`, the 26–29 s revisit table) answers the decay question, not the first-detection one.
   - The plan's reason for accepting this is explicit and reasonable on its face: *"the pilot is
     looking ahead himself, and the flanks are where Petrovich adds the most"* (Stage 1, "How ahead
     is covered"). That is the right kind of argument — it is the project's own whose-job test,
     applied correctly in direction. But it is asserted, not checked: nothing in the plan measures
     or even estimates how often a real threat (AAA, SAM, a vehicle cresting a rise) would appear
     exactly in the windscreen-ahead bearing where the player's own attention is already loaded
     with flying the aircraft, rather than scanning — which is a different claim from "the pilot can
     see directly ahead at all." A player flying low and fast, eyes on instruments or terrain, is
     not necessarily watching 12 o'clock the instant something appears there.
   - The pilot would see: a slower naked-eye pickup of a new threat straight ahead than today, with
     no callout to compensate until that pickup happens — this is the one sector where "Petrovich
     helps the pilot evade dangerous units" (root `CLAUDE.md`) is least backed up by the player's
     own eyes if the player's attention is in fact elsewhere.
   - Suggests: this does not need un-shipping the reshape — the thirds-and-order are the user's own
     direction and the flank gain is real. It needs either (a) the user confirming the "pilot
     already looks ahead" assumption is good enough as stated, or (b) a one-line note in the test
     card asking the user to specifically notice ahead-threat pickup latency on the acceptance
     flight, since this plan has no other way to measure it before merge.

### Questions for the user

1. The plan sweeps left → ahead → right (one continuous pass, one flick-back). Your words named
   the three regions but not an order — is that the sweep you want, or did you mean left, then
   right, then ahead, as the sentence reads literally?
2. Seeing 12 o'clock once per cycle instead of twice roughly doubles the worst-case time for
   Petrovich's own eye to first catch a new contact dead ahead (≈8 s → ≈14 s), on top of the
   26–29 s revisit figure already in the plan. The plan accepts this because you're watching ahead
   yourself while flying — does that hold even when you're focused on instruments or terrain at low
   level, or should ahead get a second visit per cycle despite the cost (the plan rejected that: 10
   legs, four glass steps, under 2.5 s of binoculars per step)?

## Plan re-check 2 — 2026-11-02

**Verdict:** ALIGNED. Both prior CONCERNS are resolved cleanly, and both resolutions check out
against the live source, not just the plan's prose: `SCAN_PLAN`'s default is confirmed as
`(12, 11, 10, 9, 12, 1, 2, 3)` in `perception/gaze.py`, and `GLASSING`'s call to `is_worth_a_look`
is confirmed to pass no `stall_cooldown_s` today (`belief/optic_policy.py:2918`), matching the gap
the plan says it closes. One selectivity point is worth a line to the user, not a blocker, and
Decision 6 is correctly left unescalated.

| expectation | stage | status |
|---|---|---|
| E1 (two groups stay two) | 2 | met — unchanged |
| E2 (one group stays one) | 2 (partial) / BL-B111 | contradicted for 4–10% cross-optic false-split under BL-B110 alone, same as before, dated to BL-B111 — unchanged |
| E3 (no callout until verdict, bounded) | 2 | met — unchanged |
| E4 (look at A's area, debug-visible, B first) | BL-B111 Stage 4 | missing in BL-B110 (unchanged), scheduled |
| E5 (absence counts only where visible) | BL-B111 Stage 3 | missing in BL-B110, scheduled |
| E6 ("moved" only if believable) | BL-B111 Stage 4 | missing in BL-B110, scheduled |
| E7 (composition as graded suspicion) | BL-B111 Stage 4 | missing in BL-B110, scheduled |
| E8 (never pre-empts a threat/9K113) | BL-B111 Stage 4 rows | met where it will exist |

### Findings

1. **Both prior CONCERNS resolved, and the resolution is grounded in the user's own words, not a
   reading of them.** — lens: Grounded in
   - Order: *"always start from ahead and sweep to left/right alternating"* is read as ahead → left
     → ahead → right, which is exactly `SCAN_PLAN`'s existing table — verified in
     `perception/gaze.py` line 299-300, not assumed from the plan's prose. No reshape, no new test
     churn, and 12 o'clock keeps its ≈8 s worst first-notice (prior finding 4 is moot — the single-
     visit-per-cycle premise that produced ≈14 s no longer applies, because the table never changed).
   - Budget: *"four is too short ... 12 s sounds ok"* is built as a 12 s **rolling** per-cycle
     budget that gates a look's start, never its length, with no per-step cap — a literal reading of
     "don't limit the time too tightly," not a rounded-off version of it.

2. **Selectivity is matched well, with one real gap the plan already names rather than hides.** —
   lens: Whose job / Purpose
   - The user's rule has two parts: (a) raise binoculars only when they can add detection,
     classification or identification *at the current distance* — already enforced by
     `can_still_improve`/`tier_ranges`, confirmed unchanged; (b) once raised, don't cut the look
     short — built exactly as the start-gate/natural-end design.
   - `GLASS_STALL_COOLDOWN_S` (180 s) closes a third, narrower gap the user did not ask about
     directly: a look that already happened and taught nothing is currently retried anyway at 64 s
     at the same range (confirmed live: `GLASSING`'s `is_worth_a_look` call passes no
     `stall_cooldown_s`, so the long-cooldown branch never engages there today). That is the
     measured form of "additional information not available at current distance" extended from
     range to *recency*, and it reuses `BL-B85`'s existing pattern (`SIGHT_STALL_COOLDOWN_S`)
     rather than inventing a second mechanism — the right call under "do not reinvent the wheel."
   - The one place this could over-suppress: the user's own composition language (E7, *"3 and 5
     could be obscured, that deserves more attention"*) describes a case where a look's value
     depends on *aspect or masking clearing*, not on the aircraft closing range. `GLASS_STALL_
     COOLDOWN_S`'s only escape is `RETRY_RANGE_FRACTION` (closing to 80% of the attempt range);
     nothing re-admits a contact whose look failed for a transient reason (a tree line, a bad
     aspect) if the aircraft does not also close distance in the next 180 s. The plan's own Risks
     section names this plainly (*"a contact that failed once because of a transient cause... is
     not glassed again for three minutes"*) and marks the constant `#needs-flight` — so this is not
     a hidden gap, and E7's actual mechanism (composition suspicion driving a deliberate re-look) is
     BL-B111 work, not this plan's, so it cannot be contradicted by something not yet built here.
     Worth one line in the test card so the pilot is listening for it specifically, not just
     noticing "binoculars came up less than expected" in general.

3. **Decision 6 is correctly left to the Implementer, not the user.** — lens: Whose job / The
   envelope
   - The accepted overrun (≤2 s past `POSITION_HALF_LIFE_S`, flank-only, full-budget windows only)
     was traced against the real consumers (`certainty_of`, `lifecycle_event_kind`,
     `contacts.py`'s `fresh` gate), confirmed present at the cited call sites. The only audible
     effect is a watched flank contact's kilometre-crossing line landing up to ~2 s late, in a
     scenario (12 s of binoculars inside one 16 s cycle) the plan itself says needs a multi-group
     burst to occur at all.
   - That is local, reversible (a single tunable, `GLASS_BUDGET_PER_CYCLE_S` or
     `POSITION_HALF_LIFE_S`), and does not materially change what the pilot hears — exactly
     `AGENTS.md`'s bar for proceeding without escalation. No finding here; noted because the plan
     re-check prompt asked the question directly.

4. **The second-order note on BL-B111's hold growing to ≈17 s is the correct place to carry this
   plan's one real downstream cost, and it is carried.** — lens: Grounded in
   - With no per-step cap, a busy sector can now spend up to two full 6 s looks before B's own look
     and A's area-look (BL-B111) get their turn, pushing the structural hold past
     `CALLOUT_MAX_AGE_S` (10 s). The plan states this is where BL-B111 picks it up as "load-bearing"
     rather than "required," which is the right escalation target — BL-B111 hasn't been architected
     yet, so this plan cannot resolve it, only flag it accurately. Confirmed it is flagged
     (plan.md, "Second-order effect").

### Questions for the user

- None required to proceed. One optional note for the acceptance flight, already reflected in
  Finding 2 above: if binoculars seem reluctant to re-check a contact that was obscured (tree line,
  bad aspect) rather than one the aircraft is closing on, that is `GLASS_STALL_COOLDOWN_S` (180 s)
  — a single tunable to shorten if three minutes feels too long once flown.

## Plan re-check 3 — 2026-11-02

**Verdict:** ALIGNED. The fifth pass (Stage 0a, the refined optics priority, Decisions 7–11) traces
cleanly against the goal check and the user's own last three sections of `explore-notes.md`. Every
constant the plan cites to ground "no binocular look is ever needed for rough location"
(`RANGE_FRACTIONAL_SIGMA = 0.17`, `BEARING_SIGMA_DEG`) checked out against
`body-layer/src/perception/estimation.py` on a grep, not just the plan's own table, and
`SCAN_PLAN`'s default `(12, 11, 10, 9, 12, 1, 2, 3)` was re-confirmed in `perception/gaze.py` —
unchanged since re-check 2, so the "order already matches the user's words" claim still holds.
`LookTarget.watched` (`belief/optic_policy.py`) exists exactly as the exact-location predicate
uses it. No new blocking finding; two points are worth a line to the user, and Decision 10's
non-escalation is confirmed correct.

| expectation | stage | status |
|---|---|---|
| E1 (two groups stay two) | 2 | met — unchanged |
| E2 (one group stays one) | 2 (partial) / BL-B111 | contradicted for 4–10% cross-optic false-split under BL-B110 alone, same as before, dated to BL-B111 — unchanged |
| E3 (no callout until verdict, bounded) | 2 | met — unchanged |
| E4 (look at A's area, debug-visible, B first) | BL-B111 Stage 4 | missing in BL-B110 (unchanged), scheduled |
| E5 (absence counts only where visible) | BL-B111 Stage 3 | missing in BL-B110, scheduled |
| E6 ("moved" only if believable) | BL-B111 Stage 4 | missing in BL-B110, scheduled |
| E7 (composition as graded suspicion) | BL-B111 Stage 4 | missing in BL-B110, scheduled |
| E8 (never pre-empts a threat/9K113) | BL-B111 Stage 4 rows | met where it will exist |

### Findings

1. **The rough-location allowance plateaus at 250 m below 1.25 km, rather than continuing to
   tighten close in — moot today because the model over-delivers, but the fence itself does not
   literally track "the closer, the more specific."** — lens: Grounded in / Purpose
   - The user's own wording (*"the further away we are, the more imprecise the location is
     allowed to be. At close distances a more specific location can and should be obtained"*)
     reads as continuous: tighter and tighter as range falls. The built allowance,
     `max(250 m, 0.2 · R)`, stops tightening once `R` drops below 1.25 km and sits flat at 250 m
     all the way to zero range.
   - In the sim: today this costs nothing, because the naked-eye model's actual delivered sigma at
     close range is already far tighter than the floor (81–85 m down-range at 500 m, against a
     250 m allowance) — the table in Stage 1 shows this. So the pilot hears the tight figure the
     model actually produces, not the loose one the fence would still pass.
   - The pilot would see: nothing different today. The risk is only a silent one — a future change
     to the naked-eye model (Decision 10's own named risk, `test_estimation.py`'s fence) could
     degrade close-range precision all the way down to 250 m at, say, 300 m range (80% of the
     range itself) and still pass this fence, because the fence does not get stricter below
     1.25 km the way the user's sentence implies it should.
   - Grounded in: the user's "Decision 7 and the refined priority" section, verbatim, and the
     allowance definition and table in plan.md, Stage 1, "Priority 1" (confirmed against
     `RANGE_FRACTIONAL_SIGMA`/`BEARING_SIGMA_DEG` in `perception/estimation.py`).
   - Suggests: not a blocker — Decision 10 already flags that a naked-eye regression is the one
     thing that could break this, and the fence exists for exactly that. Worth tightening the fence
     itself to keep shrinking below 1.25 km (e.g. a pure `0.2 · R` with no floor, since the model
     already clears it with margin at every measured range) so a future regression at *close*
     range — the range the user specifically called out — is caught as readily as one far out.

2. **Exact-location looks are gated on `watched`, which is a faithful reading of a standing
   "look after this" instruction, but leaves a one-off question ungated — plausibly out of this
   plan's scope, not a contradiction of it.** — lens: Whose job / Grounded in
   - The user's words, *"anything the player asks for"*, sit in a list about what should earn a
     binocular look toward exact position. `watched` (`attention.effective_attention`, a voice
     "watch that truck at three o'clock") is the existing mechanism for "the player singled this
     contact out," and the plan's grep-confirmed wiring (`LookTarget.watched`) maps it correctly.
   - What it does not cover: a one-off question — *"where exactly is that group"* — asked without
     first placing a watch. Nothing in this plan adds a location look triggered by a live query;
     a query would be answered from whatever belief already exists at ask-time.
   - The pilot would see: asking about an unwatched group's exact position gets today's belief,
     not a fresh binocular fix, unless they first say "watch that group."
   - Grounded in: `explore-notes.md`, "Decision 7 and the refined priority" — the sentence is
     about optics-priority input, not about live query handling, and the plan's own scoping
     (excluding an attack-run target, which is also "asked about" in a sense) shows the same
     judgment call made consistently elsewhere in Stage 1.
   - Suggests: confirm with the user that `watched` is the intended proxy for "asks for," not a
     live-query path — likely yes, since a one-off query-triggered look is a different mechanism
     (crew-query handling, not scan/optics ordering) and is not what this entry's goal covers.

3. **The one real cost of the slow, circling approach profile — the pre-existing eye-aliasing gap
   growing to ≈40 s worst case — lands in exactly the scenario the user described as the reason for
   that profile, and the plan leaves it unfixed by design; already disclosed, worth a line in the
   test card.** — lens: Whose job / The envelope
   - The user's own reason for the careful, ~100 km/h, sideways/circling approach is *"so that
     Petrovich has time to scan without us flying headfirst into danger."* The plan's own Risks
     section states the eye's eight-leg sweep already aliases a crossing contact for ≈28 s quiet,
     growing to ≈40 s with a full glass budget, at the rotation rates that same approach profile
     produces (0.5–2°/s) — and that the fix (a perception cone-overlap change) is explicitly out
     of this entry.
   - The pilot would see: during exactly the cautious, circling approach meant to buy Petrovich
     scanning time, a contact crossing a sector-leg boundary at the wrong phase can still go
     roughly 40 s between naked-eye sightings — longer than the approach is meant to allow for.
   - Grounded in: plan.md, "Body rotation", "Pre-existing, not introduced, stated", and Risks &
     Unknowns' "Rotational eye aliasing" entry — both already honest about this, not hidden.
   - Suggests: not a reason to hold the plan — it stays below the lost/group-expiry cliffs (a
     debounce delay, not a dropped contact), and the real fix is a separate, named piece of work.
     Worth one line in the Stage 1 test card asking the user to specifically notice eye pickup
     latency while circling, since nothing else measures this pre-flight.

4. **Decision 10's non-escalation is correct under `AGENTS.md`'s own bar.** — lens: Whose job
   - The allowance-as-test-fence choice changes nothing the pilot can hear today (no code path
     compares a belief to it, confirmed by Stage 1's own "Priority 1" reasoning: no binocular look
     is ever raised for rough location). It is local, reversible (a test fence, not even a
     tunable), and matches the inclusion test in root `CLAUDE.md`'s "Behaviour-affecting constants
     are tunable" section (a constant that does not affect behaviour stays an ordinary literal).
     Correctly left to the Implementer, not escalated.

### Questions for the user

1. Tighten the rough-location allowance below 1.25 km to keep shrinking with range (e.g. drop the
   250 m floor and use a pure `0.2 · R`), so the test fence tracks "closer means more specific"
   continuously rather than plateauing — or is 250 m fine as a floor since the model already beats
   it with margin at every measured range? (Finding 1; recommendation: tighten the fence, cheap and
   changes nothing delivered today.)
2. Confirm `watched` (a standing "watch that contact" instruction) is what you meant by "anything
   the player asks for" for exact-location looks, rather than a one-off question asked without a
   watch — the latter isn't built here and would be a different mechanism (crew-query handling).
   (Finding 2; recommendation: yes, `watched` is the right proxy — a live-query-triggered look is
   out of this entry's scope.)
3. One line for the Stage 1 test card: during the circling/sideways approach, specifically notice
   how quickly Petrovich's eye picks up a new contact crossing from one side sector to another —
   the pre-existing eye-aliasing gap (Finding 3) can reach ≈40 s there, below the entry's own lost
   cliffs but worth confirming in the air. (Recommendation: add the line; no plan change needed.)
