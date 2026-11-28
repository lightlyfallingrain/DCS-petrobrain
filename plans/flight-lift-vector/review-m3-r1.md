# BL-16 M3 revision R1 — Reviewer

Branch `feature/bl16-lift-vector-law`, commit `74dfae71d2533e8e7ed96068cb3cae16788e7287`
(parent `9d7ffdb2b3495e6f04596b3b471518d9979b10b0`), fast-forwarded cleanly into this worktree from
`a29eff71` (`git merge --ff-only`, clean tree, HEAD confirmed a strict ancestor before merging).
Diff reviewed: `git diff 9d7ffdb2 74dfae71` (11 files, 582 insertions / 50 deletions).

This is a video-game add-on for DCS World (Mi-24P/Petrovich); everything below is simulated game
logic, nothing controls real hardware.

Inputs read: `plans/flight-lift-vector/plan.md` ("M3 revision R1" + "M3 amendment" section D),
`explore-notes.md` (last paragraph, the user's own speed-give wording), `implementation-m3.md`
("## R1"), `performance-m3.md` findings 1–2, `security-m3.md` findings 1/2 and the
`project_bl16_m3_terrain_projection_wrong_frequency`/`project_bl16_terrain_relay_xz_unbounded_
magnitude` agent-memory entries those findings came from.

## R1-a — speed-give delta (220→170, 130→100, 100→none)

`flight_control.lua`'s section-D speed-give block now computes
`v_floor_mps = max(state.speed_goal_mps - profile.speed_give_max_delta_kmh/3.6,
profile.speed_give_floor_kmh/3.6)` instead of the old bare absolute floor.

- **`speed_goal_mps` is the right "commanded" value, verified by grep, not assumed.** It is set
  only from `goal.ias_kmh`/`law_apply_goal` (line 736) and from the take seed (line 843/926) — the
  commanded speed read back to the pilot — never from `v_ref` (the shaped reference the speed
  shaper is actively moving) or `measured.ias_mps`. The block's own pre-existing comment
  ("`speed_goal_mps`/`desired.ias_kmh` are never touched") is upheld by the new code too: neither
  is written anywhere in this change.
- **Behaviour on a mid-climb commanded-speed change**: `v_floor_mps` is recomputed from
  `state.speed_goal_mps` on every `law_update` call while `shortfall > 0`, so a commanded-speed
  change mid-climb is reflected on the very next due tick — no staleness.
- **Worked cases, traced through the code and the tests**: 220→170 (`max(220-50,100)=170`),
  130→100 (`max(130-50,100)=100`, the absolute floor wins over the relative one), 100→none
  (`max(100-50,100)=100`, equal to the commanded speed, so `v_ref` cannot fall under the same
  forced shortfall that produces a real give at 220/130). All three are exercised by
  `test_flight_control_law.py`'s `TestM3OrdinaryClimbTradesSpeedNoTerrain` — a shared
  `_run_scenario(speed_kmh=, dropped_speed_kmh=)` driver now parameterises the existing 220→170
  case and the two new tests. Ran the three locally under `luajit` (`pytest -k M3` and `-k
  Terrain`, both clean) rather than trusting the implementer's own transcript.
- Card rows 4 and 11 (`docs/acceptance/2026-11-28-bl16-m3-card.md` and the `.html` sibling) both
  read "speed falls by at most ~50 km/h (not below 100)" — matches R1-a exactly, and the two files
  agree with each other (diffed).
- `speed_give_max_delta_kmh` is placed in `flight_profile.lua` beside its sibling
  `speed_give_floor_kmh`, not in a `tuning.py`-style mechanism — correct: aircraft-layer has no
  tuning-constant loader at all (root `CLAUDE.md`: "Outside body-layer the loader does not
  exist"), so a plain profile loop value is the only available placement, and keeping the pair
  together is the right call over splitting it for no functional reason. Implementation.md's own
  "Non-obvious choices" note says so, correctly.

No issue found here.

## R1-b — terrain-projection gate and LOS cache

**Gate (`performance-m3.md` finding 1).** The `run_active_frame` terrain projection is now gated
on `law_due(t, fc_law_last_update_t, flight_profile.ACTIVE)` — the *same* call `run_active_frame`
makes again a few lines later to decide whether to run `law_update` itself. Traced this by hand
rather than taking the comment's word for it:

- `measured` is a fresh local table built at the top of `run_active_frame` on every call (`local
  measured = read_measured()`), never carried across frames — so `measured.terrain`, once set
  (fresh or `nil`), is read by `law_update` later in the *same* function call, on the *same*
  frame, never a stale value from a previous frame.
- Every early-return path between the terrain-gate check and the `law_update` call (`check_
  envelope` failing, a take frame) also resets `fc_law_last_update_t = nil` and returns before
  `law_update` would run — so a frame that computes `measured.terrain` and then takes one of
  those early returns never claims to have fed it to the law; it is simply discarded with
  everything else that frame, consistent with "every other `fc_law`-reset site."
- **The collision-defer path, traced to the end rather than left as the implementer's own
  disclosure.** On the collision frame (`law_is_due and estimator_due_this_frame and not fc_law_
  deferred_last_frame`), the terrain gate's own `law_due()` call is `true` (it doesn't look at
  `fc_law_deferred_last_frame`), so a projection is computed but `law_update` is deferred to next
  frame — one wasted computation, matching the implementer's own "disclosed, not fixed" note. On
  the very next frame, `fc_law_last_update_t` still hasn't advanced (law_update didn't run the
  frame before), so `law_due()` is still `true`: the terrain gate recomputes a *fresh* projection
  against the *current* position, and `law_update` *does* run that same frame and consumes it.
  So the deferred frame never reads a stale or missing projection — it is strictly one extra
  projection computed and thrown away, not a correctness gap. Confirms the implementer's own
  "not a regression" claim rather than just accepting it.
