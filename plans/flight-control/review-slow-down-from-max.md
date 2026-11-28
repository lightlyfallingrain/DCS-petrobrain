# Review: Mode-2 "slow down" from MAX (commit `c9cb44d7`)

**Reviewed commit:** `c9cb44d7` ("Mode 2: 'slow down' from MAX steps to 250, not 'Action file
error.'"), on branch `fix/bl16-flight-epoch-bound` (pushed as `feature/bl16-lift-vector-law`).
Context: `1b481700` (`docs/acceptance/2026-11-28-sortie-feedback.md`, "Mode-2 fixes card").

**Branch/tip note (read first):** the requested tip was `c9cb44d7`. This worktree's own branch
(`worktree-agent-aa5c17c9d68423233`, tip `918f5c35`) is **not** an ancestor of `c9cb44d7` and
`c9cb44d7` is not an ancestor of it — they share a distant common ancestor (`1561d370`), not a
fast-forward relationship, so the stated ff-only merge rule did not apply. A dedicated worktree
for `fix/bl16-flight-epoch-bound` already exists elsewhere
(`/Users/sg/Code/DCS-petrobrain-epochfix`, tip `c9cb44d7`, clean). I reviewed and ran checks
against a detached checkout of `c9cb44d7` inside this worktree (clean tree, no edits made there),
then returned to this worktree's own branch to write and commit this file — so this review
file is **not** on `feature/bl16-lift-vector-law` and needs harvesting onto that branch (or
wherever the orchestrator wants the review to live) rather than being picked up by a ff-only
merge from here.

## Required Fixes

None. The commit is correctly scoped, the diagnosis is right, and the tests are meaningful.

## Optional Refinements

- **Same gate-mirror/action-mirror split exists, unfixed, at every other mode-2 "current value"
  action** — `CrewConsole.increment_heading` (`assert current is not None` on
  `parked_flight_state.held_heading`, gated by `"flight_control_heading"`, which reads
  `CrewState.held_heading = flight_authority_state.heading_deg`), `step_altitude` and
  `hold_altitude` (same pattern against `held_altitude`/`"flight_control_altitude"`), `level_off`
  (same against `held_heading`/`"flight_control_heading"`), and `level_flight`'s own
  `assert (held_heading is not None or held_altitude is not None or held_speed is not None)`
  gated by `"flight_control_any"`. All five read `CrewState`'s mirror
  (`belief.crew_console.crew_state()` builds every one of `held_heading`/`held_altitude`/
  `held_speed` from `flight_authority_state.heading_deg`/`alt_m`/`ias_kmh`, BL-16 Stage 2), while
  the action body itself reads `parked_flight_state`'s separate overlay mirror — exactly the split
  this fix's own new docstring (`step_speed`) names as the root cause. Nothing today reproduces a
  "known on one mirror, unknown on the other" gap for heading/altitude the way `"MAX"` did for
  speed (there's no equivalent literal-string value in `apw_course_text`/`apw_alt_text`), but a
  timing window is plausible: `flight_authority_state` is seeded "from measured at a take / from
  overlay at a park" by `Export.lua`'s own edge handler, while `parked_flight_state` fills from
  AI-wheel status it must independently finish reading — if either mirror lags the other across a
  park/take edge, the same `AssertionError` -> "Action file error." is reachable through any of
  these five sites. Flagged per the task's own ask; not fixed here (out of scope for this commit,
  and the task said list, don't fix).
- `_parse_held_speed`'s `_parse_float` fallback (unchanged, pre-existing) does not reject
  `"inf"`/`"-inf"`/`"nan"` — `float("inf")` doesn't raise, so a (currently unseen) overlay string
  of that shape would produce a non-finite `held_speed` rather than `None`. This predates the
  commit (the same gap already existed for `held_heading`/`held_altitude` through the same
  helper) and `_parse_held_speed` doesn't introduce a new unguarded parse — the standing
  `math.isfinite()`-at-parse rule is already not met by `_parse_float` itself. Worth a follow-up
  ticket, not a blocker on this fix.

## Checks run (against the commit's own tree, detached at `c9cb44d7`)

```
ruff format --check src tests   -> 236 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 96 source files
pytest -q tests/test_rules_flight_actions.py tests/test_ai_pilot_wheel.py \
          tests/test_rule_gates.py tests/test_body_ai_pilot_wheel.py
                                 -> 232 passed
```

## Findings

### 1. Consumers of `ParkedFlightState.held_speed` after the sentinel change

`held_speed` can now read `AI_PILOT_SPEED_MAX_SENTINEL_KMH` (`1_000_000.0`) instead of `None` once
the overlay shows `"MAX"`. Traced every reader:

- **`body.py:4079-4080`** (level-flight freeze): `if state.held_speed is not None:
  set_parked_speed(goal, now_sim, state.held_speed)`. Previously unreachable at MAX (branch
  skipped, speed never froze while at MAX). Now reachable: `set_parked_speed` is typed
  `requested_kmh: float | Literal["max"]` and does `requested_kmh == "max"` first, but with a
  plain float input that comparison is `False`, so it falls to `nearest_speed_step(1_000_000.0)`
  — which already special-cases "above the highest finite step -> the sentinel itself"
  (`nearest_speed_step`'s own docstring, BL-B140). Same result either way: correct, not a
  regression, just a previously-dead branch now live and behaving the way the finite-value branch
  already does.
- **`capture_flight_snapshot` (~line 929-936)**: `speed = goal.speed_target_kmh if ... else
  state.held_speed`. Previously, a held MAX with no outstanding goal made `speed is None`, so the
  whole snapshot returned `None` (no "align for launch" at MAX held speed). Now it captures
  `speed_kmh=1_000_000.0` in the `FlightSnapshot` (a plain `float` field, no `Literal["max"]`
  needed there). This is a second, unstated bug fix riding along with the stated one — align-for-
  launch at a held MAX speed previously could not snapshot at all. Not scope creep worth blocking
  on; worth naming to the user since it wasn't in the commit message.
- **Recovery** (`seed_recovery_goal`, ~line 1024): `speed_target_kmh=snapshot.speed_kmh` — carries
  the sentinel through unchanged if that's what was captured. Consistent with the point above.
- **Wire**: `body._apply_ai_pilot_wheel_goal` sends `final_goal.speed_target_kmh` verbatim to
  `write_ai_pilot_goal` (`POST /command/ai_pilot_goal`), and, when non-`None`, dual-writes the same
  raw float into `set_fields["ias_kmh"]` for `POST /command/flight` (BL-16 Stage 3's parity
  write). Both already carry the raw `1_000_000.0` sentinel for the pre-existing "speed max"
  voice command (`set_speed_max` -> `AiPilotGoalRequest(speed_kmh="max")` -> `set_parked_speed`
  resolves the same sentinel) — this fix doesn't introduce a new wire shape, it just reaches two
  call sites (`body.py:4079`'s level-flight freeze, and `capture_flight_snapshot`) that were
  previously unreachable at MAX. `core.lua`'s `fmt_num_or_null` (`%.5f`) formats `1000000.0`
  without truncation or precision loss, so the "carries fine on the wire" assumption holds.
- **Readback/speech**: no site speaks a raw `held_speed` number for the MAX case — `step_speed`'s
  own caller (`crew_console.step_speed`) already special-cases `stepped >= AI_PILOT_SPEED_MAX_
  SENTINEL_KMH` before it ever reaches a readback (`is_max: True, speed_kmh: 0`), unaffected by
  this change since `stepped` is computed by the module-level `step_speed` ladder walk, not by
  `_parse_held_speed` directly.

No consumer found that would mis-render or mis-command on the new sentinel value; the two newly
reachable call sites behave the same way the already-reachable "speed max" path already does.

### 2. Diagnosis check

Confirmed directly against `Export.lua`/`ai_pilot_wheel.lua`/`flight_desired.lua` (this worktree's
checkout of `aircraft-layer/dcs-export/Petrobrain/`), not just the commit message:

- `ai_pilot_wheel.lua`'s own `held_targets()` does `speed_kmh = tonumber(ai_pilot_speed_text)` —
  `tonumber("MAX")` is `nil` on the Lua side too, the same gap `_parse_float` has in Python.
- `flight_desired.lua`'s `reseed_from_overlay()` only overwrites `desired.ias_kmh` `if held.
  speed_kmh ~= nil` — so at `"MAX"`, that assignment is skipped and `desired.ias_kmh` keeps
  whatever it was already holding (`250` from the preceding "speed 250", in the sortie's own
  sequence), **not** reset to `nil`.
- So `flight_authority_state.ias_kmh` (`CrewState.held_speed`, what `"flight_control_speed"`
  gates on) stays at the stale-but-known `250` straight through the transition to MAX — the gate
  passes — while `ParkedFlightState.held_speed` (the Python-side overlay mirror this action
  reads) was `None` pre-fix. Diagnosis is correct: the gate really does pass at MAX, for exactly
  the reason stated.

### 3. Other assert sites with the same mirror split

Listed under Optional Refinements above (`increment_heading`, `step_altitude`, `hold_altitude`,
`level_off`, `level_flight`'s `assert ... or ... or ...`). Not fixed, per the task's own
instruction.

### 4. Test quality

- `test_a_held_max_speed_is_the_max_sentinel_not_unknown`
  (`tests/test_ai_pilot_wheel.py`) — drives `advance_parked_flight_state` off a real HTTP fixture
  with `apw_speed_text: "MAX"` and asserts `state.held_speed == AI_PILOT_SPEED_MAX_SENTINEL_KMH`.
  Fails pre-fix (`_parse_float("MAX")` is `None`). Meaningful.
- `test_gate_passing_on_a_mirror_the_overlay_lacks_is_not_ready`
  (`tests/test_rules_flight_actions.py`) — builds a console with `held_speed=None` (the overlay
  mirror) but `flight_authority_state.ias_kmh=250.0` (the gate mirror), dispatches `speed_step`,
  and asserts `["Unable, not ready."]`. Pre-fix this raises `AssertionError` inside `step_speed`,
  which the rules engine turns into `"Action file error."` — doesn't match, so the test fails
  pre-fix. This is the test that actually pins the second half of the fix (assert -> branch).
  Meaningful.
- `test_slows_down_from_max_to_the_top_step` — constructs the console with
  `held_speed=AI_PILOT_SPEED_MAX_SENTINEL_KMH` directly (bypassing the parse path) and checks the
  readback steps to `250`. This one would pass both before and after the fix on its own (the
  module-level `step_speed` ladder walk and the `assert stepped is not None` were never the
  broken half when `current_kmh` is already non-`None`) — it's a correctness/readback check for
  the already-working ladder-walk, not a regression pin by itself, but it's reasonable positive-
  path coverage alongside the other two and not decorative.

## Verdict

APPROVED

## Review Confidence

Full read of the commit's two source diffs, the test diffs, every `held_speed` consumer in
`body-layer/src` (`body.py`, `ai_pilot_wheel.py`, `crew_console.py`, `rules/gates.py`), and the
relevant `Export.lua`/`ai_pilot_wheel.lua`/`flight_desired.lua` Lua source to verify the gate/mirror
diagnosis independently rather than trust the commit message. Checks run against the commit's own
tree via a clean detached checkout (`c9cb44d7`), not against this worktree's unrelated branch.
