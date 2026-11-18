# Re-review — BL-16 mode 1, Stage M2 review-fix round

Branch `feature/bl16-raw-axes`, target tip `36366f22`. The dispatched worktree's `HEAD` was
`59192cfa` (an unrelated, already-merged fix from a different feature) and not an ancestor of
`36366f22`, so per the dispatch instructions I created `review-m2b` at the target tip in this
worktree (`git branch review-m2b 36366f22 && git checkout review-m2b`) rather than fast-forwarding.
Tree was clean before and after.

Reviewed against: `plans/flight-control/review-m2.md` (the prior NEEDS REVISION, Required Fixes
1–3), `plans/flight-control/implementation.md`'s new "M2 review-fix round" section,
`plans/flight-control/plan.md` (Decisions 18, 21–25), and the diff `6f94b00c..36366f22` (commits
`9700464b`, `40e58280`, `36366f22`).

## Review Summary

All three items from `review-m2.md` are fixed, correctly and at the scope the review asked for.

**Required Fix 1 (taking-window goal drop / false-confirmation readback).** `body.py`'s
`_apply_flight_control` now holds a pending goal transition unsent and uncleared for as long as
`state.phase == "TAKING"`, sends it once `phase == "ACTIVE"`, and drops it (consumed, never sent)
once `phase == "PILOT"` (a failed take). `FlightControlPhase` is a four-value `Literal` (`PILOT`,
`TAKING`, `ACTIVE`, `OVERLAY`) and every value is accounted for: `OVERLAY` is already cleared
earlier in the function (pre-existing code), `TAKING` holds, `ACTIVE` sends, anything else (i.e.
`PILOT`) falls through to the comment-documented drop — no fifth case can reach the new branch
unnoticed. I independently mutated `body.py` back to the pre-fix unconditional-send form (removing
the `state.phase != "TAKING"` guard and the `ACTIVE` check) and reran
`test_body_flight_control.py`: all three new tests (`test_a_goal_during_taking_is_held_not_sent_
and_not_cleared`, `test_a_held_goal_is_sent_once_phase_becomes_active`,
`test_a_goal_held_through_a_failed_take_is_dropped_not_sent`) went red, confirming they actually
exercise the fix rather than passing vacuously. Reverted; `shasum` before/after matched. The two
pre-existing tests' `phase="PILOT"` → `phase="ACTIVE"` changes are legitimate: those tests exist to
exercise the goal-send path, which is only reachable from `ACTIVE` under the new code (the old
default `phase="PILOT"` was an artifact of the test never setting phase, not a realistic scenario
a goal action can reach — `has_controls`, and therefore an `axes_*` goal action, requires `TAKING`
or `ACTIVE`, never bare `PILOT`).

One residual point, not a defect: the readback still speaks the commanded value immediately
("Heading 315") before the goal has actually reached the law, for the duration of the one-frame
`TAKING` window. The fix resolves this in substance rather than literally — the held goal is sent
on the very next poll once `ACTIVE` is confirmed (sub-second in practice), so the window during
which the spoken readback and the actual commanded value disagree is now bounded to one frame and
self-corrects, rather than being lost permanently as it was before. The review's own required fix
asked for exactly this (hold-and-retry or re-apply, not "fix the readback timing too"), so this is
in scope and resolved.

**Required Fix 2 (`TestPauseRowHolds` asserting presence, not value-unchanged).** Both tests now
inject a real heading-goal mismatch (90° against a zero-heading mock) between take and the paused
frame, then compare written roll/pitch before and after within `2 * FLIGHT_WOBBLE` (`0.0021`) — the
tolerance the alternating wobble parity requires, since even a correctly-frozen rewrite differs
from the prior write by up to one wobble step. I reran the exact mutation the original review used
(`law_update(fc_law, 0.5, measured, fc_limits)` in the pause branch instead of freezing) against
this diff's code: both `TestPauseRowHolds` tests fail (roll moves `0.199 → 0.771`, far outside
tolerance), confirming the strengthened assertion actually catches the mutation it was written for.
Reverted (`luac5.1 -p` clean, `shasum` matched before/after). The implementer's own memory note
(`.claude/agent-memory/implementer/feedback_bl16_m2_pause_test_needs_real_tracking_error.md`)
correctly identifies *why* a goal mismatch was necessary — without one, every reference is bit-exact
at take and an un-frozen `law_update` is a mathematical no-op, which would have made a naive
value-equality assertion pass under both the fix and the bug. This is exactly the right level of
diligence for a strengthened test and matches what I independently verified.

**Documentation accuracy (`OMEGA_ALT`).** `implementation.md`'s Notable Discoveries entry is
reworded to state what the counterfactual actually measured (0.2 already well under the 10 m floor
at every tested climb rate; 0.5 only reduces overshoot further) rather than implying 0.2 crossed a
pass/fail line. No gain changed, wording-only, matches the review's own table.

## Required Fixes

None.

## Optional Refinements

- The one-frame readback-ahead-of-confirmation window noted above under Required Fix 1 is now
  bounded and self-correcting rather than permanently lost, but it still exists as a theoretical
  sub-second mismatch between what Petrovich says and what the law is doing. Not required — the
  review's own fix alternatives both accepted this residual, and fixing it fully would mean
  deferring the readback itself until `ACTIVE`, a larger change not asked for here. Worth a one-line
  note if a later stage ever investigates readback timing more generally.

## Verdict

**APPROVED**

## Review Confidence

Full read of the diff (`6f94b00c..36366f22`), both strengthened Lua tests, the three new body-layer
tests, the updated `apply_goal_fields` comment, and `implementation.md`'s new section. Both required
fixes were verified by mutation, run directly in this worktree (not re-read from the implementer's
report): reverted `body.py`'s RF1 fix and confirmed all three new tests go red; reapplied the
review's own RF2 mutation to `flight_control.lua`'s pause branch and confirmed both
`TestPauseRowHolds` tests go red. Both reverted cleanly (`shasum`-confirmed). All mechanical checks
rerun directly in this worktree:

- **aircraft-layer**: `ruff format --check`/`ruff check src tests` pass; `mypy src` — 28 files, no
  issues; `pytest tests -q -m "not slow" -n auto` — 952 passed (smoke-equivalent); the three
  flight-control-specific test files — 68 passed; `luac5.1 -p` on `flight_control.lua` — pass.
- **body-layer**: `ruff format --check`/`ruff check src tools tests` pass; `mypy src`
  (`PYTHONPATH=../world-model/src`) — 92 files, no issues; `pytest tests -q -m "not slow" -n auto`
  — 3590 passed, 4 xfailed; `test_body_flight_control.py` alone — 11 passed.

(Venvs for both subprojects do not exist inside this worktree — they live only in the main
checkout — so each was invoked explicitly as `/Users/sg/Code/DCS-petrobrain/<sub>/.venv/bin/<tool>`
against this worktree's source tree, run from inside the subproject directory for correct
CWD-relative config discovery.)
