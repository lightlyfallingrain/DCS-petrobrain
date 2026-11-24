### Implementation Summary

BL-B133: Petrovich does not *start* a routine utterance while the player holds the ICS (intercom)
or RADIO trigger. The real wire endpoint turned out to be `GET /ptt/state`, not the `GET
/ptt/latest` the backlog item's own text named — `aircraft-layer/src/api/server.py` and `schema/
ptt.py` confirm the route and the server-side SPU-8 gating of `"intercom"`.

**Where the hold lives, and why:** `belief.speech_worker.SpeechWorker._run`/
`_wait_for_ptt_release`, not `CrewConsole._print`. `SpeechWorker._run` is already the single place
that decides *when* a queued line's `client.push_speech` call actually starts (on its own
background thread), so gating there needs no change to `_print`'s synchronous, immediate-return
`enqueue()` contract, and blocking there blocks neither the poll thread nor whichever thread calls
`_print`. A line already *playing* is untouched: the gate only runs before `_process` starts for
the *next* item, never during one already in flight, so "a line already playing plays to the end"
falls out of the existing structure rather than needing a new check.

**The decision itself** (`belief.ptt_hold.PttHoldGate.is_held()`, new module):
- `intercom or radio` (either trigger) holds, matching the user's "either".
- **Release debounce, not press debounce.** A full press transits the intercom stop for 19-32 ms
  each way (measured, `ptt_source.py`'s `INTERCOM_DEBOUNCE_S`). Starting to hold early is harmless
  (only delays a line that was going to wait anyway), so the press edge needs none. Letting go
  early on a transit blip would open a real window to start a line the trigger is about to
  re-claim, so a `held=False` reading must persist for `PTT_RELEASE_DEBOUNCE_S` (0.1s) before
  `is_held()` reports released — ordinary hysteresis, reset by any intervening `True`.
- **The debounce only ever applies to a genuine held→released transition.** A fresh gate (or one
  that has already settled released) reports a `released` sample as released immediately — this
  was a real bug caught by `test_idle_untouched_trigger_is_never_reported_stale`: the first version
  unconditionally started a debounce window on the very first `is_held()` call whenever the
  current sample read released, so a brand-new gate (or one polled only occasionally) would report
  "held" for up to one debounce window for no reason tied to any actual release. Fixed by tracking
  `_confirmed_held` (the last debounced state) and only starting the release timer when that was
  `True`.
- **Failure posture — unknown reads as released, never held forever, each logged once, not once
  per poll:**
  - *Unavailable* (`AircraftLayerError` — network down): reuses the existing `ConnectionReporter`
    transition-only `report_failure`/`report_success` mechanism (the same one `SpeechWorker`
    already shares with `_poll_transcripts` for the audio-adapter seam) rather than inventing a
    second "log once" mechanism. `body.py` wires a *separate* `ConnectionReporter` instance
    (`label="ptt feed"`) — sharing `audio_adapter_reporter` would make an aircraft-layer outage log
    as an audio-adapter one or vice versa.
  - *Stale* (checked only when the sample currently reads **held**): if `received_wall_clock_s` is
    older than `PTT_STALE_AFTER_S` (120s), treat as released. `Export.lua` sends a `ptt` line only
    on change, so an *untouched* trigger's timestamp ages indefinitely — that is the ordinary idle
    case and must never be flagged stale (it already reports released with no need to look at the
    age at all; this was the same bug class as above, caught by the same test). What the bound
    actually guards against is a collector surviving a crashed/ended mission while the last cached
    sample happened to read "held" — nothing would ever refresh it, and the gate would hold
    Petrovich mute for the rest of the process's life. **Tradeoff, stated explicitly in the module
    docstring: a genuine radio call longer than 2 minutes will let Petrovich start talking over
    it.** Chosen because an occasional early start is recoverable in a way an indefinitely silent
    crew member is not. This is the one open question worth flight-testing.
- No persistent-staleness-of-the-feed-itself check beyond the above (e.g. "last successful poll
  too long ago") — a failed `GET /ptt/state` already resolves to released via the unavailable
  path, so there was nothing further to add there.

**Order/no-loss, and the urgent-arrival race:** `SpeechWorker.enqueue(bypass_gate=True)` already
calls `interrupt()` before the urgent item joins the (now-empty) queue. `interrupt()` now also
sets a new `threading.Event` (`_ptt_wait_abort`) that `_wait_for_ptt_release` polls alongside the
gate — without it, a routine item already dequeued and waiting on the gate would finish its wait
*before* the worker thread ever looked at the urgent item sitting in the queue behind it, delaying
the urgent line. With it, the held routine item is dropped (same "superseded, dropped" policy
`interrupt()` already applies to anything still in the queue) and the urgent item speaks
immediately. A routine item that is merely *waiting* on the queue (not yet dequeued) is already
safe: `interrupt()`'s existing `_clear_queue()` removes it before it is ever seen.

### Files Changed
- `body-layer/src/aircraft_client.py` — new `get_ptt_state_latest()` (`GET /ptt/state`), mirroring
  `get_spu8_state_latest`'s "not an error" empty-cache posture exactly.
- `body-layer/src/belief/ptt_hold.py` (new) — `PttHoldGate`/`PttSource` Protocol, the hold/
  debounce/staleness decision described above, plus the two new tunables.
- `body-layer/src/belief/speech_worker.py` — `SpeechWorker` gained `ptt_gate`, `_ptt_wait_abort`,
  `_wait_for_ptt_release`; `_run` consults the gate before a non-urgent item's `_process`;
  `interrupt()` also sets the abort event.
- `body-layer/src/body.py` — builds a `PttHoldGate` (its own `ConnectionReporter`, label
  `"ptt feed"`) and wires it into the production `SpeechWorker`.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`); the two
  new keys' rendered first sentences read as intended (checked, not just the source comment).
