# BL-B104 — behaviour alignment

## Goal check — 2026-10-30

**Verdict:** CONCERNS

### Why

When Petrovich has seen a ground unit, everything that later points at it — the 9K113 sight at the
start of an attack run, the guidance words, the "ground, two o'clock, three kilometres" report —
must point at **where that unit actually stands, on the ground**, so the sight can pick it up and the
pilot can find it. Today the believed point floats at whatever altitude the helicopter had when it
looked, so it drifts into the sky as the aircraft descends into the run (sortie 2026-10-30 §4: +72°
believed vs −84° true), and the sight never sees the target it was told to track.

Second "why": *why does the sight need the right point?* Because an ATGM run whose sight cannot
acquire the target is "utterly pointless" (user, §4). So the measure of success is not a better
number in belief — it is **the sight acquiring the engaged unit and saying "Tracking."**, and the
pilot hearing reports he can use.

### Player expectations

- **E1** — A ground contact's believed point is never above the helicopter or in the sky. After any
  climb or descent since the last look, the sight's belief aim still points down at the ground near
  the unit.
- **E2** — When an ATGM run starts on a unit Petrovich saw earlier, the sight starts close enough to
  it (inside the 9K113 wide field, ±5.75°) to acquire it directly at typical run geometry; at far,
  shallow geometry the bearing-line search finds it. Either way he says **"Tracking."** and the sight
  stays on it.
- **E3** — The range the pilot hears in a report is roughly right — **no worse than today** at the
  geometry Mi-24 attack runs actually happen at (50–800 m AGL, 2–6 km) — and it visibly firms up as
  the helicopter closes and Petrovich keeps looking.
- **E4** — Guidance words ("come left", "on the nose") lead the pilot onto the real unit, not to an
  empty patch of ground in front of or behind it.
- **E5** — The same unit re-seen from a changing angle or range stays **one** contact: no second
  "new contact" callout for something already reported. Two groups on the same bearing at different
  ranges stay **two** contacts.
- **E6** — Air contacts behave exactly as before (no regression the pilot would hear).
- **E7** — Petrovich is still not omniscient: a unit looked at many times is reported confidently
  but not exactly; nothing he could not have seen changes where he thinks a unit is.

### Open assumptions

- **How large the depression error is, and in what unit** — serves the why: an error whose effect
  **on the ground** stays comparable to today's (~17% of range) across the envelope and shrinks with
  closeness, optic and repeated looks; would not: a fixed angular σ equal to `BEARING_SIGMA_DEG`
  (3°) applied to depression, which at shallow angles turns into kilometres (Finding 1).
