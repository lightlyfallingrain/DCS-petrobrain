### Performance Review

Reviewed `BL-B58` option 2 / `BL-B59` (bounded fold displacement) on
`fix/bl-b59-retention-hysteresis` at `078232b`, against the BL-11 baseline (12.6 ms median
work/poll, 1.000 s realised period) and BL-12's own measured full-`reconcile` numbers
(`plans/group-contact-identity/performance-review.md`). Single-user, LAN-only, 1.0 s poll budget
— no hard real-time constraint yet.

### Findings

#### `position_belief.clamp_fold_displacement`

- **Location:** `body-layer/src/belief/position_belief.py:652-701`. A pure function, two identity
  branches (`max_displacement_m is None` or `prior is None`), one `hypot` plus comparison in the
  common within-bound case, one more constant-time rebuild only when the bound actually binds.
- **Measured** (`plans/bounded-fold-displacement/scratchpad/probe_perf.py`, 5,000–20,000 calls
  each, can-this-harness-fail probe passed first — a deliberately slower 50×-rebuild shape
  measured 35.17 µs against the shipped 0.167 µs, >200× separation, so the harness is sensitive
  enough to trust): identity branch 0.083 µs, within-bound no-op 0.167 µs, past-bound (the
  rebuild path) 0.917 µs. All three are O(1) and sub-microsecond.
- **Risk:** none at any contact count this project will see. Even a (synthetic) scene where every
  tracked contact folds past its bound on the same poll — 60 contacts, BL-12's own stress scale —
  costs `60 × 0.917 µs ≈ 0.055 ms`, under 0.5% of the 12.6 ms budget.
- **Action:** MONITOR (nothing to fix; recorded as the measurement a future change should be
  checked against).

#### `Contact.record`'s new `ambiguous_fold` path

- **Location:** `body-layer/src/belief/contacts.py:525-593`. Adds one arithmetic expression
  (`max_displacement_m = growth_rate_mps * max(0.0, elapsed)`) and one call to
  `clamp_fold_displacement`, both gated behind the existing `growth_rate_mps` the function
  already resolved pre-plan for `fold_position`/`clamp_to_detection_envelope` — **no new call to
  `contact_growth_rate_mps` or `object_model.profile_for`, confirmed by reading `record`'s body**:
  the variable at line 564 is the one line 587 reuses.
- **Measured:** `record(percept)` (unambiguous) median 12.08 µs; `record(percept,
  ambiguous_fold=True)` median 12.17 µs — **delta 0.083 µs**, i.e. exactly the identity-vs-bound
  branch cost measured above, and two orders of magnitude below `record`'s own ~12 µs baseline
  (which is dominated by classification fusion and the position fuse itself, both pre-existing).
- **`object_model.profile_for`'s cache**: verified doing its job by construction rather than
  re-measured — this feature adds no new call site to it at all, so the existing 0.04 µs/call
  cached cost (`body-layer/research/2026-10-05-performance-review.md` finding 1) is unchanged.
- **Risk:** none. The fold branch itself (`len(passing) >= 2` in `ContactStore.ingest`) is already
  the rare, already-expensive path BL-B58's own docstring calls out; this plan adds one
  sub-microsecond call to it.
- **Action:** MONITOR.

#### `GroupStore.reconcile`'s trace gains `fold_budgets`

- **Location:** `body-layer/src/belief/groups.py:1482-1497` (phase 1–3 path; not added to the
  `"expired"` phase record at `:1528`). `trace_records` is built **unconditionally** inside
  `reconcile`, same as every other field on that record — this was already BL-12's own design,
  not something this plan introduced; `fold_budgets` is one more list comprehension per cluster
  (`[round(contact.fold_displacement_m, 1) for cid in sorted(cluster)]`), O(cluster size).
- **Measured, default path (no `--group-trace`)**: reran `plans/group-contact-identity/
  scratchpad/probe_bl12_perf.py` unmodified against the merged tree at `078232b` —
  - typical sortie tick (12 contacts/4 clusters): full reconcile median **0.103 ms** (BL-12's own
    baseline: 0.100 ms)
  - busy tick (30/8): **0.296 ms** (BL-12: unmeasured at this exact scale, consistent)
  - stress (60/15): **1.377 ms** (BL-12's `_cluster_contacts` alone was 1.170 ms at this scale)
  No measurable regression — the `fold_budgets` list comprehension is inside noise.
- **Measured, `--group-trace` on**: `reconcile(..., trace_sink=writer.write)` at 4 clusters:
  median **0.287 ms**, delta over the no-sink path **0.182 ms** — against BL-12's own prior
  measurement of 0.266 ms / 0.166 ms delta for the same scene *before* `fold_budgets` existed.
  The ~0.016 ms difference is consistent with `round()` + one extra list-of-pairs allocation per
  cluster, not a new order of magnitude, and both numbers sit at ~2% of the 12.6 ms budget even
  at the busiest scale BL-12 measured (15 clusters: ~0.5 ms of synchronous trace I/O, unchanged
  finding from BL-12's own review).
- **Action:** MONITOR, same verdict BL-12's own review reached for this writer (`GroupTraceLogWriter`
  is default-off, a true no-op without the flag, and immaterial even on — nothing new to flag
  because `fold_budgets` did not change that picture).

### Scaling

Nothing added by this feature is worse than O(1) per fold (`clamp_fold_displacement`) or O(cluster
size) per trace record (`fold_budgets`, already the shape every other trace field has). The
feature changes no loop bound, no per-tick full-dataset iteration, and introduces no new
`profile_for`/`contact_growth_rate_mps` call site. `_cluster_contacts`'s own O(n²)-in-contacts
shape (BL-12's, pre-existing, already reviewed) is untouched — this plan's diff is confined to
`contacts.py`'s fold branch, `position_belief.py`'s new pure function, and one trace field.

### Per-poll delta against the 12.6 ms baseline

Negligible and within measurement noise at every scale tested (12–60 contacts, 4–15 clusters):
sub-microsecond per fold, ~0.003 ms per cluster for `fold_budgets` when `--group-trace` is on,
zero when it is off. No change to the 12.6 ms median or the 1.0 s realised period is expected or
measurable.

### Verdict

APPROVED
