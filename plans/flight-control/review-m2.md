# Review — BL-16 mode 1, Stage M2 (the controller)

Branch `feature/bl16-raw-axes`, target tip `f78d90af`. The dispatched worktree's `HEAD` already
equalled `f78d90af` on inspection (`git rev-parse HEAD`), tree clean — no merge or checkout needed.

Reviewed against: `plans/flight-control/plan.md` ("Revised 2026-11-18" mode 1 re-cut, "The control
law, as a first implementation should follow it", Decisions 21–25, "Stages" M2 entry),
`plans/flight-control/implementation.md`'s "Mode 1, Stage M2" section, `review-m1b.md`, M0
measurements (`git show eef87430:aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`
on `probe/bl16-flight-axes`), and the diff `a2450e34..f78d90af`.

## Review Summary

The law is well-structured: five pure functions over an explicit state table exactly as the plan
asks, bit-exact at take (confirmed by direct toy-plant test and by my own reading of
`law_init_at_take`'s `t_p`/`t_r` solve), NaN/nil-guarded on every new getter, and the two caught bugs
(`ALT_ACCEL_CAP_MPS2` vs `max_climb_vs_mps` in the stopping-height formula; the `api/server.py`
limits whitelist silently dropping M2's 8 new keys) are real, correctly fixed, and backed by
counterfactual reverts I independently re-ran. Both subprojects' format/lint/type/test checks pass
clean (821/2811 fast-test runs, 68/68 flight-control-specific tests), `luac5.1 -p` passes, and the
rendered `defaults.toml` first sentences for all 8 new tunables read correctly with no truncation or
corruption.

Two things need fixing before this merges, and one documentation claim needs correcting. All three
are cheap.

## Required Fixes

### 1. A goal spoken during the one-frame `taking` window is silently dropped, and nothing detects or corrects the resulting mismatch between the reported goal and what the law actually flies

The implementer's own account treats this as "not expected in practice" because `held_*` HOLD-until-
known gates block a goal action before `active` is confirmed. That is true for the **relative**
forms (`turn_heading_relative`, `level_off` via `_flight_control_heading`/`_flight_control_speed`/
`_flight_control_altitude`/`_flight_control_any`, which gate on `held_* is not None`), but **not**
for the absolute-set forms — `axes_set_heading`/`axes_set_speed`/`axes_set_altitude` all route
through `_flight_control`, which only checks `has_controls` (`body-layer/src/rules/gates.py:85-90`).
`has_controls` is already `True` the instant `phase` becomes `"TAKING"`
(`crew_console.py:3278-3300`: `has_controls = parked.parked_active or flying_axes`, and
`flying_axes = axes.phase in ("TAKING", "ACTIVE")`), i.e. before Lua has run even one frame.
`_apply_flight_control` (`body.py:3505-3575`) sends a queued `flight_control_goal_transition`
unconditionally whenever `phase != "OVERLAY"` — there is no check for `phase == "ACTIVE"` before
sending.

On the Lua side, `apply_goal_fields` (`flight_control.lua`) only calls `law_apply_goal` when
`fc_law ~= nil`; while `fc_law is nil` (off/taking/armed) the goal is recorded into the `fc_goal_*`
wire-echo locals (so `GET /flight_control/latest` reports it) but is never applied to `fc_law`
itself. When `law_init_at_take` later runs, it seeds `heading_goal_deg`/etc. from the **measured**
value at capture, never reading the pre-existing `fc_goal_*` locals. The result: `fc_goal_heading`
(and the analogous altitude/speed fields) keep reporting the spoken goal indefinitely — nothing ever
reconciles them — while the law is actually holding whatever it captured at take. Meanwhile
`axes_set_heading` returns `{"ok": True, "heading_deg": deg}` unconditionally and the readback speaks
that value immediately, regardless of whether the goal reached the law. A pilot who says "I have
controls, heading 315" close together gets told "Heading 315" and Petrovich keeps flying whatever
heading he had at takeover — a false confirmation, not merely a dropped frame.

This is the kind of "co-moving state fields stay consistent across every transition" / "callouts
fire when the pilot would expect" case Security no longer backstops (root `CLAUDE.md`'s rebalanced
review scope, this role's checklist). No test exercises this window at all (`grep -n taking
tests/test_flight_control_lua.py` finds nothing but a comment).

**Fix** — one of:
- Have `body.py`/`_apply_flight_control` hold a queued goal transition until `state.phase ==
  "ACTIVE"` rather than sending it during `"TAKING"` (symmetric with the `held_*` gates'
  already-stated intent), or
- Have Lua apply any still-pending `fc_goal_*` value the frame `fc_law` is created (read it inside
  `law_init_at_take`'s own caller, not just measured values), so a goal that does arrive during
  `taking` is not lost.

Either way, add a test exercising a goal command delivered while `fc_mode == "taking"`.

### 2. `TestPauseRowHolds` asserts a write happened, not that it is unchanged — it does not catch a regression that un-freezes the shaper during a pause

The plan's own pause-row requirement is explicit: *"the last outputs are written again with
wobble. Shapers and integrators are frozen."* `test_a_paused_frame_rewrites_outputs_unchanged`
(`test_flight_control_lua.py:714-727`) only asserts `written[2001] ~= nil` — that *something* was
written to the pitch command, not that it equals the pre-pause value, and not that `fc_law`'s
integrators didn't move.

I confirmed this is not merely theoretical: I mutated the pause branch of `run_active_frame` so that
on a paused/huge-jump frame it calls `law_update(fc_law, 0.5, measured, fc_limits)` and writes the
result — i.e. it advances the shaper for half a second instead of freezing it, a direct violation of
the plan's pause-row requirement. `TestPauseRowHolds` (both of its tests) still passed unchanged.
Mutation reverted; `git status --porcelain aircraft-layer/` confirmed clean before and after.

**Fix** — strengthen the test to compare the written pitch (or `fc_law`'s own `psi_ref`/`h_ref`/
`v_ref`, read back via the status push) against its value immediately before the pause, asserting
equality (or, for the law state, that the fields it owns did not change across the paused frame).

## Documentation accuracy (fold into the fix above or a follow-up commit; not a code defect)

### `OMEGA_ALT`'s raise from 0.2 to 0.5 is not demonstrated by the current toy-plant test

`implementation.md`'s Notable Discoveries states `OMEGA_ALT` was raised "to keep the overshoot
comfortably inside the altitude band (well under the ≥10 m floor) for the climb rates tested (1–4
m/s)." I reverted `OMEGA_ALT` to `0.2` and ran both the full `test_flight_control_law.py` suite (11
passed) and a standalone probe at the plan's own tested climb rates:

| `OMEGA_ALT` | climb rate | goal (m) | max overshoot (m) | band (m) |
|---|---|---|---|---|
| 0.2 | 4 m/s | 208.0 | 2.41 | 20.8 |
| 0.5 | 4 m/s | 208.0 | 0.33 | 20.8 |
| 0.2 | 5 m/s (the shaper's own ceiling) | 212.5 | 2.40 | 21.25 |
| 0.5 | 5 m/s | 212.5 | 0.31 | 21.25 |

At `0.2`, overshoot is `2.4 m` at every climb rate tested — already well under the `10 m` floor the
claim cites, and the existing test passes at both values (confirmed above, "all 11 passed"). The
gain increase is a reasonable judgement call (less overshoot is better, all else equal) but the
specific claim that it was *needed* to stay under the stated floor, for the climb rates actually
tested, is not what the numbers show. Reword the Notable Discoveries entry to state what was
actually observed (less overshoot at 0.5, not a pass/fail boundary crossed), so a later reader
retuning `OMEGA_ALT` doesn't treat `0.2` as unsafe when it demonstrably isn't, at this scale.

## Checked, not required fixes

- **OMEGA_ALT raise vs. the toy-plant test's own pass criterion (task point 1)**: not a weakening.
  "Any overshoot stays inside the band" is the plan's own listed alternative pass criterion
  (`plan.md`'s "Offline tests run under luajit", bullet list), not a blanket "never reverses" — the
  test correctly asserts what the plan allows. Only the *narrative* in Notable Discoveries overstates
  what that gain choice bought (see above).
- **No slip-ball feedback in the pedal channel (task point 2)**: acceptable for M2. `LoGetSlipBallPosition`
  was never probed (not even M0-A), and guessing its sign/units risks a wrong-sign pedal command —
  worse than omitting the term. Correctly named "owed by M0-E and a slip-ball probe both" in the
  module header and `implementation.md`. No action required now; worth a slip-ball probe card before
  Flight M-A if pedal coordination proves too weak on the feedforward term alone.
- **`sortie-log-triage`'s flight-trace section (task point 5)**: the plan places it under "Flight
  M-A", not under M2's own bullet list, and it is also structurally a skill-file edit routed through
  its own worktree per root `CLAUDE.md`'s "Workflow". Leaving it unbuilt here is the right call, for
  both reasons.
- **Behaviour-affecting constants**: all 8 new body-layer tunables go through `tuning.py` with
  `lo`/`hi` bounds and their own individual `#:` comment (not a shared block — the exact mistake
  `implementer`'s own memory file for this round names having made and caught). Rendered
  `defaults.toml` first sentences read correctly for all 8 (checked directly, not from the source
  comment). The Lua-side "M2 control law constants" block carries the "would want the X-T26
  mechanism; outside body-layer it does not exist" note — closing the exact gap `review-m1b.md`'s
  Required Fix 1 found in the previous round for `STOWED_THRESHOLD`/`LIVE_SEAT_ZERO_EPS`.
- **Safety**: output saturation (`law_clamp(..., -1.0, 1.0)` on every axis in `law_outputs`), rate
  limiting (`OUTPUT_RATE_LIMIT_PER_S` in `write_outputs`), bank/pitch clamps (`MAX_BANK_DEG`,
  `THETA_MIN_DEG`/`THETA_MAX_DEG`), NaN/nil guards on every new getter (`LoGetAngularVelocity`/
  `LoGetVerticalVelocity`/`LoGetTrueAirSpeed`/`LoGetAltitudeAboveSeaLevel`, all fail-soft to a
  defined default), the pause-row freeze (present in code, under-tested — Required Fix 2), and
  release-stops-writes-same-frame (`TestReleaseStopsWritesSameFrame`, unmodified and still passing)
  all check out.
- **`_FLIGHT_CONTROL_LIMITS_BOUNDS`'s silent-drop-on-unknown-key pattern (task point 4)**: this
  whitelist shape (`for field in BOUNDS: if field not in raw: continue`) is the pre-existing
  convention for every `/command/*` endpoint in this file, not something introduced here — the
  8-key fix correctly closes the specific bug this round found. The *pattern itself* (silently
  dropping, never erroring, on an unrecognised `limits` key) is a standing hazard for the next
  wire-field addition, already documented as a lesson in the implementer's own memory file for this
  round. Not a required fix on this diff (fixing it project-wide is a separate, larger change
  touching every `/command/*` handler) — worth a backlog item.
- **Cross-key coupling, `MAX_TURN_BANK_DEG` vs. `MAX_BANK_DEG`**: no import-time assertion ties
  them, and their independent bounds (`5.0–45.0` vs. `10.0–60.0`) allow a jointly-invalid pair (e.g.
  `max_bank_deg=10`, `max_turn_bank_deg=45`) where the commanded turn rate implies a bank the law's
  own `phi_d` clamp can never reach — a steady tracking error, not a crash or an unsafe write (the
  output stays within `max_bank_deg` either way). Defaults are consistent (20 ≤ 30). Not a required
  fix; flag for Flight M-A/M5 tuning awareness, since nothing would stop a later tuning session from
  setting an inconsistent pair.
- **No dedicated toy-plant test for `OUTPUT_RATE_LIMIT_PER_S`** (the plan's "per-frame output change
  and its rate of change stay under the limits" criterion): covered only implicitly. Low risk — the
  limit is deliberately generous ("not itself behaviour the pilot would tune... kept generous," per
  the module's own comment) and guards against a shaper bug rather than expressing tunable
  behaviour. Optional refinement, not required.
- **Body-layer's "full mode-1 action bodies, clamps, readback values, held_* projection"** (the
  plan's M2 bullet for body-layer) were already built in Stage M1/BL-17 (confirmed via `git log`:
  `axes_set_heading`/`axes_set_altitude`/`axes_set_speed`/`axes_level_off`/`axes_hold_altitude` all
  predate `a2450e34`). This round's body-layer diff is correctly scoped to the shaper-limit/band
  tunables and `in_band_*` mirrors only — not a gap, the plan's bullet was already satisfied before
  this round started.

## Checks run

**aircraft-layer** (fresh `.venv`, `pip install pytest mypy ruff pytest-xdist` + `pip install -e .`):
- `ruff format --check src tests`: pass (85 files)
- `ruff check src tests`: pass
- `mypy src`: pass, no issues (28 source files)
- `.claude/scripts/fast-tests.sh aircraft-layer`: 821 passed
- `pytest tests/test_flight_control_lua.py tests/test_flight_control_law.py
  tests/test_flight_control_api.py -q`: 68 passed
- `luac5.1 -p` on `flight_control.lua`: pass

**body-layer** (fresh `.venv`, same packages + `pip install -e .`):
- `ruff format --check src tools tests`: pass (241 files)
- `ruff check src tools tests`: pass
- `mypy src` (`PYTHONPATH=../world-model/src`): pass, no issues (92 source files)
- `.claude/scripts/fast-tests.sh body-layer`: 2811 passed, 4 xfailed

**Counterfactual/mutation checks run myself** (not just re-reading the implementer's own):
1. Reverted `_FLIGHT_CONTROL_LIMITS_BOUNDS`'s own 8-key addition mentally traced, not re-run (the
   implementer's own counterfactual for this one — reverting and re-running the two new
   `test_flight_control_api.py` tests — is independently plausible from reading the code path; I
   re-derived the whitelist-drop mechanism directly from the source rather than re-running it).
2. Reverted `OMEGA_ALT` 0.5→0.2 and ran `test_flight_control_law.py` (11/11 still pass) plus a
   standalone `luajit` probe at both the plan's tested climb rates and the shaper's own ceiling (5
   m/s) — see "Documentation accuracy" above.
3. Mutated `run_active_frame`'s pause branch to advance the law for a synthetic `dt=0.5` instead of
   freezing it — `TestPauseRowHolds` (both tests) still passed. Reverted; `git status --porcelain`
   confirmed clean before and after.

## Verdict

**NEEDS REVISION** — two required fixes (the taking-window goal drop with its false-confirmation
readback, and the pause-row test's missing unchanged-value assertion), plus one documentation
correction. Everything else checked is sound: the law's structure, the two real bugs this round
caught and fixed, the tuning/rendering convention, and every mechanical check (format/lint/type/
test/Lua-parse) across both subprojects.

## Review Confidence

Full read of the diff (`a2450e34..f78d90af`), the Lua control law in its entirety, the toy-plant
and whole-module Lua test files, the body-layer tuning/limits diff, and the relevant gate/action code
in `crew_console.py`/`body.py`/`rules/gates.py` the taking-window finding required tracing. Mutation
checks run directly (not merely re-read from the implementer's report) for the two required fixes
and the documentation-accuracy item. Not independently re-verified: the implementer's own
counterfactual for the `_FLIGHT_CONTROL_LIMITS_BOUNDS` fix (traced by reading, plausible and
consistent with the passing pinning test, but not re-run by reverting it myself).
