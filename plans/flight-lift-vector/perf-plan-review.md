### Performance Review

Light pass on the **plan**, no code yet: `plans/flight-lift-vector/plan.md` (BL-16 mode 1
lift-vector law, branch `feature/bl16-lift-vector-law`, tip `7174ba85`). No hard real-time budget
applies yet (Petrobrain Runtime has not started) — the bars here are the standing ones: no
per-request/per-frame allocation that doesn't need to be, no redundant query, work gated to the
frequency it actually needs. `Export.lua`'s `LuaExportBeforeNextFrame` already runs
`run_flight_control` unconditionally every DCS frame (~140 Hz) today; the plan's new estimator (A)
runs inside that same callback, so everything below is judged at that rate, not the 5 Hz status
push. Prior art read: `plans/flight-control/perf-m1-m2.md`, `perf-sortie-1120.md` (established
baseline: per-frame `GetDevice(0)`/`LoGet*` calls are the credible cost, the ~30-field
`pairs()` state-table clone is accepted/MONITOR, trace-gated reads at 5 Hz are free). Memory
checked: `project_bl16_m1_m2_redundant_envelope_measured_reads.md`,
`project_flight_control_p1_perframe_indication_read.md`,
`project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy.md` — all a "same device/API read twice in one
tick" or "per-frame read count keeps growing" shape; the plan has instances of both.

### Findings

#### Estimator now runs every frame in *every* mode, not only `active` — a real widening of the per-frame footprint

- **Location:** Plan, "Affected Modules": "New `est_*` estimator … run **every frame in every
  mode** so it is warm at a take." Today, `read_measured()`'s ~10 `LoGet*` calls and
  `update_live_seat_tracking`'s 6 `GetDevice(0)` reads already run unconditionally every frame
  (the pre-existing, already-MONITORed cost in `perf-m1-m2.md`/`perf-sortie-1120.md`), but the
  *law* itself (`law_update`, the ~30-field clone, the trig-heavy lift-vector math) only runs while
  `fc_mode == "active"` — i.e. only while Petrovich is actually flying the axes, which is a
  minority of most sorties. The new estimator — two velocity sources, two derivative stages
  (`a = dv/dt` then a second running mean), Euler-rate transform, ball average — is specified to
  run continuously regardless of mode, including the entire time the human pilot flies with no
  delegation at all.
- **Risk:** this is the exact shape `project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy.md` and
  the standing `GetDevice(0)`-growth finding already watch for — "if a fourth such function is
  added, re-open this finding" — except here it is not a new axis read, it is turning an
  *always-active-only* cost class into an *always-every-frame* one. At realistic DCS frame rates
  (~140 Hz, single-aircraft, so this never scales with contact count or world size — the project's
  own "measure n before scaling" caution does not apply to a count that is fixed at 1) the risk is
  not asymptotic blow-up, it's a permanent floor added to every frame of every sortie, including
  ones where mode 1 is never engaged. The plan's own goal (estimator warm at a take) is sound and
  worth the cost; the concern is scope — e.g. whether the second velocity source (below) and the
  ball read need to run this widely too.
- **Action:** MONITOR. Not a blocker: the plan is explicit about the reason (no estimator startup
  lag at a take) and each individual op is cheap scalar arithmetic plus a bounded number of
  `LoGet*` calls. Worth a one-line acceptance criterion on LV-0's card (10 s straight-and-level row
  already does this) that confirms no visible frame-time cost with the estimator warm and mode 1
  never engaged — the plan already has the row, it just doesn't currently say what to watch for in
  it.

#### Both velocity sources (`"position"` and `"vector"`) computed every frame forever, for a trace-only cross-check

- **Location:** Plan, section A: *"LV-0 compares it against `dP/dt`... if they match, the profile
  selects `"vector"`... and **the other source stays in the trace as the cross-check**."* Read
  literally, this means the unselected source's own ring buffer and least-squares slope keep
  running every frame, in every mode, indefinitely after LV-0 — not only during the LV-0 card
  flight where the comparison is actually needed.
- **Risk:** this is a straightforward redundant-computation finding, same genus as
  `project_bl16_m1_m2_redundant_envelope_measured_reads.md` (two independent computations of
  values only one consumer needs). Once `VELOCITY_SOURCE` is fixed by LV-0, the unselected source
  buys nothing except a trace line nobody is watching outside a debug flight, at the cost of a
  second per-frame ring buffer, a second least-squares fit, and (for `"position"`) a second
  `LoGetSelfData` read if `"vector"` was selected.
