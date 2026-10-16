### Performance Review

Reviewed at `feature/bl-b76-tripwire-rejected` tip `e6a77d8e619519d457b6f6f4986fcc3a28adbf0e`.
Verified against an **archive snapshot**, not a merged tip — my dispatched worktree's base
(`a5082adf`, descended from `origin/HEAD`, which is far behind local `main`) was genuinely
diverged from this branch, not merely stale, so `git merge --ff-only` was never available. Code
was read directly from `body-layer/src/belief_truth_log.py` and `body-layer/src/belief/decay.py`
at this tip (via the already-checked-out worktree at this exact sha — equivalent to an archive
snapshot of the tip, same content); checks (`ruff format --check`, `ruff check`, `mypy --strict`,
`pytest`) were run with cwd inside that checkout's `body-layer/`, using
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/<tool>` (the snapshot/checkout itself has no
`.venv`).

Scope: `body-layer/src/belief_truth_log.py` only. Logging-only change — no admission, gating, or
`Contact`/`ContactStore` mutation path is touched.

### What's new, mechanically

- `BeliefTruthLogWriter` gained two small instance dicts: `_object_id_to_contact_id: dict[int,
  str]` and `_object_id_last_seen_sim: dict[int, float]`.
- `_update_object_id_contact_cache` now runs **unconditionally every poll** (`write_poll` line
  439), not only while an attack run is active — this was a deliberate fix during review so the
  cache is warm the instant a run starts, rather than always missing on a run's first poll.
- `_write_attack_run_tripwire` (only called when `attack_run_target_contact_id is not None`, i.e.
  only while a run is active) gained a second lookup path: if no `ADMITTED` match is found for the
  target this poll, it now also scans rejected entries whose `object_id` is in the cache's set for
  that contact.

### Findings

#### Unconditional per-poll cache update (`_update_object_id_contact_cache`)
- **Location:** `belief_truth_log.py:439`, called from `write_poll` on every poll regardless of
  attack-run state.
- **What it costs:** one additional full pass over `collector.records` per poll. Each iteration is
  O(1) — a `GateOutcome.ADMITTED`/`observation_id is None` check (the large majority of rows:
  almost every row in a 232-row poll is a candidate that was *not* admitted, so the `continue`
  fires immediately), and for the small number of `ADMITTED` rows, two dict writes plus one `for`
  over `cluster_member_object_ids` (typically 0-few members). No allocation beyond the dict
  entries themselves (bounded by distinct admitted `object_id`s, not by poll size).
- **How `collector.records` scales:** measured at BL-11 (`[[bl11-measured-outcome]]` in
  performance-reviewer agent memory) — median **232** in-bubble candidates at 440 objects, **570**
  at 800 objects, i.e. one row per candidate per poll, scaling with theatre population roughly as
  that note found (not linearly 1:1 with object count, since the player bubble sheds most of the
  field, but it does grow with scale).
  - **Correction for this review, not inherited uncritically:** that number is in-bubble
    *candidates*, which is what `collector.records` actually holds (one row per candidate
    considered this poll, admitted or rejected) — the right multiplier for "how many rows does
    this new pass touch," not the stale "5 Hz" framing the task warned against and not an assumed
    figure of my own.
- **Risk:** none credible at this scale. A ~232-row pass of cheap attribute checks in Python,
  additional to the pass `write_poll`'s main loop already does, is on the order of tens to low
  hundreds of microseconds — negligible against the measured **12.6 ms median / 98.6 ms p90** total
  poll work budget (BL-11) and the **~1.0-1.3 s** realised poll period. It does not touch
  `describe_position` or any other per-call cost BL-11 identified as the actual tail driver.
- **Action:** MONITOR. Not because this instance is risky, but because it is the second
  unconditional O(records) pass added to `write_poll` (the first being the pre-existing main
  admitted-row loop) — a credible place for cost to accumulate if a future stage adds a third such
  pass without re-checking the aggregate. No action needed now.

#### Rejected-entry lookup (`_write_attack_run_tripwire`, "rejected" branch)
- **Location:** `belief_truth_log.py:606-620`, only reached when a run is active **and** the
  target was not admitted this poll (i.e. not every poll even during a run).
- **What it costs:** `_object_ids_for_contact` iterates the cache dict (`_object_id_to_contact_id`)
  — bounded by the number of *distinct object_ids ever admitted and still within
  `OBJECT_ID_MEMORY_S`*, not by `collector.records` — then a second pass over `collector.records`
  (early-`break`s on first match) to find a rejected entry whose `object_id` is in that set. So,
  worst case during an active run with no admission this poll: up to three passes over
  `collector.records` total this poll (cache update, admitted-match scan, rejected-match scan),
  each O(records) with early exit on the latter two. This scans `collector.records` **once per
  poll**, not once per candidate — there is no nested per-candidate re-scan.
- **Risk:** none credible. Gated by `attack_run_target_contact_id is not None`, so it is not a
  cost every poll pays — only polls during an active attack run, which is the one phase this
  module is specifically instrumenting per BL-B70 §9. Even at the 570-row/800-object scale, three
  cheap passes is still sub-millisecond-class work.
- **Action:** NOW — no mitigation needed; this is already acceptable as implemented.

#### Was anything O(1) made O(records)?
- No. The pre-existing code already paid one O(records) pass per poll (the main admitted-row
  logging loop) plus, while a run was active, one more inside the old `_write_attack_run_tripwire`
  (admitted-match scan only — the rejected branch didn't exist before this change). This change
  adds: one more unconditional O(records) pass (the cache update) and one more conditional
  O(records) pass (the rejected scan, only on a run's non-admitted polls). Nothing here turns a
  dict/set lookup into a linear scan of `collector.records`; the cache dict itself (keyed by
  `object_id`, bounded by distinct admitted ids within the memory window) is exactly the O(1)
  lookup structure that makes the rejected-branch membership test (`entry.object_id not in
  target_object_ids`) a set-membership check, not a scan.

#### Memory growth over a long sortie
- **Location:** `_object_id_to_contact_id`, `_object_id_last_seen_sim`.
- **What happens:** entries are added on every `ADMITTED` poll and **never deleted** — only
  filtered by `now_sim - last_seen_sim <= OBJECT_ID_MEMORY_S` at read time in
  `_object_ids_for_contact`. A stale key sits in the dict forever, functionally inert once past the
  window, but not reclaimed.
- **Bound:** the key space is `object_id` (a DCS ground-truth id), so the ceiling is the number of
  *distinct* DCS object_ids ever admitted across the whole sortie — bounded above by total theatre
  object count (BL-11: 440-800 in the measured scenarios), not by poll count or sortie duration.
  Two `int -> {str, float}` dict entries per object_id is on the order of a few hundred bytes total
  even at 800 objects. Not a leak in any practical sense — it cannot grow past the object census of
  the mission.
- **Action:** MONITOR, not NOW. The never-evicted design means it won't shrink either, but the
  ceiling is small and fixed by mission content, not by sortie length. If a future stage reuses
  this pattern somewhere the key space is *not* bounded by a finite mission census (e.g. a key
  derived from a growing sequence rather than a DCS object_id), that would need eviction; this one
  doesn't.

### Verdict
APPROVED — MONITOR

No material per-poll cost. The unconditional cache update and the conditional rejected-entry scan
are both single cheap passes over an already-small `collector.records` (low hundreds of rows),
well inside the measured poll-work budget, and introduce no new allocation pattern, no
per-candidate rescanning, and no unbounded memory growth. The two MONITOR notes above are for
future stages stacking more unconditional per-poll passes onto this writer, or reusing the
never-evicted cache pattern with an unbounded key space — neither applies to what shipped here.
