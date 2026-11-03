### Performance Review

Batch: BL-B110 Stages 0a, 0, 1 (`feature/expected-area-check`, tip `20de6ab1`, fast-forwarded into
this worktree from `c588a88d`). Budget: body-layer's 1.0 Hz poll loop
(`project_body_layer_poll_loop_diagnosis` memory — the real default is 1.0 s, not the stale 5 Hz
docstring figure; `logger.py`/`body.py` sleep *after* the work, so realised period is work +
interval). No hard real-time budget this phase (Petrobrain Runtime has not started) — the question
is whether this batch's hot-path additions could push the realised poll period noticeably above
1.0 s at realistic contact counts (dozens; this project's largest recorded sortie is 55).

### Scope read

New/changed hot-path code, all exercised once per poll from `ConsolePerceptionRunner.run_once`:

- `body._resolve_sector_scan` (new, called once/poll)
- `perception.geometry.sector_runs_for_legs`/`n_sectors_for_legs` (new; called once/poll via the
  above, for the free-scan case)
- `perception.gaze.sector_azimuth_span_deg`/`sector_legs_for`/`gaze_at`'s extended branch (new/
  extended; called once or twice/poll)
- `belief.optic_policy.choose_glass_look`, `_within_sector`, `_glass_budget_admits_look`,
  `_rolled_glass_window`, `_advance_sector`, `_start_glass_look`, `_glass_can_improve` (new; called
  from `_decide_without_guidance`, once/poll, each touching the per-poll target list)
- `belief.optic_policy.location_gain_for` (new; called once per live contact, inside
  `look_target_for`, inside `body._look_targets`)
- `belief.position_belief._apply_floor`'s new `prior_inflated_covariance` cap (one extra `min`,
  per fold — fold frequency unchanged by this batch)
- `belief.decay.py`'s new I2 assert, `tuning._check_scan_decay_coupling`'s 5-key/2-invariant
  extension — both import-time only, not on any per-poll path

### Findings

#### `location_gain_for` / `look_target_for` — new per-contact cost in `_look_targets`
- **Location:** `belief/optic_policy.py:location_gain_for`, called from `look_target_for`, called
  once per live contact from `body._look_targets` (unchanged call site, pre-existing O(n) over
  `store.contacts`).
- **Risk:** a per-poll, per-contact computation that is new to this batch — `profile_for` lookup
  (already `@cache`d, confirmed present at `object_model.py:558`), `apparent_extent_m`,
  `distinctiveness_of`, `tier_ranges`, one `PositionEstimate.range_uncertainty_m` call, one
  `look_sigma_m` call. Measured directly in this worktree (`body-layer/.venv`, real production
  functions, not a synthetic stand-in): **1.92 µs/call** for `location_gain_for` alone, **5.75
  µs/call** for the whole `look_target_for` build (up from the pre-batch ~4.1 µs/contact figure in
  `project_9k113_search_and_choose_look_scaling`, i.e. this batch adds roughly 1.6 µs/contact on
  top of the existing cost). At this project's largest recorded sortie (55 contacts) that is
  **0.32 ms/poll** total; at a generous 200-contact stress case, **1.15 ms/poll**. Both are three
  orders of magnitude under the 1.0 s budget.
