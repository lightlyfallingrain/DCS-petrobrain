# Performance Review — atgm-run-sight-tracking

Branch `fix/atgm-run-sight-tracking`, tip `5794a105`. Reviewed via literal-sha diff against
merge-base `a0e8bf11` (body-layer/src only); measured in an isolated `git archive` snapshot
(body-layer @ 5794a105 + world-model @ main) with the body-layer venv. Budget context: no hard
real-time budget yet (root `CLAUDE.md` scope); the bar is "no per-poll cost that scales badly".

### Performance Review

What is new on the per-poll path, classified by frequency:

| change | frequency | scaling |
|---|---|---|
| `_look_targets` → `_look_target_position` (`remembered_target_alt_m` + one `dataclasses.replace` of `GeoPosition`) | every poll | O(contacts in store) — the loop already existed; this adds a constant per contact |
| `_sight_lock_seen` | 3× per poll | O(1): three attribute reads |
| `_decide_sighting_locked` search branch: `_bearing_line_search_offsets` rebuild, one int index | per poll, only while an ATGM run is locked **and** not yet seen | O(band / step), bounded by tuning limits |
| `drain_sight_lock_tracking` | per poll | O(1) edge compare; speech only on rising edge |
| `OpticState.sight_lock_search_since_sim` | per poll | one extra field in an existing `replace` |

### Measurements

Harness: `_look_targets(store, ownship)` timed with the corrected `_look_target_position`
versus a monkeypatched baseline returning `contact.last_position` (the pre-branch behaviour).
**Can-fail probes asserted before any timing:** store holds exactly `n` contacts; every
contact takes the `replace` path (corrected alt differs from `last_alt_m`); A/B outputs differ in
elevation (so the two variants are not the same code). All passed.

| n contacts | before | after | delta |
|---|---|---|---|
| 10 | 0.045 ms | 0.055 ms | 0.97 µs/contact |
| 50 | 0.226 ms | 0.277 ms | 1.03 µs/contact |
| 200 | 0.901 ms | 1.097 ms | 0.98 µs/contact |

`_bearing_line_search_offsets`: 3 offsets (wide sight, 0.19 µs) / 7 offsets (narrow, 0.33 µs)
at defaults; worst case inside the declared tuning bounds (overlap 0.8, band 35°) is 31 / 59
offsets — still sub-10 µs. The `max(step, 0.01)` degenerate path (FOV `None` → ~3000 offsets)
is unreachable: `sight_look_optic` returns only `SIGHT_WIDE_OPTIC` (5.75°) or
`SIGHT_NARROW_OPTIC` (3.00°), both with a real `fov_half_angle_deg`.

### Findings

#### Per-contact `replace` in `_look_targets`
- **Location:** `body._look_targets` → `_look_target_position` (every poll, every contact)
- **Risk:** ~1 µs/contact, ~+20 % on an already-O(n) loop. ContactStore is known not to prune
  (memory `project_contact_store_never_pruned`), so n grows with sortie length — but even at
  1000 contacts this is ~1 ms per poll, and the existing `look_target_for` work per contact
  (~4.5 µs) dominates. Not credible as a budget problem.
- **Action:** MONITOR
- **Mitigation:** none needed. If `_look_targets` ever shows up in a profile, the fix is the
  store's own pruning / live-contact filter, not this helper.

#### Offset tuple rebuilt every searching poll
- **Location:** `optic_policy._decide_sighting_locked` (locked, not-seen polls only)
- **Risk:** none at realistic scale — a 3–7 element tuple, sub-µs, only during one engaged run.
  Could be cached per optic, but that would be optimisation without evidence.
- **Action:** MONITOR (no action)

#### `_sight_lock_seen` evaluated three times per poll
- **Location:** `body.run_once` and `_run_crew_text_poll_loop` (before/after `run_once`)
- **Risk:** none — attribute compares; the before/after pair is required for edge detection.
- **Action:** none

No new I/O, no blocking calls, no new full-store iteration, no allocation proportional to
anything other than the pre-existing contact loop.

### Verdict
APPROVED — MONITOR (PASS)
