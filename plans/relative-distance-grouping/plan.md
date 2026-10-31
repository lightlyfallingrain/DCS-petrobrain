# Relative-distance grouping — plan (`BL-B108`)

Architect pass 2026-10-31, on `feature/relative-distance-grouping` at `c2c3c6b0`. Inputs:
`explore-notes.md` (the user's own words; the specification), `alignment.md` (goal check,
CONCERNS, E1–E7 and findings 1–6, Q1–Q4 now answered). No DCS-internals claim is load-bearing
here (everything is in body-layer's own error model and belief code), so no investigator pass.

### Goal

When Petrovich decides whether two separately seen things are one group (in one look, or the thing
he saw before), he uses his **relative** judgement of distance, which is precise, not his
**absolute** range, which stays as poor as today. So two groups on one bearing at clearly different
distances become two contacts, and one group stays one contact through dwell, closing and orbiting.

### Effort / value, stated once

This is not a threshold change. The fold in `BL-B104`'s 1 s analysis comes from the error *model*:
today a look's along-line error is ~1.0σ redrawn **independently every look** plus a 0.4σ per-object
bias (`perception/estimation.py`), and belief fuses looks as independent (`position_belief.
fold_position`). A tight gate on that model splits one group into several (alignment finding 1).
A wide gate folds two groups into one (the bug). Only a **correlated** error, stable look to look,
shared between nearby things, decorrelating with geometry, gives both. That costs a perception-model
rewrite of the range draw, a correlated fusion/gate in belief, and rewritten pinned tests. The value
is what the pilot hears: two groups as two callouts, and no re-detection callout on an attack run or
an orbit. That value is the whole point of the feature, and nothing cheaper delivers it. The cheaper
designs considered are under Stage 2, with why each fails.

### The model in one picture

Along-line-of-sight (range) error of one look, as a fraction of `σ = RANGE_FRACTIONAL_SIGMA (0.17,
unchanged) × range × optic scale`:

```
e_range = σ · ( s · Z_view(bearing, ln R)          # stable, shared by everything in that part of the view
              + f · Z_near(bearing, ln R)          # stable, shared only by things at about the same distance
              + a · z_look(poll, optic) )          # redrawn every poll, shared within that poll
          s = sqrt(1 − f² − a²)
```

- **Z_view / Z_near** are deterministic, smooth, unit-variance noise fields over the **perceived
  look geometry** (world bearing from observer, log range). They are not keyed by object id. Same
  place, same view, so the same cues and the same estimate (user answer 2, E4). Z_view decorrelates
  over `RANGE_DECORRELATION_BEARING_DEG` of line-of-sight rotation, or a range ratio of
  `RANGE_DECORRELATION_RANGE_RATIO` (closing). This is what makes triangulation and closing improve
  the estimate (E5). Z_near decorrelates over a much smaller range ratio,
  `RANGE_NEAR_DECORRELATION_RANGE_RATIO`, so two things at 2.0 and 3.5 km have independent `f`
  terms while a 200 m line's members share theirs. Implement both as random-Fourier-feature fields
  (K ≈ 16–32 cosines, phases and frequencies from the existing `_deterministic_unit_gaussian_pair`
  hash idiom). Their autocorrelation is stationary and has a closed form (Gaussian kernel). Belief
  needs that closed form in Stage 2. Interpolated lattice noise does not have one.
- **Per optic class** (`unaided`, `binocular`, `sight_wide`, `sight_narrow`): each has its own
  field seeds, so a better optic is an **independent** look and fusion can genuinely improve on it
  (Q3). Sharing one field across optics would let belief infer Z exactly from two optics and
  recover truth. Fusing two fully correlated estimates of unequal σ extrapolates past both, which
  is omniscience by arithmetic. Range scale: unaided 1.0 (unchanged), **binocular 0.7 (new,
  Q3)**, sight 0.5 / 0.3 (unchanged).
- **What follows, at the defaults (f = a = 0.2, so s ≈ 0.96):**

| quantity | value | what the pilot gets |
|---|---|---|
| absolute σ, one naked-eye look | 0.17 R (±780 m at 4.6 km) | spoken range keeps today's error (E4) |
| look-to-look spread, same geometry | 0.2 σ ≈ 0.034 R | repeat looks give the same number (E4) |
| relative σ, two things at different distances in one look | √2·f·σ ≈ 0.048 R | "which is further" is easy (finding 1) |
| merge zone along the line of sight, 3σ | ≈ 0.144 R: ±350 m at 2.4 km, ±660 m at 4.6 km | the user's own ±400/±700 m proposal |
| merge zone across the line of sight, 3σ | ≈ 0.24 R (bearing error, unchanged) | so "near-circular" means within ~1.6:1, not a 3:1 ellipse |
| clear case, 1.5 km apart at ~3 km | ≈ 10σ of relative error apart | always two (E1) |
| ambiguous case, 2.0 vs 2.5 km | 500 m against a merge zone of ≈ 325 m (in one look) or a gate of ≈ 410 m (3σ, across looks) | **two by default**. It becomes one at `RANGE_RELATIVE_SHARE` ≈ 0.31 (in one look) or `RANGE_LOOK_SHARE` ≈ 0.3 (across looks). E6: adjustable, no verdict tested |

**Two judgements, two tunables, deliberately.** *"Which of these two is further?"* (one look) is
limited by `f`, the part not shared between things at different distances. *"Is this the thing I saw
before?"* (across looks, same geometry) is limited by `a`, the look-to-look spread, because under
the same-thing hypothesis both stable terms are shared. The two numbers coincide at the defaults by
choice. Both are the user's "only flights will tell" numbers.

Cue B, the depression cue from `surface_range_estimate` (BL-B104), takes the **same three-part
structure** with its own seed domain. Otherwise a per-look independent depression draw, which
dominates at altitude, would undo the stability for surface units at 300 m AGL and above. Bearing,
the cross-line error, is **out of scope and unchanged**: 3° per look plus the existing per-object
bias. That is why the across-axis is the wider one.

### Where grouping is decided: the four places, and what each does now

| place | question it answers | change | why |
|---|---|---|---|
| `perception/clustering.py` | can he see two things at all? | **none to the predicate.** Pin tests only | Q1: angular overlap still decides it (2026-09-18 rule stands). Already single-link, Q2 |
| `perception/group_salience.py` | do these dots read as one massed formation? | add an along-line check: a pair is cohesive only if \|ΔR\| ≤ `GROUP_COHESION_GAP_UNIT_WIDTHS`·mean size + 3·√2·f·σ(R̄) | today 10 unit widths of **angle** lets units ~1 km apart along the line count as one group at 4 km / 200 m AGL (alignment "which mechanisms") |
| `belief/association_over_time.py` gate (+ `contacts_plausibly_same`) | is this the thing I saw before? | correlated-difference Mahalanobis (Stage 2) | the fold itself. Finding 2 |
| `belief/groups.py` cohesion | do these contacts belong together? | **none to the formula.** It is already a top-down world gap (≤140 m backstop, ≤500 m caps), so already circular. Pin tests | its inputs become relatively precise under Stage 1–2, which is what was missing (finding 1) |

Within one look, salience compares **true** ranges against the modelled relative σ. That is a
declared modelling choice (finding 6 allows it within a look). Across looks, the gate compares
**only** perceived quantities: the remembered estimate, the new estimate, and the two look
geometries. It never uses a true range or ratio for something not currently in view.

### Affected Modules / Files

- `body-layer/tests/support/mock_flight_scenario.py`: default `poll_interval_s` 5.0 → 1.0.
- `body-layer/tests/test_bl_b104_scenario_mock_flights.py`: fix the two 1 s-brittle tests. The
  E1 fold scenario becomes a regression test.
- `body-layer/src/perception/estimation.py`: three-part range draw, fields, binocular scale, cue B
  restructure, a pure `stable_range_correlation(...)` for belief to import. The range half of
  `systematic_bias_m` is retired; its cross half stays.
- `body-layer/src/perception/source.py`: `PositionUncertainty` gains the look's stable along-line
  σ and optic class (perceived facts, so the no-omniscience boundary holds).
- `body-layer/src/perception/naked_eye_source.py`, `hybrid_source.py`: pass poll sequence and optic
  class into the draw. `bias_object_id` is no longer used for range.
- `body-layer/src/belief/position_belief.py`: `PositionEstimate` carries a look **anchor**. One
  helper, `correlated_innovation(estimate, look) -> (S, C)`, is used by both `fold_position`
  (Bar-Shalom–Campo fusion) and the gate. The floor is revised.
- `body-layer/src/belief/association_over_time.py`: `passes_gate` and `contacts_plausibly_same` use
  the helper.
- `body-layer/src/belief/contacts.py`: `record`/`from_percept` pass the anchor through, and so do
  the clamps.
- `body-layer/src/perception/group_salience.py`: along-line condition.
- `body-layer/src/mission_memory/admission.py`: admit at every identification level (Q4).
- `body-layer/config/defaults.toml`: regenerated.
- Tests: `test_estimation.py`, `test_position_belief.py`, `test_association_over_time.py`,
  `test_group_salience*.py`, `test_clustering.py`, `test_groups*.py`, mission-memory admission tests,
  and the new `test_relative_distance_scenarios.py`.
- `docs/STRUCTURE.md`: entries for estimation, position_belief, association_over_time and
  group_salience.

### Implementation Plan

**Stage 0: 1 s test flights (behaviour-neutral, its own commit).**
- `build_scenario_frames(..., poll_interval_s=1.0)`.
- `test_run2_shallow_approach_range_error_converges_and_bounded`: replace "end error ≤ first-poll
  error" (that compares against one lucky draw) with the model's own budget. Every observed poll's
  error ≤ 3σ_down declared for that look. Final error ≤ 3σ at the final range, which is
  structurally smaller because σ scales with range.
- `test_cockpit_mask_pitch_down_recovers_masked_forward_target`: the hard-coded
  `_MASK_ESTABLISHED_T_SIM = 115` falls before the true ~743 m mask edge (`AGL/tan 22°`), at 1 s
  as well as 5 s. Derive the window from geometry: the first poll whose **true** range is inside
  the edge by more than the believed-range 3σ at that range. Do not use a time constant.
- Add the E1 fold scenario (far group 4.6 km first alone, near group 2.4 km seconds later) as
  `xfail(strict=True)` against today's code. It becomes a plain pass at Stage 2.
- Run the whole scenario module and note its wall time (risk below).

**Stage 1: perception error model (`estimation.py`).** Mechanism plus tunables, per the picture
above.
- New tunables, all `status="judgement"`, `#needs-flight`, under `perception.estimation.`:
  - `RANGE_LOOK_SHARE` 0.2 (lo 0.0, hi 0.6)
  - `RANGE_RELATIVE_SHARE` 0.2 (lo 0.0, hi 0.6). Per-key bounds keep `f² + a² ≤ 0.72 < 1`, so the
    cross-key coupling cannot be violated (the X-T26 trap).
  - `RANGE_DECORRELATION_BEARING_DEG` 30 (lo 5, hi 120)
  - `RANGE_DECORRELATION_RANGE_RATIO` 1.5 (lo 1.1, hi 4.0)
  - `RANGE_NEAR_DECORRELATION_RANGE_RATIO` 1.15 (lo 1.02, hi 1.5)
  - `BINOCULAR_RANGE_SIGMA_SCALE` 0.7 (lo 0.1, hi 1.0)

  Each `#:` comment's first sentence says what the pilot notices (the rendered `defaults.toml`
  only carries the first sentence).
