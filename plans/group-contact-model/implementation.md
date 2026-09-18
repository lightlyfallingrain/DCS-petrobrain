### Implementation Summary

Stages 1 and 2 of `plans/group-contact-model/plan.md` only, per instruction. Stage 3
(calibration, needs a live sortie) and Stage 4 (surfacing cardinality) were explicitly not
started. Two commits on `feature/group-contact-cardinality`, branched from `main`:

- `8ea06b6` — Stage 1: `belief/cardinality.py` mechanism, no behaviour change.
- `ece33ed` — Stage 2: perception clustering, count emission, veto removal.

### Files Changed

**Stage 1**
- `body-layer/src/belief/cardinality.py` (new) — `CountBucket` ladder (ED's `OP_1UNIT`…
  `OP_MORETHAN15UNITS` vocabulary, verbatim from `aircraft-layer/research/2026-09-08-pb1-5-
  worldobjects-filter-and-ambient-detection.md`), `CardinalityBelief`, `fold_cardinality`
  (interval containment standing in for `classification.py`'s specificity level),
  `CARDINALITY_CONTRADICTION_LOCKOUT_S`, `cardinality_belief_from_bucket_name`.
- `body-layer/src/belief/decay.py` — added `cardinality_confidence_at`, reusing
  `IDENTITY_HALF_LIFE_S`, mirroring `classification_confidence_at`.
- `body-layer/src/belief/contacts.py` — `Contact` gains `cardinality: CardinalityBelief`
  (defaults to `OP_1UNIT` via `field(default_factory=...)`, not a required constructor arg, so
  every existing direct `Contact(...)` call site — including `test_decay.py`'s own helper — kept
  compiling untouched) and `cardinality_lockout_until_sim`. `from_percept` seeds it from
  `percept.count_bucket` when present, `OP_1UNIT` otherwise. No fold logic wired into `record` at
  this stage (added in Stage 2, since no percept carried `count_bucket` yet in Stage 1).

**Stage 2**
- `body-layer/src/perception/clustering.py` (new) — `ClusterCandidate`/`Cluster`,
  `cluster_candidates` (single-link position clustering, radius = `naked_eye_cluster_radius_m`,
  no chaining cap — Stage 3's job), `count_bucket_for` (a non-overlapping partition of the
  cardinality ladder for forward selection). `naked_eye_cluster_radius_m` and its bucket-width
  helpers were **moved here, not duplicated**, from `belief.association_over_time`'s private
  `_naked_eye_uncertainty_m` — the cluster radius and the association gate's own per-percept
  uncertainty are the same number by construction, and `perception/` may never import `belief/`,
  so the shared function had to live on this side.
- `body-layer/src/belief/association_over_time.py` — deleted the presence-tier merge veto (the
  two lines + comment block named as Stage 2's removal point); `uncertainty_radius_m` now
  delegates to `perception.clustering.naked_eye_cluster_radius_m`; docstring rewritten to explain
  why the veto is gone and what replaces its reasoning.
- `body-layer/src/perception/source.py` — `Observation` gains `count_bucket: str | None = None`.
- `body-layer/src/belief/percept.py` — `Percept` gains `count_bucket`, threaded through
  `percept_of`.
- `body-layer/src/belief/contacts.py` — `Contact.record`/`from_percept` now fold cardinality via
  `fold_cardinality` when `percept.count_bucket is not None`; left untouched (a hold) when it is
  `None` (the scope/hybrid channel, which supplies no count evidence).
- `body-layer/src/perception/naked_eye_source.py` — `poll()` now clusters the admitted
  `(candidate, result)` pairs via `perception.clustering.cluster_candidates` before building
  `Observation`s; `_build_observations` (new) resolves `continues_observation_id` by majority
  object overlap across the *whole* poll's clusters in two passes (per-cluster vote counting,
  then a single global majority-owner pass per historical observation id) so a splitting cluster
  never lets more than one child inherit the parent's continuity. Bearing/range are now quantised
  from each cluster's centroid; `derived_world_position` likewise becomes the centroid.
  `NAKED_EYE_MAX_NEW_PER_POLL` still throttles individual-object admission (unchanged), not
  cluster count directly — documented as a Stage 2 scoping decision, not a Stage 3 pre-tune.
- `body-layer/CLAUDE.md` — Structure section updated for `belief/cardinality.py`,
  `perception/clustering.py`, `Contact.cardinality`, and the reworked `naked_eye_source.py`/
  `association_over_time.py` entries.

### Tests Added

- `body-layer/tests/test_cardinality.py` (Stage 1) — all four `fold_cardinality` outcomes
  (refine/reinforce/hold/contradict), the genuine-partial-overlap generalisation
  (`OP_TO5UNITS`/`OP_5TO7UNITS`'s own overlapping boundary), the contradiction lockout and its
  expiry, `cardinality_belief_from_bucket_name`'s known/unknown-name behaviour,
  `cardinality_confidence_at`'s decay, and founding-percept `OP_1UNIT` seeding via a real
  `ContactStore.ingest`.
- `body-layer/tests/test_clustering.py` (Stage 2) — `count_bucket_for`'s boundary table,
  merge/split by radius, single-link chaining (documented, not defended against), homogeneous vs.
  mixed aggregate classification, centroid computation, empty input.
- `body-layer/tests/test_calibration_cluster_merge_undercount.py` — **rewritten**: twelve objects
  at ~9 km now fold into exactly one contact with `OP_ABOUT15UNITS`; the same twelve at a
  deliberately well-separated close-range layout (redesigned from the original bearing/range
  values, which were found by hand-computation to actually trigger single-link chaining across
  class groups at those specific distances) split into six contacts with small exact counts.
- `body-layer/tests/test_mock_flight_chain.py` — the single-threaded chain test's assertions
  rewritten around the real, hand-run clustering/continuity behaviour for that fixture's actual
  geometry (objects 101/102 are 400 m apart): one contact throughout, not two, with the reasoning
  (cluster radius vs. the wider, symmetric-budgeted spatial gate) documented inline as a named
  Stage 3 calibration boundary, not a regression.
- `body-layer/tests/test_naked_eye_source.py` — two new tests (clustered emission producing a
  plural `count_bucket`; a cluster split giving the majority child continuity and the minority
  child `None`); four existing cap/debounce tests got wider, hand-verified candidate spacing
  (`_CAP_TEST_RANGES_M`) so they keep testing the cap mechanism rather than incidentally
  triggering Stage 2 clustering.

### Checks

(body-layer/ only touched)
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 34 source files)
- pytest -q: pass (632 tests; 608 pre-existing + 24 new/rewritten)

### Notable Discoveries

- **Single-link chaining is real, not theoretical, at the plan's own original test distances.**
  Reusing the pre-Stage-2 test's bearing/range values for a "close range" scenario (500 m–3 km)
  caused the twelve-unit complex to chain into 3 clusters instead of 6 class-pure ones — down-range
  bucket width jumps from 100 m to 500 m past 1000 m range, and the honest cluster radius at ~3 km
  (~920 m) exceeds several real inter-group gaps. Confirmed by hand-running `cluster_candidates`
  before writing the test, not guessed. This is exactly the plan's own documented Stage 3 risk
  ("the single most likely thing to need a second calibration pass") showing up organically —
  the close-range test fixture was redesigned with generous, computed margins instead.
- **The association gate's radius and the cluster radius can legitimately disagree at a boundary.**
  In the mock-flight fixture, once naked-eye's own clustering splits two 400 m-separated real
  objects into two singleton clusters, `association_over_time.spatial_gate_radius_m` (which sums
  *both* sides' uncertainty plus a growth term, the BL-2.6 symmetric-budgeting fix) is still wide
  enough to fold the minority split back onto the same contact. Not a bug — the channel genuinely
  cannot rule out "one object" at that range even once its own cluster boundary crosses — but it
  means `test_mock_flight_chain.py`'s two real objects never become two contacts across that
  fixture's full flight. Documented inline as a Stage 3 boundary case.
- **Majority-overlap continuity needs a global (batch-wide) resolution pass, not a per-cluster
  one.** An earlier version resolved each new cluster's `continues_observation_id` independently
  by its own member votes; this let two children of the same parent cluster (e.g. a majority
  truck-singleton and a minority infantry-singleton, both of whose members had voted for the same
  prior merged observation) both claim the same continuity, silently re-merging a genuine split.
  Fixed with a two-pass algorithm (`_build_observations`) that finds the single global majority
  owner per historical observation id before minting any new one — caught only by actually running
  the mock-flight fixture, not by the unit-level cluster tests.
- **`Contact.cardinality` needed a default, not a required constructor arg**, to satisfy Stage 1's
  literal "existing suite passes untouched" criterion — `test_decay.py`'s own `_contact()` helper
  constructs `Contact` directly without a `cardinality` argument, and per this project's own
  feedback memory (`feedback_decouple_fixtures_from_tuned_defaults`), existing tests were not to be
  edited to make Stage 1 pass.

---

### Stage 3a / Stage 4a (2026-09-18)

Stages 3a and 4a only, per instruction (running order `3a → 4a → sortie → 3b → 4b`). Stage 3b
(calibration) and 4b (speech/events) explicitly not started — 3b needs a live sortie the user must
fly, 4b was out of scope. Two commits on `feature/group-contact-cardinality`:

- `17e398f` — Stage 3a: same-source/same-poll exclusion in `ContactStore.ingest`.
- `d7e6e4a` — Stage 4a: `facts["cardinality"]` + `console._SHOW_FACT_KEYS`.

#### Files Changed

**Stage 3a**
- `body-layer/src/belief/contacts.py` — `ingest` gained a read-only pre-scan over the batch before
  its existing single-pass loop: `_resolve_continuity` is evaluated once per observation and
  memoized in `continuity_by_observation_id` (so the main loop never calls it a second time), and
  every observation that resolves by continuity records its contact id under
  `claimed[(percept.source, percept.t_sim)]`. The gate branch then filters candidates by
  `candidate.id not in claimed[claim_key]` before counting how many pass; whichever contact an
  observation ends up on (continuity, gate merge, or founding) is added to `claimed[claim_key]`
  before the next observation in the batch is processed. `association_over_time.py` (gate radius
  formulas, `passes_gate`) is **untouched** — confirmed with `git diff --stat` showing no changes
  to that file in this commit.
- `body-layer/tests/test_contacts.py` — two new tests pinning the rule:
  `test_same_source_same_poll_observations_never_merge` (two same-source, same-`t_sim`, spatially
  close, class-compatible observations found two contacts) and
  `test_different_source_same_poll_observations_still_fuse` (the identical geometry, but different
  sources, still merges into one — the cross-channel-fusion guard).
- `body-layer/tests/test_mock_flight_chain.py` — the single-threaded chain test's assertions and
  inline derivation comment rewritten for the new 2-contact outcome (see "What the mock flight
  chain now produces" below); `test_calibration_cluster_merge_undercount.py` is **unchanged** —
  confirmed with `git diff --stat` showing no changes to that file in this commit, which is Stage
  3a's own narrowness guard per the plan.
- `body-layer/CLAUDE.md` — `contacts.py` Structure entry gained a paragraph describing `ingest`'s
  pre-scan and the same-source/same-poll rule.

**Stage 4a**
- `body-layer/src/belief/tools.py` — new `_cardinality_facts(contact, now_sim) -> dict | None`
  helper, `_classification_facts`'s sibling: returns `{lo, hi, confidence}` (confidence via the
  already-existing `belief.decay.cardinality_confidence_at`, `lo`/`hi` straight off
  `Contact.cardinality`), or `None` when the held claim is still `belief.cardinality.UNKNOWN`
  (0, inf) — the lattice's root, "no cardinality claim at all" per that module's own docstring.
  Wired into `_contact_facts`: `facts["cardinality"]` is only set when `_cardinality_facts` returns
  non-`None`, matching this module's documented absent-not-null convention (the same pattern
  `attention_source`/`motion_when_seen` already use).
- `body-layer/src/belief/console.py` — `_SHOW_FACT_KEYS` gained `"cardinality"`, placed right after
  `"classification"`.
- `body-layer/CLAUDE.md` — `tools.py`/`console.py` Structure entries updated for both additions.

#### Tests Added

- `test_same_source_same_poll_observations_never_merge` — pins the core Stage 3a rule.
- `test_different_source_same_poll_observations_still_fuse` — pins the rule's source-scoping
  (keyed on `(source, t_sim)`, not the whole batch), which is what keeps cross-channel fusion
  working.
- No new tests for Stage 4a beyond the existing suite exercising `_contact_facts`/`show <id>` —
  4a is a pure plumbing addition over already-tested `fold_cardinality`/`cardinality_confidence_at`
  machinery, and `test_mock_flight_chain.py`'s rewritten assertions (below) now directly assert
  `facts["cardinality"]`'s shape end-to-end, which was judged sufficient coverage rather than
  adding a redundant unit test.

#### Checks

(body-layer/ only touched)
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 34 source files)
- pytest -q: pass (634 tests; 632 pre-existing + 2 new)

