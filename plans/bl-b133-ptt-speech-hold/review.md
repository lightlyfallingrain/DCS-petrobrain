### Review Summary

Reviewed `feature/bl-b133-ptt-speech-hold` at tip `758db694` (one commit on `c3ed21b4`), via
`git checkout --detach 758db694` (direct checkout succeeded on a clean tree — the archive fallback
was not needed). `body-layer/.venv` did not exist in this worktree and was created
(`python3.14 -m venv`, same package set: `numpy<2.5`, `pyproj>=3.6`, `lupa==2.8`, `ruff`, `mypy`,
`pytest`, `pytest-xdist`).

The shape is right: the hold lives in `SpeechWorker._run`/`_wait_for_ptt_release`, not
`CrewConsole._print`, matching the plan's own reasoning and this project's "actions/when in one
place" rule; urgent bypass, "let it play," seat-OR'ed trigger reading, and the tuning/`defaults.toml`
mechanics are all correctly built and tested. Two real defects found, both load-bearing to the
feature's actual purpose, neither flagged as such in `implementation.md` (the staleness one is
flagged as a *tradeoff*, not as something to fix; the race is not mentioned at all).

### Required Fixes

1. **Staleness is keyed to the wrong clock — a routine, physically-held PTT longer than
   `PTT_STALE_AFTER_S` (120 s) will make Petrovich start talking over the player, which is exactly
   the behaviour U1 exists to prevent.** `Export.lua`'s `push_ptt_state` sends a line only on
   change (confirmed, `aircraft-layer/dcs-export/Petrobrain/ptt_ics.lua`), so a *steadily held*
   trigger's `received_wall_clock_s` ages identically to a dead feed's — `PttHoldGate._is_stale`
   cannot tell "the player is still holding it" from "the collector died with a stale cached
   sample" (the scenario the module docstring says it guards against), because it is reading the
   same signal for both. The module docstring's own "comfortably longer than any ordinary
   intercom/radio call" claim is asserted, not checked, and a tactical brief or a long ATC
   exchange is not an exotic case. `implementation.md` states this as an accepted, flight-test-
   deferred tradeoff ("the one open question worth flight-testing") — but it is not a judgment call
   about feel, it is a provably wrong signal, checkable without flying: the task's own check #1
   predicted exactly this and asked for the fix unless no freshness signal exists. One does exist
   and was not used: `GET /telemetry/latest` is pushed every export tick regardless of value
   (5 Hz, throttled in `Export.lua`, not send-on-change) — its own `received_wall_clock_s`
   freshness (or, more directly, body-layer's existing mission-restart detection,
   `body._reset_mission_state`/`_check_for_new_mission`, which every other per-run component resets
   on) is the right place to detect "the collector survived a dead mission," since that is the only
   concrete failure case named in the docstring. `PttHoldGate` currently has neither a reset hook
   nor access to that signal (`ptt_gate` is absent from `_reset_mission_state`'s list in
   `body.py`). Fix: either (a) wire `PttHoldGate` into the mission-restart reset path so a dead
   mission clears any stuck `held=True` state at the actual lifecycle event instead of guessing a
   duration, or (b) key `_is_stale` off a feed that is known to refresh continuously (telemetry's
   own timestamp) rather than the PTT sample's own age. Either removes the real failure mode
   without penalizing a genuine long hold. Confirmed the mechanism (not a hypothetical): with
   `_ptt_body(intercom=True, received_wall_clock_s=T)` and a fake wall clock advanced past
   `PTT_STALE_AFTER_S`, `is_held()` returns `False` even though nothing about the player's actual
   trigger state has changed — this is exactly `test_stale_held_reading_reports_released_and_warns_once`'s
   own assertion, written as confirming the *intended* behaviour rather than flagging it as the
   defect it is against U1's literal, unqualified "while either is pressed."

