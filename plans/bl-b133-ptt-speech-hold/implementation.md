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