- `body-layer/CLAUDE.md` — module-list entries for `ptt_hold.py`/the `speech_worker.py` change,
  and the Tuning section's curated-constants list.
- `body-layer/ROADMAP/BL-B133.md` — `[~]` in-progress (not `[x]` done — that is Reviewer/DoD's
  call), with a "Built" note summarizing the above and naming the one open-for-flight question.
- `body-layer/tests/test_aircraft_client.py` — `_PTT_STATE_BODY` fixture, two new tests for
  `get_ptt_state_latest`.
- `body-layer/tests/test_speech_worker.py` — `_FakePttGate` double, six new tests (see below).
- `body-layer/tests/test_ptt_hold.py` (new) — ten tests against a real loopback server plus fake
  clocks.
- `plans/bl-b133-ptt-speech-hold/implementation.md` (this file).

**`body-layer/.venv` did not exist in this worktree** (fresh feature worktree) and was created
(`python3.14 -m venv`), with the same package set as the main checkout's venv
(`numpy<2.5`, `pyproj>=3.6`, `lupa==2.8`, `ruff`, `mypy`, `pytest`, `pytest-xdist`) — no
`pyproject.toml`/dependency change.

### Tests Added
`test_ptt_hold.py` (against a real loopback `http.server` + injected fake `monotonic`/
`wall_clock`, never real sleeps):
- `test_intercom_held_reports_held` / `test_radio_held_reports_held` — either trigger holds.
- `test_released_with_no_prior_hold_reports_not_held_immediately` — the fixed "no debounce owed
  without a prior hold" behaviour.
- `test_never_moved_reports_not_held` — `null` payload (startup) reads as released, no debounce.
- `test_release_debounce_keeps_held_true_until_window_elapses` / `..._resets_on_a_flicker_back_to_held`
  — the mechanical-transit guard and its hysteresis.
- `test_stale_held_reading_reports_released_and_warns_once` — the staleness guard, one warning
  despite repeated stale reads.
- `test_idle_untouched_trigger_is_never_reported_stale` — the idle case never warns (this is the
  test that caught both bugs described above).
