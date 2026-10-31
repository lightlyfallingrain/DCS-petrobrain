# Relative-distance grouping — plan (`BL-B106`)

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
Decision 5a-i (step 10). It also unblocks `[[BL-B107]]`, the second-group callout wording, which is
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
