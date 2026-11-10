# Expected-area look (BL-B111) — alignment

Base: `main` at `b92d59c9`. This builds on the BL-B110 goal check
(`plans/expected-area-check/alignment.md`, E1–E8, Q1–Q5 answered 2026-11-01). That check still
stands and is not redone here. This section covers only what changed because BL-B110's Stage 2
was not built (Decision 13 (a)), which leaves BL-B111 as the only planned route to "two groups on
one bearing called as two".

## Goal check — 2026-11-10

**Verdict:** CONCERNS. The goal is right, it is Petrovich's job, and it is now worth more than
when it was split out. But the design BL-B111 inherits opens a check only where BL-B110's Stage 2
trigger fires. That trigger was not built, and on honest numbers it would fire on 5–15 points of
one cell family. Planned literally, BL-B111 would build the look, the LOS query and the verdict
table, and then almost never use them. Before Architect starts, the user needs to settle what
opens a check (Q1, Q2).

### Why

So that the pilot hears the right number of groups in the right places when a sighting lands on
the bearing of a group Petrovich remembers but cannot see right now. A second group must be called
as a second group, and a remembered one must not be called new again. The honest grid
(`plan.md`, seventh pass) shows that range numbers cannot separate two groups 1.5 km apart on one
bearing (≈2σ). **The look is the only thing that adds the missing information:** a glance that
puts A's expected place and B in view at the same moment, the way the user settles it (*"look
around the area a bit and that would tell me"*).

Second why: the verdict has to rest on something he saw. The fold, the merge-echo rule and the
long-gap split are all silent guesses made from arithmetic.

### What changed since the BL-B110 goal check

- **E1 is now BL-B111's main delivery, not a remainder.** On honest numbers a nearer group on a
  remembered bearing goes unannounced 58–86% cross-optic (gate fold) and 63–73% eye → eye
  (merge-echo, `[[BL-B114]]`). BL-B110 delivered none of this.
- **The entry's own value statement is stale.** `BL-B111.md`'s first bullet, "the 4–10%
  cross-optic false split that BL-B110 accepts is removed", describes Stage 2's trade, and Stage 2
  was not built. BL-B110 introduced no false split. What BL-B111 removes is the fold (E1) and the
  heard long-gap duplicate (E2, `[[BL-B113]]` past 120 s: 10–12% by eye, 6–7% binocular).
- **`[[BL-B109]]`'s precondition now sits on BL-B111.** Its wording explore (the user: *explore
  together*) belongs to this entry's planning, not to a later one.

### Player expectations

E1–E8 carry over unchanged from the BL-B110 goal check. The table below says what each now means
for BL-B111. E9–E12 are new.

| | expectation | change |
|---|---|---|
| E1 | Two groups stay two: once A has been seen at its place, B is heard as new and A is not re-announced | now the primary deliverable |
| E2 | One group stays one: a re-sighting of A is not heard as "new contact" | now also covers the long-gap duplicate (BL-B113 past 120 s) |
| E3 | No callout until the verdict, bounded, never silently dropped | bound ≈17 s worst, ≈5–8 s typical (plan) |
| E4 | The look is at A's area, visible in the eyesight view, B first then A | unchanged |
| E5 | Absence counts only where he could have seen | unchanged; Stage 3 |
| E6 | "Now at …" only when composition and displacement are believable | unchanged |
| E7 | Composition is graded suspicion, never a verdict without a look | unchanged |
| E8 | Never pre-empts a threat callout or the 9K113 sight | unchanged |

- **E9 — The look happens whenever the question honestly arises.** Whenever a sighting could be a
  remembered group he cannot see right now, he checks before deciding. That covers B folded into
  A, B founded beside A and about to be silenced as A's echo, and B founded beside a lost A. A
  narrow numeric trigger does not count. The pilot test: with two groups on one bearing and the far
  one out of view, the binoculars go to the far group's place, and that look shows up in the
  eyesight view.
- **E10 — A re-sighting where the group was produces no new line.** If the check finds A where he
  left it, the pilot hears nothing new. The neutral *"That group, now two o'clock, three
  kilometres"* comes only when the place he would call has actually changed (Q3).