- `test_unreachable_feed_reports_released_via_connection_reporter` /
  `..._logs_once_with_no_reporter_configured` — the unavailable path, both with and without a
  shared reporter.

`test_speech_worker.py` (against a `_FakePttGate` double, `SpeechClient` fake, never a real PTT
feed — the feed itself is `test_ptt_hold.py`'s job):
- `test_routine_line_waits_for_ptt_release_then_speaks_in_order` — held → nothing starts → release
  → both lines speak, in order.
- `test_urgent_line_speaks_while_ptt_held` — urgent bypasses the gate entirely.
- `test_radio_held_blocks_a_routine_line_same_as_intercom` — confirms `SpeechWorker` adds no
  second, narrower check of its own (the gate already folds both into one bit).
- `test_already_playing_line_is_not_interrupted_when_ptt_goes_down` — the "let it play" case.
- `test_held_routine_line_is_dropped_by_an_urgent_arrival_while_waiting` — the urgent-preempts-a-
  waiting-item race described above.
- `test_ptt_feed_unavailable_does_not_hold_speech` — wiring-level confirmation of the unavailable
  posture.

`test_aircraft_client.py`:
- `test_get_ptt_state_latest_returns_parsed_dict` / `..._raises_on_unreachable_host`.

### Checks
body-layer only (the one subproject touched):
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (`Success: no issues found in 93 source files`)
- `.claude/scripts/fast-tests.sh body-layer`: pass (2813 passed, 4 xfailed — pre-existing xfails,
  unrelated to this change)
- `tests/test_ptt_hold.py` / `tests/test_speech_worker.py` / `tests/test_aircraft_client.py` run
  individually (not just via the fast-tests smoke pass): all pass, 68 tests across the three files
  for the touched area specifically.
- `tests/test_tuning_defaults_toml.py` (the staleness-of-`defaults.toml` guard): pass.

world-model/aircraft-layer: untouched by this change (no files under either), so no commands run
there.

### Notable Discoveries
- The backlog item's own text names `GET /ptt/latest`; the real route (confirmed in
  `aircraft-layer/src/api/server.py`) is `GET /ptt/state`. Noted in the ROADMAP "Built" paragraph
  so a future reader does not go looking for a route that was never real.
- Two real bugs in my own first draft, both caught by the same test
  (`test_idle_untouched_trigger_is_never_reported_stale`) and both from the same root cause —
  comparing a fixed/old `received_wall_clock_s` against a real `time.time()` default in a test that
  didn't inject one, which then surfaced that the *product* code had the matching defect for the
  idle case (debounce starting on the very first call regardless of history; staleness evaluated
  even when not held). Both fixed before this report; see "Where the hold lives" above and the
  module's own docstring for the corrected design. Flagging per the project's "red before green"
  convention: I did not deliberately break the mechanism first, but the fix was driven by an
  assertion that actually failed for the stated reason, not a tautological one.
- `PTT_RELEASE_DEBOUNCE_S` and `PTT_STALE_AFTER_S` have no asserted relationship with each other or
  with any other tunable (no cross-key coupling registered in `tuning.py`) — I did not add one.
  They are each independently bounded (`lo=0.0,hi=1.0` and `lo=10.0,hi=600.0`), and I see no
  invariant between them or with `audio-adapter`'s own `INTERCOM_DEBOUNCE_S` (a different process,
  different venv, not coupled by this loader) that a per-key bound could miss.

### Review fixes (`plans/bl-b133-ptt-speech-hold/review.md`, both REQUIRED, now resolved)