- **What happens when the perturbed ray does not reach the ground** (points level or above the
  horizon; helicopter low, unit on a ridge above it) — serves: a bounded fallback that still yields a
  sane range (today's estimate, or the far edge of what was visible); would not: no position, an
  infinite range, or a point behind the observer.
- **Which height a multi-unit cluster gets** — serves: the heights of the units actually in that
  cluster (each roughly where it stands); would not: one unit's height for a group spread over a
  slope, or the ownship's.
- **When the unit's height is read** — serves: only at the moment of a percept, as part of that look;
  would not: refreshed from the feed between looks (that would track a moving unit's terrain without
  seeing it).
- **Which units count as "on the ground"** — serves: everything whose DCS category puts it on the
  surface — vehicles, infantry, statics/structures, **ships** (on the water, AGL 0 at sea level);
  would not: a category list that leaves ships or statics on the old flat model. Helicopters landed or
  hovering a few metres up are category "air" but are on the ground in every way the pilot cares
  about (question below).
- **Slant vs horizontal range** — the old model treated slant range as ground range; the new one
  should not reintroduce that anywhere a range is reported.
- **Who else reads the believed altitude** — the cockpit-mask check currently works *because* target
  and ownship share the same fake altitude (the error cancels). With a real ground height the mask
  will start using the real depression — e.g. a unit under the nose becomes hidden by the airframe.
  That is more correct, but it is a behaviour change the pilot can notice, and should be planned, not
  discovered.
- **The `remembered_target_alt_m` stopgap** (just merged) — serves: retired for ground contacts once
  this lands, so there is one source of a ground unit's height; would not: two coexisting answers to
  "how high is this unit" for the sight and for guidance.

### Findings

1. **A depression error as large as the bearing error places shallow targets kilometres off — worse
   than today in most of the Mi-24 envelope.** — lens: World truth / The envelope
   - Assumption: "depression ± σ, similar angular error" to bearing (3°), range then follows from the
     ray meeting the ground.
   - In the sim: ground position along the line of sight from a depression error σ is roughly
     R²·σ/h (R range, h height above the unit). Today's range error is 0.17·R. The two are equal at
     **R ≈ 3×h** (depression ≈ 18°). Every look shallower than that — which is nearly every look an
     Mi-24 makes at 50–800 m AGL and 2–6 km — gets **worse**, not better:

     | geometry | today (1σ, 17%) | ray, 3° depression σ | ray σ needed to match today |
     |---|---|---|---|
     | 300 m AGL, 1 km | 170 m | 175 m | 3.0° |
     | 300 m AGL, 3 km | 510 m | 1.6 km | 1.0° |
     | 420 m AGL, 5.3 km (sortie run 2) | 900 m | 3.5 km | 0.8° |
     | 300 m AGL, 5 km | 850 m | 4.4 km | 0.6° |
     | 50 m AGL, 3 km | 510 m | ray above horizon on a 1σ draw | 0.16° |

     The error is also lopsided: a ray nudged toward the horizon goes long by far more than one nudged
     down goes short, so the believed point is biased **long**.
   - The pilot would see: reports that are wildly long or short at ordinary attack distances; the
     sight sent to the bearing-line search nearly every run; guidance leading him past or short of the
     unit. E2/E3/E4 broken.
   - Grounded in: plain geometry, the sortie-2 numbers (§4: bearing good, ~700 m short at 4.7–5.7 km,
     ~420 m too high), and the operating-envelope memory. The user's sentence *"the likely elevation
     error would be in the same range as the azimuth angular error"* reads either as an angle (3°) or
     as ground error of similar size along and across — the two give completely different behaviour.
   - Suggests: specify the error by what the pilot experiences (how far off on the ground, by range,
     optic and looks) and derive the depression σ from that, or keep a ground-range error and use the
     unit's ground height only for altitude. Which one is the user's call (Q1).

2. **The altitude half is what failed in the sortie; the range half is the weaker case.** — lens:
   Purpose
   - In sortie run 2, with the altitude corrected, the 700 m-short point would have put the sight
     ~5° off at the start of the run — at the edge of the wide field, and inside what the bearing-line
     search covers. The +420 m altitude error, not the range, is what swung the aim away.
   - Suggests: AGL 0 from unit data is unambiguous and should land first; "range not guessed" earns
     its place only if it meets E3 (no worse than today). If it cannot, the user should know before
     the trade is made, not after a sortie.

3. **A noise-free direction plus the true ground height would be the true position.** — lens:
   Bounded knowledge
   - The ownship-relative channel is deliberately exact while looking
     (`RELATIVE_DIRECTION_SIGMA_DEG = 0`, user §20, 2026-10-14). If belief were built from that exact
     direction and the unit's own height, belief would land on truth — the "precise is not
     omniscient" floor (per-object systematic bias) would vanish.
   - Suggests: the depression feeding belief is the *stated, remembered* direction with its own
     error and its own never-averaging bias, kept separate from the exact relative channel used for
     tracking — the two-mechanisms distinction the project already holds. E7.
   - Unit height itself is not a leak: user, 2026-10-14, *"unit data has elevation"*, and an observer
     sees a unit standing on the ground. It stays a leak-free fact only if it is read with a look.

4. **Association gating was tuned to the flat model; the new error shape is long and thin along the
   line of sight.** — lens: Crew sense
   - Vignette: two BTR groups on the same bearing, 3 km and 4.5 km, helicopter at 150 m AGL. With a
     long thin ellipse each look of either group can fall within the other's gate → one contact
     jumping between them, and the sight sent to the wrong group. The converse: a gate too tight for
     the new shape splits one group into two, and Petrovich calls the same unit "new contact" twice.
   - The pilot would see: duplicate callouts, or one report covering two threats. E5.
   - Suggests: the plan states what the gate becomes and checks both directions (one unit re-seen,
     two units on one bearing).

5. **Low pop-up and valley geometry is where the ray model degenerates — and it is ATGM geometry.**
   — lens: The non-obvious case
   - Vignette: helicopter in a valley at 50 m AGL, SAM on a ridge 200 m above it at 3 km. True
     elevation is *up* (+3.8°); the ray meets the unit's height above the aircraft. A small error
     either way is fine here; but the same helicopter looking at a unit on flat ground at 3 km has a
     depression of 0.95°, and a 1σ draw at 3° points above the horizon — no intersection at all.
   - Suggests: the plan defines the no-intersection behaviour explicitly, and the bearing-line search
     remains the sight's answer; reports still need a sane range.

### Questions for the user

- **Q1** — At a typical run geometry (say 300 m AGL, 4 km), how far off may Petrovich's first
  naked-eye position be along the line of sight? Today it is ~±700 m; a 3° depression error would be
  ~±2.8 km. Did "same range as the azimuth error" mean the angle, or the ground error?
- **Q2** — If the perceived direction points level or above the horizon (low hover, unit above you),
  should he fall back to a range estimate as today?
- **Q3** — Ships: same rule — on the surface, at sea level?
- **Q4** — A helicopter landed or hovering a few metres up: on the ground (ground rule) or air
  (unchanged)?
- **Q5** — Air contacts keep today's flat model, including its believed altitude = ownship altitude
  at the look — accepted for now?

## Plan check — 2026-10-30

**Verdict:** ALIGNED

All five goal-check questions were answered in `explore-notes.md` before Architect wrote the plan,
and each answer is traced below next to the expectation it serves.

| expectation | stage | status |
|---|---|---|
| E1 (never above helicopter/in sky) | 2 | met — `surface_alt_m` from the look's cluster centroid, `implied_position` at that height |
| E2 (sight acquires, says "Tracking.") | 2+3, sight_head unchanged | met — altitude fixed first (F2), range fused (F1); bearing-line search kept as fallback |
| E3 (range no worse than today, firms up) | 3 | met — inverse-distance fusion proven (Monte Carlo) never worse than cue A, tightens with closing/looks; test asserts RMS ≤ 1.05×today |
| E4 (guidance lands on the real unit) | 2 (altitude), bearing untouched | met — bearing was already correct per sortie log; only depth was wrong, and that's what Stages 2–3 fix |
| E5 (one contact stays one, two stay two) | 4 | met — explicit scenario tests both directions; "stop and report" rather than silently retune if they fail |
| E6 (air contacts unchanged) | Decision 4 | met — flat model, unchanged, explicit test control point |
| E7 (not omniscient) | 3, Decision 2 | met — depression perturbed in its own hash domain, grep-pinned away from `RelativeDirection`; convergence test checks it lands on a systematic offset, not truth |

| open assumption (goal check) | plan | status |
|---|---|---|
| depression error size, as ground distance not angle | Stage 3, `DEPRESSION_SIGMA_DEG=3.0` reconciled through inverse-distance fusion to ~661–680 m at 300 m/4 km | met — matches explore Q1's "~700 m sounds sensible" |
| no-intersection fallback (level/above-horizon ray) | Stage 3: cue B absent ⇒ cue A alone | met — matches explore Q2 (size/terrain cue already is cue A) |
| cluster height | Stage 2: `cluster.centroid_alt_m`, members' own mean | met, with a note below |
| height read only at a look | Stage 2, explicit | met |
| which units are "on the ground" | Stage 1 domain rule + Stage 5 helicopters | met — vehicles/infantry/statics/ships/landed-or-low-hover heli, matching the goal check's list exactly |
| slant vs horizontal conflation | Decision 3 | met — slant stays the *reported* convention (unchanged, normal), horizontal used internally; the conflation removed from projection, not reintroduced in reporting |
| cockpit-mask readers | dedicated section, tested, on the Stage 6 card | met — named as an intended, felt behaviour change rather than a side effect discovered later |
| `remembered_target_alt_m` stopgap | Decision 5 | met — narrowed to ground contacts only, air path kept |

### Findings

1. **Cluster height is a single mean per cluster, not "each roughly where it stands."** — lens: World truth
   - Assumption: the goal check's wording suggested per-member height might matter for a group spread
     over a slope; the plan uses one centroid height for the whole cluster.
   - In the sim: a `Contact` already represents a whole cluster as one point (one bearing, one
     range) in the existing model — this is not a new compromise BL-B104 introduces, it is the
     existing one-point-per-group representation extended to altitude the same way it already
     applies to position.
   - The pilot would see: no difference from today's granularity — a reported group is already one
     point, now that point also has a real height instead of the ownship's.
   - Grounded in: `plan.md` Affected Modules, `naked_eye_source.py`'s existing clustering.
   - Suggests: not a misalignment, noted so a future per-unit-height want (e.g. a scattered group on
     a ridge where units differ by tens of metres) is a deliberate decision later rather than a
     rediscovery that this already happened.

2. **`DEPRESSION_SIGMA_DEG = 3.0` and `HELI_SURFACE_AGL_MAX_M = 10` both serve the stated intent, not
   just a plausible-sounding default.** — lens: Purpose
   - 3.0° is not applied naively (which the goal check's Finding 1 showed would be worse than today
     at shallow geometry) — it is fused in inverse distance specifically so the useless cue at
     shallow angles gets down-weighted, and the plan's own table shows the fused output landing at
     the user's confirmed ~700 m, not at the naively-computed multi-kilometre error. 10 m matches the
     user's own words, "a few metres up," as a tunable judgement call, not a guess.
   - Suggests: nothing — this is the goal check's hardest finding (F1) closed correctly, called out
     because the dispatch asked specifically whether these defaults serve intent.

### Questions for the user

None outstanding — all five goal-check questions (Q1–Q5) were already settled in `explore-notes.md`
before this plan was written, and the plan traces to each answer rather than re-deciding it.

## Plan check — 2026-10-30 (amendment: Stage 8 + Stage 7 turn leg)

Scope: only the amendment (`plan.md` lines 433–730), against the user's verbatim decisions it
cites — explore-notes.md's "E5 fold on a closing run" (growth rule) and "Scenario mock flights"
(manoeuvre). This amendment is not yet implemented (`implementation.md` still describes the
pre-review Stage 7); checked as a plan only.

**Verdict:** ALIGNED

| expectation (user's own words) | stage | status |
|---|---|---|
| "not observed moving -> tiny growth of position uncertainty" | 8 | met — `motion is None` or `"stopped"` both return `UNOBSERVED_MOTION_GROWTH_RATE_MPS` (0.3 m/s) |
| "observed moving -> uncertainty grow at movement speed" | 8 | met — `motion.state == "moving"` returns `plausible_speed_mps(profile.op_class)`; no measured per-contact speed exists yet, so class table stands in, matching the plan's own "unless a believed speed exists to use instead" |
| "most typical case is units being stationary" (None treated same as stopped) | 8 | met — explicit design choice, called out against the narrower `bounded-fold-displacement` precedent that did *not* fold `None` in |
| installation components (SA-3 etc.) stay immobile | 8 | met, and correctly ordered first — checked before the motion/domain gate, so `0.0` can't be overridden by the new tiny rate |
| air contacts stay bit-identical (E6) | 8 | met — gated on `Contact.on_surface`, not `Contact.motion`, with the reasoning spelled out for why `motion` alone would have been wrong (an air contact can carry `motion.state == "stopped"` too) |
| E5 fold itself (two groups stay two) actually fixed, not just the growth rate changed | 8 | **not yet verified** — stage says so itself: an order-of-magnitude argument (340 m needed vs. ≈19 min unseen at 0.3 m/s vs. ≈42 s at the old 8 m/s rate), explicitly not a substitute for running the restored Stage 7 scenario; if it still folds, the plan correctly names this as Stage 4's own stop-and-report case, not something to retune around |
| "Add turn to the test scenario" | 7 amendment | met — new `Turn` leg kind, scenario 3 rebuilt as a closing run with a turn onto the groups' bearing |
| "Simple mock flights that still contain some aircraft manoeuvre" (plural) | 7 amendment | **partially met** — scenario 3 (closing run) and scenario 1 (Run 1, gets a `Turn` before the `Descend`) both get real manoeuvre; scenario 2 (shallow approach) is left untouched and stays a pure `Level` leg, same shape Finding 2 flagged |

### Findings

1. **Scenario 2 stays manoeuvre-free; the amendment satisfies review.md's own bar for Finding 2,
   not the user's plural wording as fully as it could.** — lens: Purpose
   - Assumption: review.md's Required Fix for Finding 2 accepted "add a leg with real
     lateral/attitude change ... to at least one scenario" as sufficient — a bar the amendment
     clears twice over (scenarios 1 and 3). The user's own sentence was *"Simple mock flights that
     still contain some aircraft manoeuvre"* — plural *flights* — which review.md's Finding 2
     originally read as applying to each of the two flagged scenarios (2 and 3), not one of them.
   - In the sim: this is test scaffolding, not something the pilot ever sees — it affects only
     whether the regression suite exercises a believable flight, not any in-cockpit behaviour. So
     the stakes are "does this test suite catch what it's meant to", not a player-facing miss.
   - Suggests: not a blocker, since it meets the review's own accepted resolution and the plan is
     explicit about which scenario was chosen and why (Run 1's existing descent was the natural
     fit). Worth a one-line note to the user or Architect that scenario 2 remains pure `Level`,
     in case "simple mock flights" was meant more broadly than review.md's bar allowed — a quick
     confirmation avoids relitigating this after Stage 7 ships a second time.

2. **Stage 8's fix for the E5 fold is argued, not yet demonstrated, and the plan is honest about
   that rather than overclaiming "fixed."** — lens: World truth
   - In the sim: the worked numbers (340 m needed from growth alone; ≈42 s at the old rate vs.
     ≈19 min at the new one) are a single-look-formula estimate, explicitly flagged as not
     accounting for the near contact's real fused covariance or the real elapsed unseen time the
     restored scenario will produce.
   - The pilot would see: if the argument doesn't hold once the real scenario runs, exactly the
     E5 violation goal-aligner's Finding 4 and review.md's Finding 1 already described — two groups
     folding into one mid-run.
   - Grounded in: plan.md's own "Does motion-aware growth alone fix review.md Finding 1's real
     fold?" section, which states the follow-up condition itself.
   - Suggests: nothing additional — the plan already names the next check (run the restored
     scenario; stop-and-report if it still folds) and the right owner (Implementer/Reviewer, not
     a retune). Flagged here only so this check doesn't get skipped once Stage 7's `Turn` leg is
     in place and the temptation is to call Stage 8 "done" off the arithmetic alone.

### Questions for the user

- Is leaving scenario 2 (shallow approach) as a pure `Level` leg acceptable, or did "simple mock
  flights that still contain some aircraft manoeuvre" mean every scenario should have one? (Finding 1
  above — not a blocker either way, since review.md's own bar is met.)
