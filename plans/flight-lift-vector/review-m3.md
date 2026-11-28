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