- **E11 — The visibility answer is about the place, never the unit.** The probe point is A's
  believed position, set on the terrain at that point plus a vehicle's height. Ownship elevation is
  never used (calibration case: *ownship elevation*), and neither is A's true position. No answer
  means "cannot look", never "empty".
- **E12 — Each remembered SAM site gets one threat line.** If a remembered threat is re-seen, it
  is called at once (Q2 of BL-B110). A later "same" verdict must not produce a second line that
  sounds like another site (Q4).

### Open assumptions

- **What opens a check.** This is the load-bearing one; Finding 1 explains why.
  - Serves the why: any sighting that resolves onto, or is founded beside, a remembered contact
    that is not in the current look. That means the gate fold, the gate split that merge-echo
    would silence, and the gate split beside a lost A.
  - Would not serve it: Stage 2's as-if-gate trigger (fires on 5–15 points of one cell family),
    or anything that waits for range arithmetic to flag the case. The honest grid shows the
    arithmetic cannot flag it.
- **What counts as "A observed" in the look.**
  - Serves the why: units at A's place that are not B's units. Within `OBJECT_ID_MEMORY_S`, that
    is A's own objects re-seen through continuity. Past it, a separate cluster in the same field.
  - Would not serve it: "something seen in A's area". When B *is* A (same group, stationary,
    re-seen), B lies inside A's area, and the look would wrongly read "A observed → different".
    Vignette 1 walks this.
- **Glass budget for area looks.**
  - Serves the why: area looks rank first and spend the shared 12 s. If the budget is spent, B is
    called new right away, which is the user's own Q3 direction (*"call B as new"*: missing a group
    is worse than a duplicate).
  - Would not serve it: an exemption that quietly stretches flank revisits past the 30 s
    half-life the user accepted. The other side is a user call (Q5).
- **The relocation threshold.**
  - Serves the why: speak "now at" only when the o'clock or range he would call has changed.
  - Would not serve it: speaking it on every "same" verdict. That turns a silent, correct fold into
    a line on every long-gap re-sighting (Q3).
- **The probe point** is covered by E11. It must come from belief and sit on the terrain.
- **Trees and buildings.**
  - Serves the why: forest by world-model landcover, as Stage 3 already says. `land.isVisible` is
    terrain-only.
  - Would not serve it: treating terrain-clear as visible inside a town. The plan names no
    building mask. Stage 3 should say that urban areas count as "cannot look" or state the gap.
- **World-model LOS.** The offline LOS is testing-only (user, `docs/acceptance/2026-10-05-sortie-feedback.md`),
  so the live answer must come from the DCS Hook (option (a)). That is already the plan. It is
  restated here so that a fallback is not added.

### Findings