**Fix 1 — staleness was keyed to the wrong clock.** `Export.lua` sends a `ptt` line only on
change, so a steadily held trigger's own `received_wall_clock_s` ages identically to a dead
collector's cached sample — the gate could not tell them apart, meaning a routine hold longer than
`PTT_STALE_AFTER_S` (120s) would make Petrovich start talking over the player, exactly what U1
forbids. Fixed two ways:
- **Rekeyed staleness to the telemetry feed, not the PTT sample.** `PttHoldGate` now takes a
  required `telemetry_received_wall_clock_s: Callable[[], float | None]` constructor argument;
  `_is_stale()` compares `wall_clock() - telemetry_received_wall_clock_s()` against the bound,
  never the PTT sample's own timestamp. `body.py` wires this to `crew_runner.last_telemetry_
  received_wall_clock_s`, a new `ConsolePerceptionRunner` field `run_once` already sets every poll
  from the same `GET /telemetry/latest` call it already makes (`Export.lua` sends telemetry every
  tick regardless of PTT value, unlike `ptt`'s send-on-change) — no second request. Renamed
  `PTT_STALE_AFTER_S` → `PTT_FEED_STALE_AFTER_S` and rewrote its `#:` comment/module docstring
  accordingly; regenerated `config/defaults.toml` and read the rendered first sentence, not just
  the source. Required (no default): an omitted wiring must fail loudly (`TypeError` at
  construction), not silently disable staleness detection — project's "fail loud, not recover"
  rule. `telemetry_received_wall_clock_s() -> None` (never received) is treated as at least as
  stale as any bound.
- **Wired `PttHoldGate.reset_for_new_mission()` into `body._reset_mission_state`** (new
  `speech_worker: SpeechWorker | None = None` parameter, threaded through `_check_for_new_mission`
  and the one production call site, `speech_worker=crew_console.speech_worker`) — a genuine DCS
  mission (re)start clears a stuck `held=True` state at the actual lifecycle event, as the review
  suggested as option (a). `SpeechWorker` gained a matching `reset_for_new_mission()` that
  delegates to its own `ptt_gate` (no-op if unset) — needed because `CrewConsole.reset_for_new_
  mission` preserves `speech_worker` as the same object across a restart rather than rebuilding it,
  so this is the one call site where the gate's state actually gets cleared.

  Did both (a) and (b) from the review's "either/or" rather than picking one: the telemetry-freshness
  rekey alone does not help a session that never sees a new mission-start event (DCS idling at the
  main menu after a crash, nothing to detect); the mission-restart reset alone does not help a feed
  that stays nominally "the current mission" but has stopped actually updating. Together they cover
  both named failure modes.

**Fix 2 — a real race in `SpeechWorker._wait_for_ptt_release` could lose an urgent-arrival
interrupt.** The original code called `self._ptt_wait_abort.clear()` unconditionally at the top of
`_wait_for_ptt_release`; an `interrupt()` landing in the window between `_run` dequeuing a routine
item and that `clear()` running would have its `set()` silently wiped, leaving the wait blocked on
`is_held()` alone until the trigger was physically released. Confirmed by direct repro before
fixing (same technique the review used): setting the `Event` before calling `_wait_for_ptt_release`
left the call blocked a full second later against a held gate.

Fixed by replacing the bare `Event` as the source of truth with a lock-protected pair scoped to
exactly one item's wait at a time: `_gate_wait_active` (set by `_run`, under `_gate_lock`,
immediately after dequeuing an item that needs the gate, before calling `_wait_for_ptt_release`) and
`_gate_wait_superseded` (set by `interrupt()`, under the same lock, *only if* `_gate_wait_active` is
currently `True`). `_wait_for_ptt_release`'s loop checks `_gate_wait_superseded` under the lock on
every iteration instead of relying on the `Event`; the `Event` stays only as a prompt-wake
optimisation (`interrupt()` still calls `.set()` so a waiting thread does not sit through a full
`_PTT_WAIT_POLL_INTERVAL_S` after an interrupt). This closes the exact window the review found: an
`interrupt()` racing in between dequeue and the wait's own first check now always sees
`_gate_wait_active` already `True` (set by `_run` moments earlier, before the race window could even
open) and marks the flag — there is no code path where the signal can be set-then-silently-cleared,
because nothing ever blindly clears `_gate_wait_superseded`; it is only ever reset to `False` at the
*start* of a new item's own wait (under the same lock), not at the top of `_wait_for_ptt_release`
itself.

