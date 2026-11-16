# Review: BL-16 Stage P2a/P2b (voice goals for heading/altitude/speed + HVRT translate)

Branch `feature/bl16-p2-voice-goals`, reviewed at `e38e2862` (fast-forwarded cleanly from
`370f37c0`, which the worktree was at). Reviewed commits `78612734^..c1977eca` (the P2a/P2b
feature work itself) plus the two merges that followed (`c6673bbb`, `e38e2862`, which bring in
`fix/ai-wheel-pilot-seat-gate` and `feature/seat-change-triggers` from `main`) against
`plans/flight-control/plan.md`'s "Revised 2026-11-16 — Stage P2 ready to build" section, its
"Decisions Requiring User Input (Stage P2) — answered 2026-11-16", `implementation.md`'s
"Implementation Summary — Stage P2a/P2b" and the seat-gate merge note, and
`docs/acceptance/2026-11-16-ai-wheel-pilot-seat-feedback.md`.

### Review Summary

The goal channel (heading/altitude/speed, the rotation mechanism) and HVRT translate are both
built end to end — body-layer actions/`decide_ai_pilot_wheel`/`crew_console` dispatch, the
aircraft-layer wire (`POST /command/ai_pilot_goal`, shape-validated with `math.isfinite`/bool
exclusion on every numeric field, closed vocabularies elsewhere — the recurring LAN-boundary bug
class is guarded against), `Export.lua`'s per-tick press loops, and the audio-adapter vocabulary/
slot parsers. Single construction sites hold (`ParkedFlightState(`/`AiPilotWheelGoal(` each have
exactly one, grepped). Every new behaviour-affecting constant goes through `tuning.py` with
`lo`/`hi` bounds, and I read the **rendered** `defaults.toml`, not just the source comments — all
four new entries render correctly (no truncated backtick spans, no line-wrap corruption), the
arithmetic checks out against `Export.lua`'s own `AI_PILOT_QUICK_PATH_MAX_AGL_M = 700.0`, and the
generator's "first sentence only" rule drops no behaviour-changing warning, only informational
second sentences. The vocabulary reaches `vocabulary.py`'s `PHRASES`/`TOKENS` tables (not just
`command_matcher.py`), so `to_prompt()` carries every new word to whisper — the exact gap root
`CLAUDE.md`'s "Spoken vocabulary and the STT prompt" rule exists to catch. Export version strings
match (`"2026-11-16d"` on both sides). `ai_pilot_wheel.lua` is at 68 top-level locals/0 upvalues
(`luac5.1 -l -p`), far under the 200/60 ceiling; `luac5.1 -p` is clean on `Export.lua` and both
`Petrobrain/*.lua` files I touched for this review.

Checks, run directly (fresh `.venv`s built for this review, Python 3.12):

- **aircraft-layer**: `ruff format --check`/`ruff check` clean; `mypy src` clean (27 files);
  `.claude/scripts/fast-tests.sh aircraft-layer` → 709 passed.
- **audio-adapter**: `ruff format --check`/`ruff check` clean; `mypy src` clean (16 files);
  `.claude/scripts/fast-tests.sh audio-adapter` → 297 passed, 1 skipped.
- **body-layer**: `ruff format --check`/`ruff check` clean (the implementer's reported
  pre-existing `I001` in `test_bl_b104_association_scenarios.py` did not reproduce here — not a
  regression either way); `mypy src` clean (84 files); `.claude/scripts/fast-tests.sh body-layer`
  → 2574 passed, 4 xfailed.

I also answered the main loop's own question by reading the code rather than inferring it: **a
seat switch away from the operator seat does drop body-layer's own `AiPilotWheelGoal`, and nothing
resumes it on return — by construction, not a second check.** `Export.lua`'s seat-gate fix
computes `ai_pilot_parked_active` from `in_operator_seat and stick_park or nil`
(`ai_pilot_wheel.lua:991-994`), so leaving the operator seat forces `apw_parked_active` false over
the wire exactly as a real unpark does. `body.py`'s `_apply_ai_pilot_wheel_goal` reacts to that
one flag (`if not runner.parked_flight_state.parked_active: ... goal=None`), which is the same
branch `test_unparking_drops_the_goal_and_the_send_cursor` already exercises — there is no
separate seat-aware code path to test on the body-layer side, because body-layer never reads the
seat itself. Matches E-P10 and the pilot's own rule ("AI never flies when player is in pilot
seat") without a stale command resuming on return to the operator seat.

