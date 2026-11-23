# Review: BL-16 LV-0 debug pass (2026-11-23)

Reviewed on `rev/bl16-debug-1123`, tip `d7420e88db4e42a0528ef3506be5e7f28412f20a` (the branch's
fetched tip was not reachable from this worktree's prior HEAD, so a clean checkout was used rather
than a fast-forward — reported per the dispatch instruction).

Scope: `a2f462e0` (debugger fixes, problems 1 and 2) and `d7420e88` (main-loop testing-aid logging,
light review). Inputs read in full: `plans/flight-lift-vector/debug-2026-11-23.md`,
`docs/acceptance/2026-11-23-sortie-feedback.md`, `plans/flight-lift-vector/plan.md`,
`plans/flight-desired-state/plan.md`, `body-layer/CLAUDE.md`.

### Review Summary

**Problem 1 (release readback deferred to ack).** Verified independently, not taken on the
debugger's word:

- `aircraft-layer/dcs-export/Petrobrain/flight_desired.lua`'s `handle_flight_command`'s `release`
  branch calls `flight_control.request_release(seq)` — which sets `fc_mode = "off"` and clears
  `fc_law` **synchronously**, before `push_ack` ever runs on the very next line. By the time the ack
  the player's "you have controls" line waits on is even queued, Lua has already stopped writing.
- `run_flight_control` only calls `run_active_frame` (the sole writer of `LoSetCommand`) while
  `fc_mode` is `"active"`/`"taking"`. The only path back into `"active"` from `"off"` is a fresh
  unpark-take or voice take, both of which require an explicit, later player action — there is no
  self-arm or seat-change path that resumes writing after an acked release (checked the self-arm
  edge-tracker, the armed→unpark-take branch, and the envelope-release branch; none can fire from
  `"off"` without a new take).
- The user's own clarification ("not only move, but he must never *write* the axis values") is
  satisfied: the write stops before the ack is even generated, not merely before the spoken line.
- `resolve_pending_take` (reused unmodified for both `flight_pending_take` and the new
  `flight_pending_release`) never speaks the accepted line on a refusal or timeout — both resolve to
  "Unable, not ready." This is the one function backing both handover directions, and its own
  test class (`TestResolvePendingTake`) already covers accept/refuse/timeout/still-waiting/ack-and-
  timeout-same-tick generically, so reuse here is correctly covered by existing tests for the
  decision logic itself.

**Required fix — found by mutation, not by reading.** `CrewConsole.drain_flight_control`'s new
release-resolution block (crew_console.py, the `if self.flight_pending_release is not None:` block
immediately above the existing take-resolution code) has **no test exercising it directly**. I
commented it out (`if False and ...`) and ran the full body-layer suite: **3785 passed, 0
failures** — the exact behaviour the user flagged as the defect ("Petrovich must never hold
controls after he has confirmed player has controls") could silently regress to never speaking
"You have controls." at all, or speaking it immediately again, with every existing test still
green. `test_a_release_transition_is_sent_and_cleared` and its sibling
(`test_body_flight_control.py`) only cover the *queuing* half (`_apply_flight_requests` populating
`flight_pending_release`); nothing calls `drain_flight_control` with an acks string that resolves
it. Reverted the mutation before writing this review; `git status --porcelain` on `crew_console.py`
confirms no residue.

**Problem 2 (estimator reset/priming).** Confirmed LV-0 is still shadow-only: `law_update`/
`law_outputs` take no `fc_est` argument, and the estimator's own output fields (`est.v`, `est.a`)
feed only the trace log and the status push — never `fc_law` or `write_outputs`. No behaviour
change to mode-1 axis output, matching the task's framing and the plan's own "no behaviour change"
framing for LV-0. `est_ring_primed`'s `count < 2` branch is correctly re-zeroed by any real
`est_reset` (ring `count = 0`), so the new priming logic composes correctly with the plan's
existing dt-cap/mission-stop/reset re-priming rule rather than duplicating or conflicting with it.
The four new Lua-side tests (`test_flight_control_estimator.py`) each reproduce one concrete traced
symptom (duplicate-timestamp spike, invalid-self-data snap-to-origin, mission-start bridging from
`vec_*`, and the documented residual without it) rather than asserting generically that "no spike
happens" — meaningful, not decorative.

**Problem 3/4.** Correctly left unfixed with hypotheses recorded, per the task's own instruction
not to redesign the law and to document rather than silently patch a FIFO design trade-off. No
fix was claimed for either, so there is nothing to require here.

**`d7420e88` (testing aid).** Three `debug_log` calls, all inside the existing `DEBUG` flag gate
(`core.lua`'s `debug_log`, checked once at load time — confirmed by reading `core.lua` directly,
not assumed). Additive, no behaviour change, matches the project's "light path" testing-aid
posture. No concerns.

**Checks** (both touched subprojects, `rev/bl16-debug-1123`):
- `aircraft-layer`: `ruff format --check`, `ruff check`, `cd aircraft-layer && .venv/bin/mypy src`
  — all clean. `luac5.1 -p` (the correct DCS-embedded version — the debugger's own report used
  `luac5.5`, which is **not** what root/aircraft-layer `CLAUDE.md` specifies; re-ran with `luac5.1`
  myself) on both touched files — both parse clean. `GETGLOBAL` leak check on both touched files —
  every name resolves to a genuine DCS API, an existing cross-module global (`flight_desired`,
  `flight_control`, `ai_pilot_wheel`, `client`, `debug_log`, the `fmt_*`/`json_escape_string`/
  `extract_json_*`/`safe_call` helpers — none of which is declared `local` anywhere in these files,
  consistent with this codebase's existing shared-global pattern across `Petrobrain/*.lua`
  modules), or Lua stdlib — no leaked own-helper reference. `.claude/scripts/fast-tests.sh
  aircraft-layer`: 992 passed.
- `body-layer`: `ruff format --check`, `ruff check`, `cd body-layer && .venv/bin/mypy src` — all
  clean. `.claude/scripts/fast-tests.sh body-layer`: 2900 passed, 4 xfailed (pre-existing,
  unrelated). Full suite also run directly as part of the mutation check above: 3785 passed, 4
  xfailed.
- Both subprojects' `.venv` were symlinked in from the main checkout for this review (no `.venv`
  exists in a fresh worktree) and removed again before this commit; `git status --porcelain` is
  clean apart from this review file.