- `perturbed_bearing_range` / `surface_range_estimate`: the down component becomes the three-part
  draw. `z_look` is keyed by `(poll sequence, optic class)`, shared by every cluster in that poll.
  Bearing keeps its per-observation draw and its object bias, on separate hash domains from the
  range draw.
- `PositionUncertainty` gains `sigma_down_stable_m` (`s`- and `f`-parts combined) and
  `optic_class: str`.
- Export `stable_range_correlation(d_bearing_deg, range_ratio, same_optic) -> (rho_view, rho_near)`,
  the closed-form kernel of the two fields. It is the **only** place belief learns how errors
  correlate. It reads model parameters, never a realisation.
- Property tests, statistical over many seeds and geometries, not single pinned offsets:
  - absolute RMS ≈ 0.17 R (±10 %)
  - same-geometry repeat spread ≈ a·σ
  - two things in one look at ratio ≥ 1.5: difference RMS ≈ √2·f·σ
  - members 20 m apart: difference ≪ 20 m-scale
  - correlation falls to ≈ e⁻¹ at the stated rotation and range ratio
  - different optic: independent
  - smoothness: at 1 s, 60 m/s, the stable term moves < 0.02 σ per poll
  - cue B obeys the same structure
- `test_estimation.py`'s exact-offset pins are **rewritten**, not extended (escalation item 1).
- **Stages 1 and 2 are one batch.** Stage 1 alone makes belief over-confident: stable error, fused
  as independent, then floored. The scenario suite is expected green only after Stage 2.