I deliberately did not reuse a bare `clear()`-based fix: the review itself flags that "don't clear at
the top" alone reopens a different bug — an urgent item's own `enqueue(bypass_gate=True)` calls
`interrupt()` but never itself consumes the flag (it skips the gate branch in `_run` entirely via
`item.bypass_gate`), so a leftover `True` from that interrupt could otherwise leak into a later,
unrelated routine item's wait. The scoping fix is `_run` resetting `_gate_wait_superseded = False`
fresh at the *start* of every new gated item's branch (not just after a fresh `interrupt()`) —
verified by `test_an_earlier_supersession_does_not_leak_into_a_later_waits_abort`, which drives
exactly that sequence (routine A superseded → urgent plays → routine B must still wait normally,
not be dropped).

New tests (both "red before green" — written to fail against the pre-fix code, confirmed, then the
fix applied and confirmed green):
- `test_ptt_hold.py`: `test_a_long_genuine_hold_with_a_live_telemetry_feed_stays_held` (ten
  simulated minutes held, live telemetry throughout, never released early — the property Fix 1
  exists for), `test_dead_telemetry_feed_past_the_bound_releases_a_held_reading` (telemetry stops
  refreshing, PTT sample's own payload never changes — released once the *telemetry* age crosses
  the bound), `test_no_telemetry_ever_received_is_treated_as_stale_while_held`, `test_reset_for_
  new_mission_clears_confirmed_held_and_release_debounce`. `test_stale_held_reading_...`/`test_idle_
  untouched_trigger_is_never_reported_stale` rewritten to the new telemetry-keyed semantics rather
  than left asserting the old (wrong) behaviour.
- `test_speech_worker.py`: `test_interrupt_racing_between_dequeue_and_wait_start_is_not_lost`
  (deterministic repro of the exact race, no real threading/timing — sets `_gate_wait_active = True`
  the way `_run` would have just set it, calls `interrupt()`, then asserts `_wait_for_ptt_release()`
  returns `False` immediately rather than blocking), `test_an_earlier_supersession_does_not_leak_
  into_a_later_waits_abort` (the anti-regression test for the "don't reopen the stale-leak bug"
  constraint above).
- `test_mission_start_reset.py`: `test_reset_mission_state_resets_ptt_gate_via_speech_worker_when_
  given` / `..._is_a_noop_for_speech_worker_when_omitted`, matching the existing `fired_on_tracker`/
  `lost_contact_tracker` pair's own shape.

### Checks (review-fix pass)
- `ruff format --check src tests`: pass (230 files already formatted, 1 reformatted during this
  pass — `body.py`'s new lambda argument)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (`Success: no issues found in 93 source files`)
- `.claude/scripts/fast-tests.sh body-layer`: 2820 passed, 4 xfailed
- `tests/test_ptt_hold.py tests/test_speech_worker.py tests/test_mission_start_reset.py
  tests/test_aircraft_client.py tests/test_tuning_defaults_toml.py`: 113 passed
- `tests/test_body.py` (body.py changed significantly — `_reset_mission_state`/`_check_for_new_
  mission` signatures, `ConsolePerceptionRunner`, `run_once`): 237 passed

### Notable discoveries (review-fix pass)
- `mypy tests/` (not part of the formal gate — `CLAUDE.md`'s command is `mypy src` only) reports
  pre-existing errors in `test_ptt_hold.py`/`test_speech_worker.py`/`test_mission_start_reset.py`
  unrelated to this change (a `Callable[[], float]` used as a fake clock with `.advance()`, `_Fake
  PttGate`/`_FakeAircraftClient` not structurally matching their Protocols, two unrelated pre-
  existing issues in `test_mission_start_reset.py`) — confirmed via `git stash` that every one of
  these already existed before this review-fix pass; two new instances of the same pre-existing
  `Callable`/`_FakeAircraftClient` pattern were added by my own new tests, consistent with the
  existing convention rather than a new defect.
