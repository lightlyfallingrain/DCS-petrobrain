### Implementation Summary

Implemented BL-15 Stages 1-2 only, per the dispatching brief: the aircraft-layer
mission-start signal (Hook -> loopback UDP -> collector -> `GET /mission_start/
latest`) and body-layer's detection + `reset_for_new_mission()` of belief and
mission memory. Stage 3 (theatre switching, gated on the investigator's
unresolved `DCS.getCurrentMission()` finding) and Stage 4 (live acceptance,
`WORKFLOW.md`) are untouched, as instructed.

### Files Changed

**aircraft-layer** (new Hook-to-collector channel, mirroring the F10/unit-velocity pattern):
- `aircraft-layer/src/schema/mission_start.py` — new `MissionStartEvent`/`MissionStartParseError`. `from_dict` rejects missing/non-int `sequence`, `bool` masquerading as `int`, and non-string `theatre`, mirroring `F10CommandEvent.from_dict`'s validation discipline per the security plan review's carried-forward requirement.
- `aircraft-layer/src/schema/__init__.py` — re-exports the new schema.
- `aircraft-layer/src/collector/cache.py` — new `MissionStartCache` (latest-of-one `push`/`latest`, not a drained queue like `F10CommandQueue` — a mission start is a single current fact, not a backlog).
- `aircraft-layer/src/collector/mission_start_receiver.py` — new `MissionStartReceiver`, loopback UDP, port 7799 (next free after `firing_receiver`'s 7798). Structurally mirrors `UnitVelocityReceiver`.
- `aircraft-layer/src/collector/__main__.py` — wires the new cache/receiver into the process, new `--mission-start-host`/`--mission-start-port` flags.
- `aircraft-layer/src/api/server.py` — `GET /mission_start/latest`, same shape/lifecycle as every other `/latest` endpoint (JSON `null` on an empty cache).
- `aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua` — new Hook script. One-shot per `onSimulationStart` (no per-frame poll, unlike the F10 commands Hook). Theatre resolution via the already-proven `net.dostring_in("scripting", "return env.mission.theatre")` bridge; failure degrades to `theatre: null`, never blocks the signal.
- `aircraft-layer/CLAUDE.md` — one paragraph in the channel inventory.
- `aircraft-layer/tests/test_mission_start_{schema,cache,receiver,api}.py` — new, mirroring the existing per-concern test-file layout.

**body-layer** (detection + reset, theatre/world-model untouched):
- `body-layer/src/aircraft_client.py` — `get_mission_start_latest()`, mirroring `get_line_of_sight_latest()`'s "not an error" empty-cache posture.
- `body-layer/src/belief/contacts.py` — `ContactStore.reset_for_new_mission()` (re-invokes `__init__()`).
- `body-layer/src/belief/tasks.py` — `TaskStore.reset_for_new_mission()` (same mechanism).
- `body-layer/src/mission_memory/store.py` — `MissionMemory.reset_for_new_mission()` (captures `_sink`, re-invokes `__init__()`, restores the sink — the one field that must survive).
- `body-layer/src/perception/source.py` — `reset_for_new_mission()` added to the `PerceptionSource` Protocol (required, not optional — every concrete source carries state that would otherwise leak across a restart).
- `body-layer/src/perception/naked_eye_source.py`, `hybrid_source.py` — implement it by clearing dedup/counter attributes directly (can't re-invoke `__init__` wholesale — too many required constructor args that must stay exactly as they are).
- `body-layer/src/logger.py` — `ConsolePerceptionRunner.last_mission_start_sequence: int | None` (new field) and `reset_for_new_mission()`; `_reset_mission_state(runner, crew_console, mission_memory)` orchestrator (store/tasks reset *before* runner/crew_console, per the shared-object-identity ordering hazard); `_check_for_new_mission(runner, crew_console, mission_memory, aircraft_client) -> bool` (polls, compares sequence, no-ops on the very first poll of a process); wired into both `_run_console_poll_loop` (with `crew_console=None`, since `--console` has no `CrewConsole`) and `_run_crew_text_poll_loop`, at the top of each poll before `run_once()`.
- `body-layer/src/belief/crew_console.py` — `CrewConsole.reset_for_new_mission()`, preserving `silenced` (plan's conservative default, pending the user's own call).
- `body-layer/tests/test_mission_start_reset.py` (new), `test_mission_memory_store.py`, `test_logger.py`, `test_naked_eye_source.py`, `test_hybrid_source.py`, `test_replay.py` — see below.

### Tests Added

- `test_mission_start_reset.py` (new, the plan's required per-class completeness test):
  - `test_contact_store_reset_clears_every_field` / `test_task_store_reset_clears_every_field` — enumerate fields via `vars()` (plain classes, no `@dataclass`), poison every one, reset, assert each equals a fresh instance's corresponding field. The one non-trivial comparison is `ContactStore._groups` (a `GroupStore`, which has no `__eq__` of its own — default identity equality would make two freshly-constructed instances compare unequal even when structurally identical) — handled by falling back to a one-level `vars()` comparison when a field's type has no custom `__eq__`.
  - `test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest` / `test_crew_console_reset_preserves_declared_fields_and_resets_rest` — enumerate via `dataclasses.fields()`, asserting every preserved field is passed through by *identity* (not just equality — `store`/`tasks` must be the same object) and every other field resets to its constructor default.
  - `test_crew_console_reset_preserves_silenced_true` — the stated conservative default.
  - `_check_for_new_mission`/`_reset_mission_state` unit tests: first-poll no-op even with a sequence present, sequence-change triggers a reset, no-op on an unchanged sequence, no-op on an empty cache, and the orchestrator itself clearing tasks + mission memory.
- `test_mission_memory_store.py` — `reset_for_new_mission` clears entries/`struck_by`/`latest_live_seq`, restarts `_next_seq`/`_next_mark_index` at 1 (the plan's own named risk, not hidden), preserves a configured sink, and leaves a never-configured sink (`None`) as `None`.
- `test_logger.py` — `test_crew_text_poll_loop_resets_belief_on_mission_restart`, the wiring-level proof: drives the real `_run_crew_text_poll_loop` on a background thread (via a `FakeConsoleAircraftClient` extended with a mutable `mission_start_sequence` attribute) and confirms `runner.tasks`/`crew_console.commands_handled` actually clear. Also added `get_mission_start_latest` to `FakeConsoleAircraftClient` (required for every existing poll-loop test to keep passing, since `_check_for_new_mission` is now called every poll) and a `reset_count` to `FakeSource`.
- `test_naked_eye_source.py`, `test_hybrid_source.py` — one reset test each, poking private dedup/counter attributes directly (not via a full `poll()`, which is already covered by every other test in those files).
- `test_replay.py` — added trivial `reset_for_new_mission()` to `FakePerceptionSource`/`EmptySource` (now required by the widened `PerceptionSource` Protocol; `replay()`'s structural type check would otherwise fail).

### Checks

**aircraft-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy --strict` (`cd aircraft-layer && .venv/bin/mypy src`): pass (25 source files)
- `pytest`: pass (374 passed)
- `luac5.1 -p` on the new Hook script: pass

**body-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass (68 source files)
- `pytest`: pass (2179 passed, 4 xfailed — xfails pre-existing, unrelated to this change)

**world-model/**: not touched by this change, no checks run.

### Notable Discoveries

- **The "re-invoke `__init__`" reset pattern silently fails to reset an
  `init=False` dataclass field declared with a plain `default` (as opposed to a
  `default_factory`).** Confirmed by direct repro (`field.py` experiment in the
  session, not just read from docs): Python's generated `__init__` only emits a
  `self.attr = ...` assignment for an `init=False` field when that field has a
  `default_factory`; a plain `default` on an `init=False` field lives as a
  class-level attribute and is never reassigned per instance once an instance
  attribute has shadowed it. `ConsolePerceptionRunner._last_look_direction`
  (`field(default=None, init=False, repr=False)`) is exactly this shape — the
  per-class completeness test caught it immediately (fails with the sentinel
  still present after `reset_for_new_mission()`), and the fix is one explicit
  `self._last_look_direction = None` line after the `__init__` re-invocation,
  documented in that method's own docstring with the repro. No other field on
  `ConsolePerceptionRunner` or `CrewConsole` has this shape (checked every
  `field(...)` declaration on both classes) — `live_los_coverage` on
  `NakedEyePerceptionSource` is the only other `init=False` field in scope and
  it uses `default_factory`, which is unaffected. **Worth flagging generally**:
  any future class adopting this project's "re-invoke `__init__`" reset
  pattern should check for this exact field shape before trusting the pattern
  to cover it.
- **mypy `--strict` accepted `self.__init__(...)` calls with `# type: ignore[misc]`
  on all five reset methods without an "unused ignore" warning** — strict mode
  includes `warn_unused_ignores`, so this confirms the ignore is load-bearing
  (mypy does flag calling `__init__` directly as an error) rather than
  decorative.
- **Test-impact check (per role instructions) found one real gap and one near-miss
  before implementation, not after:** the plan's own Stage 1 implementation text
  named `aircraft-layer/CLAUDE.md`/`test_logger.py`/`test_mission_memory_store.py`
  as touched files, but did not anticipate that widening the `PerceptionSource`
  Protocol would require updating three existing test doubles
  (`FakePerceptionSource`/`EmptySource` in `test_replay.py`, `FakeSource` in
  `test_logger.py`) or that `FakeConsoleAircraftClient` (used by every existing
  poll-loop test) would need a new method the instant `_check_for_new_mission`
  was wired into the poll loop — both were caught by running the full suite
  immediately after wiring, not by re-deriving the impact list by inspection
  first. Recorded here per the "missing entry is the dangerous one" guidance,
  since this is exactly that shape of gap.
- **`_check_for_new_mission` degrades silently on a transport failure**
  (`AircraftLayerError` -> log-and-continue, same posture as
  `post_look_direction`'s own try/except) — a collector that's down or
  unreachable for a poll or two never crashes the loop and never fires a
  spurious reset, it just tries again next poll.

### Deviations from the plan

None in substance. One naming choice the plan left open: the new UDP port is
**7799**, not "the next free one after 7797" as the plan's prose said — by the
time this stage was implemented, `firing_receiver.py` already occupied 7798
(a prior, unrelated feature), so 7799 is the actual next free port. Confirmed
by grepping every `DEFAULT_PORT` declaration in `aircraft-layer/src/collector/`
before picking the number, not by trusting the plan's text.

---

## Second batch: Stage 3 (theatre switching, revised), Decision 5 (per-mission
## log files), Reviewer optional refinement 1

Implemented on top of the reviewed Stage 1-2 batch (`97b76dec`). Scope:
Stage 3 theatre switching with the user's revised loud-refusal default
(`stage1-decisions.md` decision 1 REVISED), decision 5's per-mission log
rollover, and the Reviewer's optional refinement 1 (naked-eye/hybrid reset
field-coverage tests).

### Files Changed

**body-layer** (three commits on `worktree-agent-a44d45aa18125002c`):

- `src/perception/naked_eye_source.py` — `reset_for_new_mission` now also
  resets `live_los_coverage` to a fresh `LiveLosCoverage()` (decision 5:
  per-run logs now roll per mission, so a coverage counter spanning
  several missions no longer corresponds to any single log file —
  reverses the prior "process-lifetime regression guard" reading the
  Reviewer's pass confirmed).
- `src/belief/crew_console.py` — `refused: bool` field,
  `WORLD_MODEL_NOT_LOADED_REFUSAL` constant, `_refusal_response(now_sim)`
  checked at the top of `handle_command`/`handle_line`/`handle_transcript`
  (the three production entry points; there is no single dispatcher all
  three already funnel through, so the same check is repeated at each
  rather than invented as one call site that doesn't exist).
  `reset_for_new_mission`'s docstring updated to note `refused` resets
  with the rest of per-mission state (not preserved) — `logger.
  _maybe_switch_theatre` re-evaluates it immediately afterward.
- `src/logger.py` — `_enter_refusal_mode` (drops the old store, stops
  perception, sets `crew_console.refused`), `_maybe_switch_theatre`
  (resolves/opens/validates the new theatre's store, with the
  `THEATRE_PROJECTIONS` membership check strictly before path
  construction — carried over from `main()`'s own startup guard, per the
  security plan review's Mode-2 requirement), `_check_for_new_mission`
  widened with `world_model_dir`/`trace_sink`/`forest_occlusion`
  parameters (all defaulting to the Stage-1/2 no-op values, so every
  existing call site is unaffected unless it opts in). `_mark_here_fn`/
  `_mark_target_fn` changed to read `runner.theatre` live rather than a
  `theatre: str` parameter bound once at construction — found while
  wiring Stage 3: a runtime switch would otherwise mark future positions
  under the *previous* theatre's coordinate projection forever, the same
  stale-closure trap `_speech_log_sink` already had to avoid for
  `belief_truth_writer`. `_reroll_run_logs` (decision 5): re-stamps each
  of the five per-run logs to a fresh filename on a detected mission
  (re)start, reusing `run_log_paths.per_run_log_path` rather than a
  second stamping scheme; closes the two logs holding an open file handle
  (`DetectionTraceWriter`/`BeliefTruthLogWriter`) before replacing them,
  and rebuilds `crew_console.speech_log_sink`'s closure (the one writer
  captured by value, via `_speech_log_sink`) — the other three
  (`group_trace_sink`/`transcript_log`/`MissionMemory`'s sink) are plain
  fields read fresh each call, so reassigning them is the whole fix for
  those three. Both poll loops wired: `world_model_dir` and the five
  pre-stamp base paths threaded through as new trailing parameters (all
  default `None`, no-op when absent), and `_mission_memory_step`'s own
  `theatre` argument switched from the poll loop's closed-over initial
  value to `runner.theatre` (the live value `_maybe_switch_theatre`
  updates). `main()`: `--world-model-dir`'s help text extended to cover
  its new optional role alongside an explicit `--theatre`/
  `--world-model-db` pair (not only with `--mission-understanding`); each
  per-run log's pre-stamp (`~`-expanded) base path is now captured before
  the stamping calls overwrite `args.*`, threaded to both poll-loop thread
  constructions as new trailing positional args.
- `body-layer/CLAUDE.md` — one new block after the `--detection-trace`
  paragraph documenting mission-start detection, theatre switching
  (including the `--world-model-dir`-alongside-explicit-pair addition),
  loud-refusal mode, and per-mission log rollover.
- Tests: `tests/test_naked_eye_source.py`/`tests/test_hybrid_source.py`
  (field-coverage completeness tests, Reviewer optional refinement 1 —
  `NakedEyePerceptionSource` needs three buckets, `HybridPerceptionSource`
  two, since it has no per-poll-overwritten field at all);
  `tests/test_crew_console.py` (six refusal-mode tests: all three entry
  points return the fixed line, a refused command does not dispatch —
  checked via `TaskStore` staying empty rather than just the returned
  text, does not end silence or increment `commands_handled`, and an
  un-refused console dispatches normally); `tests/test_mission_start_
  reset.py` (unit tests for `_maybe_switch_theatre`/`_enter_refusal_mode`
  covering the no-op/refusal/success paths, plus two `_check_for_new_
  mission` end-to-end tests combining reset + switch);
  `tests/test_logger.py` (`FakeConsoleAircraftClient` gained a
  `mission_start_theatre` attribute; two wiring-level tests drive the real
  `_run_crew_text_poll_loop` thread against two small on-disk fixture
  stores to prove the plumbing, not just the unit-level function);
  `tests/test_mark_fn_theatre.py` (new — confirms `_mark_here_fn`/
  `_mark_target_fn` read `runner.theatre` live across a simulated switch,
  by checking the recorded mark's `lat`/`lon` actually changes);
  `tests/test_run_log_reroll.py` (new — seven tests for `_reroll_run_logs`
  covering each of the five logs' reroll, the stale-closure fix, the
  all-`None` no-op, and the `--console`/no-`CrewConsole` guard).

### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass (68 source
  files)
- `pytest tests -q`: pass (2209 passed, 4 xfailed — same 4 pre-existing,
  unrelated xfails as the first batch)

**aircraft-layer/**: not touched by this batch, no checks run.

### Notable Discoveries

- **Two stale-closure traps, both found by tracing every place `theatre`/
  a writer is captured, not by inspection alone.** `_mark_here_fn`/
  `_mark_target_fn` took `theatre: str` as a plain parameter bound once at
  `main()`'s call site — a runtime theatre switch updates
  `runner.theatre`, but a closure that already closed over the old
  parameter value never sees it. `crew_console.speech_log_sink` (built via
  `_speech_log_sink(belief_truth_writer, runner)`) has the identical
  shape for the *writer*, not the theatre. Both were fixed the same way
  `_speech_log_sink` already handles `runner.scan_plan`/`optic`: read the
  live field at call time rather than capturing a value. Neither was named
  in the dispatching brief — found while enumerating every reader of
  `theatre`/`belief_truth_writer` in `logger.py` before writing the reroll
  function, per this role's own "scope your verification to the
  containing unit" guidance.
- **`runner.enrichment` is a third thing that goes stale on a theatre
  switch, not mentioned in the plan.** It is built lazily over whichever
  `world_model_conn`/`theatre` were current the first time `run_once`
  needed it, then mutated in place every poll after — a switch that
  replaces `world_model_conn` without also clearing `enrichment` would
  leave it silently querying a connection `_maybe_switch_theatre` is about
  to close. Cleared explicitly in both `_maybe_switch_theatre` (success
  path, so the next poll rebuilds it fresh) and `_enter_refusal_mode`
  (failure path, so a later recovery does not inherit a reference to an
  already-closed connection either).
- **`--console`'s own REPL-thread `EnrichmentContext` (`_run_console_repl`'s
  `repl_conn`) does *not* follow a theatre switch** — it is built lazily
  from the `world_model_db`/`theatre` values `main()` passed to that
  function once, which are never updated. Left alone deliberately:
  `--console` is a debug harness with no `CrewConsole`/refusal surface at
  all (per `_enter_refusal_mode`'s own docstring), and widening this would
  mean re-deriving the REPL thread's own connection-rebuild logic, which
  is out of this batch's scope. Flagging so a future reader does not
  assume `--console`'s enrichment tracks a live switch the way
  `--crew-text`'s does.
- **The `_mission_memory_step` call sites in both poll loops read a
  closed-over `theatre: str` function parameter, not `runner.theatre`** —
  found the same way as the two closures above. Fixed by reading
  `runner.theatre` (with an `assert ... is not None`, since by the point
  this runs in the loop it always has been set) instead of the stale
  local. Without this fix, mission-memory entries written after a
  successful theatre switch would still be tagged with the *old*
  theatre's name for whatever `admission.step` does with it.
- **Test-impact check (per role instructions) found no gaps this round** —
  grepped the test suite for every existing test touching `_check_for_
  new_mission`, `ConsolePerceptionRunner`, and `CrewConsole` before
  starting, and the plan's own Stage 3 test guidance ("fake two-theatre
  fixture stores ... mirroring `latakia-20km`/`gemerek-20km`") matched
  what `test_main_rejects_world_model_db_theatre_mismatch` already does in
  `test_logger.py` — reused that exact pattern (`store.writer.
  open_for_build`/`insert_region`) rather than inventing a second one.

## Batch 3 — Reviewer required fix + one related small item

Addresses `plans/bl15-mission-start/review.md`'s Batch 2 required fix and its
`fired_on_tracker` optional refinement.

### Required fix: `drain_events`/`drain_brain` guard against `self.refused`

Added an explicit `if self.refused: return []` to both methods in
`body-layer/src/belief/crew_console.py`, so "no proactive speech while
refused" is a property of `CrewConsole` itself rather than a consequence of
`_enter_refusal_mode` currently only ever being reached right after a full
reset.

**Drain and discard, not leave queued — chosen for both, but implemented
differently per method because their internal state is shaped differently:**

- `drain_events`: `self.scheduler.tick(...)` still runs unconditionally (it
  has no network/print side effects — confirmed by reading: it only reads
  `ContactStore`/`enrichment` and mutates its own `_consumed` set/
  `busy_until_sim`), and *that* is what marks any real event consumed out of
  the store. The guard sits after the `tick()` call and before `_print`, so
  only the "speak it" step is suppressed — the result is discarded, not
  returned.
- `drain_brain`: here `self.brain_client.poll_replies()` is still drained
  (so a reply is not left in the brain client's own queue to resurface
  later against a world model it was never computed for), but each reply is
  **not** run through `_handle_brain_reply` — that method calls `self.
  _print` unconditionally and, via `_handle_brain_pick`/`_handle_brain_
  confirm`, can call `self._act` (which can mutate `_pending_confirmation`/
  tasks/attention). Discarding its return value would not undo either side
  effect, so the guard instead pops the matching `_pending_escalations`/
  `_stand_by_spoken_for` entries directly and discards the reply, never
  calling `_handle_brain_reply` at all. `_speak_stand_by_if_due` is skipped
  entirely too (nothing is "overdue" worth announcing while refused).

**Mutation-tested both guards by removal, per role instructions** — four new
tests in `test_crew_console.py`, each constructing a `CrewConsole` directly
with `refused=True` against a non-empty store/pending-escalation state
(bypassing the reset-always-precedes-refusal call graph the review's own
finding named as the thing making this incidental rather than structural):
`test_refused_drain_events_speaks_nothing_against_a_non_empty_store`,
`test_refused_drain_events_consumes_rather_than_leaves_the_event_queued`,
`test_refused_drain_brain_speaks_nothing_against_a_pending_escalation`,
`test_refused_drain_brain_consumes_rather_than_leaves_the_reply_queued`.
Removing the `drain_events` guard fails both of its tests (`['BMP-2.'] ==
[]`); removing the `drain_brain` guard fails both of its tests
(`['Unable, no such command.'] == []`). Restored after each check (full
suite green, 2216 passed + 4 xfailed before and after).

### Small related item: `fired_on_tracker` is per-mission state, not reset

The reviewer's optional refinement was right that this is a real gap, not
just a documentation note. `FiredOnTracker._scanned_event_count` indexes
into `ContactStore.events` by position; `ContactStore.reset_for_new_mission`
resets that list to empty, but nothing told the tracker. After a restart,
`events[_scanned_event_count:]` on the now-short new list silently returns
nothing until the new mission's own event count organically grows past the
old tracker's count — `fired_on` mission-memory entries stop being written
for an arbitrary stretch after every restart. `_last_write_sim` (keyed by
shooter contact id, also mission-scoped since `ContactStore` mints fresh ids
per mission) is equally stale, though a collision there is less likely.

Brought under the existing pattern:
- `FiredOnTracker.reset_for_new_mission()` (`body-layer/src/mission_memory/
  admission.py`) — re-invokes `__init__()`, the same idiom `ContactStore`/
  `TaskStore` already use.
- `_reset_mission_state`/`_check_for_new_mission` (`body-layer/src/
  logger.py`) both gained an optional `fired_on_tracker: FiredOnTracker |
  None = None` parameter (default `None` so the pre-existing three/
  four-argument call sites — including the direct unit-test calls in
  `test_mission_start_reset.py` — are unaffected), threaded through to the
  new reset call. Both poll loops' `_check_for_new_mission` calls now pass
  `fired_on_tracker=fired_on_tracker` (the instance each loop already owns
  for its own `_mission_memory_step` calls).

**Tests added** (`test_mission_start_reset.py`):
`test_fired_on_tracker_reset_clears_every_field` (the same `vars()`-
enumerated completeness-test pattern `ContactStore`/`TaskStore` already
use), `test_reset_mission_state_resets_fired_on_tracker_when_given`,
`test_reset_mission_state_is_a_noop_for_fired_on_tracker_when_omitted`.
Mutation-tested the wiring: removing the `if fired_on_tracker is not None:
fired_on_tracker.reset_for_new_mission()` line from `_reset_mission_state`
fails `test_reset_mission_state_resets_fired_on_tracker_when_given`
(`assert 500 == 0`); restored, full suite green again.

### Checks (body-layer, after Batch 3)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (68 source files)
- `pytest tests -q`: pass — 2216 passed, 4 xfailed (up from the Batch 2
  baseline by the 7 new tests above)