- **Action:** MONITOR. Linear in contact count and already cheap per the measurement above —
  consistent with every prior per-contact-cost finding in this subsystem's memory
  (`project_optic_policy_dict_copy_cost`, `project_9k113_search_and_choose_look_scaling`). No
  mitigation needed now; re-measure only if contact-count assumptions change materially (this
  project's own stated scale ceiling).
- **Mitigation:** n/a — no action required at current scale.

#### `choose_glass_look` inherits `choose_look`'s pre-existing O(n²), fed a sector-filtered subset
- **Location:** `belief/optic_policy.py:choose_glass_look` → `choose_look`'s `covered()` closure,
  called from both the `GLASSING` continuation branch and the `SCANNING`-at-home dispatch in
  `_decide_without_guidance`.
- **Risk:** `choose_look`'s O(k²) coverage closure is unchanged by this batch (not touched by the
  diff) — already measured and carried forward as a MONITOR item in
  `project_9k113_search_and_choose_look_scaling` (18.75 µs @ k=5 up to 27.66 ms @ k=200). What this
  batch changes is the *candidate set* `k` is drawn from: `_within_sector` filters `targets` down
  to the swept sector's own wedge (widened by half a binocular field — `body.py`'s
  `_SECTOR_MARGIN_DEG`) before `is_worth_a_look`/bucketing run, so `k` here is bounded by *one
  sector's* worth-looking contacts, not the whole live-contact list — strictly narrower than the
  unsectored pre-Stage-1 candidate set, never wider. No credible path to this batch increasing the
  quadratic term's practical `k` beyond what was already reviewed as negligible.
- **Action:** MONITOR (inherits the pre-existing disposition; this batch does not add new exposure
  here, and narrows it if anything).
- **Mitigation:** n/a.

#### `sector_runs_for_legs(SCAN_PLAN)` recomputed unconditionally every poll in the free-scan branch
- **Location:** `body._resolve_sector_scan`, free-scan path (`scan_plan.commanded_sector is None
  and scan_plan.commanded_legs is None`).
- **Risk:** `SCAN_PLAN` is a module-level constant (never mutated at runtime) partitioned into the
  same sectors every single poll that free-scan is active — this is precomputable work done
  per-poll instead of once. Measured directly: **1.07 µs/call** against `SCAN_PLAN`'s real length
  (8 legs). At 1.0 Hz this is 0.0001 % of the poll budget — genuinely negligible at this project's
  table sizes, and not worth a cache-invalidation mechanism for a microsecond.
- **Action:** MONITOR, not NOW. Flagged because it is a textbook "precompute instead of
  per-request" case and costs nothing to note, not because the measured cost is a real risk. Would
  become worth a `@lru_cache`/module-level constant only if `SCAN_PLAN` ever grew by two or three
  orders of magnitude, which this project's own o'clock-hour table structure makes implausible.
- **Mitigation (if ever revisited):** hoist to a module-level constant computed once at import
  (`_FREE_SCAN_SECTORS: Final = sector_runs_for_legs(SCAN_PLAN)`), mirroring how
  `SCAN_CYCLE_PERIOD_S` is already derived once at import rather than per-poll. Not required now.

#### `position_belief._apply_floor`'s new cap — no new per-poll cost
- **Location:** `belief/position_belief.py:_apply_floor`, `fold_position`'s call site.
- **Risk:** none credible — one additional `min()` against a covariance trace already computed by
  the fuse (`prior_inflated_covariance` is passed in, not recomputed), at the same fold frequency
  as before this batch. No new allocation, no new iteration.
- **Action:** none (confirmed non-issue, included for completeness since it was named in the
  review scope).
- **Mitigation:** n/a.

#### Import-time-only additions (`decay.py` I2 assert, `tuning._check_scan_decay_coupling`'s 5-key extension)
- **Location:** `belief/decay.py`, `tuning.py`.
- **Risk:** none — both run once at module import, never on the poll path. Confirmed by reading
  both call sites; not re-measured, since import-time cost is explicitly out of this role's remit
  (startup, not runtime).
- **Action:** none.
- **Mitigation:** n/a.

### What was and was not independently measured

Measured directly in this worktree (`body-layer/.venv`, real production functions, no mocks):
`location_gain_for`, `look_target_for`, `sector_runs_for_legs`. Not re-measured: `choose_look`'s
O(n²) (carried forward from `project_9k113_search_and_choose_look_scaling`'s existing figures,
since this batch does not touch that function and only narrows its candidate set) and
`gaze_at`'s new `sweep_legs`/`sweep_started_sim` branch (read in full — a modulo-free index
computation, the same cost class as the pre-existing branches beside it, O(1) per call; not
separately timed because its shape is identical to branches whose cost was never the issue).

### Verdict

APPROVED — MONITOR