**Stage 2: correlated fusion and gate (`position_belief.py`, `association_over_time.py`).**
- `PositionEstimate` gains `anchor`: observer (x, z), bearing and range to the estimate, optic
  class, and `sigma_down_stable_m` of the last look that fused into it. Founding sets it from the
  look. Every fold sets it to the new look.
- `correlated_innovation(estimate, look) -> (S, C)`:
  - `C` is the along-line cross-covariance between the estimate's stable error and the look's,
    `ρ · σ_stable,anchor · σ_stable,look`, along each side's own LOS unit vector. For the gate, ρ
    comes from `stable_range_correlation` evaluated on the **hypothesis** that the look is the
    contact: the bearing/range from the current observer to the contact's believed position,
    against the anchor's. For the fold (gate already passed), it is evaluated on the look's own
    geometry.
  - `S = P_est + P_look − C − Cᵀ`.
- **Gate**: `mahalanobis(S, Δ) ≤ GATE_SIGMA_THRESHOLD²`. Unchanged 3σ, and still both-sided
  (memory: never single-sided).
- **Fold**: Bar-Shalom–Campo, `x = x_est + (P_est − C) S⁻¹ Δ`, `P = P_est − (P_est − C) S⁻¹ (P_est
  − Cᵀ)`. This is the standard fusion of two estimates with known cross-correlation. Do not
  hand-roll a discount factor. The gate and the fold see the same `S` by construction, the same
  "can never silently disagree" property `percept_position_uncertainty` already gives the two.
- Floor (`_apply_floor`): the along-line floor becomes `ρ_view · s · σ_down` of the current look,
  so it binds only at the same geometry. The cross floor is unchanged (0.4, bearing out of scope).
- `contacts_plausibly_same`: the same helper, anchor against anchor.
- Worked check, numbers to reproduce in a test.
  - E1 fold case: contact founded at 4.6 km, near look at 2.4 km six seconds later, ownship ~300 m
    closer. Under the same-group hypothesis ρ_view ≈ 0.98, so S along ≈ (410 m)². The 2.2 km
    offset is about 5σ, so the look **is rejected** and a new contact is founded.
  - Straight-in reacquisition of one group after closing 4.6 → 2.4 km: ρ_view ≈ 0.07, so S along ≈
    (870 m)². The group's own offset passes.
- Rejected alternatives, recorded:
  - **(a) Change perception only, keep the independent fold.** The gate budgets the stable error
    twice, so it stays wide along the line and the fold persists.
  - **(b) Correlation in the gate only, with a trace floor in the fold.** After a 90° rotation the
    floor, taken from the latest look, pushes triangulation back up, and E5 fails.
  - **(c) Covariance Intersection.** Too conservative: it never tightens, even under triangulation.
- Approximation, stated: the estimate's correlation with a future look is taken against the
  **last** fused look only (one anchor), not the full history. The property tests below bound
  what that costs.
- Tests:
  - N same-geometry looks: mean → the stable-biased value, along σ never below `s·σ`.
  - 90° orbit at 3 km: along-original-LOS σ shrinks, no gate failure on any poll.
  - Straight-in 5 → 1 km at 1 s: per-poll mean jump ≤ the bound in `clamp_fold_displacement`
    (check that clamp still never binds on a single-group closing run). No new contact.
  - Different-optic look: fuses as independent.
  - The 9 `PositionEstimate(` construction sites carry the anchor. See Co-moving Fields.
- `precise-position-belief`'s convergence tests ("uncertainty strictly decreases", the 0.4σ floor)
  are **rewritten** (escalation item 1).

**Stage 3: within-look grouping (`group_salience.py`, pin `clustering.py` and `groups.py`).**
- `group_salience`:
  - Hoist each candidate's horizontal range in `_resolvable_terms`, beside the existing hoisted
    terms. That keeps the 5× win `BL-B40` measured.
  - Cohesive iff the existing angular test **and** `|R_a − R_b| ≤ GROUP_COHESION_GAP_UNIT_WIDTHS ·
    mean size_m + GATE_SIGMA_THRESHOLD · √2 · RANGE_RELATIVE_SHARE · σ_down(R̄, optic)`. No new
    constant: it is derived from Stage 1's tunables, so the in-one-look half of E6 is tuned where
    the error model is.
- Pin tests:
  - Clustering, Q1: two units 2.0 / 2.5 km on one bearing at 30 m AGL, overlapping, stay one blob.
  - Clustering, Q2: a column along the line of sight with overlapping neighbours is one cluster.
  - Clustering, E2: separable units 1.5 km apart in one look are two clusters.
  - `groups.py`, E2: two contacts 1.5 km apart along one LOS are never one `Group`.
  - `groups.py`, Q2: a 1 km column with 60 m gaps, seen at 3 km under the new model, is one
    `Group`.
  - `group_salience`: units 1 km apart along the LOS at 4 km / 200 m AGL are no longer mutually
    salient. The 200 m twelve-unit calibration line still is (the `group-detectability` dataset
    must not regress).

