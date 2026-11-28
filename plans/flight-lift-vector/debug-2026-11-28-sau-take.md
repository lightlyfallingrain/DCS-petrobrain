### Debug Report

### Observed Issue

BL-16 M4 (commit `03b67fcb`) should press SAU H, K, T channel OFF (B stays ON) the moment
Petrovich takes the raw axes (mode 1). Two flown sorties on 2026-11-28, both after a mode-1 take:

- **Sortie 2** (`lv3-aircraft_layer_debug.log`): take at 18:39:45-46, no `device=10` cockpit-switch
  command ever received by `Export.lua` afterward.
- **Sortie 1** (`lv2-aircraft_layer_debug.log`): take at 18:22:56 (`flight ack seq=7 a:m1 mode=m1`,
  `t=23.182`); the H/K/T-off commands (`device=10 cmd=3007/3003/3011`) did not arrive until
  18:23:35 -- 39 real/sim seconds later, with no further `fd_mode` change logged in between (the
  mode stayed `m1` the whole time, confirmed by two intervening `flight ack ... mode=m1` lines).

### Hypothesis

The wiring added by `03b67fcb` is correct and matches spec exactly (confirmed by reading
`controls_to_petrovich_edge`/its firing site in `body.py`, and by the two existing reviews
`review-m4-sau.md`/`review-sau-handover.md`, both of which independently verified the effector/
device/cmd/arg mapping against the raw dump). The defect is in `belief.effector_engine.advance`'s
own, pre-existing readback mechanism, which this is the first *safety-critical* user of:

- Each `EffectorTrigger` run reads its own cockpit args once via a synchronous `client.read_args`
  call. If that call keeps failing (`AircraftLayerError`), the run retries every poll for up to
  `EFFECTOR_CONDITION_READBACK_WAIT_S` (5.0 s) of **sim** time, then gives up and treats every arg
  as unknown.
- For a **non-absolute** effector shape (every SAU button here -- momentary, `default_square_
  button`, confirmed in `effectors.toml`), an unknown self-check readback **skips the row with only
  a `logger.warning`, never writes** -- this is deliberate, documented behaviour
  (`advance`'s own module docstring, "Each run carries a snapshot"), and is proven by the existing
  `test_effector_engine.py::test_e2_non_absolute_unknown_readback_skips_with_warning`.
- Critically, **once a sequence-row run gives up, it is never retried** -- the trigger is removed
  from `EffectorRunState.runs` and nothing re-fires it until the next genuine `fd_mode` edge (a full
  release-and-retake). This is explicitly contrasted with the engine's *other* kind of run (an ad
  hoc, rule-originated single-target write via `request_write`), whose own docstring says the
  opposite: "unlike a sequence row ... a rule-originated write is a command the pilot explicitly
  asked for, so that case is kept and retried ... rather than silently abandoned."

