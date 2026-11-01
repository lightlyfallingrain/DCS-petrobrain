### Performance Review

Batch reviewed: `feature/relative-distance-grouping` (BL-B108), Stages 0-5 plus the review
follow-up (cross-optic `xfail` fix) plus the 2026-11-01 amendment (Stages A-D, the tiered-field
cross-optic model). Tip `f8629e468e567d1129cc65292d6a4b5b886d9a4a`, fast-forwarded cleanly from
`d299dd52` (this worktree's prior HEAD).

Scope, per the dispatch: per-poll hot paths at 1 s polls, realistic scale (tens of contacts, a
few hundred world objects) — `perception/estimation.py`, `belief/position_belief.py`,
`belief/association_over_time.py`, `perception/group_salience.py`,
`mission_memory/admission.py`. Measured directly against the body-layer venv
(`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python`, worktree source on `sys.path`), not
estimated.

**Budget context (no hard real-time budget in this phase, per root `CLAUDE.md`):** the only
committed numbers are BL-11's own measured baseline — poll work median **12.6 ms**, p90
**98.6 ms**, against a 1.000 s poll period (`[[project_bl11_measured_outcome]]`, this role's own
memory). That figure predates `BL-B108` and is the closest thing to a working reference for "is
this noticeable," not a budget this feature is held to.

### Findings

#### `perception.estimation._tiered_field` / `_stable_fraction` — real, measured, linear per-cluster cost

- **Location:** `perception/estimation.py`, `_tiered_field` → `_field_value` (the `_FIELD_FOURIER_K
  = 256` random-Fourier-feature loop), reached from `_stable_fraction` (2 calls: `z_view`, `z_near`),
  reached from `perturbed_bearing_range` (air clusters, 1×) and `surface_range_estimate` (ground
  clusters, 2×: cue A + cue B). Called once per cluster, every poll, for every currently-visible
  cluster (`naked_eye_source._build_observation`, `emit_mode="every_poll"` — the only mode
  `body.py`'s crew pipeline uses), not only newly-admitted ones.
- **Measured** (this worktree's venv, harness in
  `/private/tmp/.../scratchpad/perf_probe_estimation.py` and `perf_probe_optics.py` — can-this-
  harness-fail probe included: a `+0.5 ms`/`_field_value`-call injection visibly moved the
  reported figure before being removed):

  | optic (ladder tier depth) | ms / air cluster (`perturbed_bearing_range`) |
  |---|---|
  | `unaided` (4 tiers — **the default optic**) | **0.86** |
  | `binocular` (3 tiers) | 0.57 |
  | `sight_wide` (2 tiers) | 0.38 |
  | `sight_narrow` (1 tier) | 0.19 |
  | `scope` (outside ladder, flat field) | 0.22 |

  Ground clusters pay **2×** this (`surface_range_estimate`'s cue A + cue B), measured
  **1.63 ms/cluster at `unaided`**. Linear in cluster count (confirmed at n=10/50/200: 0.773 /
  0.764 / 0.764 ms/cluster — no cache benefit kicks in across clusters, and none should: the
  `functools.cache` on `_field_frequencies` amortises only the frequency-*table generation*
  (keyed on `(field_name, optic_class, length_scales, salt)`), not the per-call evaluation, which
  depends on `coords` — true bearing/range — and is never the same twice across real clusters.
  The review's own "worth that role's own look at cache-key cardinality" concern
  (`review.md` round 1, Optional Refinements) is answered: cache-key cardinality is not the
  issue, because the cache was never meant to amortise the per-call trig sum in the first place.

- **Why `unaided` is the worst case, and that is not an edge case.** `_tiered_field` sums one
  `_field_value` call (256 cosines) per ladder tier with `k_tier <= k_o`. `UNAIDED_OPTIC` has the
  largest `k` (1.0), so it is the tier that includes every other tier beneath it — 4 `_field_value`
  calls per `_tiered_field`, 8 per `_stable_fraction` (`z_view` + `z_near`), 16 per ground cluster
  (cue A + cue B). And `body-layer/CLAUDE.md`'s own invariant is "the default optic is
  `UNAIDED_OPTIC`, not binoculars" — so the most expensive tier depth is also the one Petrovich is
  in for most of a sortie, not a rare raised-binoculars case.
- **At realistic scale** (prompt's own framing: "tens of contacts"), unaided, mixed air/ground:
  30 clusters (20 air + 10 ground) ≈ 20×0.86 + 10×1.63 ≈ **33.5 ms/poll** added by this one code
  path alone, that did not exist pre-`BL-B108` (the old model was an O(1) table lookup + a
  never-redrawn hash-derived bias — no field evaluation at all). At 50 clusters, ≈ 55 ms. This is
  **not** quadratic and **not** a redundant-work pattern (one call per cluster, as the module's own
  "a group is ranged once" design states) — it is a genuine, deliberate increase in *per-call* cost
  for a real accuracy requirement (`_FIELD_FOURIER_K = 256`, measured and justified in
  `implementation.md` finding 5: 16-32 draws left realised variance 0.5-1.5× of target; 256 holds
  every optic class within the plan's declared ±10%).
- **Risk, stated plainly:** at "tens of contacts" this adds roughly 2-4× BL-11's own 12.6 ms
  median poll-work baseline, in a subsystem (perception estimation) that was previously close to
  free. It does not threaten the 1.000 s poll period at any contact count this project's own
  envelope produces (even "a few hundred world objects" collapses to a much smaller clustered
  count by the time it reaches this code — BL-11's own in-bubble *candidate* median was 232 at 440
  objects, and clusters are fewer still), and the dominant poll cost remains elsewhere
  (`describe_position` at 57-85 ms/call, per `[[project_bl11_measured_outcome]]`) — so this is not
  a budget violation today. But it is the first non-O(1) math on this particular hot path, it
  scales linearly with however many clusters a scene produces, and nothing bounds that count the
  way `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` bounds *new* admissions per poll (every *already-tracked*
  cluster is still re-perturbed every poll, uncapped).
- **Action:** MONITOR. Not a NOW fix: the cost is deliberate, already measured and justified by the
  implementer (K=256 is a quality tradeoff, not an oversight), stdlib-only numpy-free vectorisation
  is not available under this subproject's dependency policy, and no committed budget is crossed.
  Re-measure if either (a) a future change raises typical cluster counts well past "tens" (a dense
  multi-group furball), or (b) Petrobrain Runtime's own hard real-time budget is set — at that
  point this is the first place to re-check, not re-discover.
- **Mitigation, if ever revisited (not requested now):** `_ladder_sorted()` is called fresh inside
  every `_tiered_field` call (a 4-element dict sort, allocated each time) even though the ladder's
  `k` values are fixed for the process's whole life once `tuning.real` resolves at import
  (`body-layer/CLAUDE.md`'s own "Tuning" section: import-time resolution, no mid-sortie reload).
  Memoising it the same way `_field_frequencies` already is would save a small, fixed per-call
  overhead — but this is noise next to the 256-cosine trig sum itself (confirmed by the measured
  numbers above: the per-tier cost scales almost exactly with tier count, not with any constant
  per-call overhead), so it is not worth a change-request on its own.

#### `perception.group_salience` Stage 3 along-line check — cheap, correctly short-circuited

- **Location:** `_cohesive_from_terms`, reached from `group_salient_ids`'s O(n²) pair loop (n =
  resolvable candidates, pre-existing shape, bounded by BL-11's own measured in-bubble counts).
- **Risk:** none credible. The new along-line test (`look_sigma_m` call + arithmetic, no field
  evaluation) only runs **after** the pre-existing, cheaper angular test already passed
  (`if theta_sep > ...: return False` precedes it) — the same short-circuit-before-expensive-work
  shape this role's own memory already flags as the right pattern here
  (`[[project_belief_los_call_pattern]]`). `look_sigma_m` itself is two dict lookups and
  arithmetic, not a field call. This role's own prior measurement of the whole pair loop
  (`[[project_group_salience_hoist_residual]]`: 1.1 ms median / 5.5 ms max in situ at realistic
  in-bubble counts, saturating around 232-440 candidates) is not meaningfully moved by an O(1)
  addition gated behind an already-cheap filter.
- **Action:** none.

#### `belief.position_belief` / `belief.association_over_time` — pure closed-form, no field evaluation

- **Location:** `correlated_innovation`, `_apply_floor`, `_down_variance_along`, `passes_gate`'s
  hypothesis-scaling.
- **Risk:** none credible. Every one of these reads `stable_range_correlation`/
  `view_range_correlation`/`optic_range_correlation` — closed-form outputs of
  `perception.estimation`'s model parameters, never a field realisation. `optic_range_correlation`
  is two dict lookups and a `min`/`max`. `passes_gate`'s added hypothesis-scaling allocates one
  extra `PositionUncertainty`/`Covariance2D` per candidate pair, the same small-dataclass pattern
  already used throughout this module — no new allocation *class*, same per-pair O(1) shape as
  before `BL-B108`. This is exactly what the module docstring claims ("the only place `belief/`
  learns how two looks' down-range errors correlate... never a field realisation") — verified by
  reading every call site, not assumed from the docstring.
- **Action:** none.

#### `mission_memory.admission` — gate removal, not a hot-path shape change

- **Location:** `_maybe_write_entry_for_contact`'s dropped `nameable` gate (Stage 4).
- **Risk:** none credible on the performance axis. This widens *which* contacts qualify for a
  memory write (presence-level contacts now included, not just `CLASS`-or-above), which is a
  correctness/behaviour change, not an iteration-pattern or allocation change — the call is still
  once per contact per poll (pre-existing shape), still gated by `GROUP_ENTRY_CONFIDENCE_FLOOR` and
  the existing material-change check before an actual write. The only consequence is a modest
  increase in the long-run row count of the append-only mission-memory log over a sortie (more
  contacts now ever get a first entry) — not a per-poll cost concern, and in line with the
  project's own append-only, never-pruned design for this store.
- **Action:** none.

### Verdict

APPROVED — MONITOR

The one real finding (`_tiered_field`'s per-cluster cost) is a deliberate, measured, bounded
cost increase on a hot path that was previously near-free, not a defect. It does not cross any
committed budget today — BL-11's own 1.000 s poll period has wide headroom even at the dense end
of this prompt's own stated scale, and the poll's dominant cost remains elsewhere. Flagged for a
future re-check rather than a change request now, per this project's "do not block work on
hypothetical problems" instruction and the explicit absence of a hard real-time budget in this
phase.