**Stage 4: mission memory keeps every group (Q4, E7).**
- `_maybe_write_entry_for_contact`: drop the `nameable` gate; keep the first-entry confidence gate.
  The first entry is written once confidence reaches the floor, at whatever level, presence included. The
  composition records the level and confidence it has, and an unknown-level contact writes an empty
  composition, which is already the total case.
- Material-change and resight rules are unchanged. Air defence is unchanged.
- `GROUP_ENTRY_CONFIDENCE_FLOOR` **stays** as the first-entry gate (user, 2026-10-31: *"keep the
  confidence floor"*). Only the `nameable` gate goes. A presence-only claim (0.3) is admitted after
  enough reinforcement to reach the floor; a class claim (0.6) on founding. Test both, plus that a
  single-glimpse presence contact gets no entry.
- Test: a presence-only stationary group goes lost under the nose (cockpit mask, 2 min) and the
  entry is still recallable.

**Stage 5: scenario suite at 1 s (E1–E7) and the test card.**
- New `tests/test_relative_distance_scenarios.py` on `mock_flight_scenario`, real naked-eye
  pipeline:
  - **E1a**: far group first alone, near seconds later. Two contacts, two `CONTACT_DETECTED`.
  - **E1b**: both groups in the first look. Two contacts.
  - **E3**: a 200 m line of 6, dwell from about the same place, look away past the continuity
    window and back. One contact or group, one detection callout.
  - **E4**: same scenario; spoken range across same-geometry looks spreads ≤ 3·a·σ, and the
    declared along σ never drops below `s·σ` during dwell.
  - **E5a**: straight-in 5 → 1 km. One contact, no re-detection callout, and absolute error
    shrinks.
  - **E5b**: 90° orbit at 3 km. One contact, no new-contact callout.
  - **Q2**: a 1 km column driving along the LOS. One group.
  - **E7**: Stage 4's case end to end.
  - **E6**: no verdict on the 1.25 case in a scenario. Two unit tests show the decision on that
    geometry **flips** inside the declared bounds: salience when `RANGE_RELATIVE_SHARE` crosses ≈
    0.31, the gate when `RANGE_LOOK_SHARE` crosses ≈ 0.3. That proves it is adjustable without a
    code change.
- Group identity check: in E1a, assert the second group does not inherit the first group's
  `Group` id through `group_matches` test 5. Absolute centroid uncertainty now stays larger, so
  test 5's slack is more permissive than before. If it fails, the fix is the shared helper in test
  5. Otherwise leave it to `[[BL-B105]]`.
- Regenerate `config/defaults.toml` and read the **rendered** entries.
- Test card: branch `main` after merge, `#needs-flight`. Cards:
  - two groups on one bearing, approached so that the far one shows first
  - an orbit of one group
  - a straight-in run
  - a stationary group overflown and then asked about after 2+ min

### Co-moving Fields

Not the strict step-6a trigger (there is no externally written mode), but the same failure class.
`PositionEstimate.anchor` must travel with `x/z/covariance` through **every** construction site
(`grep -n 'PositionEstimate(' body-layer/src`: 9 sites).

| Site | Must hold after |
|---|---|
| `estimate_from_look` (founding) | anchor = this look |
| `fold_position`, fused branch(es) | anchor = the new look |
| `fold_position`, sanity-reject / hold branch | anchor **unchanged** (no evidence fused) |
| `clamp_to_detection_envelope` | anchor unchanged: a clamp moves the mean, not the look history |
| `clamp_fold_displacement` (both returns) | anchor = the look being folded, since the fold happened, only clamped |
| `_apply_floor` | anchor unchanged |
| hold/inflate path (`as_of_sim` advance) | anchor unchanged |
| `speech.py` placeholder | anchor `None`. The helper treats `None` as ρ = 0 (independent: the conservative, wider gate) |

Use `dataclasses.replace` everywhere a site derives from an existing estimate, never a fresh
constructor (`BL-B71` lesson).

### How each alignment item is answered

- **E1**: Stage 2 gate (worked numbers) and Stage 5 E1a/E1b.
- **E2**: separate clusters already (Q1). Salience gains an along-line check (Stage 3). `groups.py`
  is capped and pinned.
- **E3**: shared Z_near and the stable terms keep members and repeat looks consistent (Stages 1,
  2, 5).
- **E4**: absolute σ unchanged, repeat spread a·σ, along floor `s·σ` at the same geometry.
- **E5**: decorrelation by geometry and correlated fusion. Smooth fields mean no jump (Stages 1,
  2, 5).
- **E6**: `RANGE_RELATIVE_SHARE` (in one look) and `RANGE_LOOK_SHARE` (across looks). Tested as
  flips, no verdict. The default comes out as two.
- **E7**: Stage 4.
- **Findings**:
  - F1: Z fields shared by geometry, not by object.
  - F2: hypothesis-geometry ρ in the gate.
  - F3: Q1, clustering unchanged.
  - F4: deliberate reversal of precise-position-belief's dwell convergence, see second-order.
  - F5: Q4.
  - F6: the perceived-only rule above.

### Risks & Unknowns

- **One-anchor approximation.** After mixed-optic or mixed-geometry histories, the estimate's true
  correlation with a new look is not exactly that of the last look. The worst case is a slightly
  over-tight gate after a look through a better optic followed by naked-eye looks. The Stage 2
  property tests bound it. If they cannot be met, escalate rather than add a second anchor.
- **Large old absolute error can absorb a new nearby group after a big geometry change.** A
  contact seen only from 4.6 km keeps ±780 m (Q3, accepted). After ownship has closed far enough
  that ρ ≈ 0, a different group first seen inside that ellipse can pass the gate if the first group
  is out of view at that moment. Honest under the model, and outside E1's "seconds apart" case.
  Watch for it in flight.
- **Cross-axis is now the wider one** (≈0.24 R vs ≈0.144 R at defaults). "Near-circular" is
  delivered as within ~1.6:1. `BEARING_SIGMA_DEG` (existing tunable) is the lever if the flight
  says otherwise. A stable structure for bearing is out of scope.
- **Very low altitude (< ~10 m AGL)**: 2 km and 5 km on one bearing can overlap in angle and stay
  one blob (Q1). This is outside the 50–800 m envelope, so accepted.
- **Mission-memory volume.** Every founded contact now gets an entry, including short-lived
  presence-only ones and merge-echo duplicates. Recall and kneeboard may get noisier. No guard is
  added, per the user's "keep all". Watch the sortie's memory log.
- **Downstream consumers of fused range uncertainty get wider values for distant groups**:
  `contacts.py:1729` (watch-reporting kilometre deadband, plan Decision 5a-i), `groups.py`
  centroid uncertainty and `group_matches` slack, `marks.py`, `group_view`. This is honest, not a
  defect. The kilometre report may go quieter for a far group under dwell. Cross-range consumers
  (`optic_policy` sweep width) are unaffected, because bearing is unchanged.
- **Test-suite wall time at 1 s** is ~5× frames per scenario, against the shared
  `_THREAD_JOIN_TIMEOUT_S`. Measure in Stage 0. If scenarios need it, compress legs rather than
  going back to 5 s.
- **Performance**: one field evaluation per observation (≤ dozens per poll, K ≈ 32) is
  negligible. `group_salience`'s extra compare is O(1) per pair with ranges hoisted. Do not
  recompute range inside the pair loop.

### Second-order effect

This reverses `precise-position-belief`'s "uncertainty strictly decreases with looks" for
same-geometry dwell. At merge, add a `Decision REVISED` pointer there and in `watch-reporting`
Decision 5a-i (step 10). It also unblocks `[[BL-B109]]`, the second-group callout wording, which is
only worth building once two groups on one bearing reliably exist.

### Decisions Requiring User Input

**Answered 2026-10-31** (`explore-notes.md`, "Plan-escalation answers"): 1 rewrite -- yes; 2 binocular
0.7 -- yes; 3 -- keep the confidence floor, drop only the identification-level gate.

1. **Pinned tests will be rewritten, not extended.** These are the exact-offset pins in
   `test_estimation.py`, and `precise-position-belief`'s dwell-convergence assertions. They encode
   the old independent-looks model, which the user's answer 2 overturns. This is escalated per
   `AGENTS.md`. The recommendation is to rewrite them as statistical property tests.
2. **Binocular range scale 0.7 (Q3)**: this makes binocular absolute range tighter than today, while
   naked eye is unchanged. It is a judgement default. OK to ship as `#needs-flight`?
3. **Mission memory without the confidence floor (Q4)**: retiring `GROUP_ENTRY_CONFIDENCE_FLOOR`'s
   first-entry gate means low-confidence class claims also get entries. Read as "regardless of
   identification level". Confirm that includes "regardless of confidence".

---

## Amendment 2026-10-31: cross-optic error model

Architect pass on `feature/relative-distance-grouping` at `2f6de2cc`, after two review rounds
left Required Fix 1 open (`review.md`). Every number below comes from running the code: the
shipped code, and a monkeypatched prototype of the design applied to the real `ContactStore`,
gate and fold. The prototype was run against the full body-layer suite. Probe scripts are in
the session scratchpad, not the repo. A short version of each probe is reproduced as a test in
Stage D.

**This supersedes**, in place and by pointer (`docs/PROCESS.md`, "Superseding a decision"):

- Stage 1, "Per optic class... each has its own field seeds, so a better optic is an
  **independent** look". → **REVISED** below: tiered (nested) fields.
- The review follow-up's `CROSS_OPTIC_RANGE_SHARE` (`implementation.md`, "Review follow-up").
  → **RETIRED** below.
- Stage 1's `RANGE_DECORRELATION_RANGE_RATIO` default 1.5. → **REVISED** to 4.0 below. This is
  a calibration change with its own commit.
- Stage 2, "The gate and the fold see the same `S` by construction". → **REVISED** below. The
  gate and fold still share one helper. The fold adds a cap that the gate does not.
- The "model in one picture" table row "relative σ, two things at different distances in one
  look ≈ √2·f·σ". It was **not true** of the shipped noise at the clear-case ratios (see
  Verification). It holds under the revised calibration.

