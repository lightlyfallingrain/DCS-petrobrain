### Performance Review

Batch: BL-16 revised Stage P1 (takeover and stabilisation). Diff reviewed: `993be9a5..306af5f0`
(`d3bfe9df` aircraft-layer, `72bac70e` body-layer mirrors, `306af5f0` review-fix round). Reviewer
has approved (`plans/flight-control/review-takeover.md`, including "## Re-review"). Builds on the
posture `plans/flight-control/perf-batch-a.md` established: per-frame `Export.lua` work is only
what must be per-frame, and one `list_indication(6)` read per 5 Hz tick serves every consumer.

### Findings

#### `list_indication(6)` read stays one-per-tick, shared — mitigation held

- **Location:** `aircraft-layer/dcs-export/Export.lua:3019` (`local helperai_raw =
  safe_call(get_helperai_indication)`, inside the 5 Hz gate at line 3007-3010), fed into
  `update_ai_pilot_wheel_overlay(helperai_raw, t)` (line 3028) and reused by
  `encode_petrovich_indication_line`'s own consumer further down the same function — confirmed by
  reading the call site directly, not inferred from the comment. `run_ai_pilot_wheel(t)` (called
  every frame, line 2997, ahead of the 5 Hz gate) never calls `get_helperai_indication` or
  `list_indication` at all; it only does the release-deadline check, two cheap
  `get_argument_value(852/952)` reads, and stage-transition comparisons.
- **Risk:** none. This is exactly the shape `perf-batch-a.md` required (device read decoupled
  from frame rate, shared by both consumers). Verified rather than assumed — same device-read
  call count as before this revision landed.
- **Action:** none (confirms prior mitigation still holds).

#### New takeover/correction state machine — stage-gated, not continuous per-frame cost

- **Location:** `ai_pilot_takeover` table (module-level, created once at load —
  `Export.lua:2224-2239`) and its reader/writer functions (`ai_pilot_tap30`,
  `ai_pilot_open_hold`, `ai_pilot_begin_hold_phase`, `ai_pilot_decide_correction`,
  `ai_pilot_check_hold_convergence`), called from `run_ai_pilot_wheel` (per-frame) and
  `update_ai_pilot_wheel_overlay` (5 Hz).
- **Risk:** none credible. The one-shot closures (`safe_call(function() ... end)` pairs inside
  `ai_pilot_tap30`/`ai_pilot_open_hold`/the quick-pulse branches) only allocate when a stage
  transition actually fires — once per takeover for the blind toggle and menu-open tap, once per
  5 Hz tick only while a hold or quick-pulse sub-step is active, never unconditionally every
  frame. The per-frame body of `run_ai_pilot_wheel` itself (deadline check, two
  `get_argument_value` reads, `ai_pilot_park_rising`, a handful of `stage ==` string comparisons)
  is the same cost shape the prior revision already had — no new table/array allocation was added
  to the unconditional per-frame path. The `ai_pilot_takeover` table replacing a dozen-odd
  module-level locals (forced by Lua 5.1's 200-local ceiling, per the plan and the implementer
  memory `project_export_lua_200_local_ceiling.md`) is itself a one-time allocation, mutated in
  place thereafter — not a per-frame or per-tick allocation.
- **Action:** none.

#### Held-press correction loop checked at 5 Hz against a measured press rate — behaviour-adjacent, not a perf risk

- **Location:** `ai_pilot_check_hold_convergence` (`Export.lua`), called from
  `update_ai_pilot_wheel_overlay`, i.e. once per 5 Hz tick (200 ms) while a hold is open.
- **Risk assessed:** the plan's own measured held-press profile (`docs/acceptance/
  2026-11-16-bl16-batch-a-feedback.md`, "Takeover rehearsal probe") is ~16 m/s up to 2.5 s, then
  ~50 m/s after. At the faster rate, one 200 ms tick moves the held value ≤10 m. The tolerance
  band (`AI_PILOT_ALT_TOLERANCE_M` = 20 m) is wider than that single-tick step, so the loop cannot
  skip over the band in one tick: approaching from outside, the largest possible overshoot past
  the boundary is bounded by the step size (≤10 m), which stays inside a 20 m-wide band. At the
  slower early-phase rate (16 m/s → ≤3.2 m/tick) the margin is even larger. So a 5 Hz check is
  measured-adequate against the measured rate, not merely assumed — this is the dod-batch-a.md
  MONITOR item (*"whether a 5 Hz tick is fast enough for release-on-tolerance"*) being answered by
  this stage's own numbers, consistent with the plan's own "Second-order effect" note.
  **This is flagged for visibility, not as a performance defect** — a correctness/tolerance
  question, not a cost-at-scale one, and per this role's scope the acceptability of the resulting
  overshoot is the Reviewer/user's call, not mine. No change requested here.
- **Action:** MONITOR (note on file; re-open only if a live flight shows the loop timing out or a
  tolerance breach the architect's own 60 s safety ceiling wasn't meant to catch).

#### Python side — collector/schema parse of four new optional wire fields, body-layer mirrors

- **Location:** `aircraft-layer/src/schema/ai_pilot_wheel.py` (`arg_852`/`arg_952`/
  `takeover_stage`/`correction_path`, all optional, parsed with the same bounded per-field
  shape the existing five optional-string fields already use), `aircraft-layer/src/collector/
  server.py` (version-string bump only), `body-layer/src/belief/ai_pilot_wheel.py`
  (`advance_parked_flight_state` — four more dataclass fields, one `_as_optional_float` helper
  reused twice).
- **Risk:** none. Same shape `perf-batch-a.md` already cleared for this endpoint: one bounded
  dict-get-and-validate per field, no loop over a collection, no new per-poll allocation beyond
  four more scalar fields on an already-small dataclass construction, at the same 5 Hz-class poll
  cadence as before (not a frame-rate path on the Python side at all).
- **Action:** none.

### Verdict
APPROVED