#### `association_over_time.py` confirmation

`git diff --stat` on both commits shows zero lines changed in
`body-layer/src/belief/association_over_time.py` — `spatial_gate_radius_m` and `passes_gate` are
byte-identical to before Stage 3a, as required.

#### What the mock flight chain now produces

Re-ran the fixture directly (not guessed) after the Stage 3a change: **2 contacts, 2
`CONTACT_DETECTED` events, 42 observations** (unchanged from Stage 2 — Stage 3a does not touch
clustering or observation counts).

- `CONTACT_1` — the truck: Hybrid's frame-0 founding percept, `type`-level `"Ural truck"`, both
  sources (`naked_eye_visual_filtered`, `petrovich_detection_associated`), `certainty="observed"`.
  Its `cardinality` held `OP_2UNITS` (2, 2) through polls 0–13 (the merged cluster's own count);
  poll 14's truck singleton report is `OP_1UNIT` (1, 1) — disjoint from (2, 2) — so
  `fold_cardinality` contradicts to the hull **(1, 2)** and arms
  `CARDINALITY_CONTRADICTION_LOCKOUT_S` (30s). Verified live rather than assumed: the fixture's
  last poll is at t_sim=95.0 (5s/poll, poll 14 at t_sim=70.0), well inside the 30s lockout, so
  `facts["cardinality"]` still reads `{"lo": 1, "hi": 2, ...}` at the fixture's end. **This is the
  correct outcome, not a bug to chase** — the contact honestly cannot tell whether it is looking at
  one occupant or two until the lockout clears and a fresh reading is allowed to re-narrow it; the
  plan's own Stage 3a design section names this exact hedge as a deliberate non-goal ("a split
  still registers as a cardinality contradiction, not as a known structural event").
- `CONTACT_2` — the infantry: founded fresh at poll 14 by the same-source/same-poll exclusion
  (before Stage 3a this singleton would have folded onto `CONTACT_1` via the wider, symmetric-
  budgeted spatial gate, in the same poll the truck singleton claimed `CONTACT_1` by continuity).
  Naked-eye only, presence-level `"OP_GROUPSOMETHING"`, `certainty="observed"`, `cardinality`
  `OP_1UNIT` (1, 1).

#### What in the design did not survive contact with the code

- Nothing structural. The pre-scan/claimed-set mechanism, the `(source, t_sim)` keying, the
  exclude-before-counting ordering, and the "add to claimed after resolving" step all matched the
  design's §"Mechanism — exactly what changes" section as written, and the line count landed close
  to the design's own "roughly fifteen lines plus docstrings" estimate.
- One number required live verification rather than trust: the design's own worked derivation
  flagged the poll-14 lockout-vs-fixture-length question as "verify rather than assume, as the
  figure depends on the fixture's poll cadence" — confirmed above by actually running the fixture,
  not by re-deriving the arithmetic by hand.
- Stage 4a's "absent-when-unknown" convention needed one judgment call the plan left implicit:
  what counts as "unknown" for a cardinality claim. Resolved by reading `cardinality.py`'s own
  docstring, which names `UNKNOWN` (0, inf) as the lattice's literal root/"no claim at all" —
  matched against that exact interval rather than e.g. a low-confidence heuristic, since every
  contact is seeded with a real claim at founding and `UNKNOWN` is reachable only via a
  contradiction hull spanning everything.

---

### Stage 3b-i — the resolution rework (ellipse, not circle)

#### Files Changed

- `body-layer/src/perception/clustering.py` — `naked_eye_cluster_radius_m` (scalar, `math.hypot`)
  removed; replaced with `EllipseRadii`, `naked_eye_cross_range_radius_m` (acuity-derived, divides
  by `BINOCULAR_RANGE_MULTIPLIER` where `visibility.py` multiplies), `naked_eye_down_range_radius_m`
  (unchanged formula, re-justified as a depth-discrimination stand-in, not a reporting artefact),
  `naked_eye_ellipse_radii_m`. New shared geometry helpers `los_components_m` (decompose a
  separation vector into cross/down-range against an observer's line of sight to a pair's midpoint)
  and `within_ellipse` (the quadratic containment test), reused by both this module and the belief
  gate. `cluster_candidates` gained `observer_x`/`observer_z` parameters and now runs a true
  elliptical membership test instead of a scalar-radius one. `count_bucket_for`'s caller changed:
  `_build_cluster` now derives the count from `_count_cross_range_subclusters` (grid-binning a
  cluster's members' cross-range offsets from its own centroid), not `len(members)` — see "What did
  not survive contact with the code" below for why a naive single-link version of this function was
  rejected after being built and proven dead.
- `body-layer/src/perception/naked_eye_source.py` — `cluster_candidates` call site passes
  `ownship_state.x, ownship_state.z`; module docstring updated.
- `body-layer/src/belief/association_over_time.py` — `uncertainty_radius_m` (scalar) kept as a
  conservative legacy reduction (`max` of the two ellipse axes) for `Contact.last_position_
  uncertainty_m`'s own storage; new `uncertainty_radii_m` returns the full `EllipseRadii`.
  `spatial_gate_radius_m` removed (no longer a well-defined single number); `passes_gate` now
  decomposes the percept-vs-contact separation via `clustering.los_components_m` (LOS frame from
  `percept.ownship_at_observation`) and tests it via `clustering.within_ellipse` against both
  sides' per-axis budgets plus isotropic elapsed-time growth. For the scope channel (an isotropic
  circle, `SCOPE_UNCERTAINTY_M` on both axes) this reduces algebraically to the old scalar
  `distance <= radius` test exactly — confirmed by inspection, not just by the existing scope-only
  gate tests staying green untouched.
