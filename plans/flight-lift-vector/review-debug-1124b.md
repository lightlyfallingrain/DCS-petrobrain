# Review: BL-16 LV-1 debug pass 2, 2026-11-24 (pedal-sign revert, RPM guard, seat rule)

Reviewed `ebbbdcc5` (diff against its parent) on `feature/bl16-lift-vector-law`. Inputs read in
full: `plans/flight-lift-vector/debug-2026-11-24b.md`, `docs/acceptance/2026-11-24-sortie-feedback.md`,
the first-pass `debug-2026-11-24.md` and `review-debug-1124.md`, the updated research notes
(`2026-11-18-bl16-m0-flight-axes-findings.md`, `2026-11-20-slip-ball-recon.md`), `BL-16.md`'s new
bullet, and both touched test files line-by-line against the production diff.

## Summary

All four claimed changes are present and each is internally consistent with the diagnosis in
`debug-2026-11-24b.md`:

1. **Pedal-sign revert.** `flight_profile.lua` and both test mirrors (`test_flight_control_law.py`,
   `test_flight_control_lua.py`) go back to `k_ball_pedal = +0.3`, `rotor_dir = +1.0`,
   `k_turn_coord_pedal = +0.02`, `pedal_limit_positive = 0.5`, `pedal_limit_negative = -1.0` —
   exactly the pre-first-pass values. The collective-near-pedal-limit guard that the first review
   (`review-debug-1124.md`) required to be fixed was fixed by deriving its side from
   `law_sign(k_pedal_from_collective_rate * rotor_dir)` rather than a hard-coded limit name
   (`flight_control.lua` lines ~868-884) — that fix is sign-agnostic and was **not** touched this
   pass, and correctly flows through the revert unchanged: `rotor_dir = +1` now makes
   `pedal_push_sign > 0`, so the guard checks `pedal_limit_positive` (0.5, the scarce/right side
   again) — the same side it protected before the first pass ever ran. Confirmed by reading the
   code, not just trusting the comment.

   Every other pedal-domain consumer I could find (`t_y`, `d_t_y`, `pedal_limit`, `SIGN.pedals`,
   the anti-windup clamp at lines ~998-1004) reads the gains/limits symbolically and needs no
   separate update. `SIGN.pedals` (command = `-arg`) is untouched, as stated, and was never in
   question either pass.

2. **RPM guard strict compare.** `rotor_rpm_limited` changed from `<=` to `<` against
   `limits.rotor_rpm_floor_pct + profile.rotor_rpm_near_floor_margin_pct` (85 + 5 = 90), which is
   exactly `ROTOR_RPM_DUMMY_PCT`. New test `test_the_shipped_dummy_rpm_reading_lets_collective_rise`
   reads the dummy from the real module (`flight_control.read_rotor_rpm_pct()`), not a restated
   literal, so a later change to either constant that re-creates the lockout will fail this test.
   I did not find a test with `rotor_rpm_pct` hard-coded to exactly `90.0` as a boundary check
   independent of the dummy — the new test doubles as that boundary case, since the dummy's value
   *is* 90.0, so this is adequate, not a gap.

