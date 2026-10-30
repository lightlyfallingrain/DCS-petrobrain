# Relative-distance grouping — behaviour alignment

## Goal check — 2026-10-31

**Verdict:** CONCERNS

The goal is sound and well grounded in the user's own words (`explore-notes.md`). The concerns are
about three places where a planner must fill a gap, and the obvious fill would quietly defeat the
why: how the *relative* judgement is produced, what happens when the viewing angle changes, and how
the new rule sits beside the user's 2026-09-18 "separability is angular" decision.

### Why

When two groups sit on roughly one bearing at clearly different distances, the pilot needs to hear
about **both**, because they are two places to avoid or two things to attack. Petrovich currently
folds them into one contact, which is how one of them goes unreported.

Asked "why" a second time, the answer is that a real front-seater judges *which is further* and
*is this the thing I saw before* far better than he judges *how far*. Size, depression angle and
terrain all give him that relative judgement. Petrovich's grouping decisions are being made on the
absolute-range error, which is the one quantity he is worst at.

So the purpose is: **one real group gives one contact, and two real groups give two**, judged the
way a human observer judges them. This must not cost honesty about absolute range, which keeps
today's error.

### Player expectations

- **E1** — Two groups roughly on one bearing and clearly at different distances (the clear case:
  about 1.5 km or more apart at 2–5 km) give the pilot **two contacts and two callouts**. This holds
  whichever is seen first: both in the same look, or the far one alone first and the near one
  seconds later (the BL-B104 scenario that folded).
- **E2** — Units kilometres apart along the line of sight are **never reported as one group with
  one count**, even though they fit in the same field of view.
- **E3** — One real group seen repeatedly from about the same place (dwell, look away and back)
  **stays one contact**. There is no second "new contact" callout for it, and its 200 m line does
  not split into two groups because of range noise.
- **E4** — The **spoken range** of a single sighting keeps today's size of error (about ±700 m at
  4–5 km). Repeated looks from the same place give **the same number**, not a value that jitters
  between looks, and not a value that gets more precise just from staring.
- **E5** — The range estimate **does improve when the pilot closes or comes at the group from a
  different angle**. While it improves, the group stays the same contact. There is no re-detection
  callout during a straight-in attack run or while orbiting.
- **E6** — The ambiguous middle case (2 km vs 2.5 km, especially very low) may come out either way.
  How it comes out is adjustable after a flight, through tunables, without a code change.
- **E7** — A stationary group that drops out of sight under the nose and goes "lost" is **still
  there in mission memory** (kneeboard or recall) afterwards.

### Open assumptions

- **Where the "relative" judgement comes from, for two different objects seen in the same look.**
  - Serves the why: neighbouring things seen together share most of their range error. That is the
    point of the scene, size and terrain cues, so their placement relative to each other is good
    while their absolute placement is not.
  - Would not: each object or cluster gets its own independent draw, stable or not. Two independent
    ±σ errors make the *difference* about √2 times worse than the absolute error, which is the
    opposite of the user's claim. Today that is how it works: one draw per cluster, with independent
    per-object biases.
- **What "the same as before" is compared against when the earlier sighting is no longer in view.**
  - Serves the why: Petrovich's own remembered estimate, compared with his new estimate. The
    per-object stable error (scope item 2) is what makes that comparison meaningful.
  - Would not: any comparison that reads the true range ratio, including "true ratio plus a little
    noise", for something not currently in view. That is omniscience (lens 4).
- **The repeat-look correlation is tied to the geometry, not to the object for ever.**
  - Serves the why: the stable error holds while the range and line of sight are about the same, and
    it decorrelates as the pilot closes or the line of sight rotates (user, answer 2).
  - Would not: a per-object offset that never changes. That would never let triangulation help, and
    it would let a closing run "snap" the estimate in one jump.
- **The circular merge zone applies to "same view geometry".**
  - Serves the why: near-circular while the line of sight is about the same. After a large
    line-of-sight rotation, the old belief is still wrong by its old along-line-of-sight error, and
    the new look legitimately differs by about that much, so the decision must still say "same
    group".
  - Would not: a fixed circle against the stored belief position regardless of how the geometry
    changed. That splits an orbited group (Finding 2).
- **The merge zone is a gap between neighbours, not a cap on a group's whole extent.**
  - Serves the why: single-link, so a column strung out along a road toward you stays one group.
  - Would not: total extent or distance from the centroid. That breaks a long column into two.
  Needs the user (Q2).
- **Which grouping mechanisms are in scope.** The brief names `perception/clustering.py` and
  `belief/association_over_time.py`. Two more also decide what "one group" is:
  `perception/group_salience.py`, which uses an angular cohesion of 10 unit widths, so units about
  1 km apart along the line of sight count as one salient group at 4 km and 200 m AGL; and
  `belief/groups.py`, a cohesion test over the fused belief positions with a 500 m cap. E2 is a
  pilot-level claim, so the planner must say which of the four can still put km-apart units into one
  reported group, not only fix the two named.
