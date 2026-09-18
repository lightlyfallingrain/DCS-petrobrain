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
