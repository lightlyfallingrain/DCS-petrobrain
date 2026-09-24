# Precise position belief

### Goal

Give each contact a **precise believed position carrying its own explicit, anisotropic uncertainty**,
produced by a perception-side error model that replaces the reporting quantisation currently doing
that job — so belief stores a coordinate, refines it across looks, and reporting keeps saying
"two o'clock, three kilometres."

---

### The diagnosis, verified

Confirmed at source, and worse than the brief states in two ways.

**One mechanism, two questions.** `perception/naked_eye_source.py` computes the true bearing/range to
a cluster centroid (`_build_observation`, lines ~802-807) and then calls `_quantise_bearing` (snap to
the nearest of 12 `OP_A*H` clock hours) and `_quantise_range_m` before writing them onto the
`Observation`. `belief/association_over_time.implied_position` reprojects exactly those two numbers
into `Contact.last_position`. So the stored coordinate is the clock-and-bucket report, reprojected.

**Two things I did not expect, both load-bearing:**

1. **`_quantise_range_m` returns the bucket's *upper bound*, not its midpoint.** Every naked-eye
   range is therefore biased *long*, by up to a full bucket width — 500 m at 3 km, 1000 m at 6 km.
   Today's belief is not merely coarse, it is systematically wrong in one direction. Any claim that
   the current model is "conservative" is false; it is biased.

2. **The anisotropy points the wrong way.** `_naked_eye_uncertainty_m` builds
   `hypot(R·sin15°, bucket_width)`. At 3 km that is `hypot(776, 500)`: the model says Petrovich knows
   the *range* better than the *bearing*. Physically it is the reverse and not marginally — a human
   points at a thing far better than he estimates its distance. The error model is inverted.

   | range | today cross-range (R·sin15°) | today down-range (bucket width) | bucket width as % of range |
   |---|---|---|---|
   | 500 m | 129 m | 100 m | 20% |
   | 1000 m | 259 m | 100 m | 10% |
   | 3000 m | 776 m | 500 m | 17% |
   | 5000 m | 1294 m | 500 m | 10% |
   | 8000 m | 2071 m | 1000 m | 12% |

**A second channel, already precise and already exact.** `perception/hybrid_source.py` does *not*
quantise: it writes `result.bearing_deg`/`result.range_m` straight from
`perception.association.associate`, which computes them from the matched world object's true `x`/`z`.
The scope/hybrid channel therefore already hands belief a **truth-exact** position, budgeted only by
`SCOPE_UNCERTAINTY_M = 300.0`, a declared placeholder. This is today's real omniscience hole, and it
is the strongest evidence for the design below: precision without an error model is exactly the
failure mode to avoid, and it is already in the tree on the channel the user actually flies with.

**Belief also re-implements the channel's vocabulary.** `association_over_time.py` carries its own
literal copy of `_RANGE_BUCKETS_M` (24 entries) and `CLOCK_BUCKET_DEG`, explicitly "kept as an
independent literal copy rather than importing that module". Belief currently *infers* a perception
channel's error from a duplicated transcript of that channel's internals. That is a boundary
weakness, not just duplication — and removing it is how this change *strengthens*
`belief/percept.py`'s rule rather than eroding it.

