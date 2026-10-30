# Definition of Done — elevation-mark calibration fit (lean pass)

Branch `fix/9k113-el-calibration`, tip `8bb7e896313431bdb036e0a133aaa988e4135768`. **This verdict
is scoped to that commit** — if the branch moves, re-check before relying on it.

Lean pass per user direction (2026-10-30, "rather heavy and time consuming"): no notes harvest
(nothing new — this is a constant re-fit using a method this project already uses), no new
agent-memory entry, no test card (live acceptance already published on `BL-B80`'s hands-off-switch
entry; the result folds into that same outstanding sortie).

## What it is

Two elevation-mark calibration constants in `aircraft-layer/dcs-export/Export.lua`
(`MARK_BORESIGHT_EL` 0.83 -> 0.8333, `MARK_DEG_PER_UNIT_EL` 1/0.037 -> 1/0.0277), replacing a
2026-10-28 gimbal-derived guess with a value fitted against DCS AI Petrovich tracking a real unit
(BMD-1) with the 9K113 hands-off flag on, truth from body-layer's detection trace rotated into the
airframe frame — 107 samples, rms 0.006 deg, flat/linear across -1.7..-14.5 deg. Derived field
bounds and every consumer (`ASP17_FIELD_EL_UP_DEG`/`DOWN_DEG`, `sight_mark_is_clipped`,
`push_slew_trace`, the homing/closed paths) updated in lockstep. Test harness constants and one
docstring (renamed test, corrected stale "measured 2026-10-28" cross-reference) updated to match.
Research note added (`aircraft-layer/research/2026-10-30-9k113-asp17-elevation-mark-flight-fit.md`);
the superseded 2026-10-28 note carries a supersession pointer rather than being deleted or
silently left authoritative.

## Checklist

**Code Quality**
- [x] aircraft-layer's own commands pass, run from inside `aircraft-layer/` with
      `body-layer/.venv/bin` tools (its CLAUDE.md's "Commands" section, as `mypy`'s config
      discovery is CWD-only):
      - `ruff format --check src tests` — 75 files already formatted
      - `ruff check src tests` — all checks passed
      - `mypy src` (strict via `pyproject.toml`) — no issues, 26 source files
      - `luac5.1 -p dcs-export/Export.lua` — clean (syntax check; Lua is not type-checked)
      - `pytest -q` — 649 passed, 2 failed. The 2 failures
        (`test_collector_server_accept_errors.py::test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers`,
        `::test_close_during_a_blocked_accept_ends_the_loop_cleanly`) are the known pre-existing
        environment issue (`OSError: [Errno 98] Address already in use` on `sock.bind`, a port
        collision in this sandbox, not a code defect) — confirmed pre-existing on `main` earlier
        today and reproduced identically by Reviewer's own run in `review-el-calibration.md`.
      - No body-layer source changed by this branch (only Lua + an aircraft-layer test file +
        research notes) — no body-layer gate needed.
  - No other subproject touched (diff is confined to `aircraft-layer/`, `plans/`, `aircraft-layer/research/`).
- [x] No unhandled errors/panics in data paths — the change is two numeric literals and derived
      comments; no new control flow.
- [x] No debug output left in committed code — grepped the touched files for `TODO`, none found.
- [x] No leftover debug code or TODO comments introduced by this feature.

**Scope & Correctness**
- [x] Matches `plans/9k113-sight-pointing/plan.md` — this is a calibration re-fit of the v3 design's
      existing `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` constants, the same mechanism the plan's
      "mechanism and calibration never share a commit" invariant (body-layer/CLAUDE.md) expects to
      recur as better flight data arrives — not new scope.
- [x] No unplanned scope added — diff is confined to the two constants, their dependent comments/
      derived field bounds, the test harness mirror, and a research note. Reviewer confirmed no
      hardcoded old values remain anywhere else in `Export.lua`, and grepped body-layer for any
      duplicated encoding of the mark field (none — body-layer only knows the mechanical gimbal
      field-of-regard, a different, independently-sourced fact).
- [x] No CLAUDE.md invariants violated — "mechanism and calibration never share a commit" (this
      commit changes only calibration numbers, no logic); DCS stays authoritative (the fit is
      against DCS's own AI-tracked truth, not an external source).
- [x] All new files staged — confirmed via `git status --porcelain` (empty) after the ff-merge;
      the research note and review file are both tracked.

**Testing**
- [x] Core logic covered — `test_sight_servo_lua.py`'s elevation-mark/clip/field tests exercise the
      new constants via the Lua harness; the renamed
      `test_elevation_down_field_bound_is_past_the_gimbal` asserts the new derived behaviour (parks
      at the -15 deg gimbal stop, not a field inset) rather than being a stale assertion against
      the old numbers.
- [x] Tests are meaningful — Reviewer confirmed the rename is a like-for-like replacement guarding
      something real (the field clip never engaging on a side it no longer reaches), not a
      weakened test.
- [x] No existing tests broken by this change (the 2 failing tests are the pre-existing,
      unrelated environment issue above, present on `main`).

**Documentation**
- [x] Reviewer findings addressed — `review-el-calibration.md`'s only item (stale
      "measured 2026-10-28" date in `_mark_raw`'s docstring) is fixed in the tip commit
      (`8bb7e896`), confirmed by diff. No required fixes were raised.
- [x] Non-obvious behaviour explained — the research note carries method, sample count, residual,
      and the two things it rules out (a wrong rotation order would show as a residual trend, not
      noise this small; hand-slewing was tried and rejected as biased). The superseded note is
      marked, not deleted, preserving the pilot's original "about boresight" quote per
      `docs/PROCESS.md`.

**Security**
- [ ] No `security-plan-review-el-calibration.md`/`security-review-el-calibration.md` written.
      **Deliberately skipped** — user direction 2026-10-30 to skip performance/security passes for
      a small change (two numeric constants, no new code path, no new dependency, no new external
      input). Same disposition as this milestone's own hands-off-switch entry
      (`body-layer/ROADMAP/BL-B80.md`, "Performance/Security passes skipped by user direction
      (small change)"). Consistent with root `CLAUDE.md`'s own standing batching rule for these two
      roles — this is not a silent omission.

## Acceptance boundary

**What this cannot verify by construction**: whether the real 9K113's ATGM cross now visibly sits
on the target in actual flight. The fit is statistically strong against logged truth (rms 0.006
deg over 107 samples spanning the deployed elevation range), but that is a fit against a recorded
trace, not a live observation of the cross against the real optic. The next sortie is what closes
this.

**`#needs-flight`** — recorded on `body-layer/ROADMAP/BL-B80.md` below, not as a separate debt list
entry.

## Unblock condition executed

This entry's clearing condition is "fly it and confirm the cross sits on the target" — there is no
command to run here (it is a live-DCS visual check, not a script), so nothing to execute
mechanically. Noted rather than skipped silently.

## Verdict

**PASSED** (lean pass, security/performance deliberately exempted per user direction above).
Acceptance testing is **PENDING (live)** — carried forward as `#needs-flight` on `BL-B80`, batched
with the hands-off-switch calibration flight already outstanding there. No test card published
separately for this entry: it is the direct output of the flight the hands-off-switch card already
named, not a new ask of the user.