### Verification of the current code (hypothesis checked, partly refuted)

**One methodological fact first.** The down-range draw depends only on look geometry, optic and
poll. `bias_object_id` keys only the *bearing* bias. So the reviewer's "10 bias draws" were 10
copies of **one** range realisation, which explains why they came out 10/10 or 0/10 and never
anything in between. Rotating the scene also samples only one realisation, with about 12
effective samples at a 30° length scale. Honest rates need an **ensemble of field
realisations**. The probes below get one by salting the field seed, 100–400 realisations each.

Realised correlation of the stable down-range term, ensemble of 400 realisations, shipped code:

| pair | realised ρ | belief declares | RMS of the range-error difference |
|---|---|---|---|
| unaided vs binocular, same geometry (3.5 km) | **−0.07** (independent by construction: `optic_class` is in the seed) | **0.575** | 749 m |
| unaided near 2.25 km vs far 3.75 km, same bearing | **+0.23** | 0.196 (real geometry) | **642 m** |
| unaided 2.0 vs 2.5 km (E6) | +0.70 | | 309 m |
| unaided 4.6 → 2.4 km (closing) | +0.12 | | 825 m |

E1 fold rate, shipped code, 100 realisations. Far contact founded from 3 looks, the other group
seen once 6 s later, same bearing, stationary observer:

| case | 3.0/1.5 | 3.75/2.25 | 4.5/3.0 | 5.0/3.5 | 4.0/2.0 | 4.6/2.4 |
|---|---|---|---|---|---|---|
| unaided/unaided, far first | 4% | 9% | 11% | 9% | 4% | 5% |
| unaided/unaided, near first | 13% | 18% | 20% | 22% | 11% | 12% |
| far unaided, near binocular, far first | 21% | 46% | 60% | 62% | 32% | 37% |
| far unaided, near binocular, near first | 31% | 59% | 71% | 73% | 38% | 42% |