2. **A genuine race in `_wait_for_ptt_release` can lose a legitimate urgent-arrival interrupt and
   delay the urgent line until the PTT is physically released — not until the next poll, until the
   *trigger is let go*, directly contradicting U1's "say urgent ones even when I hold trigger."**
   `_wait_for_ptt_release` unconditionally calls `self._ptt_wait_abort.clear()` on entry, *then*
   enters its `is_held()`/`wait()` loop. If `interrupt()` (an urgent `enqueue`) sets
   `_ptt_wait_abort` in the window between `_run` dequeuing the routine item and
   `_wait_for_ptt_release`'s `clear()` call — a real, if narrow, window; nothing serializes the two
   — that `clear()` silently discards the pending signal, and the wait then blocks on
   `is_held()` alone until it goes physically false, which (per Required Fix 1) can be well past
   when the urgent line should have spoken. The existing test for this path
   (`test_held_routine_line_is_dropped_by_an_urgent_arrival_while_waiting`) only exercises the safe
   ordering — it waits for `gate.calls > 0` (i.e. past the `clear()` call) before enqueuing the
   urgent line — so it cannot and does not catch this. Confirmed directly, not just by inspection:
   calling `worker._ptt_wait_abort.set()` *before* calling `worker._wait_for_ptt_release()` against
   a gate that is held leaves the call still blocked a full second later (repro run against this
   checkout; the unconditional `clear()` at entry wipes the pre-set flag). The fix is not simply
   "don't clear at the top" — that reopens a different bug (a stale, already-consumed `set()` from
   an earlier interrupt leaking into a later, unrelated item's wait, since urgent items that
   bypass the gate entirely never consume the flag). It needs either a lock shared with
   `interrupt()`'s `set()`/`_clear_queue()` so the two can't interleave, or a monotonic
   interrupt-sequence counter captured at dequeue time and compared rather than a bare `Event`
   cleared-then-checked.

### Optional Refinements

- The module docstring's "comfortably longer than any ordinary intercom/radio call in this
  aircraft" sentence, once Required Fix 1 is resolved, should either be removed or re-stated as
  "the duration past which a held sample is assumed to be a dead feed, not a real call" — the
  current wording reads as a claim about cockpit radio-call length, which is exactly the
  unsupported "X, so Y" shape this project's reviewer habit calls out.
- `test_crew_text_poll_loop_survives_a_raising_poll_and_keeps_going` failed once under
  `fast-tests.sh body-layer` (full suite) but passed both standalone and on a second full run —
  pre-existing flake (a logging-handler-closed-file error on an unrelated poll-loop test, Python
  3.15 test environment, not touched by this diff's files). Not this branch's defect; worth a
  separate ticket if it recurs.

### Verdict
NEEDS REVISION

Both required fixes are in the one module this feature exists to add (`belief/ptt_hold.py`,
`belief/speech_worker.py`'s new wait path) — not scope creep, not a nit. Fix 1 is the feature's own
core correctness property (urgent-vs-routine PTT behaviour deferred to "needs flight" is not
appropriate here since the defect is provable without flying); Fix 2 is a real, demonstrated race
in the interrupt path, not a theoretical one. Everything else — wiring, tuning, seat coverage,
debounce shape, `defaults.toml` rendering, module-map/CLAUDE.md updates — is correct and well
tested.

### Checks run
- `ruff format --check src tests`: pass (230 files already formatted)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (`Success: no issues found in 93 source files`)
- `.claude/scripts/fast-tests.sh body-layer`: 2813 passed, 4 xfailed (one flaky unrelated failure
  on a separate run, see Optional Refinements)
- `tests/test_ptt_hold.py tests/test_speech_worker.py tests/test_aircraft_client.py
  tests/test_tuning_defaults_toml.py` run directly: 69 passed

### Review Confidence
Full read of the diff (`c3ed21b4..758db694`, all 11 files), `schema/ptt.py`,
`aircraft-layer/src/api/server.py`'s `_handle_ptt_state`, and `Petrobrain/ptt_ics.lua` (the
Export.lua side, to settle check #1). Both required fixes were confirmed by direct repro against
this checkout, not inferred from reading alone.