- **Action:** NOW (cheap to fix at plan level, before it's built this way). **Mitigation:** gate
  the unselected source's computation behind the same per-frame trace flag that gates the rest of
  the diagnostic logging (`aircraft_layer_flight_debug.flag`) — compute it only while the flag is
  on, which is also exactly when the cross-check is actually useful. After LV-0 settles
  `VELOCITY_SOURCE`, the common case (flag off) does one velocity computation per frame, not two.

#### Least-squares slope over a window — confirm incremental sums, not an O(window) refit every frame

- **Location:** Plan, section A: velocity is "the least-squares slope over the last `W_V` seconds
  (first cut 0.1 s, by timestamp)"; acceleration is likewise a least-squares slope over `W_A`, then
  a running mean over `W_A2`. At ~140 Hz, `W_V = 0.1 s` is ~14 samples; `W_A`/`W_A2` are
  comparable. The plan specifies the *math* (least-squares slope, running average) but not the
  *data structure* — whether each frame refits over the whole window from stored samples (O(window)
  work plus the window's own storage) or maintains incremental running sums (Σt, Σy, Σty, Σt²) that
  update in O(1) per frame by adding the new sample and subtracting the one that ages out.
- **Risk:** at ~14-30 samples per window this is not a scale risk on its own (it's bounded, fixed,
  never grows with anything) — but it is exactly the "O(window) work where an incremental update
  would do" shape this role's checklist names, and it compounds with the previous finding (up to
  two velocity sources × two derivative stages) and with LV-3's later narrower windows. A naive
  implementation (new table per frame for the window, or iterating the whole buffer every frame to
  recompute the four sums) is also where a per-frame allocation would sneak in — the ring buffer
  itself should be a fixed-size preallocated array of slots (overwritten in place, index wrapping),
  never a growing/shrinking table.
- **Action:** NOW, as a plan-level constraint rather than code review after the fact (per the
  user's own framing: this is a *design* risk to flag before Implementer builds it either way).
  **Mitigation:** the Implementation Plan/LV-0 bullet should say explicitly: ring buffers are fixed
  size, preallocated once at `law_init_at_take`/module load (never a per-frame `table.insert`), and
  the least-squares sums are maintained incrementally (add newest, subtract oldest) rather than
  refit from the stored window every frame. This is a one-sentence addition to section A, not a
  new stage.

#### Per-frame trace — confirm the gate is checked before building the line, not after

- **Location:** Plan, "Affected Modules": "a flag-gated per-frame trace (`aircraft_layer_flight_
  debug.flag` → `aircraft_layer_flight_trace.log`) lands in LV-0," logging estimator fields, both
  velocity sources, and the unsigned/logged-only channels (`LoGetAccelerationUnits`, AoA/AoSS,
  wind) every frame while the flag is set.
- **Risk:** low as stated (it's explicitly flag-gated, matching this codebase's established
  `aircraft_layer_*_debug.flag` pattern), but the plan doesn't say *where* in the frame the check
  happens. A string-building/JSON-encode step done unconditionally and only the file write
  skipped when the flag is off would still cost a string-concat and several extra `LoGet*` calls
  (`LoGetAccelerationUnits`, AoA/AoSS, wind — none of which the law otherwise needs) every frame,
  flag or not — the inverse of "flag-gated."
- **Action:** MONITOR, carried as an Implementer-level check rather than a plan change: the flag
  check must short-circuit before any of the trace-only reads (`LoGetAccelerationUnits`, AoA/AoSS,
  wind, the unselected velocity source once the previous finding's gate exists) or the trace
  string build, not just before the file write. Also confirm the file write itself doesn't
  `flush()`/fsync every frame while the flag is on (buffered is fine for a debug aid, per root
  `CLAUDE.md`'s testing-aid framing) — a card is short enough that this is unlikely to matter, but
  worth one line in the Implementer's own notes.

#### State-table clone grows again (more estimator/profile fields) — same accepted shape, no new concern

- **Location:** Plan, section A/D/E/F: the estimator's own state (velocity, acceleration, Euler
  rates, ball average, ring-buffer indices) plus the law's existing `phi_i`/`theta_i`/`u_c_i`
  integrators. The plan is explicit the estimator lives *outside* `fc_law` and is reset/handled
  separately (Co-moving Fields table) — good, since it means the estimator's own state doesn't
  grow the already-MONITORed `fc_law` clone's field count by much; `fc_law` itself gains only the
  trim-loop fields (D/E), consistent with `perf-sortie-1120.md`'s precedent ("two more fields, no
  new action").
- **Risk:** none credible at this scale, same reasoning `perf-m1-m2.md`/`perf-sortie-1120.md`
  already gave: single-aircraft, never scales with anything, pure-Lua table op not an engine-
  boundary crossing.
- **Action:** none — noted only so this plan review shows the clone's growth was checked, not
  assumed clean.

#### Body-layer poll — new estimator status fields, same bounded shape as every prior addition

- **Location:** Plan, Affected Modules: "Status push gains the estimator fields," and
  body-layer's `collector/*` passing through new fields for the cards.
- **Risk:** none. A fixed, small set of additional scalar fields on the existing 5 Hz
  `push_flight_control_state` line and the existing per-poll status read — the same cost class
  `perf-sortie-1120.md` cleared for the slip-ball readout three findings ago. No loop, no growth
  with contact count or mission length.
- **Action:** none.

### Verdict
CONCERNS

Two items (unselected velocity source running forever past LV-0; confirm incremental least-squares
sums over fixed-size ring buffers rather than an O(window) per-frame refit) are cheap to settle at
plan level now, before Implementer builds either shape — flagging them here is cheaper than a
rebuild after LV-0. Nothing here blocks starting LV-0; the estimator-every-mode widening and the
trace gating are MONITOR, carried forward to the LV-0 card and the Implementer's own check
respectively.
