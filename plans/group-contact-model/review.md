### Review Summary

Reviewed Stages 1 (`8ea06b6`) and 2 (`ece33ed`) of `plans/group-contact-model/plan.md`, plus the
docs commit `62d125e`, against the plan's own "Settled Decisions" and the checklist items in the
review request. Ran body-layer's full verification myself (not trusted from the implementation
log): `ruff format --check`, `ruff check`, `mypy src` all clean; `pytest tests -q` → **632
passed**, matching the report.

The headline concern is real and worth stating precisely: the plan's central architectural claim
— "the model's resolution and the channel's resolution are the same number by construction" — is
**false for the specific case of a split child re-merging against its parent contact**, and this
is not a minor edge case, it is a structural consequence of two different formulas the plan itself
built: clustering forms/splits on a **single-sided max** radius, while the belief-layer spatial
gate re-tests on a **double-sided sum** radius plus a growth term. That gap is baked in by BL-2.6's
(correct, load-bearing) symmetric-budgeting fix, not by an unresolved calibration constant. I do
not think this blocks merging Stages 1-2, but it does mean the plan's Stage 3 scope as currently
written (cluster-radius policy, chaining cap, tier→coarseness table) will not close this gap, and
that needs to be said explicitly rather than left implicit in a test comment.

### Required Fixes

- **Stage 3's scope in `plans/group-contact-model/plan.md` must be amended to name the gate/cluster
  radius mismatch as its own work item, not folded silently into "the cluster-radius policy."**
  Worked the numbers by hand and confirmed against `perception/clustering.py` and
  `belief/association_over_time.py`: at the mock-flight fixture's closing range (~690 m),
  `naked_eye_cluster_radius_m(690)` ≈ hypot(690·sin(15°), 100) ≈ **205 m**. Clustering splits two
  candidates when their real separation exceeds `max(radius_a, radius_b)` ≈ 205 m — a single-sided
  test. `spatial_gate_radius_m` re-tests a split child against its parent contact using
  `uncertainty_radius_m(percept) + contact.last_position_uncertainty_m + growth·elapsed_s` — both
  sides' ~205 m summed, so ≈**410 m before any growth term is even added**. Two objects 400 m apart
  therefore clear the cluster-split threshold (205 m) but never clear the gate's re-merge threshold
  (~410 m+). This is not specific to this fixture's numbers: because the gate is definitionally
  `uncertainty_a + uncertainty_b + growth ≥ max(uncertainty_a, uncertainty_b)`, **any split whose
  children sit near the cluster's own resolution boundary — which is the common case, since that's
  exactly when a split first becomes possible — will be re-absorbed by the gate.** Shrinking the
  Stage-3 cluster-radius constant does not fix this: it only moves the point where clusters start
  splitting while leaving the gate's ~2x-wider re-test in place, so the dead zone persists at
  whatever new radius Stage 3 picks. The fix, if one is wanted, has to touch the gate's treatment of
  a percept that is itself a freshly-split cluster member (e.g. not re-summing the parent's own
  cluster-derived uncertainty against a child that clustering has already judged separable) —
  that's a real design decision, not a tuning pass, and Stage 3 as scoped today doesn't cover it.
  Concretely: add one sentence to the plan's Stage 3 bullet naming this as required scope, or split
  it into its own stage, so the eventual sortie is aimed at the right question instead of just
  re-tuning `naked_eye_cluster_radius_m`'s shape.

### Optional Refinements

- `perception/clustering.py` keeps its own literal copy of `_RANGE_BUCKETS_M`/`_CLOCK_BUCKET_DEG`
  rather than importing `naked_eye_source.py`'s copy, to avoid a dependency cycle — disclosed
  candidly in the module docstring, and the right call given the import-direction constraint. Still,
  two independent literal copies of ED's 24-bucket range table now exist in the codebase (one in
  `naked_eye_source.py` for output quantisation, one in `clustering.py` for radius derivation); if
  ED's bucket table is ever revised, both need to change together and nothing enforces that today. A
  shared private constants module (imported by both, imported by neither's current dependent) would
  remove the risk cheaply, but this is not worth blocking on now (optional).
- The physical sanity check requested: 400 m apart at 690 m range subtends ≈32° — almost exactly
  the channel's own 30° clock-bucket width. The single-sided cluster radius (≈205 m, derived
  directly from that bucket width) is therefore an honest model of the channel's own resolving
  power, not an overly pessimistic one. The pessimism, such as it is, comes entirely from the gate's
  double-budgeting for merge decisions, which is a different (also legitimate) concern — avoiding
  spurious duplicate contacts for a slow-moving/stationary single object across polls. Worth stating
  this distinction explicitly in the eventual Stage-3 design note so a future reader doesn't
  conflate "the cluster radius is too generous" (it isn't) with "the gate re-absorbs splits" (it
  does).

### Verification of specific checklist items

1. **Stage 1 no-op claim** — verified via `git show 8ea06b6 --stat`: touches only
   `belief/cardinality.py` (new), `belief/contacts.py`, `belief/decay.py`,
   `tests/test_cardinality.py`. No pre-existing test file is present in that commit's diff. Claim
   holds.
