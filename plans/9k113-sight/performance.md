### Performance Review

Once-per-feature review of `BL-B64` (the 9K113 sight perception entry — Axis A: optics table,
per-optic sigma, Stage 2 dwell/cone wiring, and the Pass 3 `home_phase` fix), whole feature,
immediately before DoD. Branch `feature/9k113-sight`, tip `f3668e8eebc8d10e0ae6e067b739952516691680`
(HEAD matched exactly on an isolated detached-HEAD worktree at that sha — this branch's own worktree
slot was already held by a concurrent Security review, so this review used a second, detached
worktree at the same commit rather than `--ff-only` into the named branch). Tree clean throughout.

This review's job was narrow by design: `plans/9k113-sight/performance-cone-gate.md` already settled
the cone's own cost (4.3 µs/candidate gate chain, cone net cost 0.02–0.11% of a 12.6 ms tick,
APPROVED — build as planned) *before* the cone was wired. Nothing here re-measures or re-litigates
that. This pass checks only what the gate-chain measurement could not cover because the code did not
exist yet: the wired `sight_cone` branch, the restructured `optic_policy.decide()`, the optic-aware
range cap, `look_sigma_m`'s per-optic path, and anything new on the poll body.

### Findings

#### OBSERV-off path costs nothing, confirmed by code reading, not projection
- **Location:** `association.filter_player_bubble` (`body-layer/src/perception/association.py:325-368`).
- **Risk:** none. The `sight_cone` branch (`if sight_cone is None or candidate_range_m >
  sight_cone.depth_m: continue`) only runs for a candidate that has *already* failed the radius
  test, and short-circuits on `sight_cone is None` before any bearing arithmetic. An OBSERV-off tick
  (`sight_cone` always `None`) pays exactly one extra `is None` check per candidate beyond the
  bubble radius — no `bearing_deg` call, no modulo arithmetic, no allocation. This matches the
  pre-wiring projection's own framing of the guard, and the wiring honours it exactly.
- **Action:** informational, confirmed clean. No change needed.

#### `optic.range_cap_m` resolution is an attribute read, not a recomputation
- **Location:** `visibility.tier_ranges` (`visibility.py:594-598`) and `visibility.check_visibility`
  (`visibility.py:881-885`).
- **Risk:** none. Both sites resolve `optic.range_cap_m if optic.range_cap_m is not None else
  NAKED_EYE_RANGE_CAP_M` — a dataclass-field read plus a ternary, sitting directly beside the
  existing `min()` call it feeds. Same order of cost as the code it replaced (a bare constant
  reference); nothing was turned into a per-candidate computation.
- **Action:** informational, confirmed clean.