The reviewer's literal probe reproduces exactly: same-optic 10/10 two contacts; far unaided and
near binocular 0/10.

**Root cause, as confirmed:**

1. **Confirmed (main-loop hypothesis, part 1).** The truth-side fields fold `optic_class` into
   the seed (`_field_value`). Unaided and binocular looks at the same scene therefore draw
   independent errors (realised ρ ≈ 0). Belief meanwhile declares 0.6 × kernel through
   `CROSS_OPTIC_RANGE_SHARE`. **Belief and noise disagree.** The tunable narrows a gate around a
   correlation the noise does not have.
2. **Refuted (main-loop hypothesis, part 3).** Same-optic separation does **not** come from a
   shared realised error. At 2.25/3.75 km the two groups' realised errors are only 0.23
   correlated, because `Z_view` decorrelates at a range ratio of 1.5, which is *inside* the
   clear-case ratios of 1.4–2.0. Same-optic mostly stays two because the hypothesis gate
   (ρ ≈ 1 under "same thing") is narrow. It is still not "always two": it fails 4–22% of the
   time across realisations. The plan's clear-case guarantee did not hold for **any** optic. The
   reviewer saw 10/10 only because one realisation happened to pass.
3. **New: an irreducible cross-optic limit.** Under any honest model, an unaided estimate of a
   group carries blur that a binocular look does not share. The best a binocular look of the
   same thing can agree with an unaided memory is ±σ_u·√(1 − k²), with k = 0.7, which is
   0.71σ_u. The gate's 3σ zone along the line is therefore at least about **0.36 × range** (1.37
   km at 3.75 km). This is physics, not a defect, and it decides the user question below.
4. **Found on the way (defect).** `surface_range_estimate` evaluates both its fields at
   `true_bearing_deg=0.0`. For **ground units** the stable error never decorrelates with line-of-
   sight rotation, so E5b orbit triangulation does not exist in the noise, while belief assumes
   it does (30°). Belief then over-claims improvement on an orbit. Every probe here, and the
   reviewer's, used the air-shape helper, so none of them could see it.
5. **Found on the way (fragility).** Every pinned-scenario test in the suite passes or fails on
   one fixed field realisation. Changing a length scale swaps the realisation. One test
   (`test_hybrid_source.py::test_repeated_scope_observations_of_a_stationary_object_do_not_
   converge_on_truth`) fails for exactly that reason under the prototype.

### The model (Stage A, `perception/estimation.py`)

**A better optic sees the same scene with less blur.** Scene cues (misjudged unit size,
terrain) are optic-independent, so they cannot shrink with magnification. What magnification
removes is the observer's own measurement blur. So the tightest optic's error is the shared
part, and each coarser optic adds its own independent blur on top. Sort the optics by range
scale k (sight_narrow 0.3 < sight_wide 0.5 < binocular 0.7 < unaided 1.0, read from
`_RANGE_SIGMA_SCALE_BY_OPTIC` at import, not hard-coded, so a tuned scale reorders correctly):

```
Z_o(g) = (1/k_o) · Σ_{tiers j with k_j ≤ k_o} sqrt(k_j² − k_{j−1}²) · G_j(g),   k_0 = 0
```

- `G_j` are unit fields seeded by **tier name**, not by optic class. Each uses the same
  geometric kernel the field already has, so `Var Z_o = 1`.
- **Corr(Z_o(g₁), Z_p(g₂)) = (k_p / k_o) · κ(g₁, g₂)** for p tighter than o, where κ is the
  existing closed-form kernel.
- Apply this to both `Z_view` and `Z_near`. `z_look` stays per optic and per poll, independent
  as today.
- The `"scope"` class (hybrid source) is not in the ladder. It keeps its own independent field,
  and belief gives it ρ = 0, which is today's behaviour.
- Implement it inside `_stable_fraction`, through one helper `_tiered_field(field_name,
  optic_class, coords, length_scales)`. No new abstraction is needed: it replaces the direct
  `_field_value` calls.
- **One exported function says how optics correlate:** `optic_range_correlation(a, b) -> float`.
  It returns `min(k)/max(k)` for two ladder optics, 1.0 for equal classes, and 0.0 if either
  class is outside the ladder. The realisation (through the tier weights) and belief both read
  it, so **the two cannot disagree**: they are the same arithmetic.
- `stable_range_correlation(d_bearing_deg, range_ratio, optic_a, optic_b)` returns
  `(k·κ_view, k·κ_near)` with `k = optic_range_correlation(a, b)`. Its `same_optic: bool`
  parameter goes.
- Add a test seam, `_FIELD_REALISATION_SALT: str = ""`, a module literal (not a tunable: it does
  not change behaviour). It is folded into `_field_frequencies`'s seed and cache key, so tests can
  sweep an ensemble of realisations (`monkeypatch` + `cache_clear()`).
- **Surface fix:** add `true_bearing_deg` to `surface_range_estimate`, pass it from
  `naked_eye_source`, and use it in both the cue A and cue B fields. This is a behaviour change
  for ground units, so it gets its own commit.

**Why not "mostly the same error, scaled down" (shared share above k).** If the binocular error
were close to 0.7 × the unaided error, the difference of the two estimates (≈ 0.3·e_u) would
reveal the error. The fused estimate would then extrapolate past both: at ρ = 0.9 the fused σ is
0.91σ_b, and it falls to 0 as ρ → 1. That puts omniscience-by-arithmetic **into the noise
itself**, not only into the belief. The nested ladder sits exactly at the honest boundary
ρ = σ_small/σ_large. There, fusing any two optics gives exactly the tighter one, so the two
weights are never negative.

### Belief side (Stage B, `belief/position_belief.py`, `association_over_time.py`)