2. **Count ladder vocabulary** — `belief/cardinality.py`'s eight named buckets
   (`OP_1UNIT`…`OP_MORETHAN15UNITS`) match `aircraft-layer/research/2026-09-08-pb1-5-
   worldobjects-filter-and-ambient-detection.md` line 442 verbatim by name. The research doc gives
   names only, not numeric boundaries, so the plan's `(lo, hi)` pairs are a reasonable inference
   from the names themselves (e.g. "TO5UNITS" → (4,5)), not independently confirmed against ED
   internals — this is disclosed nowhere as inferred vs. confirmed, but it's a low-risk inference
   and not worth an investigator pass.
3. **`fold_cardinality` mirrors `fold_classification`** — all four outcomes present and correctly
   shaped (refine adopts incoming, reinforce steps confidence toward `_CONFIDENCE_CEILING`, hold
   returns `held` untouched, contradict collapses to the hull with `confidence=min(...)` and arms
   the lockout). The added "genuine partial overlap → refine to intersection" branch is **not scope
   creep** — it's required by the plan's own decision to keep `OP_TO5UNITS (4,5)`/`OP_5TO7UNITS
   (5,7)`'s boundary overlap "as ED states it" rather than fixing it: without that branch, a count
   of exactly 5 read twice at different confidence would fall through to the disjoint-contradiction
   branch (since neither interval contains the other), incorrectly arming a lockout and flooring
   confidence on two claims that actually agree. Necessary, not gratuitous.
4. **No new tunable for cluster radius** — confirmed `naked_eye_cluster_radius_m` exists only in
   `perception/clustering.py`; `belief/association_over_time.py` no longer defines
   `_naked_eye_uncertainty_m` and imports the moved function instead (`grep` for
   `_naked_eye_uncertainty_m`/`_CLOCK_BUCKET_DEG` outside `clustering.py` turns up nothing in
   `belief/`). Import direction is legal (`belief` importing `perception`, same direction
   `association_over_time.py` already used for `naked_eye_source` constants).
5. **Stage 0 veto removal** — confirmed gone from `association_over_time.passes_gate`; the
   module docstring explains why removal is correct now that naked-eye emits per-cluster, not
   per-object.
6. **Majority-overlap continuity, determinism** — `_build_observations`' two-pass algorithm
   (global majority-owner resolution before minting any cluster's `continues_observation_id`)
   is present and does prevent two children of one split from both inheriting the parent's
   continuity. Tie-breaking is genuinely deterministic, not dict/set-iteration-order-dependent:
   `top_id = max(sorted(votes), key=...)` sorts historical ids lexicographically before taking
   `max`, so ties resolve to the lexicographically smallest id, and `winner_index_for_id` ties
   resolve to the lowest cluster index via strict `>` comparison in ascending-index iteration
   order. Cluster order itself is deterministic given deterministic candidate input order (dict
   insertion order in `cluster_candidates`, following `to_emit`'s own deterministic ordering).
7. **`WorldEnrichmentCache`** — keyed by `contact_id`, invalidates on structural inequality of
   `Contact.last_position` (a frozen dataclass). Clustering changes what `last_position` means
   (now a cluster centroid) but doesn't change the cache's invalidation contract — it will simply
   invalidate somewhat more often as centroids shift with cluster membership, which is a
   correctness-safe cost, not a broken assumption.
8. **Twelve-object results** — reran the suite myself: `test_twelve_unit_cluster_at_9km_becomes_
   one_contact_with_a_plural_count` asserts `cluster.count_bucket == "OP_ABOUT15UNITS"` for
   `count_bucket_for(12)`, correct per the non-overlapping selection table (12 ≤ 15, > 10, so
   `OP_ABOUT15UNITS`; not an off-by-one). The close-range test asserts 6 clusters, member counts
   `[1, 1, 2, 2, 3, 3]` summing to 12, and 6 contacts with matching `(lo, hi)` cardinality pairs
   `[(1,1), (1,1), (2,2), (2,2), (3,3), (3,3)]` — matches the reported figures exactly, verified by
   reading the test and by the passing suite run.

### Verdict

APPROVED WITH MINOR FIXES

The Stage 1/2 mechanism is sound, correctly scoped (Stage 1 genuinely a no-op, Stage 2 genuinely
fixes the reported false-merge defect for the twelve-object case), and honestly documented,
including the one thing I pushed hardest on. The chain-test behaviour (`test_mock_flight_chain.py`
not splitting into two contacts) is **acceptable to merge as-is** — it is a real, disclosed
boundary case, not a silently-swept regression, and the underlying mechanism (cardinality hedging
via hold/contradict rather than a confident false merge or a premature false split) is strictly
better than pre-existing behaviour. The one required fix is a documentation-level correction to
`plans/group-contact-model/plan.md`'s Stage 3 scope, not a code change: name the gate-vs-cluster
radius structural mismatch explicitly as something Stage 3 must address, since the currently-listed
Stage 3 items (cluster-radius policy, chaining cap, tier→coarseness table, per-cluster
`NAKED_EYE_MAX_NEW_PER_POLL`) do not touch the gate formula and will not close this gap by
themselves.

### Review Confidence

Full read — read the plan, implementation log, prior debug report, all touched source files
(`clustering.py`, `association_over_time.py`, `cardinality.py`, `contacts.py`'s cardinality
wiring, `naked_eye_source.py`'s `_build_observations`, `enrichment.py`'s cache), both new test
modules in full, verified the Stage 1 no-op claim against `git show --stat`, and ran the full
body-layer verification suite myself rather than trusting the reported numbers.