**Three required fixes, below, all in the HVRT/mode-cycle machinery — the part of this stage
built with less rigor than its FLT/HVR sibling.** All three are demonstrated by reading the code
directly against the implementer's own tests (one of them *by* the implementer's own test), not
inferred.

### Required Fixes

- **`ai_pilot_goal_tick_hvrt`'s mode-cycle-into-HVRT has no attempt bound, no `mode_blocked`
  report, and — because the spoken "Hold" is gated behind the same readiness check — no voice
  escape if it never converges.** Compare `ai_pilot_goal_tick` (`ai_pilot_wheel.lua:848-872`),
  which bounds its own mode-cycle by `MODE_CYCLE_MAX_ATTEMPTS` and reports `"mode_blocked"` (now
  spoken as "unable, not ready," per the pilot's own answer), against
  `ai_pilot_goal_tick_hvrt`'s own mode-cycle (`:894-899`):
  ```lua
  if ai_pilot_mode_text ~= "HVRT" then
      if ai_pilot_mode_text ~= nil then
          ai_pilot_tap30(AI_WHEEL_LEFT)
          ai_pilot_last_press = "goal_hvrt_mode_cycle"
      end
      return
  end
  ```
  No counter, no bound, no reported state. The comment at `:878-882` argues this is safe because
  HVRT is "only ever reached from `HVR` or already `HVRT`," so one press should always suffice —
  but that is exactly the same one-hop case `MODE_CYCLE_MAX_ATTEMPTS` was invented to guard
  against for the FLT/HVR channel (a short press sometimes does not register; 3 attempts, not 1,
  is the bound chosen there for a 2-hop-max graph). If the press doesn't land here, Lua taps
  `AI_WHEEL_LEFT` forever, every tick, with nothing spoken. Worse: once stuck, the player cannot
  even say "Hold" to cancel it — `_handle_hvrt_hold` (`crew_console.py`) gates on
  `_ai_pilot_hvrt_ready()` (`ai_mode in ("HVR", "HVRT")`) exactly like `_handle_hvrt_translate`
  does, so if the aircraft actually left hover (the realistic trigger — HVR reverting to FLT), the
  cancel command is rejected with "unable, not ready" too, and `hvrt_direction` is never cleared.
  The only recovery is unparking (which resets everything, E-P10) and re-parking. Give this the
  same bound + report shape `ai_pilot_goal_tick` already has, and make `_handle_hvrt_hold` clear
  the transition unconditionally (or at least whenever `hvrt_direction` is already set) rather
  than gating the *cancel* on the same readiness check that gates the *start*.

- **A heading/altitude/speed goal and an HVRT translate direction can be simultaneously
  outstanding, contradicting the plan's own "no collision to arbitrate" reasoning, and their
  per-tick presses share physical button codes.** The plan's wire-shape note says: *"HVR/FLT-only
  goals and HVRT translate are mode-exclusive by construction (a wheel cannot be in `HVRT` and
  `FLT`/`HVR` at once), so there is no collision to arbitrate."* That reasoning doesn't hold:
  `ai_pilot_goal_mode_ready` (`:430-432`) accepts **`HVR`** for the FLT/HVR goal channel, and
  `_ai_pilot_hvrt_ready` (`crew_console.py`) also accepts **`HVR`** for HVRT commands — `HVR` is
  the one state both channels are simultaneously reachable from, and nothing in
  `set_parked_heading`/`set_parked_altitude`/`set_parked_speed` or `set_hvrt_direction`/
  `clear_hvrt_direction` (`belief/ai_pilot_wheel.py`) clears the other side. A player hovering with
  an active altitude goal who then says "left" gets both an `active_param` and an `hvrt_direction`
  on the same `AiPilotWheelGoal`, sent in the same wire message. On the Lua side,
  `ai_pilot_goal_tick`/`ai_pilot_goal_tick_hvrt` both run unconditionally from
  `update_ai_pilot_wheel_overlay` every tick (`:1192-1195`); if mode transitions to `HVRT` (which
  the HVRT tick's own mode-cycle presses), the FLT/HVR tick now sees `ai_pilot_goal_mode_ready
  == false` and starts cycling `AI_WHEEL_LEFT` to get back to `FLT`/`HVR` — the *same button code*
  (3003) `ai_pilot_goal_hvrt_direction_cmd("left")` uses to hold a left translate. The two ticks
  fight: one tapping the button to leave `HVRT`, the other holding/reopening it to stay. No test
  exercises this (`grep` across `test_ai_pilot_wheel.py`/`test_body_ai_pilot_wheel.py`/
  `test_crew_console_ai_pilot_wheel.py`/`test_ai_pilot_wheel_lua.py` for `hvrt_direction` alongside
  an active FLT/HVR param finds nothing). This needs either enforcement (setting one side clears
  the other, mirroring the takeover-gate precedent already in this codebase) or a voice-level
  "unable, not ready" when the other channel already has something outstanding — the user's own
  "Petrobrain is to have full control of the wheel" answer implies it should resolve this itself,
  not leave it to chance.

- **`mode_blocked` is a permanent dead end for the common single-outstanding-goal case, contradicting
  the plan's own "retried next poll" / "goal never dropped" language and the pilot's "spoken once
  per exhausted attempt" answer (which implies more than one attempt-episode is possible).** Once
  `ai_pilot_goal.mode_cycle_attempts >= MODE_CYCLE_MAX_ATTEMPTS`, `ai_pilot_goal_tick`
  (`:848-864`) sets `progress = "mode_blocked"` and returns — and on every subsequent tick, the
  same branch returns again without incrementing `mode_cycle_attempts` or issuing another press.
  The implementer's own test demonstrates this directly rather than me inferring it:
  `test_mode_cycles_before_pressing_then_blocks_after_the_bound`
  (`aircraft-layer/tests/test_ai_pilot_wheel_lua.py:1678-1714`) ticks a 4th time *after* reaching
  the bound and asserts `press_count_after == press_count` (6, unchanged) — i.e. no further tap is
  ever issued. The only way `mode_cycle_attempts` resets is a *different* `param` arriving
  (`handle_ai_pilot_goal_command`'s `if param ~= ai_pilot_goal.param then ... = 0`) or the mode
  becoming ready on its own, with no help from Lua. With exactly one goal outstanding (the
  ordinary case — "say an altitude while the mode needs a cycle that happens not to land"), there
  is no other `param` to rotate through, so the goal is stuck forever, retried never, after one
  spoken "unable, not ready." `decide_ai_pilot_wheel`'s own rotation mechanism (when ≥2 goals are
  outstanding) incidentally unsticks it by switching `active_param` back and forth, which resets
  the counter each time — meaning the bug is masked exactly in the multi-goal case the plan
  worried about dead-time cost for, and fully exposed in the single-goal case nobody flagged. Give
  `mode_cycle_attempts` an actual retry path (e.g. reset after a cooldown, or simply don't stop
  trying) so "mode_blocked" behaves as documented — a transient, re-announced state — rather than
  a silent permanent stall recoverable only by speaking a different parameter first.

### Optional Refinements

- `hvrt_step`'s addition to the existing `ai_pilot_goal` message rather than a new op (not named
  in the plan's "wire shape" section) is a reasonable, well-flagged extension — no action needed,
  just confirming the implementer's own Notable Discoveries entry is accurate.
- `level_off`'s readback (not in the plan's Readbacks table) reusing `turn_heading`'s digit-by-digit
  shape is a sound judgement call, consistent with the action actually being a heading goal
  underneath — optional to add to the plan's table for future reference, not a blocker.
- `held_speed` conflating "unknown" with "AI at MAX" (documented on `step_speed`'s docstring, not
  fixed) is a real but narrow gap — fine to defer as flagged.
- Three separate constants now encode the 700 m radar cap (`Export.lua`'s
  `AI_PILOT_QUICK_PATH_MAX_AGL_M`, body-layer's `AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M`, and the
  pre-existing altitude-tolerance duplication) — each one documents the duplication in its own
  comment and the architecture decision (per-frame timing stays in Lua until a goal-channel
  round-trip exists) explains why; worth collapsing once that round-trip lands, not now.
- The accepted-items-ledger script (`accepted-items-ledger.sh plans/flight-control`) reported
  "U1 U2 U3 not yet answered" — this is a **stale** section: `plan.md` has multiple
  "Decisions Requiring User Input" headings across its revision history (mode 2's original,
  the Stage P1 revision, the Stage P2 revision), and the script's `awk` matches only the first
  one in the file, from the long-superseded original mode-2 section. I read the live section by
  hand instead ("Decisions Requiring User Input (Stage P2) — answered 2026-11-16", lines
  1280-1316) and cross-checked each item against code: **U4** (goal-slice rotation, 3.0 s) is
  built exactly as recommended (`AI_PILOT_GOAL_SLICE_S`, `decide_ai_pilot_wheel`'s rotation);
  **plan-aligner Q1** (HVRT reachable from hover, cycle-then-press) is built
  (`_ai_pilot_hvrt_ready` accepting `HVR`); **plan-aligner Q2** (`mode_blocked` → "unable, not
  ready" for the goal channel too) is built (`drain_ai_pilot_wheel_speech`) — modulo the Required
  Fix above about it never actually retrying. Worth teaching the ledger script to match the
  *last* "Decisions Requiring User Input" heading, or the one nearest a "ready to build"/"answered"
  marker, rather than the first, since a living plan document accumulates several.

### Verdict
NEEDS REVISION

The FLT/HVR goal channel's own logic is solid and well-tested. The three required fixes are
concentrated in the HVRT translate path and its interaction with the goal channel — a real gap in
rigor between the two halves of this stage, not scattered defects. None of the three touches the
subprojects' checks (format/lint/type/fast-tests all pass as reported above); they are behavioural
gaps a live sortie would eventually surface as "Petrovich won't stop clicking" or "he just stopped
trying," which is squarely this role's own responsibility now that Security no longer backstops
player-facing correctness.

### Review Confidence
Full read — `belief/ai_pilot_wheel.py`, `belief/crew_console.py`'s new handlers, `body.py`'s
`_apply_ai_pilot_wheel_goal`, `aircraft_client.py`'s new method, the full `git diff` for
`aircraft-layer/src/api/server.py`/`collector/command_sender.py`/`schema/ai_pilot_wheel.py`,
`audio-adapter/src/vocabulary.py`/`command_matcher.py`'s new parsers/branches, and
`ai_pilot_wheel.lua` in full (the goal/HVRT sections read end to end, cross-checked against the
takeover-correction code it reuses). Every new/modified test file read, not just counted. Checks
run directly, not taken on the implementer's word, from fresh venvs built for this review.
`luac5.1 -p`/`-l` run directly. Did not re-review the seat-gate fix or seat-change-triggers merges
in depth — both carry their own completed reviews (`plans/fix-ai-wheel-pilot-seat-gate/review.md`,
APPROVED WITH MINOR FIXES; `feature/seat-change-triggers`'s own review, APPROVED) and the merge
only touched this stage's files mechanically (field-order conflicts, both-kept), which I did read
in full via `implementation.md`'s own merge note and spot-checked in `body.py`/`crew_console.py`'s
import blocks and `ai_pilot_wheel.lua`'s unpark branch.

---

## Re-review (fix round)

Branch `feature/bl16-p2-voice-goals`, re-reviewed at `91e3e354` (fast-forwarded cleanly from
`370f37c0`, which the worktree was at). Fix commit `91e3e354` against the reviewed-`NEEDS
REVISION` commit `3d073d83`, cross-checked against `implementation.md`'s "Review-fix round,
2026-11-16 (`plans/flight-control/review-p2.md`, NEEDS REVISION)" section and this file's own
three Required Fixes above.

### Fix 1 — HVRT mode-cycle bound: VERIFIED

`ai_pilot_goal_tick_hvrt` (`ai_pilot_wheel.lua:953-1012`) now mirrors `ai_pilot_goal_tick`'s shape
exactly — a separate `.hvrt_mode_cycle_attempts`/`.hvrt_mode_blocked_since_t` pair (never shared
with the FLT/HVR channel's own counter, by design: both ticks run every overlay tick and must
count independently), bounded by the same `MODE_CYCLE_MAX_ATTEMPTS = 3`, reporting
`"mode_blocked"` and retrying after the new `MODE_BLOCKED_RETRY_S = 3.0`. `_handle_hvrt_hold`
(`crew_console.py:4624-4644`) cancels unconditionally whenever `goal.hvrt_direction is not None`,
regardless of `ai_mode` — the exact gap named (the aircraft leaving hover while a translate is
held, which previously made "Hold" itself unreachable). A bare "Hold" with nothing outstanding
still answers `"Unable, not ready."` via the pre-existing readiness check, unchanged.
`test_mode_cycle_into_hvrt_is_bounded_reports_blocked_then_retries`
(`test_ai_pilot_wheel_lua.py:2065`) and `TestHvrtHold.test_cancels_unconditionally_when_a_
translate_is_already_outstanding` / `test_still_unable_when_nothing_outstanding_and_not_in_hover`
(`test_crew_console_ai_pilot_wheel.py:273-293`) demonstrate both halves directly.

### Fix 2 — goal channel vs. HVRT arbitration: VERIFIED

`goal_param_for_wire` (`belief/ai_pilot_wheel.py:636-661`) is the single call site both of
`body.py`'s `write_ai_pilot_goal` sends route through (`body.py:3368`, `:3391`) — grepped, no
third call site exists, and no call site reads `final_goal.active_param` directly any more.
`request_goal` clears `hvrt_direction` on entry (`:427-428`) before doing anything else, so every
one of `set_parked_heading`/`_altitude`/`_speed` inherits the "a new goal clears the translate"
rule from the one function they all route through. `decide_ai_pilot_wheel`'s own HVRT-pause early
return (`:712-713`) sits after the timeout-reconciliation and takeover-stage checks and before any
promote/demote/settle logic, exactly as described — confirmed by
`TestDecideAiPilotWheel.test_an_outstanding_hvrt_translate_pauses_the_goal_channel` /
`test_a_queued_second_goal_also_stays_queued_while_paused` /
`test_the_goal_channel_resumes_once_the_translate_clears`, which exercise the pause, the
multi-goal case, and the resume in one call after the field is cleared.

**The newly found `goal_seq` gap, checked directly**: `set_hvrt_direction`/`clear_hvrt_direction`
(`:590-633`) each bump `goal_seq` only on an actual change (`if goal.hvrt_direction == direction:
return goal` / `if goal.hvrt_direction is None: return goal`), confirmed by
`TestHvrtDirection.test_an_actual_change_bumps_goal_seq` / `test_no_change_does_not_bump_goal_seq`.
Traced the two live paths end to end through `_apply_ai_pilot_wheel_goal` and
`AircraftLayerClient.write_ai_pilot_goal` (not just the unit-level bump):
`TestHvrtArbitration.test_hold_resumes_the_goal` sends exactly one wire message with `param ==
"altitude"`/`hvrt_direction is None` once "Hold" is spoken, and
`test_a_translate_active_then_a_new_altitude_goal_releases_it` sends exactly one message with
`param == "altitude"`/`hvrt_direction is None` once a new goal preempts an outstanding translate —
both would have stayed silently paused forever (the exact "Lua never learns" failure the
Discoveries note names) without the bump, since `body.py`'s own send gate is `final_goal.goal_seq
!= runner.ai_pilot_goal_last_sent_seq`. A repeated identical command
(`test_redirecting_replaces_the_direction` only changes direction; `test_no_change_does_not_bump_
goal_seq` covers the exact-repeat case) does not bump `goal_seq` and therefore does not re-send —
confirmed by reading the send-gate condition, not inferred.

On the Lua side, `ai_pilot_goal_tick`'s own top-of-function guard (`:891-894`, `if ai_pilot_goal.
hvrt_direction ~= nil then ai_pilot_goal_release_hold(); return end`) is in place as the
belt-and-suspenders second half, confirmed clean under `luac5.1 -p` (below) and exercised by
`test_an_outstanding_hvrt_direction_stops_this_tick_from_pressing` — which constructs the exact
collision message (`param="altitude"`, `hvrt_direction="left"`, both non-null, the shape
`goal_param_for_wire` now prevents body-layer from ever sending) directly against the Lua chunk
and confirms the FLT/HVR tick presses nothing while the HVRT tick is the only one that presses
once the mode reaches `HVRT`. Both ticks run unconditionally every overlay tick
(`update_ai_pilot_wheel_overlay:1283-1286`) and the mutual-exclusion is enforced by each tick's
own guard, not by a shared dispatcher — read both guards side by side rather than trusting the one
test to generalise, and they hold: `ai_pilot_goal_tick` returns before any press whenever
`hvrt_direction ~= nil`; `ai_pilot_goal_tick_hvrt` only presses when `hvrt_direction ~= nil`. The
two conditions are exact complements, so "never both press in one tick" holds by construction on
both the body-layer wire-shape side and this Lua-side guard independently, not only when both
happen to agree.

### Fix 3 — `mode_blocked` must retry: VERIFIED

Once `mode_cycle_attempts`/`hvrt_mode_cycle_attempts` reach the bound, the first exhausting tick
records `*_mode_blocked_since_t` and reports `"mode_blocked"` with no press; every subsequent tick
re-checks the elapsed time against `MODE_BLOCKED_RETRY_S`, and once it has passed, resets the
counter and falls straight through to a fresh press attempt the *same* tick rather than waiting
for a further one. `test_mode_cycles_before_pressing_then_blocks_then_retries_after_cooldown`
(`test_ai_pilot_wheel_lua.py:1688-1748`, the rewrite of the test that previously demonstrated the
bug as if it were the contract) drives this through five explicit tick times and asserts, in
order: 3 cycling attempts and 6 presses; the bound reached with no 4th press; still blocked and
still no press just short of the cooldown; one renewed attempt and 2 more presses (8 total) once
the cooldown has elapsed; and `speed_target_kmh` unchanged (`150`) throughout, i.e. the goal itself
was never dropped — the exact single-outstanding-goal case the original review named. The sibling
HVRT test (`test_mode_cycle_into_hvrt_is_bounded_reports_blocked_then_retries`) exercises the same
shape for `ai_pilot_goal_tick_hvrt`'s own, previously-unbounded cycle.

**Speech side, cross-checked in body-layer, not re-derived from the Lua change alone**:
`drain_ai_pilot_wheel_speech` (`crew_console.py:4654-4673`) is unchanged this round — its
edge-trigger (`_ai_pilot_mode_blocked_spoken`, reset whenever `lua_goal_progress != "mode_
blocked"`) already had a test for the exact "re-entry into `mode_blocked` speaks again"
case (`TestDrainAiPilotWheelSpeech.test_speaks_again_after_a_fresh_exhaustion`,
`test_crew_console_ai_pilot_wheel.py:352-363`) — a path that existed in source but, before this
fix round, Lua itself could never actually walk (the "stuck forever" bug meant `goal_progress`
never left `mode_blocked` once reached). The fix makes that pre-existing test's scenario reachable
in practice rather than only in a hand-constructed fixture: once the cooldown elapses,
`ai_pilot_goal.progress` is set back to `"cycling_mode"` on the same tick the fresh attempt is
spent, so the edge-trigger flips and "unable, not ready" is spoken again — once per exhausted
episode, not per tick, not per poll. No HVRT-specific speech code was needed or added: both
channels share one wire-level `apw_goal_progress`/`.progress` field, and the two ticks' own mutual
exclusion (Fix 2) means at most one of them is ever the one setting it in a given tick, so the
existing single edge-trigger already covers HVRT's own `mode_blocked` reports.

### Export version / Lua syntax (point 4)

`EXPORT_SCRIPT_VERSION` (`Export.lua:224`) and `EXPECTED_EXPORT_VERSION`
(`collector/server.py:162`) both read `"2026-11-16e"` — matched, grepped directly. `luac5.1 -p`
(Lua 5.1, via Homebrew) run directly against `Export.lua` and all eight files under
`dcs-export/Petrobrain/` (`ai_pilot_wheel.lua`, `commands.lua`, `core.lua`, `effectors.lua`,
`petrovich.lua`, `ptt_ics.lua`, `sight.lua`, `telemetry.lua`): clean on every one.
`grep -cE '^local ' ai_pilot_wheel.lua` → 69 (the implementer's own reported count), one new
top-level local (`MODE_BLOCKED_RETRY_S`) — well under the 200-local ceiling. The
`luac5.1 -l -p`/`GETGLOBAL` scan on `ai_pilot_wheel.lua` lists only Lua stdlib, genuine DCS APIs,
and names this codebase deliberately exports as cross-file globals via `_G.<name> = <name>` in
`core.lua` (confirmed for `WHEEL_CENTER_BUTTON`, same pattern for the rest) — not the
before-its-`local` bug the scan exists to catch, and not a new finding this round.

### Seat gate (point 5)

`update_ai_pilot_wheel_overlay` — the one function containing both `ai_pilot_goal_tick` and
`ai_pilot_goal_tick_hvrt`'s call sites (`:1284`, `:1286`) — returns immediately at its own top
(`:1203`) whenever `not ai_pilot_parked_active`, and `ai_pilot_parked_active` is itself computed as
`in_operator_seat and stick_park or nil` (`:1079-1082`), so every new press path this fix round
added is covered by the existing seat gate structurally, not by a new check — consistent with how
every other press path in this file is already gated.

### P2a regression check (point 6)

No regression found. The full targeted test files for both subprojects (36 for aircraft-layer, the
body-layer equivalent) include every pre-existing P2a test file untouched by this round, and all
pass. Read `TestDecideAiPilotWheel`'s and `TestRequestGoal`'s own pre-existing tests (promotion,
rotation-after-slice, settle-and-promote, takeover-coexistence) directly against the diff: none of
their call sites changed, only new branches were added ahead of them (the HVRT pause early-return
sits *before* the pre-existing settle/promote/rotate logic, never inside it).

### Checks, run directly (fresh venvs built for this re-review, `python3.12`)

- **aircraft-layer**: `ruff format --check`/`ruff check` clean (81 files); `mypy src` clean (27
  files); `luac5.1 -p` clean on `Export.lua` and all 8 `dcs-export/Petrobrain/*.lua` files;
  `.claude/scripts/fast-tests.sh aircraft-layer` → **711 passed**, matching the implementer's own
  reported count exactly.
- **body-layer**: `ruff format --check`/`ruff check` clean (208 files — the `I001` review-p2.md
  flagged as not reproducing also does not reproduce here); `mypy src` clean (84 files, after
  installing `numpy` into this re-review's own venv for the world-model seam's `coordinates`
  import); `.claude/scripts/fast-tests.sh body-layer` → **2588 passed, 4 xfailed**, matching the
  implementer's own reported count exactly.

### Verdict
APPROVED

All three required fixes from the first review pass landed correctly, each demonstrated by a test
that drives the actual boundary condition (the bound, the cooldown, the collision message, the
no-op repeat) rather than merely asserting a happy path. The one gap the implementer found beyond
what the review named (`goal_seq` not bumping on `set_hvrt_direction`/`clear_hvrt_direction`) was
necessary for Fix 2 to work at all, is itself covered by tests at both the unit and the
`_apply_ai_pilot_wheel_goal` integration level, and was checked here by tracing the actual send
gate rather than taking the claim on its word. No regression found in the pre-existing P2a
(heading/altitude/speed) behaviour. Both subprojects' format/lint/type/fast-tests pass cleanly
with figures matching the implementer's own report exactly.

### Review Confidence
Full read — every file named in `implementation.md`'s "Files Changed" for this fix round, read in
full against the three Required Fixes above, not diffed in isolation: `ai_pilot_wheel.lua`'s goal/
HVRT tick functions and their shared table's field comments, `belief/ai_pilot_wheel.py`'s
`goal_param_for_wire`/`request_goal`/`set_hvrt_direction`/`clear_hvrt_direction`/
`decide_ai_pilot_wheel`, `crew_console.py`'s `_handle_hvrt_hold`/`drain_ai_pilot_wheel_speech`,
`body.py`'s `_apply_ai_pilot_wheel_goal` in full (both `write_ai_pilot_goal` call sites). Every new
test in the four touched test files read for what it actually asserts, not just counted — the Fix
3 rewrite in particular, since the original review's finding was that a test's own assertion
encoded the bug as the contract. Checks run directly from fresh venvs built for this re-review
(not inherited from any prior review's environment), `luac5.1 -p`/`-l` run directly, both
subprojects' full fast-test figures cross-checked against the implementer's own reported numbers
rather than only against "did it pass." Did not re-derive the arbitration rule's own design
tradeoffs (e.g., why HVRT always wins when both a goal and a translate are requested within the
same poll batch) — the main loop's own rule and the Lua comment both state this asymmetry as
deliberate, and it is consistent with "nothing lost" (a paused goal keeps its target and queue
position, it is never cleared), so it was checked for consistency rather than re-argued.