- **`correlated_innovation` gains `for_fusion: bool`.** The along-line cross-term becomes
  `c_down = optic_range_correlation(...) · effective_down_correlation(κ_view, κ_near) · σ_sa ·
  σ_sb`. When `for_fusion` is set, it is additionally capped:
  `c_down ≤ min(var_prior_along, var_look_along)`. Each variance is that side's full along-line
  variance (inflated prior projected on the anchor's line of sight, look covariance projected on
  the look's). In 1-D this is exactly "neither weight negative", so the fused mean never
  extrapolates past both inputs. It also covers *closing*: under the new calibration two looks
  at a 1.9 ratio are about 0.8 correlated, more than σ_near/σ_far ≈ 0.52.
- **The gate does not cap.** It uses the model ρ, which is the correlation the noise really has.
  A gate produces accept/reject, never a position, so a calibrated test against the true
  correlation is honest. The fold's `S` is then ≥ the gate's `S`. Any look the gate accepts sits
  well inside the fold's `S`, so `FUSION_SANITY_SIGMA` behaves. Capping the gate too was measured
  and makes things worse: same-optic folds go back up to 4–35%.
- **The gate tests the look's σ under the hypothesis.** Under "this look is that contact", the
  look's true range is the hypothesis range. In `passes_gate`, scale the look's `sigma_cross_m`,
  `sigma_down_m` and `sigma_down_stable_m` by `hypothesis_range_m / percept.range_m`. The reported
  range is used, so only perceived quantities enter. This makes ρ *and* σ hypothesis-consistent.
  Today the look's σ is declared at its own real range. Measured: without this change, same-optic
  near-first folds 3–12% across 3.0–5.0 km. With it, 0–1%.
- **Floor** (`_apply_floor`): `down_floor = κ_view · s · σ_down_look · min(1, k_anchor /
  k_look)`. Staring through a worse optic after a better one can never go below the better optic's
  own stable floor, and a better optic's look is not discounted. `correlated_innovation` returns
  the **geometric** κ_view (not k-scaled), and the floor applies the optic factor itself.
- `contacts_plausibly_same`: the same helper, gate mode (no cap), with the optic factor.
- `LookAnchor` already carries `optic_class` and `sigma_down_stable_m`, so there is **no new
  field** and no new construction-site work. The Co-moving Fields table is unchanged.

### Calibration (Stage C, its own commit; mechanism and calibration never share one)

- `RANGE_DECORRELATION_RANGE_RATIO` 1.5 → **4.0**, `hi` 4.0 → 8.0. Rewrite the `#:` comment's
  first sentence for what the pilot notices: *"How far apart in distance two things can be and
  still have their ranges misjudged together. Higher keeps two groups on one bearing in the right
  order and spacing, and keeps a group's range error consistent while closing."*
- Why 4.0 and not a scenario fit. The user's own words: *"2 or 2.5 km and 5 are easy to tell
  apart at any altitude"*. That needs the stable error shared across a range ratio of about 2. A
  correlation of 0.8 at ratio 2 needs L ≈ 4. At 1.5 the same pair is 0.08 correlated, which
  contradicts both the user and the plan's own table.
- What it does to closing: the *fractional* misjudgement persists while closing (0.78
  correlated at 4.6 → 2.4 km), and the *absolute* error still shrinks in proportion to range. So
  E5 ("does improve when the pilot closes") holds, and a different angle still decorrelates
  (`RANGE_DECORRELATION_BEARING_DEG` unchanged). The fold cap is what stops belief from solving
  for the shared fraction.
- **Retire `CROSS_OPTIC_RANGE_SHARE`.** The cross-optic correlation is now derived from
  `BINOCULAR_RANGE_SIGMA_SCALE` (and the sight scales). A user `tuning.toml` that still sets the
  key gets the loader's unknown-key warning, which is the intended posture. Regenerate
  `defaults.toml` and read the **rendered** entry for the changed key.

### Measured on the prototype (stages A–C applied by monkeypatch to the real code)

Ensemble realised correlation (400 realisations): unaided vs binocular at the same geometry
**0.75** (model 0.7 × 0.96 + f²-part). Near/far at 2.25/3.75 km **0.84**, difference RMS
**383 m** (was 642). 2.0/2.5 km 0.94, 157 m. Closing 4.6→2.4 km 0.78. **Belief and noise now
agree.**

E1 fold rate, 100 realisations:

| case | 3.0/1.5 | 3.75/2.25 | 4.5/3.0 | 5.0/3.5 | 4.0/2.0 | 4.6/2.4 | 2.5/2.0 (E6) |
|---|---|---|---|---|---|---|---|
| unaided/unaided, far first | 0% | 1% | 0% | 0% | 1% | 0% | 2% |
| unaided/unaided, near first | 0% | 1% | 1% | 0% | 1% | 0% | 14% |
| binocular/binocular | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| far unaided, near binocular, far first | 18% | 40% | 62% | 67% | 14% | 18% | 87% |
| far unaided, near binocular, near first | 7% | 19% | 44% | 52% | 5% | 5% | 73% |
| far binocular, near unaided, far first | 3% | 11% | 40% | 50% | 3% | 3% | 95% |
| far binocular, near unaided, near first | 0% | 1% | 9% | 25% | 0% | 1% | 68% |
| **any optics, both groups in the same look** (continuity claim) | 0% | 0% | 0% | 0% | 0% | 0% | — |

Cross-optic, memory only, wider separations (fold %, far first / near first, far unaided and
near binocular): 3.0/1.0 6/1, 4.0/1.5 3/1, 5.0/2.0 4/1, 5.0/2.5 11/3.

Other checks, prototype applied:
- Full fast suite: 2885 passed, 1 failed. The failure is the realisation-pinned scope test
  (point 5 above).
- `test_bl_b104_scenario_mock_flights.py`: 5/5 passed, including the shipped two-groups test,
  without `CROSS_OPTIC_RANGE_SHARE`.
- All of `test_relative_distance_scenarios.py` passed: E3 across optics, E4 dwell, E5a/E5b, and
  both E6 flip tests.
- No omniscience: fused along σ / tighter look's σ was at least **0.985** over 72 geometries,
  for unaided→binocular, binocular→unaided, closing, and mixed. The shipped code reaches 0.886.

**The honest model meets the clear case same-optic (≤1%) and whenever both groups are in the
same look (0%). It does not meet it cross-optic when the far group is held only in memory.**
Those numbers follow directly from point 3, they are not a tuning gap, and so this becomes a
user decision (below). Even the reviewer's literal geometry (3.75/2.25, far unaided then near
binocular) still folds on the code's one fixed realisation. It sits in the 40% band.

