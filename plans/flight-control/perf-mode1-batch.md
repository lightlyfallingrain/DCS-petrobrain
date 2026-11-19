### Performance Review

Branch `feature/bl16-mode1-break`, diff `e62b7ff9..c1d8dfd8` (fast-forwarded cleanly; HEAD was a
strict ancestor of the stated tip with a clean tree before merging). One pass for the mode-1 batch
(break turn, break away, rotor envelope, VRS, rates-as-goals — Decisions 27–32).

Checked against `plans/flight-control/plan.md` (Decisions 27–32), `implementation.md`'s "Mode 1
batch" section, and `review-mode1-batch.md` (Reviewer: APPROVED, no required fixes). Confirmed
call frequency directly rather than trusting a name: `aircraft-layer/dcs-export/Petrobrain/
flight_control.lua`'s `run_active_frame` (→ `read_measured`, `check_envelope`, `law_update`) runs
from `LuaExportBeforeNextFrame`, unconditionally, every DCS frame (line 1403's own comment, "Every
frame" — the only hot path this batch touches on the DCS side). Prior agent memory on this same
file (`project_bl16_m1_m2_redundant_envelope_measured_reads`, `project_export_lua_per_frame_
closures_are_established_pattern`, `project_ac_b12_export_lua_module_split_global_lookup_cost`)
already establishes this codebase's accepted per-frame baseline (closures, `GetDevice(0)` lookups,
scalar math) — judged every new addition against that baseline, not in isolation.

### Findings

#### `read_rotor_rpm_pct()` — new per-frame call, but dormant in its expensive branch

- **Location:** `flight_control.lua`'s `read_measured()`, called once per frame via `run_active_
  frame`.
- **Risk:** in its shipped mode (`ROTOR_RPM_SOURCE = "dummy"`), the function is a single string
  comparison and a constant return — no allocation, no engine call, negligible even against this
  file's own established per-frame budget. The expensive branch (`"arg_proxy"`: a `safe_call(
  function() ... end)` closure plus one `GetDevice(0):get_argument_value` call) is **not active**
  in this batch and was never exercised outside the `TestReadRotorRpmPct` unit test's direct call
  (`M.read_rotor_rpm_pct`, not through the per-frame loop). When it is later flipped to
  `"arg_proxy"` (Decision 28's own one-line swap, owed to a future flight), it adds exactly one more
  per-frame closure + `GetDevice(0)` call — the same shape `push_ptt_state`/`push_spu8_state`/
  `push_cockpit_switch_state` and `ai_pilot_wheel.lua`'s stick-park read already use, and squarely
  inside the growth curve `project_export_lua_per_frame_push_functions` already tracks (1 → 4 → 12
  reads across three prior features). Not a new call shape; one more instance of an already-judged
  pattern.
- **Action:** MONITOR — re-open only once `ROTOR_RPM_SOURCE` flips to `"arg_proxy"` for real, and
  only if the running per-frame-read tally (already ~12+ before this batch) keeps growing at this
  rate or a frame-time symptom is actually reported, per the existing memory's own threshold.
- **Mitigation:** none needed now. When flipped live, no new mitigation beyond what the existing
  memory already prescribes (share one cached `GetDevice(0)` handle across the file's push/read
  functions, if the tally keeps climbing).

#### `law_update`'s new per-frame branches (break rate ceiling, break-height floor, VRS cap, rotor/stall collective-rate guards, break pedal bias)

- **Location:** `flight_control.lua`'s `law_update`, steps 1 (heading, altitude), 3 (collective),
  5 (pedal) — all in the unconditional every-frame path.
- **Risk:** every addition is pure scalar arithmetic and comparisons (`math.abs`, `math.max`,
  a handful of `if`/boolean conditions) over fields already present in `state`/`measured`/`limits`
  — no table or closure allocation, no new engine (`LoGet*`/`GetDevice`) calls, no loop over a
  collection. This is the cheapest possible class of per-frame addition; it does not touch the
  dimension (allocation, engine-call count, iteration) that would make a per-frame change costly.
- **Action:** no action — not a credible risk at any realistic scale. Noting only to record that
  it was checked, not skipped.

#### Python-side changes (`belief/flight_control.py`, `ai_pilot_wheel.py`, `body.py`, `crew_console.py`, `rules/actions.py`)

- **Location:** `CrewConsole.axes_break_turn`/`axes_break_away` (per-action-dispatch, not per-poll),
  `CrewConsole.drain_flight_control`'s new Decision-32 seeding block (runs once per poll, inside
  the existing `drain_flight_control` call already on that path), `body.py`'s `_apply_ai_pilot_
  wheel_goal` capture of `cbtm_break_entry_heading_deg`.
- **Risk:** all additions are O(1) — a `dataclass(frozen=True)` field, a few comparisons, one
  `replace()` call already on this path for other fields, no new query, no loop over a collection,
  no per-poll allocation beyond what `replace()` already costs for the surrounding dataclass (an
  existing, already-amortized pattern in this codebase's belief layer). `cbtm_break_target_heading_
  deg` is a three-branch pure function with no allocation.
- **Action:** no action — negligible against the per-poll (5 Hz-class) budget this layer already
  operates at.

### Verdict

APPROVED
