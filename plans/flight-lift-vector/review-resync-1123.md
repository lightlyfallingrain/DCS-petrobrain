# Review: BL-16 release-ack test + epoch re-sync (2026-11-23)

Reviewed on `rev/bl16-resync`, tip `6fa74373d7bb4f21ee82cb87b941e7482fcc5b27` (fetched from origin
`feature/bl16-lift-vector-law`, clean checkout at that sha). Scope: the tip commit only --
`body-layer/src/body.py`, `body-layer/tests/test_body_command_reset.py`,
`body-layer/tests/test_rules_flight_actions.py`, `plans/flight-lift-vector/debug-2026-11-23.md`.
Inputs read in full: `debug-2026-11-23.md` (both passes), `review-debug-1123.md`,
`docs/acceptance/2026-11-23-sortie-feedback.md`, `plans/flight-desired-state/plan.md` section 5.

### Review Summary

**Fix A -- `TestDrainFlightControlReleaseAck`.** Exactly the test `review-debug-1123.md` asked
for: three cases (accepted/refused/timeout) driven through `drain_flight_control` with
`flight_pending_release` populated directly, mirroring `TestResolvePendingTake`'s shape and the
existing readback-cutoff call site's pattern. **Re-ran the mutation myself**, independently of the
debugger's own claim: commented out `if self.flight_pending_release is not None:` in
`crew_console.py` (`if False and ...`), ran the three new tests -- all three failed for the right
reason (`accepted` asserts `[] == ["You have controls."]`; the two refusal/timeout tests fail
because `lines == []` instead of `["Unable, not ready."]`, i.e. without the block the release is
never spoken as refused *or* accepted -- the gap is total, not partial). Reverted; `git diff` on
`crew_console.py` empty.

**Fix B -- epoch re-sync.** `_resolve_command_reset` was a one-shot latch
(`if runner.command_reset_confirmed: return`); a DCS mission (re)start reloads `Export.lua`'s
module-level locals (`fc_reset_epoch`/`apw_reset_epoch`/`fd_epoch` all go back to `nil`), and the
latch never noticed, leaving `_apply_flight_requests`/`_apply_ai_pilot_wheel_goal` sending with a
`command_reset_epoch` Lua no longer echoed -- `flight_desired.lua` refused every one of them
`r:epoch`, reproducing the retest's "unable, not ready" exactly. The fix re-checks the echo on
every call; a confirmed state whose echo stops matching flips back to `False` and resets both the
resend and slow-confirm-warning clocks from that mismatch.