### Implementation stages

**A. Perception mechanism** (`estimation.py`, `naked_eye_source.py`), two commits:
1. Tiered fields, `optic_range_correlation`, `stable_range_correlation` signature, salt seam.
2. Surface bearing fix.

`test_estimation.py`'s cross-optic tests are rewritten for the derived ratio: `..._is_partial_
for_a_different_optic` becomes `optic_range_correlation` property tests. Add an ensemble test:
realised ρ between optics o and p at the same geometry ≈ k_p/k_o ± 0.1 over ≥ 200
realisations, for every ladder pair, with `"scope"` ≈ 0.

**B. Belief mechanism** (`position_belief.py`, `association_over_time.py`), one commit. Remove
the `CROSS_OPTIC_RANGE_SHARE` reads.

**C. Calibration commit.** `RANGE_DECORRELATION_RANGE_RATIO` 4.0 / hi 8.0, retire
`CROSS_OPTIC_RANGE_SHARE`, regenerate `defaults.toml`.

**D. Tests, docs, entry.**
- New `tests/test_relative_distance_sweep.py`. It uses the salt seam and the existing
  `_observation` helper, extended with a `surface: bool` path that goes through
  `surface_range_estimate` so ground units are covered too. N = 100 realisations per cell.
  Measured cost was about 1 s per 100 runs per cell.
  - **E1 same-optic** (unaided/unaided, binocular/binocular, both orders) over far ∈ {3.0, 3.75,
    4.5, 5.0} km with separation 1.5 km, plus 4.0/2.0 and 4.6/2.4. Assert fold ≤ 3% per cell
    (measured ≤ 1%).
  - **E1 in view**: every optic pair, both orders, the first group re-seen in the same poll
    with `continues_observation_id`. Assert 0 folds.
  - **E1 cross-optic, memory only**: a characterisation fence, not a guarantee. Assert each
    cell's rate ≤ the measured value + 10 points, so that a change to the gate, scales or length
    scales cannot silently widen it (the reviewer's round-2 optional item). Its final form
    depends on the user decision.
  - **E3 across optics**: one group, unaided then binocular and the reverse, over realisations.
    Never two contacts.
  - **No omniscience**: over realisations and both orders (unaided/binocular, binocular/unaided,
    closing 4.6→2.4, unaided 4.6 then binocular 2.4):
    - fused along σ ≥ the floor of the tighter look;
    - the fused mean lies between the two inputs along the line (no negative weight). Check this
      directly from the gain, not from errors.
  - **E6**: the existing flip tests stay. No verdict is asserted on 2.0/2.5.
- Rewrite `test_hybrid_source.py`'s scope test as an ensemble statement.
- Leave pinned scenarios that pass in place, but note in each that it rests on one realisation.
- Add a callout-level check to E1a: two `CONTACT_DETECTED` **callouts spoken**, not only two
  events. `contacts_plausibly_same` drives merge-echo suppression and its correlation changes in
  Stage B.
- `docs/STRUCTURE.md` estimation/position_belief entries.
- **`BL-B108.md`: state E1 as delivered for same-optic and in-view only**, with the
  memory-only cross-optic rate, unless the user decision changes it.

### Risks & Unknowns (amendment)

- **How often the memory-only cross-optic case arises in flight is unknown.** It needs the far
  group to drop out of detection in exactly the poll where the near one is glassed. On one
  bearing the far group is inside the binocular field, so in-view is the expected case.
  `sortie-log-triage` can count it (contacts founded within seconds of an optic switch on a
  bearing already held).
- **The 1-D cap with non-coincident axes** (after a large bearing change) is approximate. The
  no-negative-weight sweep test is the guard. If it fails at large Δbearing, project both
  covariances on a common axis rather than add machinery.
- **The `RANGE_RELATIVE_SHARE` E6 flip point moves**, because `Z_view` is now shared at 2.0/2.5.
  The flip tests only assert that a flip exists inside the bounds, and they passed under the
  prototype. The ≈0.31 figure in Stage 5's text is stale. Re-derive it rather than quote it.
- **The ground-unit orbit behaviour changes** with the surface fix. E5b for ground units starts
  to triangulate for real. No test covered it before; the sweep's surface path does.

### Second-order effect

The optic ladder generalises to the 9K113 (`BL-B66`): a sight look is now the shared core of
every coarser look, so raising the sight on a group Petrovich already holds tightens it without
extrapolation and without a new correlation constant.

### Decision Requiring User Input (amendment)

**Cross-optic, far group held only in memory.** An unaided range estimate carries blur that a
binocular look does not share. At the binocular scale of 0.7 you approved, the honest gate along
the line is about ±0.36 × range wide whenever an unaided memory is compared with a binocular
look. At ~3–5 km that is about as wide as the 1.5 km "clear case" separation.

Measured fold rates for the memory-only case: 5–67% across the clear-case grid.

The same scenes give 0% when the far group is still in the binocular view (it is on the same
bearing), and ≤1% same-optic.

Options:

1. **Accept as the honest limit (recommended).** Ship the model. E1 is guaranteed same-optic and
   in-view. The memory-only cross-optic rate is documented and fenced by a test, and flights
   tell how often it actually occurs.
2. **Smaller binocular range advantage**, scale 0.85 instead of 0.7. Measured memory-only folds
   drop to 3–37% (in-view and same-optic unchanged). This trades away some of what Q3 gave
   binoculars. It narrows the gap but does not close it.
3. **Neither; reopen the goal.** For example, treat any optic switch as a fresh look at the
   whole bearing. That is a perception/attention change outside this feature.

Not offered: any belief-side ρ above what the noise has. That is the round-1/round-2 fix shape,
and it is what this amendment removes.