- `body-layer/src/belief/contacts.py` — two docstring updates only (both cited
  `spatial_gate_radius_m`, now `passes_gate`; one paragraph rewritten to describe the anisotropic
  gate rather than a single scalar).
- `body-layer/CLAUDE.md` — Structure entries for `clustering.py` and `association_over_time.py`
  rewritten for the ellipse/anisotropy, including the open gate regression (see below).

#### Tests Added / Changed

- `test_clustering.py` — every geometry re-derived for the down-range-only axis (all candidates on
  the observer's own bearing, `z=0`), since the module's own low-level merge/split/label mechanics
  don't need the anisotropy itself to be under test. New
  `test_chained_cluster_with_real_cross_range_extent_reports_a_plural_count` — the one test in the
  whole suite that demonstrates the grid-binning count mechanism actually reporting a plural count
  (3-member single-link chain, cross-range only, bin count 2 not 1) — added specifically because
  the calibration/naked-eye-source tests below turned out unable to demonstrate it cleanly
  themselves (see next point).
- `test_calibration_cluster_merge_undercount.py` — **inverted per the plan's own instruction, but
  the specific along-LOS prediction did not survive contact with the code** (see below).
  `test_twelve_unit_cluster_at_9km_becomes_one_contact_with_a_plural_count` split into two: a 206 m
  row **perpendicular** to LOS at 9 km → **twelve** singleton contacts (cross-range radius ~6.75 m
  there, 18.7 m spacing resolves every pair); the same row **along** LOS at 9 km → **one** contact,
  but its count is genuinely `OP_1UNIT`, not plural (see finding below). The close-range six-group
  test's fixture was rebuilt with real cross-range spread within each group (chained via
  `_GROUP_CROSS_STEP_M = 0.3 m`, under the ~0.375 m cross radius at 500 m) instead of the original
  down-range-only layout, which is now geometrically degenerate for counting; the two 3-member
  groups land on `OP_2UNITS` not `OP_3UNITS` (a real grid-binning boundary effect, documented in
  the test itself, not a bug).