This is not an invented design -- `plans/flight-desired-state/plan.md` section 5 ("One running
number") already specifies it: *"Body-layer re-handshakes whenever the echo differs, which covers
a body-layer restart (new epoch), and an Export.lua reload on mission or DCS restart (echo becomes
null)."* The commit is a faithful, narrowly-scoped implementation of an already-decided contract,
not scope drift.

**Correctness of the un-confirm edge, checked directly, not taken on the commit message:**

- **No resend storm.** `command_reset_last_sent_wall` is not reset on the un-confirming edge, only
  `command_reset_unconfirmed_since_wall`/`command_reset_warned` are. Since that wall-clock value is
  normally long-stale (left over from the original startup handshake), the very next mismatch poll
  resends immediately (not throttled by a cooldown that has nothing to do with this new mismatch),
  and every poll after that is correctly bounded by `COMMAND_RESET_RESEND_INTERVAL_S` (2.0 s,
  unchanged). Verified against the actual code path, not just the test's assertion.
- **Warning clock restart is sensible.** `command_reset_unconfirmed_since_wall` is explicitly reset
  to `None` on the un-confirm edge, so `COMMAND_RESET_CONFIRM_TIMEOUT_S` (10 s, unchanged) counts
  from the reload, not from whenever the original handshake happened hours earlier --
  `test_resync_restarts_the_unconfirmed_since_clock_...` pins exactly this with an artificial
  10,000 s-old stale cursor and asserts the restarted clock is `< 1.0 s` old. Correct.
- **Does not fire on every ordinary mission restart.** It does flip to unconfirmed on *every*
  reload (correct -- the echo really did go stale), but the warning only fires after the 10 s
  timeout, which an ordinary resync clears within one or two 2 s resends -- consistent with the
  commit's own framing ("confirms again within one or two resends exactly as a fresh process start
  does").
- **No new tunable needed.** Both constants this behaviour depends on
  (`COMMAND_RESET_RESEND_INTERVAL_S`, `COMMAND_RESET_CONFIRM_TIMEOUT_S`) already exist and already
  go through `tuning.real`; nothing new was added that should have gone through the mechanism and
  didn't.

**Take/release/set dispatched while unconfirmed -- never silently lost, readback never lies.**
Traced the call sites directly: both `_apply_flight_requests` and `_apply_ai_pilot_wheel_goal`
(plus their respective `drain_flight_control`/`drain_ai_pilot_wheel_speech` calls) sit inside
`if runner.command_reset_confirmed:` blocks in `body.py`'s poll loop (lines ~5538, ~5630) -- this
nesting is pre-existing, not introduced by this commit, but the commit is the first thing that can
make it recur mid-sortie rather than only at process start. Two consequences, both already correct:
  1. Nothing is ever sent carrying the stale epoch during the gap -- the gate is unconditional.
  2. A `flight_pending_take`/`flight_pending_release` that was already staged and is waiting on an
     ack also does not get resolved/spoken while unconfirmed (since `drain_flight_control` is
     nested inside the same gate) -- its resolution is *delayed*, not lost: once reconfirmed, the
     next poll's `drain_flight_control` call resolves it exactly as it would have, including a
     correct timeout if `now_sim - sent_at_sim` has by then exceeded `HANDOVER_ACK_TIMEOUT_S`.
  3. Separately, `rules.gates._require_controls`'s `commands_ready` check means any *new* voice
     command dispatched during the gap gets an honest, immediate "unable, not ready" (`NOT_READY`)
     rather than being accepted and silently dropped -- confirmed by reading `gates.py` directly,
     not assumed from the commit message.
No readback is spoken for a request that was not actually applied, in either case.

**Mode-1/mode-2 consistency after a mid-take/mid-flight restart.** `FlightControlState`/
`ParkedFlightState` are refreshed from Lua's own mirrors every poll regardless of
`command_reset_confirmed` (only the *write* side is gated) -- so neither module ever drifts from
what Lua actually reports. `git show --name-only HEAD` confirms the diff touches only `body.py`
and tests; nothing in `ai_pilot_wheel.py`/`ai_pilot_wheel.lua`/`flight_authority.py` changed, which
the commit itself also states it checked. The AI-overlay-activation-is-a-handover-to-mode-2
constraint from the mid-task clarification (`docs/acceptance/2026-11-23-sortie-feedback.md`,
confirmed present: *"the player switching the AI overlay on is itself a handover to Petrovich in
mode 2 ... only a fresh take puts mode 1 back on the axes"*) is untouched by this commit by
construction -- it is a pure epoch-handshake change, orthogonal to which mode owns the axes.

**The rewritten test is a legitimate contract change, not a weakened one.**
`test_already_confirmed_is_a_true_no_op` asserted the *old* latch behaviour directly (confirmed +
an echo that had never matched -> still a no-op) -- exactly the bug. The rewrite
(`test_already_confirmed_with_both_echoes_still_matching_is_a_true_no_op`) asserts the *correct*
invariant for the new contract (confirmed + an echo that still matches sends nothing), which is
strictly narrower and still meaningfully assertive (`client.reset_calls == []` and
`command_reset_confirmed is True`), not a vacuous pass. No coverage was lost -- the old test's
premise is precisely what `TestCommandResetResync` now covers from the other, correct direction.

**New release-ack and resync tests, re-verified by mutation (not taken on the debug report's
word):**
- `TestDrainFlightControlReleaseAck`'s three cases: all fail under the block-disabled mutation
  (confirmed above).
- `TestCommandResetResync`'s four cases: reverted Fix B to the old one-shot latch
  (`if runner.command_reset_confirmed: return`) and ran `tests/test_body_command_reset.py` --
  4 of 4 `TestCommandResetResync` tests failed (the fifth, pre-existing, unaffected test in the
  file passed), for the expected reason (`command_reset_confirmed` staying `True` instead of
  flipping back). Reverted; `git diff --stat` on `body.py` empty before re-checking.

**Checks (body-layer only, the single subproject touched):**
- `.venv/bin/ruff format --check src tests` -- 230 files already formatted.
- `.venv/bin/ruff check src tests` -- all checks passed.
- `cd body-layer && .venv/bin/mypy src` -- success, no issues, 93 source files.
- `.claude/scripts/fast-tests.sh body-layer` -- 2907 passed, 4 xfailed (matches the debug report's
  own figure exactly).
- `.venv` symlinked in from the main checkout for this review and removed before committing;
  `git status --porcelain` clean apart from this review file.

### Required Fixes

None.

### Optional Refinements

- The pre-existing nesting of `drain_flight_control`/`drain_ai_pilot_wheel_speech` inside
  `if runner.command_reset_confirmed:` means a pending take/release's own ack resolution (not just
  new sends) is held during a resync gap, same as it always was at process start. This is correct
  (delayed, not lost -- see above) but worth a one-line note in `_resolve_command_reset`'s own
  docstring the next time that function is touched, since the docstring currently only states the
  claim for *new* sends ("nothing is ever sent") and not for already-pending resolution, which a
  future reader might otherwise assume is unaffected. Optional because the behaviour is already
  correct and tested via the full gate chain; this is purely a documentation completeness note.
- `[[BL-B134]]`'s "stand by" readback (named in both the debug doc and the commit as the correct
  follow-on for the player-audible gap during a resync/handshake) remains open, as it was before
  this commit -- flagging only so it is not mistaken for something this commit should have closed.

### Verdict
APPROVED

### Review Confidence
Full read. Both new test classes verified by independent mutation (not taken on the debugger's own
report): `TestDrainFlightControlReleaseAck`'s block disabled, `TestCommandResetResync`'s fix
reverted to the old latch -- each failed for the expected reason, then restored
(`git diff`/`git diff --stat` empty before moving on). Every call site named in the commit message
(`_apply_flight_requests`, `_apply_ai_pilot_wheel_goal`, `drain_flight_control`,
`rules.gates._require_controls`) traced directly in `body.py`/`gates.py`, not assumed. The plan's
own section 5 cross-checked to confirm this is a specified contract, not an invented one. The one
subproject touched (body-layer) had its full checks run directly.
