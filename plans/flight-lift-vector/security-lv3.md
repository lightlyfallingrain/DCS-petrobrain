## Security Deep Analysis: BL-16 lift-vector law, Stage LV-3

Mode 2 (per `AGENTS.md` "Recommended Role Sequences" / root `CLAUDE.md` "Agents" — once per
batch of stages actually built together, after Reviewer, before DoD).

Base: `3fdc7baec7e1236b45f7f5c79320a31eb51051b8` on `fix/bl16-flight-epoch-bound`. This worktree's
prior HEAD (`a29eff71`) was a strict ancestor with a clean tree; fast-forwarded with
`git merge --ff-only 3fdc7bae`. Scope: `git diff 78a6f3fd..3fdc7bae` (12 files, 1868
insertions/42 deletions) — code commits `4ff2e2f7` (LV-3 implementation) and `d25bdc0a` (review
fix pass), all under `aircraft-layer/`.

### Dependency Status

No dependency change. No `pyproject.toml`/requirements file touched by this batch (the diff is
entirely `aircraft-layer/dcs-export/Petrobrain/*.lua`, their test files, two memory files, and
three plan documents).

### Scope read

This batch replaces the estimator's hard-coded placeholder `λ` curve with the real
hover/forward blend (`law_lambda`, breakpoints from `flight_profile.lua`) and threads that blend
through `law_init_at_take`/`law_update`/`law_outputs`: a new all-speed yaw damper, a hover
yaw-rate integral, a hover heading shaper, a drift-hold term, a goal-acceleration slew near hover,
a hover pedal band that binds only during a commanded heading change, and a held-bank-ends-at-hover
conversion mirrored into `flight_desired.lua`'s `reseed_from_measured`/two new getters
(`get_lambda`, `get_take_speed_kmh`). Read the full diff against both `review-lv3.md` and
`review-lv3-r2.md`'s own fix-pass trace, and the plan's "LV-3 amendment (2026-11-27)" section
through its 2026-11-28 corrections.

**The plan states its own scope boundary, confirmed by the diff:** "LV-3 adds no wire field and no
body-layer change" (plan.md, Design Overview diagram 1). Verified independently — the diff touches
no `src/api/`, no `src/schema/`, no `body-layer/`; `POST /command/flight`'s field set,
`GET /flight_desired/latest`'s wire keys, and every `isinstance`/`math.isfinite`/bounds check at
that boundary (reviewed and approved in the prior batch's `security.md`) are unchanged. There is
therefore **no new LAN-HTTP attack surface** in this batch at all — the entire change is control
logic running inside `Export.lua`, reading only local DCS sensor calls (`LoGetVectorVelocity`,
`LoGetIndicatedAirSpeed`, captured cockpit args) that this project's threat model (LAN-only,
single-user; realistic attackers are a malicious dependency or an infected LAN host) does not
reach — these are not network sockets and carry no wire-format parse step an attacker could feed.

**Non-finite-value sweep, done anyway per the task brief.** Traced every new numeric path for a
NaN/Infinity that could reach a control output:

- `law_lambda(v_g_mps, profile)` (new helper) — explicitly checks `type ~= "number"`, `v ~= v`
  (NaN), and both `math.huge` signs, returning the safe forward-law default `1.0` on any of them,
  before the only division in the function (`span`, itself guarded `<= 0.0 → 1.0`). This is the
  one new value with a plausible route to a non-finite input (`est.v_g`, ring-buffer-averaged
  telemetry) and it is the one place in this diff with an explicit guard — correctly placed.
- `measured.lambda = fc_est.lambda` is therefore always `nil` (not yet primed) or a `law_clamp`-
  returned value in `[0.0, 1.0]`; every consumer (`law_init_at_take`, `law_update`, `law_outputs`,
  `get_lambda`) reads `measured.lambda or 1.0`, so a missing value degrades to the same safe
  default rather than `nil`-propagating into arithmetic.
