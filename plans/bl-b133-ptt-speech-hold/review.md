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

---

## Re-review (fix pass, `4210603e..6571eccd`, tip `6571eccd`)

Method: worktree at `/Users/sg/Code/DCS-petrobrain-ptthold` was already checked out at
`6571eccdd85e05633f0d960e15a42eadeedf7ac0` on a clean tree (`git rev-parse HEAD` confirmed before
anything else, matching the expected tip exactly) — no detach/archive needed. `body-layer/.venv`
already existed in this worktree.

### Required Fix 1 (staleness keyed to the wrong clock) — resolved

`PttHoldGate` now takes a required, keyword-only `telemetry_received_wall_clock_s: Callable[[],
float | None]`; `_is_stale()` compares `wall_clock() - telemetry_received_wall_clock_s()` against
`PTT_FEED_STALE_AFTER_S` (renamed from `PTT_STALE_AFTER_S`), never the PTT sample's own
`received_wall_clock_s`. `body.py`'s `main()` wires it to
`crew_runner.last_telemetry_received_wall_clock_s`, a new field `run_once` sets from the same
`GET /telemetry/latest` poll it already makes — confirmed no second request is issued. Both named
options from the original finding were done, not just one: (a) `PttHoldGate.reset_for_new_mission()`
is wired into `body._reset_mission_state` via a new `speech_worker` parameter threaded through
`_check_for_new_mission`, and `grep` confirms there is exactly one production call site
(`_run_crew_text_poll_loop`, `body.py:5211`), which passes `speech_worker=crew_console.speech_worker`
— not just exercised in a test. This call site is the correct one and not redundant with
`CrewConsole.reset_for_new_mission`: that method's own docstring states `speech_worker` is in the
list of fields explicitly *preserved* (same object, not rebuilt) across a mission reset, so without
this wiring nothing would ever clear the gate's stuck state. (b) is the telemetry rekey itself.
Confirmed a long genuine hold with a live feed stays held and a dead feed releases
(`test_a_long_genuine_hold_with_a_live_telemetry_feed_stays_held`,
`test_dead_telemetry_feed_past_the_bound_releases_a_held_reading`) — read both, not just their
names; they exercise exactly the two properties the original defect conflated.

**Judgment call asked for in the task: "no telemetry ever received while held = stale."**
`_is_stale()` returns `True` (so `is_held()` reports released, not held) when
`telemetry_received_wall_clock_s()` returns `None` — the state for the first instant of process
life, before any `GET /telemetry/latest` poll has completed. In principle this reopens a sliver of
the original problem: if a routine line were enqueued and the PTT gate polled before the first
telemetry poll resolves, with the player already holding the trigger, Petrovich would not be held.
Traced the actual startup ordering in `body.py:main()`: `speech_worker.open()` starts the
worker thread before the poll thread (which performs the first telemetry fetch) is even created, so
the window is real, not closed by ordering. But it is not a new defect introduced by this fix — it
is the same documented, already-existing module posture applied consistently: the docstring's own
"**Failure posture: unknown reads as released, never as held forever**" governs the `AircraftLayerError`-unavailable
case identically (an unknown PTT feed state also resolves to released, pre-dating this fix), and
`_is_stale`'s `None` branch carries an explicit comment ("No telemetry has ever been received this
process's lifetime -- at least as stale as any bound") stating the choice rather than leaving it
implicit. It is also directly tested
(`test_no_telemetry_ever_received_is_treated_as_stale_while_held`), so it is a stated design
decision, not an oversight. For a line to actually reach this window, something other than the poll
loop's own `run_once` (which sets `last_telemetry_received_wall_clock_s` before any speech gets
queued in that same poll) would have to enqueue a routine line in the sub-second gap before the
first telemetry poll resolves — narrow enough, and consistent enough with the project's stated
"unknown → released, never held forever" tradeoff elsewhere in this same module, that I am not
treating it as a required fix. Worth one line in the docstring's "Stale" paragraph calling this out
explicitly as a third case alongside "Unavailable," since right now it is only discoverable by
reading `_is_stale`'s own comment — **optional**.

### Required Fix 2 (interrupt/wait race) — resolved, verified by mutation, not just by reading