- `test_naked_eye_source.py` — `test_two_close_candidates_emit_one_clustered_observation`'s
  expected count corrected to `OP_1UNIT` (a direct 2-candidate merge can never report more than 1,
  see below). `test_a_cluster_splitting_gives_the_majority_child_continuity`'s majority-group
  geometry changed from down-range-only to a cross-range chain (mirroring the new
  `test_clustering.py` demonstration test) so it exercises a real plural count (`OP_2UNITS`) rather
  than a degenerate one; both poll assertions re-derived by running the test, not assumed.
- `test_association_over_time.py` — `test_naked_eye_uncertainty_derived_from_quantisation_buckets`
  replaced with `test_naked_eye_ellipse_derived_from_acuity_and_quantisation_bucket`, asserting the
  ellipse's two axes directly (no more `math.hypot`) plus the legacy scalar's `max` reduction.
- `test_mock_flight_chain.py` — **not predicted, worked out from the fixture's real geometry as
  instructed.** Objects 101/102 sit at `z=0`, and ownship's own track is `z=0` throughout, so their
  400 m separation is *exactly* the degenerate along-LOS case, not the perpendicular one — this
  needed stating explicitly since a careless reading of "don't predict it" could have assumed the
  opposite. Re-derived poll-by-poll against real frame ranges: the down-range-bucket-width step
  (500 m → 100 m, crossed at poll 14) splits the pair at the *same* poll boundary the old isotropic
  formula did, by coincidence of this fixture's specific ranges — total observation/contact counts
  (42 observations, 2 contacts) are **unchanged**, only the derivation comment's reasoning was
  rewritten (down-range-bucket-step, not cross-range shrinkage).
- `test_contacts.py::test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` —
  marked `xfail(strict=True)`, not deleted or silently weakened. See the load-bearing finding below.

#### What did not survive contact with the code

Three real findings, in ascending order of consequence:

