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
