### Performance Review

Batch reviewed: BL-B89 Stage 1 (9K113 sector scan), `feature/9k113-scan-procedure`, tip
`4c9d23212539f4ea89e3a312412f4066c0e1641d`. Budget: body-layer's 1.0 Hz poll loop
(no hard real-time requirement yet, but per-poll work should stay well clear of the 1 s period —
see `[[project_body_layer_poll_loop_diagnosis]]`). Single-user, LAN-only project; proportionate
depth.

### Findings

#### `choose_sighting_look` (new, `optic_policy.py`) — delegates to pre-existing O(n²) `choose_look`

- **Location:** `optic_policy.choose_sighting_look` → `optic_policy.choose_look`'s `covered()`
  closure, called once per poll from `_decide_sighting` whenever `worth_looking` is non-empty.
- **Mechanism:** buckets `targets` by `current_level` (`"class"` before `"presence"`) in one O(n)
  pass, then runs `choose_look` — O(k²) in the bucket size — on only the highest-priority
  non-empty bucket. This is a *narrower* call than before this stage (`choose_look` was already
  being fed `sight_can_still_improve`'s wider window by the prior `9k113-narrow-search` work,
  documented in `[[project_9k113_search_and_choose_look_scaling]]`); bucketing can only shrink the
  O(k²) term's `k`, never grow it, since it is always a subset of the same `targets`.
- **Measured** (`body-layer/.venv`, synthetic `LookTarget`s, this review):

  | n (total targets) | class-bucket fraction | `choose_look` (old path) | `choose_sighting_look` (new path) |
  |---|---|---|---|
  | 5 | 0.5 | 10.0 µs | 2.9 µs |
  | 20 | 0.5 | 131 µs | 36 µs |
  | 55 | 0.5 | 962 µs | 241 µs |
  | 100 | 0.5 | 3.20 ms | 0.81 ms |
  | 200 | 0.5 | 12.74 ms | 3.24 ms |
  | 200 | 0.9 (worst case: nearly everything in one bucket) | 12.59 ms | 10.25 ms |
  | 200 | 0.1 | 12.66 ms | 0.15 ms |

  At this project's largest **recorded** sortie scale (55 total contacts,
  `[[project_optic_policy_dict_copy_cost]]`), the new path costs ~241 µs/poll — 0.024% of the
  1 s budget, and *cheaper* than the pre-existing `choose_look` call it replaces at every split
  tested except the pathological 90/10 skew, where it is still comparable (10.25 ms vs 12.59 ms,
  both ~1% of budget).
- **Risk:** none at today's scale. The theoretical worst case — all `worth_looking` candidates
  in a single bucket, at a scale the sight's own ±60° regard cone makes geometrically unlikely to
  fill (per the existing memory on `choose_look`) — costs on the same order as the pre-existing,
  already-accepted `choose_look` O(n²), not a new order of growth.
- **Action:** MONITOR. Same disposition as the pre-existing `choose_look` O(n²) it wraps — not
  a regression, just inherits the existing ceiling. Re-measure if a future change further widens
  `SIGHTING`'s candidate window (another optic, a relaxed threshold) or make `choose_sighting_look`
  itself spatially-pruned, same remediation path already on file for `choose_look`.
- **Mitigation (if ever needed):** none required now; if it is, prune by azimuth bucket before
  the O(k²) pass — an Architect question, not a thing to improvise, per the existing memory note.

#### Per-poll sector-sweep generation (`body.py`: `_sight_in_regard_sweep` ×3 legs, `_sight_out_of_regard_sweep` ×1)

- **Location:** `body.py`'s poll-loop call site (around line 736), computing
  `sight_wide_near_search`/`sight_wide_far_search`/`sight_narrow_far_sweep_search`/
  `sight_out_of_regard_search` unconditionally every poll, each delegating to
  `optic_policy.search_pattern` (unmodified by this stage) + `_to_body_relative_steps`'s per-step
  rotation.
- **Mechanism:** identical in kind to the four-sweep unconditional-computation pattern already
  measured in `[[project_9k113_search_and_choose_look_scaling]]` (15.85–26.37 µs/poll, later
  re-measured at ~495.8 µs/poll worst case after the boresight-rotation change) — this stage
  renames the legs and changes band-edge *values* (`SIGHT_SEARCH_NEAR_M`, new
  `SIGHT_SEARCH_WIDE_MID_M`/`SIGHT_SEARCH_WIDE_FAR_M`) but does not touch `search_pattern` or
  `_to_body_relative_steps` themselves, and the call count stays at four computations per poll
  (three in-regard legs + one out-of-regard, same as the prior wide/narrow-near/narrow-far/
  out-of-regard count). Step counts remain hard-bounded by `fov_full_width_deg` and sector span,
  same bound as before.
- **Risk:** none — same mechanism already measured negligible (≤0.05% of budget worst case), and
  this stage changes only the geometry inputs, not the per-step cost or the number of per-poll
  calls.
- **Action:** MONITOR (inherits the existing disposition; no new measurement needed since neither
  the algorithm nor the call count changed).

#### `_sight_commanded_sector` / `_commanded_or_default_sector` / `SIGHT_AHEAD_LEGS` alternation (`body.py`, `gaze.py`)

- **Location:** `body._sight_commanded_sector`, called once per poll ahead of the four sweeps
  above.
- **Mechanism:** a handful of dict lookups, one `int(ownship.t_sim // SIGHT_AHEAD_WINDOW_DWELL_S)
  % len(...)` arithmetic op, and (on the single-o'clock-hour branch) a call into the existing
  `_gaze_for_clock_hour`. No iteration over contacts or world state.
- **Risk:** none — O(1), no allocation beyond a returned tuple.
- **Action:** none needed.

#### `OpticState`'s per-contact dict growth (pre-existing pattern, not changed by this stage)

- **Location:** `attempted_at_level`/`attempted_at_range_m`/`attempted_at_time_sim`/
  `pending_attempted_at_*` — unmodified by this stage.
- **Risk/Action:** out of scope for this review — already tracked as MONITOR in
  `[[project_optic_policy_dict_copy_cost]]` (memory growth, not per-poll CPU, Security's
  territory). Confirmed by reading the diff that this stage adds no new per-contact dict.

### Verdict

APPROVED — MONITOR (no change from this stage's predecessor's own disposition; nothing here
crosses from negligible into material at this project's recorded or realistically-projected
scale).