3. **Player-seat-first capture.** `resolve_capture_values` now checks
   `ai_pilot_wheel.player_seat()` first and captures that seat fresh when its own set reads live
   (`axis_magnitude(seat) > LIVE_SEAT_ZERO_EPS`), falling back to the pre-existing live/last-steady
   rule otherwise. The fallback for an idle known seat (M0-J/J1's explicit-handover case) is
   preserved **and still tested** —
   `test_captures_the_live_pilot_set_with_the_camera_in_the_operator_seat` sets `ap_seat =
   "operator"` with the operator args at 0 and the pilot args live, and still asserts the pilot
   value is captured, proving the new priority branch's `axis_magnitude(seat) > eps` guard
   correctly declines to fire for an idle seat. The unpark-take path (`fc_last_stowed_pilot_capture`
   / `capture_from_seat("pilot")` on the stow edge) is untouched except for a diagnostic
   `fc_capture_source` tag — confirmed by diff, no logic there changed.

   `ai_pilot_wheel.lua`'s `player_seat()` is a plain accessor returning the already-existing
   `ai_pilot_player_seat` module variable (`"pilot"|"operator"|nil`); nothing in this pass adds a
   side effect to reading it, and it is read twice per take (once in `resolve_capture_values`, once
   again for the debug line) — both reads are of the same already-computed value, harmless.

   **Timing note (not a regression, pre-existing shape):** `ai_pilot_player_seat` is refreshed by
   `ai_pilot_update_seat` inside `run_ai_pilot_wheel`, which `Export.lua` calls *after*
   `run_flight_control` each frame (`call_if(flight_control, ...)` then `call_if(ai_pilot_wheel,
   ...)`). A take's capture therefore reads one frame's worth of lag on the camera-derived seat.
   Seat changes are human-paced, so this is very unlikely to matter, but it is worth knowing if a
   future seat-swap-at-the-moment-of-take defect ever needs explaining.

4. **Trace/flag gating.** `trace_axis_args()` (8 `read_axis` calls) is only ever invoked inside
   `if ... FLIGHT_TRACE_ENABLED` blocks — the per-take debug line and the per-sample flight-trace
   line — so it costs nothing when the flag is off, consistent with this being a testing aid under
   root `CLAUDE.md`'s light-path rule. `GETGLOBAL` leak check on `flight_control.lua` lists only
   DCS APIs, stdlib and genuine existing cross-module names (`ai_pilot_wheel`, `flight_desired`,
   `flight_profile`) — no new leaked global from `trace_axis_args`/`fc_capture_source`/the take
   debug line.

**The replaced test's justification holds.** The old
`test_a_cross_fade_at_the_moment_of_take_uses_the_last_steady_set` asserted "both seats live →
use the last-steady snapshot" unconditionally. Under the new rule that branch is reachable only
when the player's own seat is unknown/idle; with a known, live seat the correct behaviour is now
the opposite (capture that seat fresh, never the snapshot). The replacement,
`test_both_seats_live_captures_the_players_own_seat_not_a_snapshot`, correctly demonstrates exactly
that reversal with `ap_seat = "pilot"` live and the operator set also live, and the new
`test_player_in_operator_seat_with_live_controls_captures_the_operator_set` demonstrates the
operator-seat symmetric case. This is a justified replacement, not a silently weakened one.

## Required Fixes

None.

## Optional Refinements

- **One test gap, not a regression but worth closing while this area is fresh:** no test exercises
  `resolve_capture_values` with the player's seat genuinely unknown (`ai_pilot_wheel.player_seat()`
  returning `nil`, e.g. `ai_pilot_wheel` not loaded, or the camera read failing) while both seats
  read live. Every test driver in `test_flight_control_lua.py` sets `ap_seat` to `"pilot"` or
  `"operator"` explicitly; none leaves it `nil`. That is exactly the one case the debug report says
  the old rule is "kept only as the fallback" for, together with the idle-known-seat case — the
  idle-known-seat case *is* tested, the unknown-seat/both-live case is not. The guard itself is a
  trivial two-value string check (`seat == "pilot" or seat == "operator"`), so risk is low, but
  this is the exact class of edge case that produced the J1 incident, and a one-line test
  (`ap_seat = nil`, both seats live, assert the last-steady snapshot is still used) would close it
  cheaply. (Optional — the logic is simple enough that I would not block on this.)
- **RPM-guard shape, raised because the task asked me to weigh it:** the fix depends on exact
  floating-point equality between a static dummy (90.0) and a tuning sum (85 + 5 = 90.0) landing on
  the correct side of a strict inequality. The debug report is upfront that this is still fragile
  ("raising `ROTOR_RPM_FLOOR_PCT` to 85 or above re-trips it against the dummy") and that the real
  fix (live RPM, arg 42) is already owed elsewhere — I agree the strict-compare fix is the right
  *minimal* change for this pass rather than also changing what counts as "near the floor" while a
  dummy is in use. A slightly more defensive alternative — skip the guard outright when
  `ROTOR_RPM_SOURCE == "dummy"`, since a dummy by definition carries no real floor information —
  would remove the coincidental-equality dependency entirely, at the cost of a second branch in a
  guard whose job is otherwise simple. Not required given the existing test pins the current
  behaviour and the fragility is already documented, but worth considering if this guard is touched
  again before the live RPM reading lands.