1. **The check inherits a trigger that does not exist, and the honest grid says it would barely
   fire.** — lens: Purpose / Unit of action
   - Assumption: `plan.md` Stage 4 says *"Stage 2's trigger now opens a check instead of releasing
     B."* Stage 2 was not built. Rebuilt as designed, it catches 5–15 points, only bino → eye with
     B nearer, and never eye → bino or the merge-echo path.
   - In the sim: the plan itself says *"In flight, a same group inside 600 s goes through object
     continuity, not the gate."* So in flight, a gate-path sighting onto, or beside, a remembered
     contact out of view is nearly always one of two cases:
     - B, a different group, whose objects are new;
     - A after a long gap.

     Those are exactly the two cases the look exists to settle. A broad trigger therefore costs
     little in flight, where the harness's same-group gate cells overstate it. The look is cheap
     and correct in the second case too.
   - What the pilot would see: no change from today. The far group's place is never glassed, the
     nearer group still folds or goes unspoken, and the new LOS machinery sits unused.
   - Grounded in: `plan.md` honest grid ("Of the three silent paths, the trigger reaches the
     smallest"), Decision 13, and the in-flight continuity note quoted above.
   - Suggests: the check's trigger is the first thing Architect settles, with Q1 and Q2 answered.
     It should be the case, not a range test.

2. **The look can fix the merge-echo path without the trade BL-B114 fears.** — lens: Crew sense /
   Purpose
   - BL-B114's trade is between tightening `contacts_plausibly_same` (missed groups) and keeping it
     (silence). Both options rearrange the same numbers. A look adds information, so the trade
     goes away: rather than silence B as A's echo while A is out of view, hold B and look.
   - This does **not** undo Decision 14. That decision rejected folding the callout rule's
     tightening into BL-B111; this is the look, used where the echo rule would otherwise guess.
     BL-B114 keeps the "cannot look" remainder. But the user deferred that gap with *"measure
     first, explore before any fix"*, so this is their call (Q2).
   - Grounded in: `BL-B114.md` ("tightening it trades missed second groups for duplicate
     callouts") and the moved believed-distinct skip, which today covers only trigger-fired pairs.

3. **A "same" verdict needs a line about the group only when it has visibly moved.** — lens: Crew
   sense
   - The BL-B110 goal check's Q4 (*"tell me about both"*) was about A having *moved*. With a broad
     trigger, most "same" verdicts in flight will be a stationary group re-seen where it was.
     Speaking *"That group, now …"* each time would be noise the user rejected (*"less noise is
     better"*).
   - Suggests: E10 and Q3.

4. **The look sees both groups at once, and that is why it works.** — lens: World truth / The
   envelope
   - At 100 m AGL, groups at 3 and 4.5 km on one bearing are about 0.6° apart in depression, well
     inside one binocular field (4.25°). The look puts both in the same poll, where BL-B108's
     in-view path already separates them (0% fold).
   - So "A's area" must not be read as a separate place to visit and judge empty. Most of the
     verdict comes from both groups being in one field.
   - This also explains the trap in Open assumption 2: when B is A, the field holds one group, not
     two.
   - Already in the BL-B110 check (its Finding 3). It is repeated here because Finding 1 makes the
     look common rather than rare.

5. **Whose job — passes.** Telling one group from two is detection and identification, the core
   of Petrovich's job. The pilot benefits directly. He will notice when it works, as a nearer
   group he is now told about.

**Vignette 1 — a remembered SAM site, re-seen after twelve minutes.**
- A is an `s-125` site, glassed and then lost behind terrain. Continuity has expired, so the
  re-sighting goes through the gate. Today the gate splits it 10–12% of the time by eye, and the
  pilot hears a "new" SAM.
- With a broad trigger, B is AD, so Q2 releases it at once and the pilot hears the threat line.
  The check continues: one group in the field, B's units, composition matching, displacement zero.
  The verdict is "same".
- The plan's verdict table then speaks *"That group, now …"*. The pilot has heard two lines about
  one stationary SAM site, and the second sounds like news. That is E12 and Q4.
- Without Open assumption 2's distinction, the look sees units "in A's area" and rules
  **different**. Then `mark_absent` never fires, but the duplicate stays permanently.

**Vignette 2 — the user's own case, ridge crossing.**
- B appears nearer as the aircraft crests the ridge, and A is still masked by a second fold of
  ground.
- Stage 3 rules "cannot look", and B is called new. That is right: E1 holds, and E2 is not
  touched because nothing was folded.
- If A unmasks one sweep later, the in-view path already has both. No issue.

### Questions for the user

1. **When should he look at a remembered group's place?** Recommend: **every time** a new
   sighting lands on, or right beside, a remembered group he can't see right now. In flight that
   is almost always a real "is this the same group?" moment. The alternative is only on a narrow
   numeric flag, which honest numbers say almost never fires.
2. **When he is about to stay silent because B "is probably A's echo" (BL-B114), should he look
   first?** Recommend: **yes**. Hold B, look, and speak B if A is seen at its place. BL-B114 stays
   for the cases where he can't look.
3. **He re-sees a group exactly where he left it: anything said?** Recommend: **silent**. Say
   *"that group, now …"* only when the o'clock or range he would call has changed.
4. **A remembered SAM site is re-seen. He calls the threat at once (your earlier Q2), then the look
   shows it is the same site. What should the second line be?** Recommend: **none if it has not
   moved**. Settle the wording in the BL-B109 explore.
5. **Should area looks spend the shared 12 s binocular budget?** Recommend: **yes, and they rank
   first**. If the budget is spent, B is called new right away, per your *"call B as new"*.