#### `look_sigma_m`'s per-optic path is a precomputed dict lookup, called once per cluster
- **Location:** `estimation.py:185-190` (`_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`, built once at
  import from the optics' own `fov_half_angle_deg` values) and `estimation.look_sigma_m`
  (`estimation.py:211-224`, `dict.get(optic.name, 1.0)` — O(1)).
  Call site: `naked_eye_source.py:1007`, one call per cluster inside `_build_observation`, not per
  raw candidate.
- **Risk:** none. No per-call allocation, no recomputation of the FOV-ratio derivation (that runs
  once at module import), and the call frequency is unchanged from the pre-`BL-B64` `naked_eye_
  sigma_m` it replaced (same call site, same cardinality — once per cluster per look).
- **Action:** informational, confirmed clean.

#### `optic_policy.decide()`'s restructuring added branch checks, not loop-scaled work
- **Location:** `belief/optic_policy.py:1221` (`decide`), called once per poll (1 Hz today), never
  per candidate.
- **Risk:** none at any realistic density. The new hands-busy check, the `SIGHTING` dispatch, the
  `home_phase`-divergence check added in the Pass 3 fix, and `_decide_sighting`/`_start_glance_away`/
  `_force_observ_off`/`_back_to_home` are all O(1) branch/dataclass-field work — dict lookups
  (`_HOME_OPTIC[state.home_phase]`), `replace()` calls on a small frozen dataclass, and plain
  comparisons. None of it scales with candidate count, contact count, or trace density; it scales
  with the fixed set of `decide()`'s own branches, which the restructuring left at the same order
  (more branches, not more work per branch). This is a poll-frequency cost, not a hot-path-per-item
  cost, and the poll body already has headroom at 1.1 ms median against a 12.6 ms tick.
- **Action:** informational, confirmed clean.

#### One genuinely new poll-body cost, and it is trivial
- **Location:** `src/logger.py:566` and `:574-577` — `decide_optic` is now called with a second
  `is_steady(list(self.attitude_history), rate_limit_deg_s=SIGHT_STEADY_RATE_LIMIT_DEG_S)`
  alongside the existing `is_steady(list(self.attitude_history))` call, doubling the number of
  `list(deque)` copies made per poll from one to two.
- **Risk:** negligible, verified rather than assumed: `ATTITUDE_HISTORY_LEN = 3`
  (`logger.py:1338`) — the deque being copied holds at most 3 `(t_sim, pitch, bank, heading)`
  tuples. A second 3-element list copy, once per 1 Hz poll, is immeasurable against a 12.6 ms tick
  budget. This is the one concrete "new per-request allocation" this review found on the poll path,
  and it does not clear the bar for a required finding — flagged for completeness per the brief's
  item 5, not because it needs action.
- **Action:** informational / no action. If a future entry adds a third `is_steady` threshold on
  the same history, worth passing the materialised list once rather than three times — not worth
  doing for two.

#### `_apply_active_gaze`'s new work (actual-aim split, `SightCone` construction) is correctly guarded
- **Location:** `src/logger.py:877-991`.
- **Risk:** none. `advance_sight_aim` is called only when a look is actively commanded (`decision.
  look_azimuth_deg is not None`), and its Axis-A body is `return desired` — an unconditional
  pass-through, no computation. `SightCone` construction is gated on `optic.regard_azimuth_half_deg
  is not None and updated_state is not None and updated_state.actual_aim_azimuth_deg is not None` —
  three cheap `is not None` checks before one small frozen-dataclass allocation (three floats). Both
  paths run once per poll, never per candidate, and both are `None`/no-op for every optic and every
  poll that isn't actively sighting with a committed aim.
- **Action:** informational, confirmed clean.

#### BL-B49 — unaffected, confirmed by absence
- **Location:** the whole poll body, `logger.run_once`.
- **Risk:** none from this feature. This entry adds no I/O, no synchronous network/DB call, and no
  unbounded iteration to the poll path — every addition above is O(1) relative to candidate count
  and bounded relative to poll frequency. `BL-B49`'s synchronous-stall defect (the dominant
  contributor to the 1 615 ms max tick) is in the enrichment path, which this feature does not touch.
- **Action:** clean negative, stated explicitly per the brief's request.

### Verdict
**APPROVED.** Every focus area the brief named resolves to a clean negative on code reading: the
cone's own cost was already measured and settled before wiring, and the wiring honours the guard the
measurement assumed. The restructured `optic_policy.decide()` adds branches, not loop-scaled work,
and runs at poll frequency (1.1 ms median / 12.6 ms worst tick budget), never per candidate. The
optic-aware range cap and `look_sigma_m`'s per-optic path are both attribute/dict-lookup reads
against precomputed values, not recomputation. The one new allocation found (a second small
`list(deque)` copy per poll, `ATTITUDE_HISTORY_LEN = 3`) is too small to matter and is recorded only
because the brief asked for a clean negative to be stated rather than assumed. No change required;
nothing re-enters Implementer.

### Worktree handoff

- Branch: `feature/9k113-sight`
- Tip sha verified: `f3668e8eebc8d10e0ae6e067b739952516691680`
- Worktree: detached HEAD at that sha (own worktree slot, separate from the concurrent Security
  review's worktree on the named branch)
- Files read/written this pass: `plans/9k113-sight/performance-cone-gate.md`, `plans/9k113-sight/
  plan.md`, `plans/9k113-sight/implementation.md`, `plans/player-bubble/performance.md` (correction
  block at line 42 noted), `body-layer/src/perception/association.py`, `body-layer/src/perception/
  visibility.py`, `body-layer/src/perception/estimation.py`, `body-layer/src/belief/optic_policy.py`,
  `body-layer/src/logger.py`; this file written: `plans/9k113-sight/performance.md`.