- **Header comment at `flight_control.lua` lines ~46-61** ("Capture source, corrected after M0-J
  ... neither a voice take nor an unpark take reads the camera seat ... at all any more") is left in
  place below the new "Revised 2026-11-24" paragraph that supersedes its opening claim for voice
  takes specifically (it remains true for unpark takes). This follows the project's "supersession is
  marked, not deleted" convention in substance — the revision paragraph is clearly dated and
  cross-referenced — but a reader skimming only the first paragraph would come away with the
  flatly-wrong impression that voice takes never read the camera seat. A one-clause edit to the
  first paragraph's opening sentence (e.g. "...did not read the camera seat at all — see the
  revision below") would remove that ambiguity. Cosmetic; not blocking.

## Checklist evidence

- **Checks run this session** (worktree had no venv; symlinked `aircraft-layer/.venv` from the main
  checkout, removed before committing nothing new needed — no production `.py` changed):
  - `ruff format --check aircraft-layer/src aircraft-layer/tests` — clean, 90 files.
  - `ruff check aircraft-layer/src aircraft-layer/tests` — clean.
  - `cd aircraft-layer && .venv/bin/mypy src` — clean, 29 files (no `.py` production code touched).
  - `luac5.1 -p` on every `.lua` file in `dcs-export/` and `dcs-export/Petrobrain/` — clean.
  - `.claude/scripts/fast-tests.sh aircraft-layer` — smoke + 52 targeted files, **1003 passed**.
- **Mutation checks** (the debug report's own claims, re-verified by reading code rather than
  re-running a mutation myself for the sign revert, since the toy-plant tests are unchanged in
  mechanism from the first pass and that independence was already confirmed in
  `review-debug-1124.md`): the dummy-RPM test reads the module's own constant, so a revert of the
  guard back to `<=` would fail it by construction (90.0 not `< 90.0`) — confirmed by inspection of
  the assertion (`> 1e-3` on a rate that would be exactly `0.0` under the old comparison, given
  `rotor_rpm_pct = 90.0` exactly equals `floor + margin`).
- **Every pedal-sign consumer grepped** across `flight_control.lua`: `t_y`, `d_t_y`, `pedal_limit`,
  `rotor_dir`, `k_ball_pedal`, `k_turn_coord_pedal`, `SIGN.pedals` — one derived-sign guard (fixed
  last pass, untouched this pass, confirmed still correct under the revert), the anti-windup clamp
  (symmetric over both limits, correct as written), no hover/mode-2 pedal code yet (LV-1 is
  forward-flight-only).
- **Comment pruning**: the dated/verbatim-user-quote lines from the first pass (slip-ball note,
  `BL-16.md`) are kept and marked "superseded again," not deleted, per the "supersession is marked"
  rule — correct. The one place I'd tighten is the header comment noted above (optional).
- **Tuning mechanism**: no new behaviour-affecting constant was introduced this pass (the RPM guard
  compare operator and the gain/limit values are existing tunables/constants whose *values*
  reverted, not new fields) — nothing new owed to `defaults.toml`/`tuning.py`, and this subproject
  has no such loader regardless (root `CLAUDE.md`).
- **Vocabulary/STT**: no spoken vocabulary changed in this diff — not applicable.
- **Git status**: `aircraft-layer/.venv` symlink (created for this review session, not part of the
  diff) is the only untracked item; not staged, will not be committed.

## Verdict

**APPROVED.**

## Review Confidence

Full read of the diff (all four claimed changes), both debug reports, the sortie feedback, the
updated research notes and roadmap bullet, and both test files' relevant sections line-by-line
against the production code. All stated verification commands (ruff/mypy/luac/fast-tests) re-run
directly in this session rather than taken on the report's word. Not independently re-run as live
mutation testing beyond what's noted above (the sign-revert toy-plant mutation was already verified
in the first review and the mechanism is unchanged); this is a deliberate scope choice given the
mutation technique and gain values were already proven once and the change here is a value revert,
not new logic.