**Reporting is already separate and already correct.** `belief/enrichment.relative_geometry`
recomputes true bearing, `_clock_position` and range from *current* ownship on every call and is
documented as never cached. No change of form is required there (see Stage 5's one small tidy).

### The precedents, read

- `plans/group-detectability/` — `LOWRES_ANGULAR_RADIUS_RAD` answered both *resolution* ("can the eye
  register a mark") and *salience* ("would a lone mark be noticed"); the fix split it into two named
  constants with independent derivations (`RESOLUTION_ANGULAR_RADIUS_RAD = 0.00128`, an admitted
  upper bound). Same shape as here: one number, two questions, split by naming both.
- `association_over_time.py`'s own docstring, Stage 3b-i rev.2 — the association gate was re-pointed
  at `perception.clustering`'s acuity ellipse and **reverted**, because the gate budgeted an
  *acuity*-scale radius (~1-7 m) against a *quantised* report that jittered by a full clock bucket
  (~300-650 m): a ~700:1 mismatch, one `xfail`ed duplicate-contact regression.

  **This plan must not look like re-committing that mistake, and the distinction is precise.** The
  reverted error was not "used acuity" — it was *budgeting one error source against a different
  one*: the thing that jittered (bucket requantisation) was not the thing that was budgeted (optical
  resolving power). Here, the jitter source is deleted in the same stage as the budget changes, and
  the budget is set by the channel's own declared estimation error rather than by anything from
  `perception.clustering`. **The gate and the cluster predicate still do not share a formula, a
  constant, or an import.** Stage 3 is where this is either right or wrong, and it is flagged as the
  regression-carrying stage.

---

### Affected Modules / Files

- `body-layer/src/perception/source.py` — new frozen `PositionUncertainty` (σ cross-range, σ
  down-range, in metres, at the observation's own observer position) plus a
  `position_uncertainty: PositionUncertainty | None` field on `Observation`. Perceived metadata,
  identical footing to `count_bucket`/`apparent_motion`/`classification_level` — a channel's own
  honest statement about its own report, never a truth field.
- `body-layer/src/perception/estimation.py` — **new.** The error model and the perturbation, one
  module, no `belief` import. Holds the fractional-range constant, the bearing-sigma constant, the
  per-observation deterministic draw, and the per-object systematic bias. Sole home for "how wrong is
  a look".
- `body-layer/src/perception/naked_eye_source.py` — `_quantise_bearing`/`_quantise_range_m` deleted
  from the emission path (Stage 2); `_build_observation` emits a perturbed estimate plus its
  `PositionUncertainty`. `_RANGE_BUCKETS_M`/`_CLOCK_BUCKET_NAMES` retained only if still needed for
  `count_bucket`/trace text — otherwise deleted.
- `body-layer/src/perception/hybrid_source.py` — same treatment; stops emitting truth-exact geometry
  (subject to Decision 4).
- `body-layer/src/belief/percept.py` — carries `position_uncertainty` through unchanged. The
  projection's field list is the enforcement point and must be extended deliberately, with the
  docstring stating why this field is perceived metadata.
- `body-layer/src/belief/association_over_time.py` — **loses `_RANGE_BUCKETS_M`,
  `_build_bucket_widths_m`, `_range_bucket_width_m`, `_naked_eye_uncertainty_m`,
  `_HALF_CLOCK_BUCKET_RAD`, and `SCOPE_UNCERTAINTY_M`.** `uncertainty_radius_m` reads the percept's
  declared uncertainty. `passes_gate` becomes a 2D (Mahalanobis-style) test on summed covariances.
- `body-layer/src/belief/position_belief.py` — **new.** The fused estimate: a `PositionEstimate`
  (mean x/z + 2x2 covariance + `as_of_sim`), its fold rule, and its scalar reductions
  (`radius_m()`, `bearing_uncertainty_deg(observer)`) for existing callers. Kept out of
  `contacts.py` to hold the diff on that already-crowded file small.
- `body-layer/src/belief/contacts.py` — `Contact.last_position_uncertainty_m` becomes a derived
  read-only property over a new `position: PositionEstimate`; `record()` folds instead of overwrites.
- `body-layer/src/belief/enrichment.py` — `_terrain_aware_world_position` must reproject the *fused*
  estimate, not the last contributing percept (see Risks). `_clock_position`'s literal `30.0` becomes
  the imported reporting constant.
- `body-layer/src/belief/optic_policy.py` — `look_target_for` passes a real
  `bearing_uncertainty_deg` from the contact's estimate instead of the `CLOCK_BUCKET_DEG / 2.0`
  default. `CLOCK_BUCKET_DEG`'s home moves (below).
- **`CLOCK_BUCKET_DEG` moves out of `association_over_time.py`** into the reporting side
  (`belief/enrichment.py`, next to `_clock_position`, which already duplicates it as a literal
  `30.0`). It is a *speech vocabulary* constant and belongs with rendering; leaving it in the gate
  module is the original conflation in miniature.
- Tests: `test_association_over_time.py`, `test_contacts.py`, `test_naked_eye_source.py`,
  `test_hybrid_source.py`, `test_enrichment.py`, `test_optic_policy.py`, plus new
  `test_estimation.py` / `test_position_belief.py`.

---

### The model

**A look yields an estimate with an elongated error ellipse, oriented along the line of sight.**

```
sigma_down_m  = RANGE_FRACTIONAL_SIGMA * true_range_m          # along the line of sight
sigma_cross_m = radians(BEARING_SIGMA_DEG) * true_range_m      # perpendicular to it
```

Both scale with range, which is what makes the model behave sensibly at every distance without a
table.

**Where the down-range figure comes from — derived, not invented.** ED's own `OP_D*` ladder *is* a
statement about range-estimation ability: it steps 100 m to 1 km, then 500 m, then 1000 m. As a
fraction of range that is 10-33%, clustered near ~15-20%. Crucially, the ladder **coarsens as range
grows**, which is the signature of an estimation error that grows with range — the vocabulary
carries information about the underlying ability. Take `RANGE_FRACTIONAL_SIGMA = 0.17`.

**Why the clock ladder does *not* get the same treatment** — this is the crux of the whole change.
The clock is a uniform 30° at every range. No perceptual mechanism produces a constant 30° bearing
error at all distances; 30° is there because there are twelve hours on a clock face. The range ladder
encodes ability; the clock ladder encodes only the word count of the vocabulary. That asymmetry is
the entire argument for keeping the range figure and discarding the bearing one.

**The bearing figure is a declared judgment constant, and I am saying so rather than dressing it up.**
It is bounded on both sides by measured things — it cannot be below the resolution floor
(`RESOLUTION_ANGULAR_RADIUS_RAD` = 0.00128 rad = 0.073°: he cannot localise finer than he can
resolve) and it is plainly far below the 15° half-bucket. Deriving it from apparent angular size
alone gives ~2.3 mrad (7 m at 3 km) — which is *exactly the ~100x-too-tight magnitude that Stage
3b-i rev.2 was reverted for*, and taking it would repeat that error. Pointing precision from a
vibrating cockpit is not acuity. **`BEARING_SIGMA_DEG = 3.0`** is proposed (105 m cross-range at
3 km), with the honest note that the load-bearing claim is the *ratio* — cross-range error is several
times smaller than down-range error, where today's model has it the other way round — not the exact
value. See Decision 3.

**Precision is not omniscience, made structural.** Removing the bucket without replacing it hands
belief `bearing_deg`/`range_m` computed from ground truth, i.e. an exact answer. So each look's
reported geometry is **perturbed** by a draw from its own ellipse, inside `perception/`:

- **Per-look noise**, drawn deterministically from a hash of `Observation.id` (reproducible in tests,
  no global RNG, no replay divergence). This is what averages down across looks.
- **A per-object systematic bias**, drawn once from a hash of the object id, scaled to
  `SYSTEMATIC_BIAS_FRACTION` (propose 0.4) of the single-look sigma, and *never* re-drawn. This never
  averages out, so a heavily-observed contact converges to a *wrong* position with small stated
  uncertainty — which is the correct behaviour and is what makes "precise and wrong" a structural
  property rather than an intention. The object id never leaves `perception/`; only the perturbed
  numbers and the declared sigmas cross.

The uncertainty floor follows for free: fused sigma is floored at `SYSTEMATIC_BIAS_FRACTION ×
single-look sigma`, so the estimate can never claim more precision than the bias it can never see.

**Refinement is covariance fusion, not a running mean.** Each look contributes an elongated ellipse
oriented along *that look's* line of sight. When ownship moves, successive lines of sight cross, and
the intersection of two long thin ellipses is small in both axes — real triangulation, which is
exactly what a crew does ("we had him at two o'clock; from here he's at eleven — he's *there*"). A
scalar running mean cannot express this and would throw away the main source of improvement. The
update is the standard information form,

```
I_new = I_old + R_look^-1 ,   I·mu = I_old·mu_old + R_look^-1 · z_look
```

on 2x2 symmetric matrices: **three floats of state per contact plus two, ~40 lines of arithmetic, no
library.** That is the honest cost, and it is small. Between updates the covariance is *inflated* by
elapsed motion (reusing `GATE_GROWTH_RATE_MPS` as the process-noise rate) so a stale contact's
ellipse grows — the same physical statement `spatial_gate_radius_m` already makes with its elapsed
term, now held on the contact instead of recomputed at every gate call.

This also *supersedes* nothing in `belief/decay.py`: I checked, and `POSITION_HALF_LIFE_S` (30 s),
`LOST_THRESHOLD_S` (120 s) and `OBSERVED_WINDOW_S` govern *reporting confidence and lifecycle*
(`position_confidence`, `certainty_of`), not metric error. They stay exactly as they are. The one
thing to watch is that two decay-shaped notions now coexist — `position_confidence` (0-1, how stale)
and the covariance (metres, how wrong) — and the plan deliberately does **not** unify them: staleness
and metric error are different questions, and collapsing them is this exact bug in a new costume.

---

### Implementation Plan

**Stage 1 — declare the uncertainty at the source; no behaviour change.**
Add `PositionUncertainty` and the `Observation`/`Percept` field. Each source declares *exactly
today's* figures (naked eye: `R·sin15°` cross, bucket width down; hybrid: 300 m isotropic).
`uncertainty_radius_m` reads the declared value and falls back to the old derivation when `None`.
Delete belief's duplicated bucket table and clock constant; move `CLOCK_BUCKET_DEG` to the reporting
side. *Verify:* the whole existing suite passes untouched, and a test asserts gate radii are
bit-identical before and after for a representative range ladder.

**Stage 2 — replace quantisation with the error model.**
Add `perception/estimation.py`; delete `_quantise_bearing`/`_quantise_range_m` from the emission
path; sources emit perturbed geometry and the real sigmas. *Verify:* new `test_estimation.py` pins
determinism (same `Observation.id` → same offset), pins that the mean offset over many ids is ~0
(unbiased, unlike today's upper-bound snap), and pins the sigma ratio. A regression test asserts a
stationary contact observed repeatedly does not spawn duplicates — the pre-existing
`test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` is the natural home, and its
premise changes from "requantisation jitter" to "per-look noise".

**Stage 3 — the 2D gate. THIS STAGE CARRIES THE REGRESSION RISK.**
`passes_gate` compares the offset between the look's estimate and the contact's mean against the
*sum* of the two covariances plus the elapsed-motion inflation — the same both-sides-budgeted shape
as today, promoted from a scalar to 2x2. Keep the threshold generous (propose 3σ) and keep
`uncertainty_radius_m` alive as the scalar reduction for any caller that still wants one. *Verify:*
the whole duplicate-contact family of tests, and a new one pinning that a contact observed from two
crossing bearings still gates correctly (the case a scalar radius handles worst). **Do not merge
Stage 3 without a live sortie** — the duplicate-contact runaway this gate caused on 2026-09-09 was
found in flight, not in tests.

**Stage 4 — fusion on `Contact`.**
`belief/position_belief.py`, `Contact.position`, `record()` folds. `last_position` becomes the fused
mean; `last_position_uncertainty_m` becomes a derived property so every existing reader compiles
unchanged. Fix `enrichment._terrain_aware_world_position` to reproject the fused estimate. *Verify:*
repeated looks from a moving observer converge (uncertainty strictly decreases), converge to
`truth + systematic_bias` and not to truth, and never below the floor.

**Stage 5 — spend it downstream.**
`optic_policy.look_target_for` passes the contact's real `bearing_uncertainty_deg`. At 3 km with
`BEARING_SIGMA_DEG = 3`, a 3σ envelope is ±9°, which is `N = ceil(18/8.5) = 3` steps rather than 4 —
and a well-observed contact collapses to `N = 1`, a stare. The hook already exists: Stage 3b's D1
explicitly says `bearing_uncertainty_deg` "can start passing it whenever there is a measured number
to pass". *Verify:* `test_optic_policy.py`'s existing sweep tests, plus one asserting a refined
contact gets a single-step look.

---

### Risks & Unknowns

- **Stage 3 is the one that can hurt.** A gate that is too tight produces the duplicate-contact
  runaway documented in `plans/classification-refinement/debug.md`: one missed match becomes a
  permanent one-new-contact-per-poll cascade, because the duplicate then makes every later percept
  ambiguous. The total gate budget at 3 km moves from `hypot(776, 500) = 924 m` to roughly
  `hypot(105, 510)` per side — smaller overall, but the thing that was jittering (requantisation, up
  to a full bucket) is deleted in the same change. That reasoning is sound and it is also exactly the
  reasoning that was wrong last time. Treat a live sortie as the gate.
- **`BEARING_SIGMA_DEG` is not measured.** Unlike the recognition tiers, it cannot be: it is the
  *crewman's* pointing precision, not anything DCS reports. No investigator pass can resolve it, and
  no test can validate it — only the pilot's judgement of whether Petrovich's callouts point at the
  right place.
- **What tests would not catch, in order of how much it would cost:**
  1. **Refinement never reaching the reports.** `enrichment._terrain_aware_world_position` walks back
     to the *most recent contributing percept* and reprojects that. If Stage 4 lands without fixing
     it, every semantic fact and every terrain-aware position silently keeps using one raw look while
     the fused estimate improves invisibly beside it. Unit tests on the fusion would all pass.
  2. **`WorldEnrichmentCache` keying.** It invalidates on `Contact.last_position` structural equality.
     Post-Stage-2 the mean moves slightly on *every* look (no bucket to snap to), so a cache that
     previously hit most polls now misses nearly always — a silent per-poll cost increase (an
     elevation-grid walk per contact), visible only as latency in flight.
  3. **A plausible-but-wrong position is harder to disbelieve than a coarse one.** "Two o'clock,
     three kilometres" derived from a confident, precise, systematically-biased estimate reads exactly
     like a correct one. Today's coarseness is at least legible as coarse.
  4. **Perturbation changes what the pilot hears.** Ranges stop snapping to bucket bounds and start
     being wrong by ~17% in both directions. At 3 km that is ±510 m, which mostly survives rounding to
     "three kilometres" — but it will occasionally flip the spoken kilometre, and `watch-reporting`'s
     kilometre-crossing trigger will see it.
  5. **Replay/trace divergence.** Any golden-file test or `detection_trace.py` output containing
     quantised bearings/ranges changes wholesale in Stage 2.
- **Not investigated, deliberately:** nothing here depends on an unverified DCS internal. The `OP_D*`
  and `OP_A*H` vocabularies are already in production use, and human estimation error is not a DCS
  fact. No investigator pass needed.

---

### What this unlocks

- **The binocular sweep stops sweeping a vocabulary.** `plans/binocular-optic/stage3b.md` sweeps ±15°
  *because the belief was bucketed* — D1 chose the clock bucket over `last_position_uncertainty_m`
  precisely because the latter was "a number nobody measured". After this change it is measured, and
  the sweep narrows to real uncertainty, collapsing to a stare for a well-observed contact. Fewer
  steps, faster identification.
- **`plans/watch-reporting/plan.md`'s LOS test gets a defensible lateral offset.** §4f-ii-a samples
  LOS at `±last_position_uncertainty_m` perpendicular to the sightline and says the uncertainty
  inheritance "is the part most likely to bite". Perpendicular is *exactly* the cross-range axis this
  model separates out — the offset becomes σ_cross (~100 m at 3 km) instead of a hypot that is
  dominated by a down-range term irrelevant to that test.
- **The kilometre trigger starts moving instead of stepping.** Decision 5 of that plan floors
  `range_m / 1000` — today that input jumps in 500 m steps, so crossings fire in bursts and cluster at
  bucket boundaries. A continuous position makes the trigger mean what it says.
- **Second-order effect:** this narrows BL-8. A contact's belief becomes a self-contained,
  serialisable value — mean, covariance, as-of time — rather than something reconstructible only by
  replaying the observation log, which is what `enrichment` does today. Persistence becomes a
  snapshot.

### BL-8, and what not to foreclose

The user's *"for important contacts a crew member would write them down on a kneeboard with pen
(→ mission memory), then that is used for future updates and reports"* is **the first concrete
requirement BL-8 has ever had**, and it is not this plan's to build. Record it as: *selected contacts
persist with their believed position across the sortie, and a written-down position participates in
later association and reporting.*

Two things this plan should avoid foreclosing, both cheap if done now and expensive later:

1. **`PositionEstimate` must be a plain serialisable value** (floats only; no live references into
   `ContactStore.observations`). Stage 4's move of authority from "replay the log" to "hold the
   estimate" is what makes a kneeboard entry possible at all — do not reintroduce a log dependency.
2. **The fold must accept an estimate from a non-percept origin** — a written-down position, or
   later a pilot's report — without special-casing. Keep the fold signature `(estimate, estimate) →
   estimate`, not `(contact, percept) → contact`. A pen mark is just another measurement with its own
   covariance.

---

### Decisions Requiring User Input

1. **Perturb, or state uncertainty without it?** Recommended: **perturb.** Without a perturbation the
   stored position is exact truth with a disclaimer attached, and the no-omniscience boundary becomes
   a comment rather than a mechanism. Against: it is the only part of this change that makes
   Petrovich measurably *less* accurate than today on the bearing axis, and it is deliberate noise in
   a system the user is still calibrating by ear.
2. **Does the scope/hybrid channel get the same treatment (Stage 2)?** Recommended: **yes.** It
   currently emits truth-exact geometry behind a 300 m placeholder — the largest omniscience hole in
   the tree. Against: it is the channel driving today's live behaviour, and changing it and the naked
   eye in the same sortie makes a regression hard to attribute. A defensible alternative is to split
   it into its own stage, flown separately.
3. **`BEARING_SIGMA_DEG = 3.0`** — a declared judgement constant that cannot be measured from DCS.
   The user is the only person on this project who has judged a bearing to a ground vehicle from a
   Mi-24 cockpit. If 3° feels wrong, say so now; the ratio matters more than the value, but the value
   sets the sweep width in Stage 5.
4. **2x2 covariance, or a scalar radius with a running mean?** Recommended: **covariance.** The
   anisotropy is roughly 5:1 and is the whole physical content of the model; triangulation from a
   moving observer is the main source of refinement and a scalar cannot express it. Against: it is
   the more "clever" of the two options, and the project's own heuristics prefer the debuggable one.
   Cost if we take it: three extra floats per contact and ~40 lines of arithmetic.
