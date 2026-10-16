### Performance Review

Scope: BL-B70 (`body-layer/src/belief/attack_run.py`, `body-layer/src/belief/speech.py`), feature
branch `feature/attack-run-fixes` @ `d826a54` (fast-forwarded from a stale worktree base). No
runtime budget applies yet (Petrobrain Runtime has not started) — this reviews headroom and
regression risk against the existing poll loop, not a hard deadline.

**Premise correction before the numbers below**: the task brief's "5 Hz spec vs ~0.7 Hz observed"
framing is stale. Per `.claude/agent-memory/performance-reviewer/project_body_layer_poll_loop_diagnosis.md`
(BL-B30 diagnosis, 2026-10-05), there is no 5 Hz spec anywhere in body-layer — the configured
default is `1.0 s` (1 Hz), the loop sleeps *after* the work (`work + interval`, not a fixed
period), and the sortie-measured realised period was ~1.33 s against a 1.43 s observed value. The
real headroom question is therefore "how much of a ~1.0-1.4 s tick does this guidance path add,"
not "how much of a 5 Hz/200 ms tick."

### Findings

#### `decide()` / `_no_look_cause()` / `_should_emit()` — all O(1), no new allocation class

- **Location:** `belief/attack_run.py::decide`, `_no_look_cause`, `_should_emit`, `_tier1_alignment`,
  `_tier2_alignment`, `_remembered_target_alt_m`; `belief/speech.py::alignment_phrase`,
  `alignment_clock_hour`, `render_alignment`, `render_attack_run_lost_sight`,
  `render_attack_run_regained_sight`, `_attack_run_last_seen_phrase`.
- **Risk:** none credible at realistic scale. Every function in this diff is a pure function of
  one contact's already-resolved `Contact`/`Group`/`OwnshipState` — trig (`math.cos`/`sin`/
  `radians`), a handful of comparisons, string formatting, and one frozen-dataclass `replace()`
  per call. `_no_look_cause`'s three primitive calls (`cockpit_mask.is_visible`,
  `profile_for`/`apparent_extent_m`/`distinctiveness_of`, `tier_ranges`, `range_m`) are the same
  primitives `check_visibility`'s gate chain already uses every poll for every candidate;
  `profile_for` is `@cache`d (0.04 µs/call, confirmed unchanged in this diff) and the others are
  closed-form geometry, not iteration. `_should_emit` is a single string comparison, replacing an
  *more* expensive angular-delta comparison the plan deleted (F1) — this diff is a net reduction
  in per-call work, not an addition.
- **Call frequency, confirmed against the caller:** `belief/crew_console.py::drain_attack_run`
  calls `decide` **once per poll, for at most one contact** — the single engaged attack-run target
  (`self._active_attack_target_task()` → one `contact_id`), via two O(1) dict lookups
  (`self.store.contact(id)`, `self.store.group_for_contact(id)`), not a loop over all contacts or
  all candidates. This call shape is unchanged by BL-B70 — the plan replaces what `decide` computes
  per call, not how often or over how many targets it is called. No full-dataset iteration, no new
  redundant query, no new state machine (the cause taxonomy is a 4-way `Literal` computed fresh
  each call from existing fields, not a persisted FSM).
- **Allocation:** one new `str | None` taxonomy value, a couple of short-lived tuples/strings per
  call, and `dataclasses.replace()` on an 8-field frozen dataclass — the same allocation shape
  `AttackRunState` already had pre-BL-B70 (it was already rebuilt via `replace()` every call).
  Nothing here is a new per-tick heap-allocation *class*; it is more of the same kind of allocation
  the module already made, at the same frequency (≤1/poll).
- **Gate-order fix (§8/the review's required fix):** `_no_look_cause` now checks range/size (gate
  3) before terrain LOS (gate 4), matching `check_visibility`'s real order. This reorders two O(1)
  comparisons against each other — not a materially different cost either way, and not a case of
  "common path does more work than before": both orders are a short-circuiting `if`/`elif` chain
  over the same handful of checks, and the common path (an admitted, resolvable tier-1 look) does
  not reach `_no_look_cause`'s range/LOS branches any more or less often under either order.
- **Action:** MONITOR, not NOW. Nothing here is a credible budget risk at the measured poll
  frequency (≤1/poll, O(1) work, no allocation class change). Worth re-measuring only if a future
  change makes `decide` iterate over more than the one engaged contact, or moves it outside the
  `drain_attack_run` call site's current once-per-poll gate.

#### `speech.py`'s new small table/string helpers — same shape as the functions they replace

- **Location:** `alignment_clock_hour`, `alignment_phrase` (extracted from the old inlined body of
  `render_alignment`), `_attack_run_last_seen_phrase`.
- **Risk:** none. These are refactor-shaped extractions of logic `render_alignment` already ran
  every call — splitting one function into three does not add work, it names work that was already
  there (plus one new cheap branch for `announce_twelve`/`qualifier`, both O(1) string
  concatenation). `_attack_run_last_seen_phrase` is a new function but only called from the §10
  transition sentences, which fire on an edge (`too_far` state flip), not every tick.
- **Action:** MONITOR (no action needed; noted only because it is new surface).

### Verdict

APPROVED