- No test drives this gate end-to-end through `run_active_frame` (every terrain-law test feeds
  `measured.terrain` directly to `law_update`), as implementation-m3.md discloses. Acceptable: the
  gate is behaviour-preserving by construction (same frame computes/same frame consumes, both
  before and after), and `performance-m3.md` itself called this finding MONITOR, not a blocking
  defect — adding a full `run_active_frame`-level terrain test was not asked for by the finding
  and would be new scope, not a fix verification.

**LOS cache (`performance-m3.md` finding 2).** `ConsolePerceptionRunner._los_cache` is keyed by
the poll's own sim-time stamp, consumed by both `_resolve_expected_area_checks` (keyed on the
`ownship.t_sim` parameter it already has) and `_compose_and_relay_terrain` (keyed on a new
`now_sim` parameter, threaded from `_apply_flight_requests`'s own `now_sim = runner.last_t_sim`).
Traced the call graph by hand, not just read the docstring:

- `run_once` (the only path that calls `_resolve_expected_area_checks`) sets `self.last_t_sim =
  ownship.t_sim` **immediately after** that call (`body.py:1519-1520`) — so the stamp
  `_resolve_expected_area_checks` used this poll is exactly what `runner.last_t_sim` holds for
  the rest of this same poll.
- `_apply_flight_requests` has exactly one call site (`body.py:6136`, inside `_run_crew_text_
  poll_loop`'s own `while` loop), reached after `runner.run_once(...)` (`body.py:5808`) in the
  same loop iteration — so `now_sim` passed into `_compose_and_relay_terrain` this poll is the
  same `ownship.t_sim` value `_resolve_expected_area_checks` used moments earlier in the same
  iteration. The two call sites genuinely share one poll's stamp; a stale hit across polls is not
  possible by construction, matching the claim.
- A failed fetch is cached as `None` too (matches both call sites' pre-existing "degrade to no
  answer" behaviour).
- Mission-reset fix verified structurally, not just read: `test_console_perception_runner_reset_
  preserves_declared_fields_and_resets_rest` iterates every dataclass field generically (`field_
  names - _RUNNER_PRESERVE`) and compares against a fresh instance's default — `_los_cache` is
  not named in the preserve set, so it is covered by the general mechanism (not only the specific
  `self._los_cache = None` line in `reset_for_new_mission`, which is also present and correct).
  Ran this test directly: passes.

No issue found here.

## R1-c — relay bounds (x/z magnitude, point-count cap)

Both layers checked against `security-m3.md`'s two findings and the project's own "grep every
sibling field in the same parse function" lesson
(`.claude/agent-memory/security/project_bl16_terrain_relay_xz_unbounded_magnitude.md`).

- **`flight_control.lua`'s `parse_terrain_relay`**: `TERRAIN_RELAY_COORD_ABS_MAX = 2000000`
  applied to both `x` and `z` (matching `h`'s own pre-existing `|h| < 1e5` bound, and matching
  the channel's *other* direction, `terrain_points`/`probe_points`), and `TERRAIN_RELAY_MAX_
  POINTS = 32` truncates the point-collection loop via `break` once reached — the `seq`/receipt
  timestamp is still taken from the full entry, only the point list is capped. Both verified by
  the two new `TestTerrainRelayMagnitudeBound` tests (out-of-range dropped/in-range kept; 40 sent,
  32 survive) — ran them directly under `luajit`, pass.
- **`server.py`'s `_terrain_relay_passes_bounds`**: the same magnitude bound on `x`/`z`
  (`_TERRAIN_POINTS_COORD_ABS_MAX = 2_000_000`, the same constant the `terrain_points` request
  direction already uses) and a count check that **rejects** (rather than truncates) an
  over-32-entry string outright. Verified the three new `TestFlightLeaseCommandEndpoint` tests
  (overlong digit literal on `x` drops `terrain` only; 33 entries drops `terrain` only; exactly 32
  still forwards verbatim) and that the whole-lease-never-rejected posture is preserved (`sender.
  lease_sent == [(1, None, None)]`/`[(1, None, "")]` shape, never a dropped lease).
- **Asymmetric check I traced specifically because the prior finding's own lesson says to**: at
  the Python layer, `_terrain_relay_passes_bounds` checks `math.isfinite(h)` but never checks
  `abs(h)` against any bound — only `x`/`z` get a magnitude ceiling there. This matches
  `security-m3.md` Finding 1's actual scope (it only asked for `x`/`z` to get the bound `h`
  *already had on the Lua side*; it never asked for a *new* bound on `h` at the Python layer).
  So this is not a missed fix against what was asked, and it is not exploitable: the relay is
  parsed independently by Lua afterward, and Lua's own `math.abs(h) < 1e5` still drops an
  out-of-range `h` before it ever reaches `run_active_frame`'s projection — the one place a huge
  `h` could do anything. **Noted as an optional refinement below**, not a required fix: `implementation-m3.md`'s
  own prose ("rejects on any non-finite or out-of-bound `x`/`z`/`h`") overstates what the code
  actually checks for `h` (finite only, no magnitude cap) — worth tightening the wording or adding
  the matching bound for full layer-to-layer symmetry, but there is no live gap today.

## Checks (reproduced independently, not taken on the implementer's word)

**aircraft-layer** (`aircraft-layer/.venv`): `ruff format --check src tests` — pass (90 files).
`ruff check src tests` — pass. `mypy src` (from inside `aircraft-layer/`) — pass, 0 issues, 29
source files. `pytest tests -q` — **1325 passed** in 129.77s (matches implementation.md's count).
`luac5.1 -p` on both touched Lua files (`flight_control.lua`, `flight_profile.lua`) — pass.

**body-layer** (`body-layer/.venv`): `ruff format --check src tests` — pass (236 files).
`ruff check src tests` — pass. `mypy src` (from inside `body-layer/`) — pass, 0 issues, 96 source
files. `pytest tests -q` (full suite, `PYTHONPATH=src:../world-model/src`) — **3927 passed,
4 xfailed** in 311.00s, matching implementation.md's own figure exactly (the 4 xfails are
pre-existing and unrelated to this change).

No `.venv` present in this worktree for either subproject — both runs used the main checkout's
venvs (`/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`,
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv`), `mypy` run with CWD inside each subproject.

## Scope check

Matches the plan's "M3 revision R1" section exactly: R1-a (speed-give delta), R1-b (performance
findings 1/2), R1-c (security findings 1/2), one batch, no more, no less. No roadmap edits made by
this review, per the task's own scope. No tuning.py/defaults.toml change needed or made — neither
R1-a's constants nor R1-b/R1-c touch a behaviour-affecting constant covered by that mechanism.

## Required Fixes

None.

## Optional Refinements

- `aircraft-layer/src/api/server.py`'s `_terrain_relay_passes_bounds` checks `h` for finiteness
  but not magnitude, while `implementation-m3.md`'s "R1-c" section describes it as rejecting
  "non-finite or out-of-bound `x`/`z`/`h`." Either add the matching `abs(h) >
  _TERRAIN_POINTS_COORD_ABS_MAX` (or `1e5`, to match Lua's own tighter bound) check for full
  layer symmetry with the Lua side, or correct the implementation note's wording to describe what
  the code actually does. Not exploitable today (Lua's own `|h| < 1e5` check still runs
  independently before any value reaches `run_active_frame`), and outside what `security-m3.md`
  Finding 1 asked for — purely a documentation-precision / defense-in-depth nicety.

## Verdict

**APPROVED.**

## Review Confidence

Full read. Traced the terrain-gate call graph, the LOS-cache poll-stamp sharing, and the relay
bound asymmetry by hand against the actual code (not the implementer's prose), reran every new/
changed test directly under `luajit`/`pytest`, and ran both subprojects' full format/lint/type/test
suites myself rather than relying on `implementation-m3.md`'s own reported numbers.
