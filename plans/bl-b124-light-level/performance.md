### Performance Review

**Scope:** BL-B124 Stages 1–5 (batched per root `CLAUDE.md`'s "batch of stages actually executed
together" rule), range `7a1c70b3..baba22f4` on `feature/bl-b124-light-level`, merged into this
worktree as `baba22f4`. Reviewed against body-layer's per-poll loop (no hard real-time budget in
this phase — `--poll-interval-s` defaults to 1.0 s) and aircraft-layer's existing 1 Hz Hook/collector
cadence.

### Findings

#### `light_level.sun_elevation_deg` (the real astronomy) inside the per-poll hot path
- **Location:** `body.py::_resolve_sun_elevation_deg`, the one call site (`run_once`, once per poll).
- **Risk:** the plan's own stated risk — closed-form solar-position trig (several `sin`/`cos`/
  `atan2`/`asin` calls) running inside the poll loop, new work in a path that already runs every
  poll. Measured directly (`body-layer/.venv`, `perception.light_level.sun_elevation_deg`,
  20,000 calls): **~1.25 µs/call**. Called exactly once per poll (confirmed: the one call site is
  guarded on `self.theatre is not None` and feeds `self.light_level_sun_elevation_deg`, which every
  downstream consumer reads rather than recomputing). At 1 Hz this is immeasurably small against
  any plausible budget.
- **Action:** MONITOR (no action needed; recorded because the plan flagged it as worth a look).
- **Mitigation:** none needed. If a future stage ever moves body-layer's poll cadence materially
  faster than 1 Hz, re-measure — the formula's cost is fixed, so the only way this becomes real is
  the poll rate itself changing, not this feature.

#### `light_level.light_factor` resolved per-optic at every `tier_ranges()` call site
- **Location:** `belief/optic_policy.py::_light_factor_for`, called at every one of the module's six
  `tier_ranges()` call sites (`improvement_window_m`, `location_gain_for`, `sight_look_optic`,
  `sight_can_still_improve`, `least_capable_sufficient_optic`'s ladder loop, `guidance_request_for`),
  each of which runs per candidate per poll in `decide()`'s decision path — this is the choke point
  the plan and prior memory (`[[feedback_tier_ranges_is_the_choke_point]]`) both name.
- **Risk:** `light_factor()` itself is a pure, allocation-light piecewise-linear lookup (three
  `_interp_scalar` calls, each a 4-iteration Python loop, returning a 3-tuple) — not the expensive
  astronomy, which is resolved once per poll and passed in as a plain `float`
  (`feedback_shared_value_across_multiple_optics_in_one_call`'s own fix: the raw sun elevation is
  threaded, not a precomputed factor, specifically so each optic resolves its own curve locally).
  Measured directly: **~0.95 µs/call**. A representative busy poll (30 candidates × 4 named optics,
  i.e. every ladder rung evaluated for every candidate, which over-counts the real call pattern —
  `least_capable_sufficient_optic` stops early on the first rung that is "good enough") costs
  **~114 µs**, against a 1,000,000 µs (1 Hz) budget — under 0.02%. Even at 10× today's candidate
  count or 10× the poll rate this stays two orders of magnitude below budget.
- **Action:** MONITOR.
- **Mitigation:** none needed now. If candidate counts or poll rate grow by an order of magnitude
  *and* the ladder loop's early-exit stops firing (e.g. a future change makes every rung get
  evaluated unconditionally), re-measure before assuming this is still free — the margin is large
  but not infinite.

#### Second, independent `GET /firing/latest` round-trip per poll
- **Location:** `body.py::ConsolePerceptionRunner.run_once` (the light-level fetch) duplicates a
  fetch `NakedEyePerceptionSource` already makes internally for emitter resolution; the runner has
  no access to that source-internal result, so it re-fetches.
- **Risk:** one extra LAN HTTP round-trip per poll, at 1 Hz, against a local aircraft-layer process.
  Already flagged in `review-stages-4-5.md` as an Optional Refinement, explicitly justified in the
  code's own comment and accepted as negligible by that review. No measurement contradicts that —
  a loopback/LAN HTTP GET at 1 Hz is not a credible risk at this project's current scale (single
  player, single aircraft-layer peer, no fan-out).
- **Action:** MONITOR (already on record; restating rather than re-opening).
- **Mitigation:** if `NakedEyePerceptionSource`'s own fetch path is ever refactored to expose its
  last snapshot to the runner (the review's own suggestion), fold this fetch into that one. Not
  worth doing on its own.

#### Hook-side `timer.getAbsTime()`/`env.mission.date` addition to the 1 Hz `dostring_in` poll
- **Location:** `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`, two new `pcall`-
  guarded reads alongside the Hook's existing 1 Hz cadence.
- **Risk:** negligible — two cheap Lua global reads, same cost class as every other field this Hook
  already reads at the same cadence. No new loop, no new allocation shape.
- **Action:** MONITOR (no credible risk; listed for completeness).

#### `EmitterKind.LAUNCH_FLASH` fold into `resolve_emitters()`
- **Location:** `perception/emitters.py::resolve_emitters`, `aircraft-layer`'s
  `EmitterTracker._apply()`/`ingest()`.
- **Risk:** none found — both iterate only the batch's own events and the tracker's own active-
  emitter dict (bounded by concurrently-firing/burning/flashing units, not the full world-object
  set). No full-dataset iteration was introduced; this is the same shape `BURNING`/`FIRING` already
  had, extended by one more kind.
- **Action:** MONITOR (no action; confirms the plan's own claim that this needed no new plumbing).

### Verdict
APPROVED — MONITOR
