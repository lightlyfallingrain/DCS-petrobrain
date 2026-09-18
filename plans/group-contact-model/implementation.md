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