For every sequence this engine previously drove (takeoff, mission-start, seat change, OBSERV,
weapons-safe/arm), a lost run is low-stakes -- it is either re-triggerable by the player repeating
the action, or cosmetic. `CONTROLS_TO_PETROVICH` is different: it is exactly the scenario the user
explicitly reasoned about in the M4 explore notes ("the SAU fights Petrovich's control writes ...
duplicates what the law already does") -- losing it silently leaves the SAU fighting the
lift-vector law for the rest of the flight, with **no spoken or logged signal reaching the player**
(only a `WARNING`-level log line, which this project's own posture otherwise reserves for things
that get a spoken "unable" or a startup banner).

**What could make `read_args` fail or stall specifically around a mode-1 take** could not be
pinned down further from available evidence -- no body-layer stderr/debug log was kept for either
sortie (only the Export-side `aircraft_layer_debug.log`, which logs nothing for an ordinary
`read_args` round trip, success or failure, mirroring exactly the gap the 2026-11-23 debug pass
(`debug-2026-11-23.md`, "Problem 4") already found and flagged for the analogous flight-take-ack
path: *"the take/ack/refusal path is genuinely invisible in this log."* Candidates considered and
not provable from the two sorties' logs alone: a transient collector/HTTP hiccup at the moment
Export.lua's mode-1 law and the new M3 terrain relay both start running every poll; a slow single
poll iteration (sim time captured once per poll, so a poll that stalls on something else entirely
would make a write that lands at the *next* sim-time tick appear "late" only in wall-clock terms).
Ruled out by direct code reading: a duplicate/mismatched `EffectorTrigger` enum; a staleness/
ordering bug in `advance_flight_authority`'s "capture previous, then compare" idiom (matches
`controls_to_player_edge`'s own, reportedly-working pattern exactly); a seat/`hands_free` gate on
the effector engine (confirmed, via `grep`, that neither `effector_engine.py` nor `effector_
registry.py` reads `CrewState.hands_free` or any seat field at all -- the coordinator's own
addendum hint, checked and ruled out); an invalid/unreadable arg number for the three new OFF
buttons (ruled out by sortie 1's own evidence -- the write *did* eventually land with the exact
expected `device=10 cmd=3007/3003/3011`, proving the read mechanism can and does resolve correctly
for these args once it succeeds).

### Evidence

- `body-layer/src/belief/effector_engine.py` lines ~505-552 (`_execute_switch_row`'s self-check/
  `absolute_write` gate) and ~598-634 (`advance`'s read-retry/give-up loop) -- read in full.
- `body-layer/tests/test_effector_engine.py::test_e2_non_absolute_unknown_readback_skips_with_
  warning` -- existing, passing test proving the give-up-with-zero-writes behaviour for a
  non-absolute effector exactly like the SAU buttons.
- `body-layer/config/sequences/mi-24p/controls-to-petrovich.md`/`controls-to-player.md` -- the two
  sequences use the identical mechanism/shape; only the *moment* each fires differs (mode-1 entry,
  the newly-loaded moment, vs. hand-back, every other poll of which the system has long experience).
- `/Users/sg/Code/DCS-petrobrain-epochfix/docs/acceptance/logs-2026-11-28/lv2-aircraft_layer_debug.
  log` lines 2956-2965 (sortie 1's take/ack/write timeline) and `lv3-aircraft_layer_debug.log`
  (sortie 2, no `device=10` line at all after the take) -- both read in full for the take window.
- `plans/flight-lift-vector/debug-2026-11-23.md`, "Problem 4" -- the prior, analogous finding that
  the take/ack path is invisible in the one log that was kept, with the same recommendation (more
  observability) rather than a guessed fix.
- Knowledge graph (`gq.sh`) was queried first; it returned no hit on this specific M4 symptom
  (expected -- its own index predates M4, 2026-11-17). `memory-search.py` returned no prior record
  of this mechanism under any of the terms tried. `plans/flight-lift-vector/review-m4-sau.md`/
  `review-sau-handover.md` were read in full per the coordinator's addendum; both independently
  verified the effector/device/cmd/arg mapping and found the mechanism correct by static review --
  consistent with this being a live-timing defect neither static review could have caught.

### Fix Applied

Did not touch `belief.effector_engine.advance`'s shared, documented, tested give-up semantics --
every other sequence in this codebase depends on "a non-absolute effector's unresolved readback
skips, permanently, once the trigger's own run completes" being true, and changing that contract
is a design decision for the Architect, not a bug fix.

Instead, added a **bounded retry at the fire site**, specific to this one safety-stated handover
(`body-layer/src/body.py`):

- `ConsolePerceptionRunner.sau_takeover_retry_until_sim: float | None` -- the sim-time deadline up
  to which `CONTROLS_TO_PETROVICH` should be re-fired every poll it is not already running. Set to
  `now_sim + SAU_TAKEOVER_RETRY_WINDOW_S` the poll `controls_to_petrovich_edge` fires; added to the
  mission-restart reset's own enumerated field list (plain dataclass default, already reset to
  `None` on `__init__` re-invocation -- documentation-only addition, no behaviour change there).
- `SAU_TAKEOVER_RETRY_WINDOW_S` (new tunable, `body.SAU_TAKEOVER_RETRY_WINDOW_S`, default 10.0 s,
  `lo=5.0, hi=30.0`) -- deliberately twice `EFFECTOR_CONDITION_READBACK_WAIT_S`'s own 5 s give-up
  budget, so a single bad readback window does not cost the whole retry allowance.
- At the `controls_to_petrovich_edge` fire site: the existing `if` (fires once, on the edge) now
  also opens the retry window; a new `elif` re-fires the same trigger every poll the window is
  still open **and** `fd_mode` is still `"m1"` **and** the trigger is not currently running, and
  otherwise (window elapsed, or the handover already reversed) clears the field so a stale retry
  can never fire against the wrong mode.

Why this is safe and bounded, not a second "retry forever" mechanism:

- A re-fire that lands **after** the original run already wrote is a true no-op: `effector_engine`'s
  own `assumed_writes` (engine-wide, keyed by arg, visible to any later run reading at `sim >=` the
  write's own sim) makes the fresh run's self-check see the already-correct value and skip silently
  -- confirmed by `test_the_handover_retries_and_succeeds_after_an_initial_readback_timeout`'s own
  final assertion (exactly one write, never two).
- The window is bounded (10 s, not forever) and explicitly closes on a mode reversal, so a genuinely
  dead channel does not retry for the rest of the flight, and the retry can never press the SAU OFF
  buttons once the controls have already gone back to the player.

### Verification

- New tests in `body-layer/tests/test_body.py` (real poll loop, `FakeConsoleAircraftClient`, a
  synthetic non-absolute `sau_off_momentary` effector -- `observ`, the existing stand-in, is
  `default_2_position_tumb`/absolute and would write *through* a give-up, the wrong shape to
  reproduce the real SAU buttons' failure mode):
  - `test_the_handover_retries_and_succeeds_after_an_initial_readback_timeout` -- `read_args` fails
    past the 5 s give-up (confirmed zero writes), then recovers inside the 10 s retry window; the
    write lands, and stays the only write through the rest of the window.
  - `test_the_retry_never_fires_once_its_own_window_has_elapsed` -- reads recover only after the
    10 s window has closed; no write ever.
  - `test_the_retry_never_fires_once_the_handover_has_reversed` -- controls go back to the player
    while the retry window is still open and reads are still failing; no write ever, even once
    reads later recover.
  - All three, plus the three pre-existing `CONTROLS_TO_PETROVICH` tests, pass individually and
    together across three repeated runs (ruled out flakiness from the give-up/immediate-re-fire
    race at the exact poll the window opens).
- `ruff format --check`, `ruff check` (`src`, `tests`): clean.
- `cd body-layer && .venv/bin/mypy src`: clean, 96 files (per `body-layer/CLAUDE.md`, `mypy` is run
  on `src` only, from inside the subproject).
- `tools/generate_defaults.py --write`: regenerated `config/defaults.toml` for the new tunable;
  `test_tuning_comment_renders.py` (checks the `#:` comment's *first sentence* carries any
  cross-key coupling, since the generator only emits that sentence) caught the coupling to
  `EFFECTOR_CONDITION_READBACK_WAIT_S` sitting in the second sentence on the first pass -- fixed by
  moving it into the first, then re-verified both by that test and by reading the regenerated
  `defaults.toml` directly.
- Full `body-layer` suite, in-process (no live DCS needed, per this subproject's own testing
  posture): `pytest tests -q -n auto -p no:cacheprovider` -- 3906 passed, 4 xfailed, no regressions.
  The `aircraft-layer` subproject was not touched (the defect and fix are entirely body-layer-side),
  so its own checks were not re-run.

### What a re-fly should show

A mode-1 take should still press H/K/T OFF (B ON) essentially immediately, exactly as before this
fix, in the ordinary case. The fix only changes behaviour on a readback hiccup around the take: if
the first attempt's reads fail for up to 5 s, Petrovich now keeps trying for up to 10 s total
(instead of giving up silently and never pressing anything for the rest of the flight). If the
channel is genuinely unreachable for the whole 10 s window, the handover is still lost for that
take -- this fix narrows the failure window, it does not make it impossible, and per the open
hypothesis above, the *underlying* cause of a readback hiccup specifically around a mode-1 take is
still unconfirmed. **Recommended testing aid for the next sortie** (not built this pass, per the
project's "testing aids take the light path" convention and the same reasoning the 2026-11-23 pass
already gave for the analogous flight-ack gap): a `--effector-trace`-style log, or at minimum a
`logger.info` on every `read_args`/`write_cockpit_switch` call's own latency, would turn "the write
landed late" into an observable number instead of an inference from Export.lua's own log.