`_gate_wait_active`/`_gate_wait_superseded`, both guarded by one `_gate_lock`, replace the bare
`Event` as the source of truth; the `Event` survives only as a non-authoritative prompt-wake. Traced
the scheme by hand: `_run` sets `_gate_wait_active=True, _gate_wait_superseded=False` under the lock
*before* calling `_wait_for_ptt_release`, so any `interrupt()` that acquires the lock from that point
on — including exactly the window the original defect found — sees `_gate_wait_active` already
`True` and marks the supersession; `_wait_for_ptt_release`'s loop checks `_gate_wait_superseded`
every iteration instead of relying on the `Event`'s own clear-then-check; `_gate_wait_active` is
reset to `False` the moment a wait resolves, and `_gate_wait_superseded` is only ever reset to
`False` at the *start* of the next gated item's wait (same critical section as setting
`_gate_wait_active=True`), so a stale `True` left by an earlier supersession cannot leak into a
later, unrelated item's wait — confirmed against
`test_an_earlier_supersession_does_not_leak_into_a_later_waits_abort`, which drives exactly that
sequence. No nested lock acquisition and no lock held across a blocking call (`Event.wait()` always
happens outside `_gate_lock`), so no deadlock path.

**Verified by mutation, per the task's instruction, not by reading alone:** reverted
`speech_worker.py` to its pre-fix content (`git show 4210603e:...`) and ran
`test_interrupt_racing_between_dequeue_and_wait_start_is_not_lost` and
`test_an_earlier_supersession_does_not_leak_into_a_later_waits_abort` against it. The race test hung
— `worker._wait_for_ptt_release()` blocked indefinitely past its own 1-second assertion window and
had to be killed — which is the predicted failure mode exactly (the pre-set abort signal silently
wiped by the unconditional `clear()`, then nothing left to wake the wait against a gate that never
releases). Restored the fixed file afterward and confirmed a clean diff against the real tip before
continuing. This is a stronger confirmation than the original review's own repro (which showed a
1-second block, not an indefinite one) because the mutation shows the *new* test — not just the
old bug — actually depends on the fix.

### No other behaviour changed

`defaults.toml`'s diff is exactly the `PTT_STALE_AFTER_S`→`PTT_FEED_STALE_AFTER_S` rename plus the
rewritten first-sentence comment, read in its rendered form (not the `#:` source) — correct,
complete, and the `lo`/`hi` bounds (10.0/600.0) are unchanged. `body-layer/CLAUDE.md`'s two touched
lines are accurate restatements of the new behaviour, not drift. `test_body.py` (237 passed) and the
full `tests/test_ptt_hold.py`/`test_speech_worker.py`/`test_mission_start_reset.py` diffs were read
in full; no test was weakened or deleted, only the two files' fixtures updated to the new required
constructor argument and new tests added. `implementation.md`'s claim that the `mypy tests/` errors
predate this pass was spot-checked by reasoning about the pattern described (a `Callable[[], float]`
fake clock missing `.advance()`, `Protocol` structural mismatches) rather than re-run via a second
`git stash`, since `mypy tests` is explicitly outside this project's formal gate (`mypy src` only)
and the pattern matches known pre-existing conventions elsewhere in this test suite.

### Checks run (re-review)
- `ruff format --check src tests`: pass (230 files already formatted)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (`Success: no issues found in 93 source files`)
- `.claude/scripts/fast-tests.sh body-layer`: 2820 passed, 4 xfailed — matches `implementation.md`'s
  own reported count, no flake seen this run
- Mutation check: pre-fix `speech_worker.py` + the two new race tests → hung/killed (confirms the
  tests are load-bearing against the actual fix, not just new assertions that happen to pass)

### Re-review Verdict
**APPROVED**

Both required fixes are resolved, correctly scoped to the one module this feature touches, and
verified — Fix 1 by reading the rekey and the mission-reset wiring down to the one production call
site, Fix 2 by mutation (reverting the fix and confirming the new tests fail/hang against the old
code, not just reading the lock scheme). The one edge case worth a human decision — "no telemetry
yet" at process startup resolving to released rather than held — is a documented, tested, consistent
application of this module's existing "unknown → released, never held forever" posture, not a new
defect; flagged above as an optional one-line docstring addition, not a blocker.

### Re-review Confidence
Full read of `4210603e..6571eccd` (all 10 files) plus `body.py`'s `main()`/`_check_for_new_mission`/
`_run_crew_text_poll_loop` call chain to confirm the one production call site. Both required fixes
confirmed by direct mechanism tracing; Fix 2 additionally confirmed by mutation (ran the new tests
against the reverted pre-fix file and observed the hang).