- `get_take_speed_kmh()` blends `LoGetIndicatedAirSpeed()` (type-checked, `nil` falls through to
  the caller's own existing IAS fallback in `flight_desired.lua`) with `fc_est.v_g_f`, which is
  itself only ever set from `est_sample`'s ring-buffer math, gated the same way as `v_g`.
- `law_turn_rate_at_bank` (pre-existing, now also feeding the new yaw damper via
  `v_t_for_yaw`/`v_t_for_yaw_at_take`) still guards its own division with `v_t_mps < 1.0 → 0.0`;
  the new `math.max(measured.v_t_mps or 0.0, profile.yaw_damp_v_floor_mps)` call sites keep that
  floor in place rather than bypassing it.
- Every new `flight_profile.lua` constant touched by this batch (`lambda_hover_kmh`,
  `lambda_forward_kmh`, `k_yaw_damp`, `yaw_damp_max`, `yaw_damp_v_floor_mps`, `k_yaw_rate_i`,
  `hover_omega_heading`, `hover_yaw_rate_max_deg_s`, `k_drift_hold`, `speed_band_min_mps`,
  `hover_pedal_band`, `hover_pedal_band_forward`, `goal_jerk_hover_mps3`, `goal_jerk_edge_mps3`,
  `pedal_limit_positive` 0.5→1.0) is a fixed Lua-literal, loaded at require-time from this
  project's own source file — not wire-derived, not reachable from any HTTP body, not a path to
  inject a non-finite value.

No new non-finite-propagation gap found. The category this project repeatedly finds (an
`isinstance`-but-not-`isfinite` wire value reaching an unguarded `int()`/comparison) requires a
wire boundary to apply at, and this batch does not add one.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `flight_control.lua` `law_lambda` (new) | Non-finite input guard | Explicit `v ~= v`/`math.huge` check before use, safe default `1.0`. Correctly defensive. | None. |
| `flight_control.lua` `law_init_at_take`/`law_update`/`law_outputs`, every `measured.lambda or 1.0` site | Missing-value default | Consistent "not primed → forward law" fallback across every new consumer; no site reads `measured.lambda` without the `or 1.0`. | None. |
| `flight_control.lua` `M.get_lambda`/`M.get_take_speed_kmh` (new getters) | Intra-process Lua call, `flight_control.lua` → `flight_desired.lua` | Both inside one DCS process (`Export.lua`'s own module composition via `dofile`, `AC-B12`), not a network call — no serialization, no parse step, no externally-reachable boundary. `flight_desired.lua`'s caller re-checks `type(...) ~= "number"` on both before use. | None. |
| `flight_desired.lua` `reseed_from_measured` | New `lambda`/`take_speed_kmh` locals | Both `type`-checked to `nil` on anything but `"number"` before use in the hover-bank-hold condition and the `desired.ias_kmh` assignment; matches the module's existing pattern for `phi_bar`/`threshold`. | None. |
| `flight_profile.lua` new constants (`lambda_*`, `yaw_damp_*`, `hover_*`, `goal_jerk_*`, `k_drift_hold`, `speed_band_min_mps`, `pedal_limit_positive` 0.5→1.0) | Behaviour-tunable Lua literals | Fixed-value, loaded from this project's own file, not wire-derived. `pedal_limit_positive`'s widening (U13, user direction 2026-11-28) is a physical-limit/behaviour decision already reasoned through in `review-lv3.md`/`review-lv3-r2.md` — not a security question. | None. |
| `io.open(...aircraft_layer_flight_debug.flag...)` / `...aircraft_layer_flight_trace.log...` | File writes | Unchanged by this diff (no hunk touches these lines) — fixed paths under `lfs.writedir()`, flag-gated debug logging, never built from external/wire data; already cleared in the prior batch's `security.md`. | None. |
| `net.dostring_in`/`eval`/`exec`/`loadstring`/`dofile` | Dynamic code execution sweep | None introduced. Only pre-existing `dofile` references (fixed-string `AC-B12` module loader) appear, in comments/unchanged lines. | None. |
| Command sockets (loopback UDP 7793, `POST /command/flight`/`/command/flight_lease`) | LAN-facing surface | Entirely unchanged — no field, bound, or handler touched by this batch. Previously reviewed and approved (`plans/flight-lift-vector/security.md`). | None. |

### Passed to Reviewer

- `law_clamp(v, lo, hi)` returns `v` unchanged (not `lo`/`hi`) when `v` is non-finite, since
  neither comparison is true for NaN — a pre-existing characteristic, unchanged by this batch,
  that only matters if a non-finite value ever reaches the final pedal/pitch/roll/collective clamp
  in `law_outputs`. This batch does not introduce or widen any path that could feed one (see the
  non-finite sweep above) — noted for Reviewer's own awareness of the law's behaviour under a
  hypothetical local-sensor glitch (a player-experience/correctness question, DCS physical-state
  territory, not a LAN/dependency security question), not raised as a finding here.
- `pedal_limit_positive` widened 0.5 → 1.0 (U13) is a physical-authority/behaviour decision
  already reasoned through by Architect and Reviewer across this plan's amendment and both LV-3
  review passes — no verdict given here.

### Verdict

**APPROVED**

No required fixes. No dependency change, no new wire field, no new file-system/network/
dynamic-code-execution surface, and the one new numeric helper most exposed to a non-finite local
telemetry value (`law_lambda`) is explicitly guarded. Nothing in this batch is reachable from a
LAN actor beyond what the prior, already-approved batch already covers unchanged.