1. **The plan's own along-LOS worked example ("one contact with a plural count bucket") is not
   achievable for a literally collinear column.** Proven, not just observed for one geometry: any
   two candidates *directly* connected by the full-ellipse merge test necessarily satisfy
   `cross_range_m <= cross_radius_m` for that pair (an algebraic consequence of the ellipse
   equation — the cross term alone can never exceed 1 for a passing pair, regardless of the down
   term). A cluster is a connected graph of exactly such edges, so a second single-link pass over
   the same members using the same cross-range test — the mechanism as first described in the plan
   ("sub-clustering a cluster's members on the cross-range axis alone") — always reconnects the
   whole cluster and always finds exactly one sub-group, for *any* cluster, *any* geometry. This
   was discovered by building the single-link version literally as described, then hand-verifying
   it against the plan's own 9 km along-LOS example and finding count=1, not plural, every time.
   The mechanism actually implemented (grid-binning a cluster's members' cross-range offsets from
   its own centroid into fixed-width bins, non-transitive) escapes this trap and can report a real
   plural count when a cluster has genuine cross-range extent gathered through chaining — but a
   literally collinear column (zero cross-range separation for every member, e.g. objects strung
   out exactly along the observer's own bearing) still and correctly reports 1, since there is no
   cross-range information at all in that geometry to count by. This is arguably the *right* answer
   physically (a column seen nose-to-tail directly along the line of sight visually overlaps into
   one blob), but it does mean the plan's own headline "along LOS → plural" phrasing needs revising
   before Stage 3b-ii treats it as a target to calibrate toward.
2. **A cluster formed from exactly 2 members can never report a plural count.** A direct
   consequence of finding 1 above, restricted to the smallest case: two candidates merge only if
   their cross-range separation is within one cross-range radius of each other, so their offsets
   from the shared centroid are each at most half that radius — always the same grid bin. Any test
   wanting to demonstrate a real plural count needs 3+ members and single-link chaining (see
   `test_clustering.test_chained_cluster_with_real_cross_range_extent_reports_a_plural_count`).
3. **A load-bearing gate regression, left open, not papered over.** `passes_gate`'s naked-eye
   cross-range budget shrank from a clock-bucket-derived figure (~300–650 m at the ranges the
   `test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` regression test
   exercises) to an acuity-derived one (~1–7 m) — correct for *clustering* (true resolving power),
   but that same figure also now backs the *gate*'s tolerance for a re-observed object's own
   bearing-bucket requantisation drifting between polls while ownship manoeuvres, which is a
   reporting-jitter question, not a resolving-power one. Measured directly (a small script replaying
   the test's exact geometry): real bucket-driven cross-range jumps up to ~700 m occur at this
   scenario's ranges, comfortably exceeding even the generous conservative pad `Contact.last_
   position_uncertainty_m` supplies (~300–500 m, the down-range-dominated `max` reduction). One
   missed match cascades through the existing two-or-more-candidates ambiguity rule into 38
   contacts for one real object. **This is not a one-line magnitude fix**: widening the naked-eye
   ellipse's cross-range radius enough to absorb ~700 m of jitter would need roughly two orders of
   magnitude more than the current acuity-derived value, which would in turn make clustering unable
   to resolve the plan's own 9 km headline scenario (12 objects 18.7 m apart) at all — the two
   uses (true optical resolving power vs. reporting-vocabulary jitter tolerance) are genuinely
   different physical quantities that happened to share one formula before this stage, and Decision
   7 explicitly requires the gate and the cluster ellipse to share the same numbers to avoid
   reopening the Stage 3a dead zone (a gate wider than the cluster's own split boundary re-merges
   legitimately-resolved objects) — confirmed by working through the counterfactual: restoring a
   wide clock-bucket-based pad on the *contact's stored side only* would make any nearby
   split-off object's percept pass that contact's gate too, reopening exactly the ambiguity-cascade
   this stage's own headline scenario depends on not happening. Resolving this properly needs either
   a genuinely separate, non-acuity reporting-jitter budget for the gate specifically, or per-axis
   `Contact` storage (new plumbing, explicitly out of this stage's "no new plumbing" scope) — a
   design decision for Stage 3b-ii or a fresh escalation, not something to paper over with an
   untuned constant. Left as a `strict=True` `xfail` with the full reasoning in its marker, per this
   task's explicit "do not tune the acuity constant's magnitude" instruction — this is not a
   magnitude problem, and treating it as one would hide the real question.

#### Checks

(body-layer/ only touched)
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 34 source files)
- pytest -q: 635 passed, 1 xfailed (634 baseline + 3 new tests − 2 tests folded into the split
  calibration test's replacement... net: +1 passing test, +1 newly-xfailed pre-existing test)

---

### Stage 3b-i rev.2 — the angular separability design (2026-09-18)

Implements `plans/group-contact-model/plan.md`'s "Stage 3b-i rev.2 — the angular separability
design" section, replacing `c625299`'s world-space ellipse (Stage 3b-i) with a true 3D angular
predicate. On `feature/group-contact-cardinality`, not yet committed as of this writing (see the
Implementer's report for the pending commit).

#### Files Changed

- `body-layer/src/perception/clustering.py` — deletion-heavy rewrite. Removed: `EllipseRadii`,
  `naked_eye_cross_range_radius_m`/`naked_eye_down_range_radius_m`/`naked_eye_ellipse_radii_m`,
  `los_components_m`, `within_ellipse`, `_count_cross_range_subclusters`, `_RANGE_BUCKETS_M` and
  its bucket-width helpers (moved to `association_over_time.py`), `NAKED_EYE_ACUITY_RAD`. Added:
  `angular_separation_rad(observer, a, b)` (`atan2(|cross|, dot)` of the two observer→candidate
  unit vectors), `angular_size_rad(size_m, slant_range_m)` (`size_m / slant_range_m`), and
  `_extent_count` (the `floor(extent_rad / unit_rad) + 1` counting rule). `ClusterCandidate` gained
  `alt_m`/`size_m`; `cluster_candidates`/`_build_cluster` take a `perception.geometry.GeoPosition`
  observer instead of bare `(observer_x, observer_z)`. Kept untouched: union-find, `_build_cluster`'s
  classification-aggregation half, `count_bucket_for` and its selection table.
- `body-layer/src/belief/association_over_time.py` — the spatial gate reverted byte-for-byte to its
  pre-`c625299` form (confirmed against `git show c625299^:...`): `uncertainty_radius_m`,
  `spatial_gate_radius_m`, `passes_gate` no longer import anything from `perception.clustering`.
  `_naked_eye_uncertainty_m` (private), `_RANGE_BUCKETS_M`, and the bucket-width helpers moved back
  here from `clustering.py`, their pre-Stage-3b-i home.
- `body-layer/src/perception/naked_eye_source.py` — `_cluster_candidate` now supplies
  `alt_m`/`size_m` (both already in hand — `candidate.alt_m`, `profile.size_m`); `poll()` builds a
  `GeoPosition` observer and passes it to `cluster_candidates` instead of `ownship_state.x/z`.
- `body-layer/CLAUDE.md` — `clustering.py` and `association_over_time.py` Structure entries rewritten
  for the angular predicate/gate revert.
- Tests: see below.

#### Tests Added/Changed

- `test_clustering.py` — rewritten around `angular_separation_rad`/`angular_size_rad` directly
  (coincident-point, 90-degree-separation, size cases), the merge/split pair tests, single-link
  chaining, a genuine extent/unit plural-count test (replacing the old cross-range grid-binning
  test), the "two-member cluster always reports `OP_1UNIT`" theorem, and a self-consistency test
  for the (A) floor at the detection-range limit.
- `test_calibration_cluster_merge_undercount.py` — the two-row table became **three tests**: the
  perpendicular case (twelve singleton contacts, unchanged in outcome), and the along-LOS case
  split into two altitude rows (200 m AGL → one contact, `OP_1UNIT`, confirmed correct and
  confident, not a shortfall; 1000 m AGL → one contact, `OP_TO5UNITS`, the new test that pins the
  altitude term). The close-range six-group test's fixture was re-derived (`_GROUP_CROSS_STEP_M`
  4.0 m, not 0.3 m; ownship at 200 m AGL, not co-altitude with the targets, since two down-range
  groups at the exact same bearing and altitude as ownship are otherwise degenerately collinear)
  and re-run rather than predicted: still six clusters `[1,1,2,2,3,3]`, count buckets now
  `[OP_1UNIT×4, OP_2UNITS×2]` (previously `[OP_1UNIT×2, OP_2UNITS×4]` under grid-binning).
- `test_mock_flight_chain.py` — re-run, not predicted, per the design's own expectation that this
  fixture (ownship 700 m MSL over two objects at 500 m — exactly the correction's 400 m/200 m
  worked case) would change more than Stage 3a did. It did: objects 101/102 separate at *every*
  range in the fixture (not just the far ones), so the merged-cluster phase across polls 0-13
  disappears entirely — naked-eye emits 2 observations/poll from poll 0 (not a ramp from 1 to 2 at
  poll 14), giving 36 naked-eye + 20 Hybrid = **56** total observations (up from 42). Contact count
  stayed **2** as predicted (Stage 3a's same-source/same-poll exclusion founds `CONTACT_2` at poll 0
  instead of poll 14). `CONTACT_1`'s cardinality is now `(1, 1)` throughout, never contradicted to
  the `(1, 2)` hull, since every naked-eye report of it was already a singleton.
- `test_association_over_time.py` — `test_naked_eye_ellipse_derived_from_acuity_and_quantisation_
  bucket` reverted to `test_naked_eye_uncertainty_derived_from_quantisation_buckets`, asserting the
  single scalar again (byte-identical formula to pre-`c625299`).
- `test_contacts.py` — the `xfail(strict=True)` marker on
  `test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` deleted, plain
  `len(store.contacts) == 1` assertion restored; docstring rewritten to record the category-error
  finding rather than delete it. The gate revert fixed this directly, exactly as the design
  predicted (not the angular clustering model) — the jitter-vs-budget ratio is a ratio of two
  angles, invariant under whatever representation computes it, so a shared acuity-derived formula
  was never going to fix the ~700:1 mismatch; reverting to the quantisation-derived figure budgets
  the thing that is actually jittering. The two Stage 3a tests in this file were **not touched**.
- `test_naked_eye_source.py` — five tests needed rework, none anticipated by the design's own §8
  (a real gap, see below): the cap/debounce fixture (`_CAP_TEST_RANGES_M`) placed all five
  candidates on the exact same bearing at ownship's own altitude, which is now a degenerate case
  (zero angular separation regardless of down-range gap) rather than a safe one — fixed by adding a
  small `lon_deg` (cross-range) cross-offset per candidate, verified pairwise-separable by direct
  computation rather than guessed, and confirmed to stay within the cockpit mask's forward
  allowance. `test_a_cluster_splitting_gives_the_majority_child_continuity` needed the same fix
  plus a genuine altitude difference between ownship and its targets (`_high_ownship`, 200 m AGL) —
  its original premise (splitting a cluster by moving one member purely down-range) does not work
  at co-altitude at all under the angular model, and even at 200 m AGL the first attempted split
  position (lat 100) exceeded the co-pilot mask's 22-degree forward depression allowance and
  dropped out of visibility entirely, caught only by running the real `poll()` pipeline, not the
  bare `cluster_candidates` function — moved to lat 600. The test now identifies the majority/
  minority child by position rather than `count_bucket`, since both land on `OP_1UNIT` under the
  new counting rule.

#### Checks

(body-layer/ only touched)
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 34 source files)
- pytest -q: 642 passed (up from 635 passed + 1 xfail; the xfail became a pass, and the net gain
  reflects new tests added across `test_clustering.py`/`test_calibration_cluster_merge_
  undercount.py` beyond the ones removed)

Net diff for the three `src/` files this stage rewrote: 381 insertions, 525 deletions — negative,
as the design's own effort/value finding requires. Full diff (src + tests + CLAUDE.md) for this
stage: 914 insertions, 963 deletions, also net negative.

#### What in the design did not survive contact with the code

- **`test_two_real_objects_stay_two_contacts` does not exist under that name.** The design's §8
  names it as a strict-`xfail` test expected to flip to passing. No such test exists in the
  codebase — the nearest candidates are `test_cross_channel_fusion.py::
  test_two_distinct_nearby_objects_stay_two_contacts` (a different, unrelated fixture, not `xfail`,
  untouched by this stage per the narrowness guard) and `test_mock_flight_chain.py`'s own
  single-threaded test, which *is* the fixture the design's reasoning actually describes (ownship
  700 m MSL, two objects 400 m apart at 500 m) and which changed exactly as predicted. Read as: the
  design's own prediction about *that geometry's behavior* was correct and confirmed by running the
  mock-flight-chain test; the specific test name/marker it expected to find was not.
- **`test_naked_eye_source.py` needed real rework, unanticipated by the design's own §8.** The
  design's test-impact section names `test_clustering.py`, `test_calibration_cluster_merge_
  undercount.py`, `test_mock_flight_chain.py`, `test_contacts.py`'s jitter test, and
  `test_association_over_time.py` — it does not mention `test_naked_eye_source.py` at all. That
  file's cap/debounce/continuity fixtures place multiple simultaneous candidates on the observer's
  exact bearing at the observer's own altitude, which the angular model treats as a genuine
  degenerate case (always merges, any down-range gap) rather than a safe non-clustering-relevant
  spread. Five tests needed geometry changes; all now pass, and the fixes are narrow (an added
  cross-offset, one test's split geometry) rather than a redesign, but this is real, reportable
  scope the design's own blast-radius analysis missed.
- Everything else in the design's §8 (three calibration tests, the mock-flight re-run, the jitter
  `xfail` deletion, the (A) floor's provable slackness, the two-member-cluster theorem, the
  along-LOS altitude sensitivity) matched exactly, including the specific numbers worked in the
  design's own tables (perpendicular adjacent-pair separation ~7.15 arcmin vs. the design's
  ~7.1-7.2 range; along-LOS 200 m AGL extent/unit ratio ~0.65 vs. the design's ~0.66; 1000 m AGL
  ratio ~3.2, `n=4`, `OP_TO5UNITS`, matching the design's own table exactly).

---

## Stage 4b — speech and events (2026-09-19)

Implemented on `feature/group-contact-speech`, branched from `main`. All source edits, no new
files (six pieces per the task, all in existing modules). Verification: `cd body-layer`, its own
venv, `ruff format`, `ruff check`, `mypy src`, `pytest tests -q`.

### Files Changed

- `body-layer/src/belief/speech.py` — `_cardinality_phrase(lo, hi) -> str | None` (reads interval
  magnitude directly, never a `CountBucket` name); `_OP_CLASS_DISPLAY_PLURAL` +
  `_plural_unit_type_display`; `_contact_report_text` gains the guard branch (singular path calls
  the exact same `_unit_type_display` with the exact same arguments, no new code executed);
  `_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"]` entry removed (dead code, see Finding below);
  `_render_lifecycle_text` gains an explicit `CONTACT_CARDINALITY_CHANGED -> None` branch; module
  docstring gains a "Stage 4b -- the count clause" section.
- `body-layer/src/belief/events.py` — `CONTACT_CARDINALITY_CHANGED` added to `EventKind` and as a
  `Final`; `Event` gains `previous_cardinality`/`cardinality: tuple[int, float] | None = None`;
  `cardinality_event(previous, current) -> EventKind | None`, `classification_event`'s flat-
  comparison analogue (no refine/contradict direction, mirrors `attention_event_kind`'s shape).
- `body-layer/src/belief/contacts.py` — `Contact.last_emitted_cardinality: tuple[int, float] |
  None = None`; `tick()` gains a fourth block, wired **lifecycle -> classification -> cardinality
  -> attention**, reusing `EVENT_COOLDOWN_S`/`_cooldown_elapsed` unchanged; `tick`'s docstring
  "Ordering" sentence extended.
- `body-layer/src/belief/tools.py` — `_estimated_units_lower_bound(store) -> int` (see Finding
  below for why it is private, not the design's public `estimated_units_lower_bound`); `get_stats`
  gains `"estimated_units"` as a fourth key; `get_situation` gains `facts["estimated_units"]` as a
  new top-level sibling key, `contact_counts`'s shape untouched.
- `body-layer/src/belief/escalation.py` — `_situational_header` gains `header["estimated_units"]`,
  unconditional (unlike `our_position`, which is gated on `enrichment`); `contact_counts` untouched.
- `body-layer/CLAUDE.md` — Structure section updated for `speech.py`, `events.py` (folded into the
  shared `belief/contacts.py` entry, where `events.py` was already documented), and `tools.py`.

### Test-inventory verification (per process step 1b)

- All 21 names in the design's `test_speech.py` regression-guard list exist verbatim; confirmed by
  direct `grep -n "^def test_"` before touching anything.
- `test_first_tick_with_no_previous_classification_emits_nothing`, `test_same_level_same_value_
  emits_nothing` (design's cited mirror templates), and `test_get_stats_counts_observations_
  contacts_and_events`/`test_get_situation_counts_and_position_summary_with_no_contacts`/`test_get_
  situation_reports_priority_contact_over_watched_and_visible`/`test_situational_header_omits_our_
  position_without_enrichment`/`test_situational_header_includes_our_position_with_enrichment`/
  `test_event_cooldown_suppresses_rapid_reemission_but_not_after_it_elapses` all exist verbatim, as
  the design claimed.
- **Mismatch the design did not name and grep found**: `body-layer/tests/test_console.py::
  test_console_module_contains_no_belief_logic` — a structural check asserting every *public*
  `belief.tools` function name is referenced somewhere in `console.py`'s source, to keep `console.py`
  a thin wrapper. The design's `estimated_units_lower_bound` (public, no leading underscore) broke
  this test immediately, since no `console.py` command was ever meant to call it directly (only
  `get_stats`/`get_situation`/`escalation.py` consume it). Fixed by renaming it to
  `_estimated_units_lower_bound`, matching the established convention `_cardinality_facts`/
  `_classification_facts` already set for tools.py helpers that exist only for other tools.py
  functions to call — not by touching the test. This is exactly the "file the plan forgot" class of
  mismatch the task warned is the dangerous one: a passing suite after the six pieces landed would
  have silently hidden that `console.py`'s own structural invariant had been violated.
- No other test file touching `speech.py`/`events.py`/`contacts.py`/`tools.py`/`escalation.py` was
  affected; grepped for `OP_GROUPSOMETHING`/`render_watch_nearest_readback`/`_contact_report_text`/
  `contact_counts`/`get_stats`/`CONTACT_CARDINALITY_CHANGED`/`last_emitted_cardinality` across
  `tests/` and `src/` — the hits outside the named files (`test_naked_eye_source.py`,
  `test_calibration_cluster_merge_undercount.py`, `test_mock_flight_chain.py`, `test_clustering.py`)
  all reference `OP_GROUPSOMETHING` as a `classification_raw`/`facts["classification"]["value"]`
  string, never as a class-level `_OP_CLASS_DISPLAY` lookup key — confirmed none of them exercise
  the removed dict entry.

### Regression-guard result

**19 of the 21 pre-existing `test_speech.py` tests are byte-identical, zero diff.** One
(`test_render_contact_report_maps_default_op_class_to_display_word`) required a deliberate fixture
change, documented as a finding below, not a silent edit. All 21 pass.

### Finding: the `OP_GROUPSOMETHING` test exercised the "unreachable" state the design argued away

The design's Sec 4 argued `_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"]` was dead code because
`classification._op_class_of` excludes `DEFAULT_OP_CLASS` from ever being returned as a class-level
value through any real resolver path — and explicitly told the implementer to check the two named
tests against this claim, calling a positive hit "a finding about an existing test building an
unreachable state, not a reason to keep the dead entry." Running the regression suite confirmed the
hit: `test_render_contact_report_maps_default_op_class_to_display_word`'s fixture called
`store.ingest` with a raw `Observation` carrying `classification_raw="OP_GROUPSOMETHING"` and
`classification_level=2` ("class") directly — `ContactStore`/`Contact.record` take `Observation.
classification_level` as given, with no `_op_class_of` resolution step in that path at all, so a
hand-built fixture can trivially construct the state the design's argument said only a real
resolver could prevent. Per the design's own explicit instruction, the fixture was corrected to
`classification_level=1` ("presence") — the level `OP_GROUPSOMETHING`/`DEFAULT_OP_CLASS` actually
occurs at in real classification (`classification.PRESENCE_CLASS` is the same string) — rather than
kept at the unreachable level, preserving the test's original intent (a common value maps to a
sensible word, not leaked verbatim) against the level where it actually applies. Expected text
changed from `"group."` to `"ground."`. This is the one place an existing speech test's expected
string changed, and it is not the count-clause leaking into the singular case the task's stop
condition was about — it is the separately-authorized `OP_GROUPSOMETHING` removal, with the design's
own text anticipating exactly this outcome.

### Tests Added

**`test_speech.py`** (14 new, one per design table row/branch plus the attachment-point cases):
`test_cardinality_phrase_singular_is_no_clause`, `test_cardinality_phrase_default_is_several`,
`test_cardinality_phrase_op_to5units_is_a_handful`, `test_cardinality_phrase_lo_16_or_more_is_many`,
`test_cardinality_phrase_fold_derived_non_named_interval_falls_back_to_several`, `test_plural_unit_
type_display_presence_level_is_contacts`, `test_plural_unit_type_display_class_level_in_table`,
`test_plural_unit_type_display_class_level_not_in_table_falls_back_to_raw_value`, `test_plural_unit_
type_display_type_level_is_unpluralized_raw_value`, `test_contact_report_text_with_no_cardinality_
fact_matches_singular_text` (the second half of the regression guard), `test_route_event_contact_
detected_speaks_plural_cardinality_clause`, `test_render_watch_nearest_readback_speaks_plural_
cardinality_clause`, `test_classification_changed_text_omits_count_clause_even_with_plural_
cardinality` (the negative case), `test_route_event_cardinality_changed_has_no_template_and_is_not_
acknowledged`.

**`test_events.py`** (3 new; cooldown suppression left untested per the design's own "optional,
implementer's call" — `_cooldown_elapsed` is already covered generically):
`test_first_tick_with_no_previous_cardinality_emits_nothing`, `test_unchanged_cardinality_emits_
nothing`, `test_cardinality_interval_change_is_contact_cardinality_changed` (both a narrowing and a
widening case).

**Changed, per §6 (the intended breakage, not a regression)**: `test_get_stats_counts_observations_
contacts_and_events`, `test_get_situation_counts_and_position_summary_with_no_contacts`, `test_get_
situation_reports_priority_contact_over_watched_and_visible`, `test_situational_header_omits_our_
position_without_enrichment`, `test_situational_header_includes_our_position_with_enrichment` — each
gained an `estimated_units`/`"estimated_units"` assertion, values derived from each fixture's actual
founding cardinality (all `OP_1UNIT`, since none of those fixtures' observations carry a
`count_bucket`), not guessed.

### Checks

(body-layer/ only touched)
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 34 source files)
- pytest -q: 659 passed (642 baseline + 17 new: 14 in `test_speech.py`, 3 in `test_events.py`)

### Notable Discoveries

- The `test_console.py` structural-invariant mismatch above is the main one — worth generalizing:
  any new *public* `belief.tools` function must either get a real `console.py` caller or be named
  with a leading underscore, regardless of what a design document's prose calls it.
- `_observation`'s test helper in `test_speech.py` had no `count_bucket` parameter before this
  stage; adding it (default `None`, preserving every existing call site's behaviour) was the
  simplest way to found plural-cardinality fixtures without a second helper or bypassing
  `ContactStore.ingest`.