### Required Fixes

- **Add a test that exercises `CrewConsole.drain_flight_control`'s release-ack resolution
  directly** (mirroring `TestResolvePendingTake`'s shape, but through `drain_flight_control` with a
  populated `flight_pending_release`, same as the one existing call site in
  `test_rules_flight_actions.py` does for the take/readback-cutoff case): accepted → speaks "You
  have controls." urgently and clears `flight_pending_release`; refused → speaks "Unable, not
  ready." non-urgently and clears it; still-waiting → speaks nothing and leaves it pending. Proven
  necessary by mutation (see above) — without it, the exact defect the user reported can regress
  with the full suite staying green.

### Optional Refinements

- The debug report's own "Checks run" section names `luac5.5 -p` rather than `luac5.1`
  (`aircraft-layer/CLAUDE.md`'s own stated requirement, "must be Lua 5.1 specifically, the version
  DCS embeds; a newer `luac` accepts syntax DCS rejects"). I re-ran the correct version myself and
  both files parse clean under 5.1 too, so this did not hide a real defect this time — but the
  debug report's own record of what was checked is wrong, and worth a one-line correction in that
  file for anyone reading it later as the account of what was verified. Optional because it did not
  change the outcome here.
- The sortie feedback file's third verbatim item ("I have controls" → "unable AI overlay" → AI
  overlay off within 5s → release and say "you have controls") is an answered, filed (`[[BL-B134]]`
  context) follow-on behaviour that this debug pass correctly did not attempt — flagging only so it
  is not mistaken for something this commit was supposed to cover.

### Verdict
APPROVED WITH MINOR FIXES

The one required fix is a test-coverage gap, not a behavioural defect — the shipped logic is
correct by every check available (independent trace-through of both body-layer and Lua sides,
full suite green, mypy/ruff/luac clean), but the user's own acceptance criterion for this exact
bug ("must never write/hold controls after confirming") is currently enforced by code that no test
would catch breaking. Given the project's auto-advance loop, this can go back through Implementer
for the one test addition and return to Reviewer, or be added directly if the main loop judges it
a trivial, same-shape addition — either way it should land before DoD, since DoD's full-suite run
would not surface the gap either (it is a missing test, not a failing one).

### Review Confidence
Full read. Both commits' diffs read in full; Lua write-path (`request_release`, `run_flight_control`,
every mode transition that could resume writing) traced by hand rather than taken on the debugger's
report; the estimator's shadow-only status confirmed by grep against `law_update`/`law_outputs`
call sites; the one coverage gap found by actual mutation (code commented out, full suite run,
reverted), not by inspection alone.
