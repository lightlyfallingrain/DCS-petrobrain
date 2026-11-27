### Performance Review

LV-3 batch (BL-16 lift-vector law, low-speed/hover regime). This is a video game add-on
(Petrobrain for DCS World); the Mi-24P flight-control law reviewed here is a simulated game
system. Tip reviewed: `3fdc7bae` (`fix/bl16-flight-epoch-bound`, fast-forwarded cleanly from this
worktree's prior HEAD `a29eff71`; diff range `78a6f3fd..3fdc7bae`, commits `4ff2e2f7` and
`d25bdc0a`). No hard real-time budget applies yet (Petrobrain Runtime has not started); the bars
are the standing ones from `plan.md`/`perf-plan-review.md`: no needless per-frame allocation, no
redundant query, work gated to the frequency it actually needs. Prior verdict for LV-0..LV-2:
`performance.md` (APPROVED — MONITOR), carried forward and re-checked rather than assumed.

Frequency map, confirmed by reading the call sites, not the plan's prose: `law_outputs` (and the
output write) still run every DCS frame (~140 Hz, confirmed at `flight_control.lua:3265/3279/3378`
— unchanged by this batch, the plan's own "output stage still writes every frame" item).
`law_update` runs at `law_hz` (~30 Hz, `run_active_frame`'s own gating, also unchanged).
`reseed_from_measured` (and its two new getter calls, `get_lambda`/`get_take_speed_kmh`) runs only
on a take/mode-transition edge (`flight_desired.lua:452/469`, `tick`'s `new_mode ~= fd_mode`
branch) — confirmed by reading the call site, not assumed from the plan's "mirrors the take rule"
wording. `flight_profile.lua` stays static per-aircraft config with no per-frame function.

### Findings

#### `law_update`'s new per-step arithmetic — bounded, no allocation, correctly rated

- **Location:** `law_update` (`flight_control.lua:909-1582`), every regime-aware addition: `λ`
  read (`measured.lambda or 1.0`), `v_m` blend, the unexplained-yaw term (`psi_dot_exp`/`yaw_e`,
  one extra `law_turn_rate_at_bank` call per step plus the existing one in the `turn_mode` branch),
  the goal-jerk slew (`a_f_goal_s`/`a_u_goal_s`, each a clamp against a scalar), the drift-hold
  blend, the `U14` collective-give fade, the hover-pedal-band bookkeeping (`pedal_hover_ref`,
  `heading_change_active`).
- **Risk:** none credible. Every addition is scalar arithmetic over locals (`law_lambda` itself is
  a pure function, no table created); `next_state` is still the one `pairs`-copy table per step
  that already existed pre-LV-3 (not a new allocation this batch adds), and no new per-step table,
  string, or closure is created anywhere in the diff. At 30 Hz this is a few dozen extra
  floating-point operations and two extra `math.tan`/`math.rad` calls per step — immaterial next to
  the existing ~1000-instruction function body (`luac5.1 -l` confirms 1016 instructions for the
  whole `law_update` closure, LV-3's share of that being well under 10%).
- **Action:** none.

#### Lua upvalue/local budget — measured directly, matches the implementer's report, ample headroom

- **Location:** `luac5.1 -l` on the tip, measured independently (not trusted from the report):
  `law_update` **8/60** upvalues, `run_active_frame` **34/60**, `run_flight_control` **38/60**
  (the implementer's "`run_active_frame`/`run_flight_control` 38/60" reads as the higher of the
  two; verified separately they are 34 and 38, both well inside Lua 5.1's hard 60-upvalue closure
  ceiling — `reference_lua51_60_upvalue_ceiling` memory). Module-level locals: `main` chunk reports
  **124/200** (122 pre-LV-3 plus the two new getters, `get_lambda`/`get_take_speed_kmh`, matching
  the implementer's count exactly).
- **Risk:** none now. The nearest figure to its ceiling is `run_flight_control` at 38/60 (63%) —
  comfortable, but the one to watch if a later BL-16 stage (SAU) adds more cross-module helper
  references to that same function rather than a sibling.
- **Action:** MONITOR — re-measure with `luac5.1 -l` at the SAU stage rather than trusting the
  running total; `run_flight_control` is the function to re-check first.

#### Trace fields (new gains: `ias`, `tas`, `v_m`, `yaw_e`, `yaw_damp_pedal`, `pedal_hover_ref`, `a_f_goal_s`, `a_u_goal_s`) — stay behind the trace flag

- **Location:** `flight_trace_log`'s call site (`run_flight_control`, unchanged gate:
  `if ran and FLIGHT_TRACE_ENABLED`) and `read_estimator_raw`'s own `FLIGHT_TRACE_ENABLED` guard
  around every trace-only read. The new LV-3 trace gains are status/state fields already computed
  as part of the law step proper (`yaw_damp_pedal`, `pedal_hover_ref`, `a_f_goal_s`, `a_u_goal_s`
  are load-bearing law state, not trace-only computation) or a cheap scalar read gated the same way
  as the existing ones (`ias`, `tas`, `v_m`, `yaw_e`).
- **Risk:** none. No new `LoGet*` call or string-building work was added outside the existing
  `FLIGHT_TRACE_ENABLED` gate; the fields riding the trace line are values the law already holds in
  memory.
- **Action:** none.

#### Carried-forward MONITOR items from `performance.md` — re-checked, unchanged by this batch

- **Estimator every frame, every mode** (`est_due` gate before `read_estimator_raw`) — this
  batch adds no new per-frame `LoGet*` call; `est.v_g`/`v_g_f`/`v_g_r` read by LV-3's new blend
  terms are pre-existing LV-0/LV-1 fields computed in `est_sample` at law rate, not new reads.
  MONITOR, unchanged.
- **Flag-gated per-frame trace `flush()`** — unchanged shape, still MONITOR, still a debug-only
  testing-aid cost per root `CLAUDE.md`'s framing.
- **Pre-existing `GetDevice(0)` read growth** (`update_live_seat_tracking`, `push_*` family) — not
  touched by this batch. MONITOR carries forward unchanged.

#### `reseed_from_measured`'s two new getter calls — edge-triggered, not hot-path

- **Location:** `flight_desired.lua:305` (`get_take_speed_kmh`, which itself calls
  `safe_call(LoGetIndicatedAirSpeed)`) and the earlier `get_lambda` call (L :261 area). Call site
  confirmed by reading `tick` (`flight_desired.lua:452-475`): `reseed_from_measured()` runs only
  inside the `new_mode ~= fd_mode` branch, i.e. on a take/mode-transition edge, never every frame.
- **Risk:** none. One extra `LoGet*` call and a few scalar reads, once per take — immaterial next
  to the per-frame budget this role actually tracks.
- **Action:** none.

### Verdict
APPROVED — MONITOR

LV-3 adds scalar arithmetic to `law_update` (still gated to `law_hz`, ~30 Hz) and `law_outputs`
(still every frame, as the plan requires for the axis write), with no new per-frame allocation, no
new per-frame `LoGet*`/query, and no new always-on trace work outside the existing
`FLIGHT_TRACE_ENABLED` gate. The implementer's reported Lua upvalue/local budget
(`law_update` 8/60, `run_active_frame` 34/60, `run_flight_control` 38/60, module locals 124/200)
was measured independently with `luac5.1 -l` and matches; all four have comfortable headroom
under Lua 5.1's 60-upvalue closure ceiling, with `run_flight_control` (63% of its own ceiling) the
one to re-measure at the next stage rather than assume. All four MONITOR items carried from the
prior `performance.md` pass were re-checked against this diff, not re-derived from scratch, and
none crosses into NOW at this batch's scale. Nothing here blocks Reviewer/Security/DoD.
