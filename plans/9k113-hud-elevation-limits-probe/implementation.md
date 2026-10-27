### Implementation Summary

Single-purpose DCS Export probe measuring the ASP-17 HUD field's elevation clip limits (555/556),
the one measurement v3 of `plans/9k113-sight-pointing/plan.md` is still missing (azimuth's clip is
already measured; elevation was left as a placeholder pending this flight — pilot, 2026-10-26,
"Elevation - measure in flight"). User request, verbatim in the task: *"create a probe for
measuring the HUD elevation limits. slew up until limit, then down until limit and log the
values."*

No Architect pass — this is a small, single-purpose recon probe scoped directly by the user, in
the same shape as the ~15 other `Export.probe-9k113-*.lua` scripts already in the tree, so it went
straight to Implementer per `AGENTS.md`'s "small features, one role" guidance.

### Files Changed
- `aircraft-layer/dcs-export/Export.probe-9k113-hud-elevation-limits.lua` — new. Open-loop
  elevation AI-axis slew (`CMD_AI_ELEV`), one signed direction at a time (`POS` then `NEG`), with
  per-frame flicker dither on both AI axes (reused from the BL-B80 v2 calibration probe's
  `pulse_el` pattern — DCS intermittently ignores a held command otherwise, confirmed in
  `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` runs 6–8). A rolling `PLATEAU_WINDOW_S`
  window on raw 555 detects when the mark stops moving; on a candidate plateau the probe keeps
  commanding into it for `MARGIN_S` to rule out a momentary stall (if 555 moves again during the
  margin, it logs `STALL not a clip` and resumes seeking rather than accepting the plateau). The
  full POS/NEG sweep repeats `CYCLES = 3` times; the closing summary reports each direction's
  per-cycle plateau values and whether they are `CONSISTENT (real clip)` within `CONSISTENCY_EPS`
  or `INCONSISTENT` (possible unresolved stall). Logs per-frame rows (`t`, commanded elevation
  value, raw 555/556/566/565, OBSERV arg 886, segment/cycle label) as the task specified literally,
  not the sparser dense-then-throttled logging the calibration probe uses — acceptable log volume
  for a probe run of a few minutes.
  - **Deliberately does not determine which signed command is visually "up"** on the glass — that
    mapping is unconfirmed project-wide (`ai-latency-probe.md` run 2 called it "sign-inverted,
    probably down" and left it open). Phases are logged as `POS`/`NEG` by command sign only; the
    test card asks the pilot which one they saw rise.
- `docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md` — new test card: deploy steps
  (back up/restore `Export.lua`), air start/straight-and-level/overlay-off setup matching every
  other 9K113 probe card in this project, a timeline table, and what to bring back (up/down
  direction mapping, cycle consistency, the log path). Results section left for the flight.

### Tests Added
None — this is a DCS-interfacing Lua probe with no automated test, same posture as every other
`Export.probe-9k113-*.lua` script in the tree (`aircraft-layer/CLAUDE.md`, "Testing": "`Export.lua`
and the live Export.lua↔collector↔API path have no automated test — correctness there depends on a
real DCS process and socket peer"). Its correctness is checked mechanically (Lua syntax, the
local-before-global-reference bug class, see Checks) and then by flight.

### Checks
(aircraft-layer/ — no venv existed in this worktree; ran via the main checkout's
`aircraft-layer/.venv/bin/<tool>` with cwd inside this worktree's `aircraft-layer/`, which picks up
this worktree's own source/test files)
- `luac5.1 -p` on the new file and every other `dcs-export/*.lua`: pass
- `luac5.1 -l -p | grep GETGLOBAL` on the new file (the local-read-as-global bug class this repo
  has hit twice): clean — only genuine DCS/Lua globals (`GetDevice`, `LoGetModelTime`,
  `LoGetVersionInfo`, `lfs`, `io`, `os`, stdlib). No own local leaked as a global.
- `ruff format --check`: pass (no Python files touched)
- `ruff check`: pass
- `mypy --strict` (run from inside `aircraft-layer/`): pass
- `pytest aircraft-layer/tests -q`: 610 passed, including
  `test_dcs_export_lua_local_order.py` and `test_dcs_export_lua_syntax.py` (if present) over the
  new file

**Re-run after the required-fix round** (same commands, same worktree gap/workaround): `luac5.1 -p`
pass; `luac5.1 -l -p | grep GETGLOBAL` on the revised file: same clean list as before
(`GetDevice`, `LoGetModelTime`, `LoGetVersionInfo`, `lfs`, `io`, `ipairs`, `math`, `os`, `pcall`,
`string`, `table`, `tostring`, `type` — all genuine DCS/Lua stdlib, nothing of the probe's own);
`ruff format --check`/`ruff check`/`mypy --strict`: pass (still no Python touched); `pytest
aircraft-layer/tests -q`: 610 passed (confirmed by name, unfiltered `-v -k lua`: 208 passed across
`test_dcs_export_lua_local_order.py`/`test_dcs_export_lua_syntax.py` and the other Lua-touching
suites, none deselected by the filter missing a target).

### Required-Fix Round (2026-10-27, Reviewer: APPROVED WITH MINOR FIXES)

Reviewer flagged that `MARGIN_S = 3.0` could not rule out the documented 9K113 AI-axis command
gate (4–18 s typical, up to flight-duration once — `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`
runs 6–8): a gate onset at the very start of a SEEK phase would read as a confirmed plateau at
≈boresight within ~3.6 s, and the `CYCLES`-cross-check cannot catch it if the gate holds for every
cycle alike (see `.claude/agent-memory/reviewer/feedback_9k113_stall_vs_clip_margin_too_short.md`).
Required fix applied, plus the suggested optional margin lengthening (both review-listed fixes were
cheap, so both went in rather than picking one):

- **Travel-plausibility check (the primary defence).** A plateau is now only accepted if its travel
  from the SEEK attempt's own starting value is at least `MIN_TRAVEL_FRACTION = 0.5` of what
  `EL_RATE_CMD`'s rate times the elapsed seek time would predict for continuous, ungated motion, and
  is not within an absolute `MIN_TRAVEL_EL = 0.006` (≈0.2°) of boresight on its own. A plateau
  failing either check is logged `SUSPECT -- near-zero travel ... NOT accepted as a plateau,
  continuing to seek` (once per flat-window episode, not once per frame) and the probe keeps
  seeking rather than treating the gate's frozen value as an edge — it is never written to
  `results[dir][cycle]`, so it cannot surface as `CONSISTENT (real clip)` in the summary; a
  gate that never releases times out (now via `phase_start`, a per-direction timer that a SUSPECT
  retry does not reset) and reports "no plateau found", not a wrong number.
- **`MARGIN_S` raised 3.0 → 20.0** (the secondary defence), above the documented 4–18 s typical gate
  window. Since the old code reused `MARGIN_S` for the RETURN phase's final centring nudge too
  (review's optional-refinements note), raising it in place would have made that nudge overshoot by
  many degrees — split into its own `RETURN_NUDGE_S = 3.0`, keeping the nudge's behaviour unchanged.
  `MAX_PHASE_S` raised 30.0 → 60.0 to comfortably fit a real seek plus the longer margin hold.
- **Card updated** (`docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md`): a "What a
  gate-stall looks like by eye, and what to do about it" section (required), the revised runtime
  estimate (4–8 min, up from 2–4, driven by the larger `MARGIN_S`), and the optional refinements —
  the sight not returning to exact centre is expected (rate command, not a position command), and a
  returned elevation half-angle far from azimuth's already-measured ≈4.3° is worth a second look.

Not done: gating `START_DELAY_S` on the Л5 lamp instead of a flat timer (review's other optional
note) — left as-is, the review itself called the flat-timer risk low given the 2× margin over the
measured ~10 s alignment.

### Notable Discoveries
- **This worktree had no `aircraft-layer/.venv`** (gitignored, not copied by `git worktree add`).
  Ran every tool via the main checkout's `aircraft-layer/.venv/bin/<tool>` with `cwd` set inside
  this worktree's `aircraft-layer/` directory — the venv's `pytest`/`mypy`/`ruff` entry points are
  just Python scripts against that venv's interpreter and packages; cwd (not the venv location)
  determines which source tree they operate on. Confirmed this picks up the worktree's own files
  before relying on it for the full suite. Future implementers in a fresh worktree on this
  subproject will hit the same gap; worth a line in `aircraft-layer/CLAUDE.md` or
  `docs/AGENT_WORKTREE_PROTOCOL.md` if it recurs.
- `aircraft-layer/research/mi24p-command-surface.md` confirms `v_axis_velocity = 10°/s` for the
  9K113's elevation AI axis (`Devices_specs/9K113.lua`), which the probe's `EL_RATE_CMD = 0.05`
  (→ 0.5°/s) and the `MARK_PER_DEG_EL = 0.028` scale estimate both cite; the latter was never
  itself confirmed against a measured elevation range (only derived from the calibration probe's
  earlier flights), so the summary's degrees conversion is explicitly labelled "rough" — the raw
  555 values are the measurement that matters.
