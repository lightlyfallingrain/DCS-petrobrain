# BL-16 M3 (terrain floor and look-ahead) — Review

Branch `fix/bl16-flight-epoch-bound` (pushed `feature/bl16-lift-vector-law`), tip `ad949ef7`
(fast-forwarded into this worktree from `a29eff71`, clean). Diff reviewed:
`ca0bcb50578ec9a9022d59b8dff0bc2de81dc75c..ad949ef7` (3 commits, 27 files).

Inputs read in full: `plans/flight-lift-vector/plan.md` "M3 amendment (2026-11-28)" section and
its "Answered 2026-11-28" decisions block; `alignment.md`'s M3 goal-check (E1–E10) and plan-check
(the three plan-aligner findings); `explore-notes.md`'s M3 section (skimmed against the plan,
which already restates it verbatim); `implementation-m3.md` in full. Code read: both `law_update`
sections (A–D), `law_terrain_w_floor`, `parse_terrain_relay`, `belief/terrain_ahead.py`,
`belief/flight_control.py`'s diff, `body.py`'s `_compose_and_relay_terrain`/`_apply_flight_requests`
call site, the Co-moving construction sites, and the relevant test files (`test_flight_control_law.py`
M3 classes, `test_terrain_ahead.py`, `test_flight_authority.py`'s rewritten carried-value tests).

## Checks run (this review, not re-trusting the implementer's log)

- `body-layer`: `ruff format --check` clean, `ruff check` clean, `mypy src` (strict, from inside
  the subproject) 0 issues/96 files, `pytest tests -q -n auto` → **3927 passed, 4 xfailed**
  (matches the implementer's number), `test_tuning_defaults_toml.py` passes on its own.
- `aircraft-layer`: `ruff format --check` clean, `ruff check` clean, `mypy src` 0 issues/29 files,
  `pytest tests -q -n auto` → **1313 passed** (matches), `luac5.1 -p` clean on all four touched
  Lua files.
- Targeted re-runs (`-k "terrain or flight_control or flight_authority or body"` / `-k
  "flight_control or line_of_sight or terrain"`) also green, run before the full suites.

## What the code actually does, verified against the plan (not just described)

- `F_eff` (Lua `f_eff`) derived every `law_update` step from `limits.floor_agl_m`/`state.alt_goal_m`,
  never stored — confirmed no construction site stores it. `FLOOR_AGL_M` 40→50 in both
  `belief/flight_control.py` and `fc_limits`'s Lua default; `max_climb_vs_mps` removed from the
  wire, `FC_LIMIT_BOUNDS`, `_FLIGHT_CONTROL_LIMITS_BOUNDS`, and every tuning table — grepped, no
  live reference remains (only comments/docstrings naming the old constant for history).
- `profile.break_floor_agl_m` is gone; the break floor is `max(f_eff, entry − loss_budget)`,
  confirmed at `flight_control.lua` ~L1241.
- The look-ahead helper (`law_terrain_w_floor`) matches section B exactly: `d_i > 0` gate, ground-
  speed-along-nose gate (`v_f < terrain_min_speed_mps` disarms the whole grid, NaN-safe via
  `v_f ~= v_f`), `R_i > goal_asl` gate, `w_i = (R_i − A) / max(d_i/V_f − lead, tau_min)`, `max` over
  points. A non-finite `d`/`t` is excluded naturally by the `type(...) == "number"` guard plus the
  comparison semantics (`NaN > 0` is false in Lua), so the missing-vs-zero distinction holds even
  without an explicit `d == d` check.
- The floor-into-shaper combination (`a_ref_terrain` vs `a_ref_h`, whichever asks for more climb
  wins, both passed through `alt_accel_cap` — never a step) matches diagram 2 exactly.
  `h_ref` follows `measured.h_m` while `terrain_binding`, confirmed at ~L1326.
- Ease-down (`terrain_ease_down_mps` = 10.0, matching U20's "at most 10") and the power governor
  (`w_ref_lead_max_mps` = 2.0, gated on **last frame's own** `dbg_shortfall`/saturated `u_c`,
  confirmed feedback-only as disclosed) are both present and wired as specified.
- Speed absorber (section D): `shortfall > 0` → `v_ref`/`dv_ref` yield toward
  `speed_give_floor_kmh` (100 km/h, U19), with **no cause-based branch** — confirmed: the trigger
  is the bare `shortfall`, exactly matching U22's "every climb trades speed," not a terrain-only
  gate.
- `clamp_altitude` now only floors at 0; `decide_carried_value_speech` needed no code change
  (confirmed by reading, matches finding 4) — tests rewritten correctly for both the no-floor case
  and the remaining negative-altitude clamp (E10).
- Non-finite handling at the Hook (`land.getHeight` failure/NaN → missing token, never 0),
  `TerrainAnswers.from_wire` (`math.isfinite`), `build_terrain_relay` (re-checks `isfinite` at the
  HTTP/JSON boundary rather than trusting the upstream check), and `parse_terrain_relay` (NaN check
  on every coordinate) are all present. The lease `terrain` field's regex
  (`_TERRAIN_RELAY_PATTERN`) structurally cannot carry an "inf"/"nan" token, so the Lua-side NaN-
  only check is sufficient in practice.
- Grid geometry: `nose = (cos ψ, sin ψ)`, `right = (−sin ψ, cos ψ)` in `terrain_ahead.py`, matching
  the plan's corrected vector (finding 8) and the x-north/z-east convention; `test_terrain_ahead.py`
  uses deliberately distinct step/half-width so an axis swap can't pass by coincidence.
- Mode 2 untouched: `law_update`/`law_terrain_w_floor` are reached only through mode-1's `fc_law`;
  `_compose_and_relay_terrain`/`write_flight_lease` run unconditionally (every mode, confirmed at
  `body.py` ~L4516), matching F's "the data path stays warm, the law doesn't act on it in mode 2."
- No new callouts: `git diff` on `belief/speech.py` and `config/rules/flight.lua` across this
  branch's M3 commits is empty.
- Co-moving table: spot-checked `terrain_return`'s four transition sites (new goal clears it,
  floor-stop-binding sets it, in-band clears it, `fc_law = nil` resets everything) and
  `fc_terrain`'s own reset-only-at-`on_stop`/`reset` site (not at every `fc_law = nil`, matching the
  "lives outside `fc_law`, like the estimator" posture) — all present as specified.
- `defaults.toml` read as rendered, not just the source `#:` comment: `FLOOR_AGL_M`,
  `TERRAIN_LOOKAHEAD_M`, `TERRAIN_STEP_M`, `TERRAIN_HALF_WIDTH_M`, `TERRAIN_RELAY_MAX_AGE_S` all
  render cleanly with correct values/bounds; the backtick-span fix disclosed in finding 5
  (`min(this, fog visibility)` renders with its space intact) confirmed directly in
  `terrain_ahead.py`'s own docstring, not just taken on the implementer's word.

## Required Fixes

1. **The test the plan explicitly added to close plan-aligner's Finding 3 was never built.**
   `plan.md`'s Tests section (backfilled at tip `ca0bcb50`, confirmed present) states: *"U22 'every
   climb' ... an ordinary commanded climb with no terrain data ('climb 300' at 220 km/h) driven
   through capped climb authority makes `v_ref` yield toward `speed_give_floor_kmh` ... so a
   regression to 'terrain only' fails a test."* No test anywhere in
   `aircraft-layer/tests/test_flight_control_law.py` or `test_flight_control_lua.py` drives an
   ordinary altitude step with `measured.terrain = nil` through capped climb authority and asserts
   `v_ref` behaviour — `grep -n "speed_give_floor_kmh"` outside fixture tables returns nothing, and
   `grep -n "v_ref"` under assertions returns nothing for this case either.
   `TestM3TerrainClimbScenario` only exercises the terrain-bound path; `TestLV2HeightGivesFirst`
   exercises `shortfall`/`theta_speed_give` but never looks at `v_ref` and runs in a break context,
   not a plain altitude command.
   `implementation-m3.md`'s "Deviations from the plan, disclosed" section lists three deviations —
   none of them this one. The implementer's own cross-check ("all three findings... were already
   backfilled into plan.md... confirmed by grep") checked that the *plan text* was corrected, not
   that the *test* it added was actually written — the exact gap plan-aligner's Finding 3 predicted
   ("if a future change narrowed the governor's lead back to 0 for a plain climb... no test here
   would catch it"). **Add the missing toy-plant case**: a plain altitude-step goal, no `measured.
   terrain`, capped climb authority (reuse the LV-2/M3 driver shape), asserting `v_ref` yields
   toward `speed_give_floor_kmh` (never below it) and returns once the shortfall ends. This is
   cheap — a `collective_was_capped`-style direct scenario, not a new closed-loop plant — and is
   the one piece of U22's behaviour with zero coverage today.

## Optional Refinements

- **The ease-down cap (`terrain_ease_down_mps`, U20's 10 m/s) has zero direct test coverage**,
  beyond the disclosed gap in `TestM3TerrainClimbScenario`'s own docstring ("a second ridge/
  ease-down-after-the-crest cycle... not reached"). That disclosure covers the *full cycle*; even a
  cheap direct check (`state.terrain_return = true`, one or two `law_update` calls, assert
  `w_ref >= -10.0` and never looser) is absent. Given U20 is a specific, recently re-answered user
  number (not the plan's own recommended 5), a minimal direct test would catch a transcription slip
  (e.g. a future edit reading `5.0` off the historical recommendation text still on file) that the
  live card alone would only catch in flight. Not blocking — the live card (row 5) is the stated
  acceptance path and the mechanism itself (code) is straightforward — but worth adding opportunistically.
- **No magnitude bound (`|h| < 1e5`) on terrain heights inside Lua**, despite plan section E's own
  text: *"each height re-checked `h == h` and `|h| < 1e5`."* `parse_terrain_relay` only checks
  `h == h` (and the matching for `x`/`z`); `law_terrain_w_floor`/`run_active_frame`'s projection add
  no magnitude check either. In practice this is low-risk: the lease `terrain` field's own regex
  (`_TERRAIN_RELAY_PATTERN`) cannot carry an "inf"/"nan" token, body-layer's own encoder already
  applies `math.isfinite` before writing a height into the string, and any resulting `w_floor` —
  however large — is clamped through `alt_accel_cap` the same way an ordinary demand is, so a
  bogus-but-finite height cannot translate into an uncapped command. Still, this is a real,
  undisclosed gap against the plan's own explicit text (not listed in "Deviations from the plan,
  disclosed"); worth closing with a one-line bound the next time this file is touched, not worth
  reopening the branch for on its own.

## Verdict

**APPROVED WITH MINOR FIXES** — the one Required Fix is a missing test, not a code defect; the law
itself, the data path, the non-finite handling, the tuning rendering, and every invariant checked
(no omniscience N/A here, no raw-axis LAN write, provenance/timestamps on the terrain relay,
read-only DCS access via `land.getHeight`) are correctly built and match the plan and the user's
answered decisions (U18–U22) exactly where checked. Add the missing U22 toy-plant case before
calling M3 done; the Optional items can wait for a later touch of this file.

## Review Confidence

**Full read** of the plan's M3 amendment, both alignment sections, the implementation summary, and
every file the plan's own "Affected Modules" list named, with the full test suites of both touched
subprojects run and passing (not just taken from the implementer's log). The one area reviewed by
targeted grep rather than line-by-line trace is the toy-plant test bodies themselves beyond the M3
classes (~4000 lines of pre-existing fixtures in `test_flight_control_law.py`) — sufficient to
confirm the Required Fix's absence (a negative claim, checked by grep for the specific mechanism
name across the whole file) but not a line-by-line audit of every pre-existing test's continued
correctness, which the full-suite pass (3927/1313 green, zero new failures) already covers more
reliably than a manual read would.

## Re-review (fix pass)

Commit `57f965d5` (branch `fix/bl16-flight-epoch-bound`, pushed `feature/bl16-lift-vector-law`),
diff `6d789b38..57f965d5` (4 files: `flight_control.lua`, two test files,
`implementation-m3.md`). That branch tip could not be checked out in this worktree (it was already
checked out in another worktree, `/Users/sg/Code/DCS-petrobrain-epochfix`), so this re-review was
done against an isolated `git archive 57f965d5` snapshot, with every check run from inside that
snapshot's own `aircraft-layer/` directory (this project's checked-out
`aircraft-layer/.venv` for `ruff`/`mypy`/`pytest`, Homebrew `luac5.1`/`luajit`).

**Checks (re-run, not re-trusting the implementer's log):** `ruff format --check` clean, `ruff
check` clean on both touched test files; `mypy src` (from inside the snapshot's `aircraft-layer/`)
0 issues/29 files; `luac5.1 -p flight_control.lua` clean; `pytest tests -q` → **1318 passed**
(matches `implementation-m3.md`'s count, 1313 + 5 new). No `body-layer` file touched, correctly not
re-run.

**2b (terrain height magnitude bound) — confirmed correct.** `parse_terrain_relay` drops a
height outside `|h| < 1e5` by simply never appending the point (`if ... then points[#points+1]
= ... end`, no `else`) — an out-of-bound height is excluded from the grid entirely, never
substituted with `0`. Re-ran `TestTerrainRelayMagnitudeBound` directly: a grid of one in-range
and two out-of-range heights reports `fc_terrain_n = 1` (not 3, not a 0-height point counted);
an all-out-of-range grid reports `0`. Matches "missing, never 0."

**Required fix 1's own test, verified by mutation.** Patched a local copy of `flight_control.lua`
to gate the section-D speed-give block behind `state.terrain_return` (simulating exactly the
"narrowed to terrain climbs only" regression plan-aligner's Finding 3 and required-fix-1 both
named) and re-ran `TestM3OrdinaryClimbTradesSpeedNoTerrain` against the mutant: it fails
(`v_ref_floor_phase` stays at the commanded 61.1 m/s instead of settling at the 27.78 m/s floor).
So the test the implementer added does close the exact gap required-fix-1 asked for, for the part
it actually exercises (yield toward the floor, never below it, on a plain non-terrain climb).

**The recovery half of the same test is not actually verified — required fix.** The task's own
suspicion (`omega_speed` 0.15 is far too fast a filter to still be 34.7/40.6 m/s short of 61.1 m/s
after 60 s/300 s) is correct, but the cause is neither the filter nor (as the implementer's log
claims) "`omega_speed` is deliberately slow" — it is that **`shortfall` never actually reaches
zero in this scenario**, for a reason that is a test-driver defect, not a law defect:

- Traced `state.dbg_shortfall`, `state.u_c`, `state.h_ref`, `state.w_ref` and `measured.h_m`
  frame-by-frame through the exact scenario (reconstructed driver, `luajit`, against the real
  `flight_control.lua`). After the RPM/speed recovery the RPM-caused shortfall does end
  (`shortfall = 0` at t≈1–5 s), but the sustained 500 m altitude error (goal 650 m, `measured.h_m`
  pinned at 150 the whole run — the test never advances it) saturates the collective again by
  t≈15 s (`u_c = 1.0`) and `shortfall` **never returns to 0 for the rest of the run** — it is
  still 2.0 and *rising* at t = 600 s, long after the law's own internal reference `state.h_ref`
  has already reached the 650 m goal (`h_ref = 650.000` by t = 300 s). The driving term is
  `k_alt_error · (h_ref − measured.h_m)` in the collective command: because `measured.h_m` is
  never updated, this gap only grows, so the collective stays pinned at max and
  `next_state.dv_ref = min(dv_ref, 0.0)` (the shortfall-driven clamp, section D) keeps re-zeroing
  every frame. The slow ~0.02–0.03 m/s² per-frame creep visible in the recovered numbers
  (27.8 → 34.7 → 40.6 → 46.5 m/s at 60/300/600 s) is a side effect of statement order (the
  ordinary shaper computes a small tentative increase before the override re-clamps it down each
  frame), not genuine convergence — `shortfall` is never actually zero when those numbers are
  sampled.
- Confirmed this is a driver artifact, not a law defect, two ways. First, with the same scenario
  but a much smaller, achievable climb (`alt_goal_m = 200` instead of `650`), `state.h_ref`
  reaches the goal by t ≈ 30 s and `shortfall` still never drops below ≈0.2 and keeps climbing —
  same mechanism, same cause (`measured.h_m` frozen), ruling out "the climb itself is just too
  big." Second, re-running the same scenario with `measured.h_m` integrated one frame-order term
  behind `state.w_ref` (i.e. a sensor that actually reports the climb happening, the one change
  that makes the scenario physically consistent) makes `shortfall` hit exactly `0.0` within
  ~1 s of the RPM/speed recovery and `v_ref` reach the commanded `61.111` m/s (not just
  "`> floor + 5`") well inside the test's own 60 s window. So the law's own recovery path is not
  slow and not broken — the merged toy plant simply never lets the shortfall end, because it
  never advances the one measured field (`measured.h_m`) the collective's altitude-error term
  reads, while the law's own internal reference (`h_ref`) is allowed to run ahead of it forever.
- This matters because it is exactly the plan's own stated requirement for this test (`plan.md`,
  Tests, U22 row): *"... and return to the commanded speed once the shortfall ends — so a
  regression to 'terrain only' fails a test."* The merged test's assertion
  (`v_ref_recovered > v_ref_floor_phase + 5.0`) and its own docstring ("once the shortfall ends,
  `v_ref` returns toward the commanded speed ... not asserted at full convergence, only that it
  is clearly moving back up") both describe a shortfall-ends-then-recovers case that this
  scenario never reaches — `shortfall` is still 2.0 and rising at the point the test samples
  `v_ref_recovered`. The weak `+5.0` margin happens to pass regardless, via the per-frame leak
  above, so a future change that broke the *actual* resumption path (e.g. a sign error making
  `v_ref` never resume at all once `shortfall` genuinely ends) would not be caught by this
  assertion — the same class of gap required-fix-1 itself was written to close, now one level
  deeper. **Required fix 2**: give the scenario a way for `shortfall` to actually reach and stay
  at `0.0` (the cheapest form: advance `measured.h_m` toward `state.w_ref`/`state.h_ref` each
  step, matching the technique this file's own bank/heading toy-plant tests already use, or pick
  an altitude goal and a point in the run where the collective genuinely un-saturates) and assert
  `v_ref` actually converges toward `speed_goal_mps` (not merely `> floor + 5.0`) once `shortfall`
  is observed to be `0.0`. Until then, U22's "resume at the commanded speed" half is unverified by
  any test, even though the plan, the original review, and this test's own docstring all state it
  is.

**Everything else from the original review unaffected.** 2a (ease-down cap, direct) and the rest
of the M3 build were not touched by this fix pass beyond what `implementation-m3.md` discloses,
and nothing in this re-review found a new issue with them.

## Verdict (re-review)

**CHANGES REQUESTED.**

1. **Fix the recovery assertion in `TestM3OrdinaryClimbTradesSpeedNoTerrain`.** The test's
   recovery check does not exercise what it claims to (U22's "returns to the commanded speed once
   the shortfall ends") because `shortfall` never reaches `0.0` in the scenario as built — a test
   construction gap (`measured.h_m` never advances), not a defect in `flight_control.lua`. Make
   the scenario reach a genuine `shortfall == 0.0` state (advance `measured.h_m` with the climb,
   or otherwise let the collective un-saturate) and assert convergence toward `speed_goal_mps`,
   not just `v_ref_recovered > v_ref_floor_phase + 5.0`. Also correct the test's own docstring/
   comment, which currently asserts a recovery that is not actually demonstrated.

Everything else re-checked in this pass — 2b's magnitude bound (missing, never 0, confirmed),
required-fix-1's floor/never-below/terrain-only-regression coverage (confirmed by mutation), and
the full `aircraft-layer` suite (1318 passed, format/lint/type clean) — is sound.

## Re-review Confidence

**Full read** of the Lua diff and both new test files, plus direct reconstruction and execution
of the merged scenario against the real `flight_control.lua` outside pytest (`luajit`, with
per-frame tracing of `dbg_shortfall`/`u_c`/`h_ref`/`w_ref`/`measured.h_m`) to establish the actual
cause of the slow recovery, a mutation run against required-fix-1's test, and a corrected-plant
run to confirm the law itself converges quickly once `shortfall` genuinely ends. Not re-walked:
the ~4000 pre-existing lines of toy-plant fixtures untouched by this fix pass (covered by the
full-suite pass instead, 1318/1318 green, matching the implementer's count).

## Re-review (fix pass 2)

Commit `bf753c88` (branch `fix/bl16-flight-epoch-bound`, pushed `feature/bl16-lift-vector-law`),
diff `b06dca5f..bf753c88` (2 files, test-only: `test_flight_control_law.py`,
`implementation-m3.md`). Fast-forwarded cleanly into this worktree from `a29eff71` (strict
ancestor, clean tree).

**Checks (re-run, not re-trusting the implementer's log):** `ruff format --check` clean, `ruff
check` clean (both from inside `aircraft-layer/`, main checkout's `.venv`); `mypy src` 0 issues/29
files (only the test file changed, no production source touched — correctly no mypy difference);
`luac5.1 -p` on every touched Lua file — none touched this pass, correctly not re-run; `pytest
tests -q` → **1318 passed**, same count as fix pass 1 (no test added or removed, one test's body
changed), matching `implementation-m3.md`.

**1. The recovery half now genuinely verifies what it claims.** Read
`TestM3OrdinaryClimbTradesSpeedNoTerrain._run_scenario` and its assertions directly: both loops
now advance `measured.w_mps`/`measured.h_m` from `state.w_ref` each step, and the new assertions
are `shortfall_recovered == 0.0` (the premise the re-review required, checked rather than assumed)
and `abs(v_ref_recovered - speed_goal_mps) < 1.0` with `speed_goal_mps` read back from the scenario
itself rather than retyped. Ran the single test directly: passes
(`1 passed in 0.06s`). **Mutation, re-run independently** (not re-trusting the implementer's own
mutation claim): patched a local copy of `flight_control.lua` to gate the section-D speed-give
block behind `state.terrain_return` (the same mutant required-fix-1 and fix-pass-2's own log both
used) and re-ran this one test against it — fails, at the floor-phase assertion
(`33.3 m/s` short of the floor instead of `< 1e-6`), confirming the test still catches the
regression it exists to catch. File restored immediately after, `git status --porcelain` clean
throughout.

Is `1.0` m/s an acceptable tolerance, or should the scenario be reshaped for tighter convergence?
**Acceptable, not a required fix.** It replaces a trend-only `+5.0` margin with a real numeric
convergence check at a fixed 60 s horizon, and the implementer's own 60.36 vs 61.11 m/s gap (here
reproduced structurally — see below) comes from a second, genuine power-limited saturation
partway through this test's 500 m AGL step, not from a loose model — tightening the scenario
(smaller climb, longer window) would mostly be trading one arbitrary number for another rather
than closing a real gap. Optional refinement only: a reader of this test five years from now has
no way to tell, from the assertion alone, that "within 1.0 m/s at 60 s" is "genuinely still
climbing out of a second saturation" rather than "a loose tolerance papering over a slow law" —
one sentence in the docstring citing the 60.36/61.11 figures (which the fix-pass log already
states, but the test file does not) would close that reading gap for free.

**2. The ~27 m/s `w_ref` overshoot and ~13 s second saturation are a toy-driver artifact, not
something the real law would command in flight when power is actually capped — confirmed by
direct execution against the production profile, not inferred from the formula.**

- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua`'s `PROFILES["Mi-24P"]` carries the
  *exact same* values this test's own toy `PROFILE`/`LIMITS` tables use for every constant that
  drives this scenario's vertical dynamics: `alt_accel_cap_mps2 = 1.0`, `omega_alt = 0.5`,
  `law_zeta = 1.0`, `k_vs_error = 0.3`, `k_alt_error = 0.05`, `w_ref_lead_max_mps = 2.0`,
  `speed_give_floor_kmh = 100.0`, `terrain_ease_down_mps = 10.0` — grepped both files directly, no
  divergence. So this is not a case of the toy plant using gentler numbers than the real aircraft
  would see; the test's dynamics and the shipped law's dynamics are the same function evaluated at
  the same gains.
- Ran the real `flight_profile.lua` Mi-24P profile through the same 650 m-goal-from-150 m scenario
  this test uses, with the test's own perfect-tracking driver (`measured.w_mps = state.w_ref` each
  step): `max_w_ref = 27.82` m/s at `t = 27.9` s, saturation (`u_c >= 0.999` or `shortfall > 0`)
  from `t = 9.7` s to `t = 27.85` s (~18 s) — the same magnitude the implementer's log and the
  original re-review both reported, confirmed with the shipped profile rather than the test's copy
  of it.
- Re-ran the identical scenario with `measured.w_mps` instead approaching `state.w_ref` through a
  first-order lag (`tau = 2.0` s) capped at a representative Mi-24P climb rate (`8.0` m/s) — a crude
  stand-in for "the rotor/engine genuinely cannot deliver the commanded rate," which is exactly the
  condition `profile.w_ref_lead_max_mps`'s power governor exists to react to. Under that lag,
  `w_ref` never exceeds `10.0` m/s (the `8.0` m/s deliverable rate plus the `2.0` m/s lead,
  bit-exact), and the lead over measured never exceeds `2.0` m/s — the governor binds as designed
  and the 27 m/s spike does not occur.
- **The mechanism is explicit in the code, not just the two runs above**: `collective_was_capped`
  (`flight_control.lua` ~L1313) gates the governor's `min(next_state.w_ref, measured.w_mps +
  profile.w_ref_lead_max_mps)` clamp — but the clamp is checked **against `measured.w_mps`**, and
  this test's driver sets `measured.w_mps` to the *already-computed* `state.w_ref` every step
  (perfect tracking by construction), so the lead condition is always trivially satisfied
  regardless of whether the gate itself is open. Nothing in the driver can ever make the real
  aircraft "unable to keep up," so the one mechanism meant to prevent exactly this overshoot never
  gets exercised by this scenario, for a structural reason, not a tuning one.

**Not a required fix.** This does not contradict the plan: M3's own text states the power governor
is feedback-only, driven by *measured* lag (`plan.md` section C, "`w_ref = max(w_shaper, w_floor),
approached at the accel cap`" and the governor keyed on "LAST frame's own `dbg_shortfall`/saturated
`u_c`") — it was never claimed to bound the reference in a scenario that defines away the very lag
it reacts to. The gap is in what this one toy driver can demonstrate, not in the law. **Flight-card
information, not a defect**: a real 500 m climb step at 220 km/h may show the collective pinned and
`v_ref` yielding speed for longer than card row 11 reads at a glance ("no overshoot at the top") —
worth a specific eye on row 11 in flight for whether `w_ref`/collective settle smoothly once real
power-limited lag is present, rather than assuming the toy plant's shape. This is the Optional
Refinements list, not a blocker: the law itself is correctly built against the plan's own stated
design, and the artifact is confined to one test's recovery-phase numbers, not to anything that
ships.

**Everything else from the prior re-review unaffected** — 2b's magnitude bound and required-fix-1's
floor/never-below/terrain-only-regression coverage were not touched by this pass and were already
confirmed; nothing in this pass found a new issue with them.

## Verdict (re-review, fix pass 2)

**APPROVED.** The one required fix from "Re-review (fix pass)" is correctly closed: the recovery
assertion now demonstrates genuine convergence (`shortfall == 0.0`, `v_ref` within 1.0 m/s of the
scenario's own commanded speed, read back rather than retyped), verified here by direct re-run and
independent mutation rather than taken on the implementer's word. The `w_ref`/saturation-duration
question from the task brief is resolved as a toy-driver artifact specific to this one scenario's
perfect-tracking shortcut, confirmed against the shipped `flight_profile.lua` values and by
reproducing a bounded result once realistic measured lag is modeled — it does not contradict the
plan and is recorded above as flight-card information (row 11) rather than a required fix. No new
Required or Optional items beyond the one docstring suggestion above (tolerance provenance), which
is itself optional.

## Re-review Confidence (fix pass 2)

**Full read** of the test diff (the only production-relevant diff — `implementation-m3.md` is the
implementer's own log) and direct, independent verification of both settled questions: the test
itself (re-run plus an independent mutation run, not re-trusting the implementer's mutation claim)
and the `w_ref` overshoot (two direct `luajit` executions of the shipped `flight_profile.lua`
against reconstructed scenarios — one reproducing the reported ~27 m/s/~18 s figures with the
real profile, one with a physically-motivated lagged sensor showing the governor binds and bounds
it). Not re-walked: the ~4000 pre-existing toy-plant lines untouched by this pass (covered by the
full-suite pass, 1318/1318, zero regressions).