- **The absolute error does not shrink with dwell.**
  - Serves the why: E4 as stated by the user ("Only way to make it more accurate is comparing to a
    map").
  - Would not: keeping the precise-position-belief fusion, which treats looks as independent and
    converges to the 0.4σ floor.

### Findings

1. **Relative judgement needs a correlated error across objects, not only across looks.**
   Lens: world truth, purpose.
   - Assumption: scope item 2 makes one object's repeat-look error stable. Nothing in the scope says
     how two *different* objects' errors relate within one look.
   - In the sim: one `Observation` per cluster, one per-look draw per observation id, and a
     per-object bias hashed off each object id (`perception/estimation.py`). Two clusters seen
     together get independent errors.
   - The pilot would see: the two groups on one bearing separated correctly, but one group whose
     members resolve into two clusters placed hundreds of metres apart along the line of sight, and
     then possibly split by a tight gate or by `groups.py`'s 500 m cap. That breaks E3.
   - Grounded in: the user's own words: *"an observer can fairly easily tell relative distance"*,
     *"One is further than the other"*, *"surrounding terrain features help judge the relative
     distances"*.
   - Suggests: the plan must state how relative precision between things seen together arises.
     Architect decides how.
2. **A circle is right only while the view geometry is similar. Triangulation must update the group,
   not split it.** Lens: the non-obvious case.
   - Vignette: the pilot orbits a stationary group at 3 km, and the line of sight turns 90°. The
     stored position is wrong by about 500 m along the *old* line of sight, which is now across the
     new one. The new look's estimate is honest and differs by about that much.
   - The pilot would see: a fixed circular gate against the stored position fails, a new contact
     appears and there is a second callout for the group he is circling. That breaks E5.
   - Grounded in: the user's answer 2 (*"a different angle to look from, triangulation by ownship
     movement"* makes it more accurate). The improvement is meant to happen *to* the group.
   - The same holds for a **straight-in closing run**. The estimate migrates toward the truth as the
     error scales down with range, and it must not cross the gate as a jump. The BL-B104 plan already
     named this concern ("a spurious new contact during a closing run").
3. **This changes how the angular-separability decision of 2026-09-18 applies within one look.**
   Lens: purpose. This is a conflict with an earlier user decision.
   - `plans/group-contact-model/plan.md`, "Correction (user, 2026-09-18)": two objects are one blob
     when they overlap in angle — *"may be one when one sits behind the other"*. At about 30 m AGL,
     units at 2.0 and 2.5 km on one bearing overlap by that rule (depression difference about
     10 arcmin against a unit size of about 11 arcmin) and merge in `clustering.py` today.
   - The new direction says size and terrain still separate them (*"they can still be told apart by
     angular unit size"*).
   - The two can both be true if the angular rule decides *whether he can see two things* and the
     relative rule decides *whether things he can see form one group*. But the brief puts
     `clustering.py` in scope for the relative rule. Only the user can say whether occlusion still
     makes one blob (Q1).
4. **This reverses part of an approved precision decision. The pilot will notice it on the
   kneeboard.** Lens: world truth, crew sense.
   - `plans/precise-position-belief/plan.md` treats per-look noise as averaging down across looks,
     with *"uncertainty strictly decreases"* for a moving observer, to a 0.4σ floor
     (`SYSTEMATIC_BIAS_FRACTION`).
   - Under the user's answer 2, a group watched from 4.5 km for a minute keeps about ±700 m of
     absolute error. That is honest, and it is what the user asked for. But mission-memory positions,
     and anything that reads the fused position, become less precise than today for groups only ever
     seen from a distance.
   - Not a concern with the direction. It is a consequence the plan must carry deliberately, not
     discover. Confirm (Q3).
5. **A lost group reaches mission memory only if it was nameable.** Lens: purpose.
   - `mission_memory/admission.py` writes a group entry only at classification level CLASS or above,
     with confidence over the floor. A group that was only ever "something there" never gets an
     entry, so E7 fails silently for that case. Whether it should is the user's call (Q4).
6. **Bounded knowledge.** Lens: bounded knowledge.
   - "Relative judgement" is easy to implement as the truth ratio with a small noise. Within one look
     that is a modelling choice, and it is tunable. Across looks, against something no longer in
     view, it is omniscience. The plan should say what perceived quantity each comparison uses.

Lenses silent: whose job (no crew-role change), unit of action (aim and slew use the exact relative
direction, not the absolute range, so they are unaffected), envelope (the clear cases cover 50–800 m
AGL; very low is the ambiguous case and the user accepts it as tunable).

### Questions for the user

- **Q1** — Two units directly behind each other at very low altitude, overlapping in view: still one
  blob, as on 2026-09-18, with relative distance deciding grouping only for things he sees as
  separate? Or does size now separate even overlapping ones?
- **Q2** — A column about 1 km long driving straight toward or away from you: one group, provided
  the gaps between neighbours are small? Or does its length alone make it more than one?
- **Q3** — A group only ever seen from about 4–5 km keeps about ±700 m on the kneeboard however long
  he watches it, where today it tightens with dwell. Is that acceptable?
- **Q4** — A group that goes lost while still only "group, something": should it also go into
  mission memory, or only groups he had named?
