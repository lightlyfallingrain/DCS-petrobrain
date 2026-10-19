### Goal

Detect a genuine DCS mission (re)start via the Hook's `onSimulationStart` callback and, on that
signal, give body-layer a clean slate: reset every piece of belief/attention/mission-memory state
that `BL-B68` found surviving a restart today, and point world-model queries at the theatre the
*running* mission actually is, instead of whatever the operator passed on the command line.
Stage 2 (mission file → Mission Interpreter → "briefing ready") is out of scope and is being
explored separately; this plan does not plan it, but is written so the mission-start signal can
grow a `mission_filename` field later without reshaping its transport.

### Investigator dependency — in flight

This plan depends on one unverified DCS-internals claim: whether the live mission's `theatre`
string is reachable from Hook state at or after `onSimulationStart` (directly via
`DCS.getCurrentMission()`, or via the already-proven `net.dostring_in("scripting", "return
env.mission.theatre")` bridge the F10 commands Hook already uses). An investigator pass is
running now (`aircraft-layer/research/` will carry a dated note) to resolve it before Stage 3
below is implemented. **The design in this plan does not change shape depending on the answer** —
Stage 1/2 (the signal transport, the belief/mission-memory reset) are unconditional; Stage 3
(theatre switching) degrades to "stay on the configured theatre and log once" if the answer comes
back negative, which is already this plan's designed fallback for an unresolved theatre, not a
special case bolted on afterward. Do not start Stage 3 until that note lands; Stages 1-2 can start
immediately.

### Affected Modules / Files

**aircraft-layer** (new mission-start signal, mirroring the F10 commands channel's shape exactly —
`plans/f10-crew-commands/plan.md`'s Hook→collector→poll pattern, reused rather than reinvented):

- `aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua` (new) — registers
  `onSimulationStart`, increments a local sequence counter, attempts to read `theatre` (mechanism
  per the investigator's finding), and sends `{"sequence": N, "theatre": "<string>|null"}` over
  loopback UDP to a new fixed port (next free one after 7797, per the existing port-allocation
  comment convention in each Hook script). No `onSimulationFrame` polling needed — this is a
  one-shot push per mission start, not a drained queue like F10 commands. Same deploy discipline
  (`Saved Games\DCS\Scripts\Hooks\`) and the same "only hard-coded strings ever cross
  `net.dostring_in`" posture as `petrobrain-f10-commands-hook.lua`.
- `aircraft-layer/src/schema/mission_start.py` (new) — `MissionStartEvent(sequence: int, theatre:
  str | None, received_wall_clock_s: float)`. Wall-clock-only provenance, same stated exception as
  `f10_command.py`'s (no cheap DCS sim-clock access from Hook state).
- `aircraft-layer/src/collector/cache.py` — add `MissionStartCache`, a **latest-value** cache
  (`push`/`latest`, mirroring `TelemetryCache`/`PetrovichWheelCache` exactly), not a queue — unlike
  F10 command selections, a mission start is a single current fact body-layer polls for change, it
  is never "drained." `collector/__main__.py` wires a new loopback UDP listener for it, mirroring
  `f10_command_receiver.py`'s receiver shape (a listener, not a sender — this is the second inbound
  channel after F10 commands).
- `aircraft-layer/src/api/` — `GET /mission_start/latest`, returning the cached event or `null`,
  same shape as `GET /telemetry/latest`.
- `aircraft-layer/CLAUDE.md` — one line in the channel inventory, matching the existing F10/overlay
  entries' style.

**body-layer** (detect the signal, orchestrate the reset):

- `body-layer/src/aircraft_client.py` — `AircraftLayerClient.get_mission_start_latest()`, a read
  mirroring `get_telemetry_latest()`.
- `body-layer/src/belief/contacts.py` — `ContactStore.reset_for_new_mission()`.
- `body-layer/src/belief/tasks.py` — `TaskStore.reset_for_new_mission()`.
- `body-layer/src/mission_memory/store.py` — `MissionMemory.reset_for_new_mission()`.
- `body-layer/src/perception/source.py` — add `reset_for_new_mission(self) -> None` to the
  `PerceptionSource` protocol.
- `body-layer/src/perception/naked_eye_source.py`, `body-layer/src/perception/hybrid_source.py` —
  implement it, clearing each source's own dedup/counter state (`_object_id_to_last_observation_id`,
  `_last_emitted_texts`, `_observation_count`, `_dropped_count`).
- `body-layer/src/logger.py` — `ConsolePerceptionRunner.reset_for_new_mission()`,
  `CrewConsole.reset_for_new_mission()` (new methods, mechanism below), a top-level
  `_check_for_new_mission(runner, crew_console, mission_memory, aircraft_client) -> bool`
  called once per poll from both `_run_console_poll_loop` and `_run_crew_text_poll_loop`, and (Stage
  3) the theatre re-resolution logic inside that same check.
- `body-layer/tests/test_logger.py`, `test_mission_memory_store.py`, a new
  `test_mission_start_reset.py` — see Stage 2/4.

### The reset mechanism — one pattern, reused for every class involved

**Chosen over a nested `MissionState` dataclass that groups every per-mission field under one
sub-object** (the alternative the dispatching brief asked me to weigh). A sub-object would be the
textbook "cannot silently escape the reset" structure, but `ConsolePerceptionRunner.run_once` and
the rest of `logger.py` read `self.scan_plan`, `self.optic_state`, `self.attack_run_state`,
`self.attitude_history`, `self.enrichment`, `self.mission_phase_tracker` directly in dozens of
places across a ~3000-line file; moving them under `self.mission.scan_plan` etc. is a mechanical
but wide-reaching rename with no behaviour change to show for it. The pattern below gets the same
safety property — a newly added field resets by default unless someone deliberately opts it out —
without that rename:

**Every class that holds per-mission state gets a `reset_for_new_mission()` method whose body
re-invokes that class's own `__init__` on `self`, passing through only the handful of fields that
must survive the reset** (open network/file handles, injected closures, references other objects
still hold). Because it is the *real* constructor running again on the same object identity:

- Any field added to that `__init__` later, and not named in the preserved set, resets to the
  constructor's own default automatically — the single source of truth for "what a fresh instance
  looks like" is the constructor itself, never a second hand-maintained list that can drift from it.
- Object identity is unchanged, so anything else holding a reference to this exact object (see the
  aliasing note below) sees the reset without needing to be told about it.

Concretely:

- **`ContactStore.reset_for_new_mission()`** → `self.__init__()`. No arguments: every field
  `ContactStore.__init__` sets (`_contacts`, `_observations`, `_events`, `_areas`,
  `_acknowledged_event_ids`, `_observation_id_to_contact_id`, the three `_next_*_number` counters,
  `_groups = GroupStore()`, `_observability_tracked`) is mission-scoped, nothing to preserve.
- **`TaskStore.reset_for_new_mission()`** → `self.__init__()`, same reasoning.
- **`MissionMemory.reset_for_new_mission()`** → capture `sink = self._sink` first, `self.__init__()`,
  then `self.set_sink(sink)` — the one field that must survive (the open `MissionMemoryLogWriter`,
  see the logging note below).
- **`ConsolePerceptionRunner.reset_for_new_mission()`** → `self.__init__(aircraft_client=self.
  aircraft_client, sources=self.sources, store=self.store, tasks=self.tasks, output=self.output,
  overlay_client=self.overlay_client, group_trace_sink=self.group_trace_sink, world_model_conn=self.
  world_model_conn, theatre=self.theatre)`. Everything else (`last_t_sim`, `last_ownship_state`,
  `enrichment`, `mission_phase_tracker`, `scan_plan`, `optic_state`, `attack_run_state`,
  `attitude_history`, `optic`, `_last_look_direction`) resets to its declared default. `store`/
  `tasks`/`sources` are passed through **unchanged as objects** — their own internal reset (below)
  must already have run before this call, or this call would hand back an un-reset store under a
  fresh-looking runner.
- **`CrewConsole.reset_for_new_mission()`** → same pattern, preserving `store`, `tasks`,
  `brain_client`, `output`, `aircraft_client`, `mark_here_fn`, `mark_target_fn`, `transcript_log`,
  `overlay_client`, `speech_client`, `speech_log_sink`. Everything else (`scheduler`,
  `_pending_confirmation`, `_confirmation_expired_sim`, `_pending_escalations`,
  `_stand_by_spoken_for`, `commands_handled`, `last_command_target_contact_id`,
  `attack_run_transition`, `observ_transition`, `_on_ground_default_applied`, `enrichment`) resets.
  **`silenced` is an open question below** — whether a pilot's deliberate mute should survive a
  mission restart is a product call, not an implementation detail; until decided, preserve it
  (the conservative default: don't change behaviour the pilot explicitly asked for).
- **Perception sources**: `reset_for_new_mission()` on `NakedEyePerceptionSource`/
  `HybridPerceptionSource` cannot re-invoke `__init__` wholesale (too many required constructor
  args — `world_model_conn`, `theatre`, `aircraft_client`, etc. — that must stay exactly as they
  are, same reasoning as `ConsolePerceptionRunner.sources` above). These clear only their own
  dedup/counter attributes directly (`self._object_id_to_last_observation_id.clear()`, etc.) —
  the same outcome, written out by hand because there is no cheap "fresh instance" to diff against.

**Shared-reference ordering is the one real hazard here, and it is why the orchestrator calls
things in a specific order, not why the pattern is wrong.** `runner.store` and `crew_console.store`
are **the same `ContactStore` object** (and `tasks` likewise) — deliberately, per `logger.py`'s own
`tasks` field docstring. Resetting that object happens exactly once (`store.reset_for_new_mission()`,
`tasks.reset_for_new_mission()`), *before* `runner.reset_for_new_mission()`/`crew_console.
reset_for_new_mission()` are called — those two calls pass the (now-cleared) same objects straight
through, they do not clear them a second time. The orchestrator function makes this order explicit
rather than leaving it to be inferred:

```python
def _reset_mission_state(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole,
    mission_memory: MissionMemory,
) -> None:
    runner.store.reset_for_new_mission()      # shared with crew_console.store
    runner.tasks.reset_for_new_mission()       # shared with crew_console.tasks
    for source in runner.sources:
        source.reset_for_new_mission()
    runner.reset_for_new_mission()
    crew_console.reset_for_new_mission()
    mission_memory.reset_for_new_mission()
```

### Implementation Plan

1. **Aircraft-layer: the mission-start signal, Hook → collector → poll endpoint.** New Hook script,
   schema, cache, UDP listener, `GET /mission_start/latest`. One-shot per `onSimulationStart` (no
   per-frame poll loop needed on the Lua side, unlike F10 commands — this reuses the inbound-UDP
   half of that channel's design, not its drain-queue half). The `theatre` field's acquisition
   mechanism is whatever the investigator's note settles; if still unresolved when this stage
   starts, ship with `theatre: null` always and revisit once the note lands — the rest of the
   channel does not depend on it. Tests: `test_api.py`-style real-server test for the new endpoint,
   `test_cache.py`-style test for `MissionStartCache`, `luac5.1 -p` on the new Hook script.

2. **Body-layer: detect the signal and reset belief + mission memory, theatre untouched.** Add
   `reset_for_new_mission()` to every class in the table above; add `_reset_mission_state`; add
   `_check_for_new_mission` (polls `get_mission_start_latest()`, compares `sequence` against a new
   `last_mission_start_sequence: int | None` field on `ConsolePerceptionRunner`, calls
   `_reset_mission_state` and updates the field on a change, does **nothing** on the very first poll
   of the process even if a sequence is already present — the process just started with clean state,
   there is nothing to reset yet, and firing a reset anyway would be harmless but pointless noise).
   Wire `_check_for_new_mission` into both `_run_console_poll_loop` and `_run_crew_text_poll_loop`,
   at the top of each poll, before `runner.run_once()`. Theatre/world-model are **not** touched this
   stage — `runner.theatre`/`runner.world_model_conn` are in the "preserve" list above, so a reset
   here is a true no-op for them, matching `BL-15.md`'s own staging (theatre is a separate line
   item). Tests: a completeness test per class — `dataclasses.fields`-driven, asserting that after
   populating every field with a non-default sentinel and calling `reset_for_new_mission()`, every
   field not in that class's documented preserve-set equals its constructor default. This is the
   test that would have caught `BL-B68`'s own gap (clearing `store` but not `attack_run_state`) —
   it fails the moment a new field is added to one of these dataclasses and nobody touches the
   preserve-set, rather than needing a human to notice during review.

3. **Body-layer: theatre switching — gated on the investigator's finding, additive to Stage 2's
   detection.** When `_check_for_new_mission` fires and the event's `theatre` is non-null and
   differs from `runner.theatre`: resolve the candidate store path the same way `--mission-
   understanding` resolution already does (`world_model_dir / f"{theatre.lower()}-full.sqlite"`),
   run the exact two guards `main()` already runs at startup — `theatre in THEATRE_PROJECTIONS`
   (the path-injection guard noted at `logger.py` ~L3005, since this string now comes from a DCS
   mission file exactly as the `--mission-understanding` path's string already does) and the
   built-region mismatch guard (`load_only_region(...).theatre == theatre`) — before opening
   anything. On success: `open_world_model` the new path **on the poll thread** (the same
   thread-affinity constraint that already shaped `_run_console_poll_loop`'s "Stage 6 fix" --
   `sqlite3.Connection` is thread-affine), close the old connection, rebuild `runner.sources` via the
   existing `_build_sources`, and set `runner.world_model_conn`/`runner.theatre`. On failure (store
   doesn't exist, fails to open, or fails the mismatch guard) — **do not crash the poll loop and do
   not silently keep running against the wrong theatre's geometry either**: log loudly once, keep
   the old `world_model_conn`/`theatre`/`sources` exactly as they were, and surface this the same way
   any other degraded-but-continuing condition does (`tuning.py`'s own "a bad value warns and
   continues" posture is the precedent). **Requires `--world-model-dir` even when `--theatre`/
   `--world-model-db` were given explicitly at startup** — today those two modes are mutually
   exclusive at the CLI (`parser.error` if neither full pair nor `--mission-understanding`+
   `--world-model-dir` is given); this stage needs `--world-model-dir` available regardless of which
   mode supplied the *initial* theatre, so the explicit-pair mode gains an optional `--world-model-
   dir` that, if present, enables runtime re-resolution and is otherwise unused. Tests: fake
   two-theatre fixture stores (mirroring the existing `latakia-20km`/`gemerek-20km` small test
   regions), asserting the swap happens on a theatre change, is a no-op on same-theatre restart, and
   degrades (not crashes) on a missing/mismatched store.

4. **Wire the F10/overlay/crew-text acceptance path and update `WORKFLOW.md`.** Add the new Hook
   script's deploy step to `aircraft-layer/WORKFLOW.md` (mirroring the F10 commands section), and
   confirm the end-to-end chain live: fly a mission, restart it (DCS's own "restart mission"
   action), confirm contacts/mission-memory are empty afterward and theatre-switch logging (if
   exercised, i.e. the user flies two different theatres back to back) shows the expected swap or
   degrade line. This is the Stage that needs the user's own DCS box — same posture as every other
   live-DCS-dependent stage in this subproject.

### Co-moving state, in the shape this plan's risk actually takes

This is not a phase/mode machine with pilot-written and internally-decided fields (step 6a's
literal trigger does not fire — there is no "current phase" tracked by two writers), but the same
failure mode applies to the reset itself: a piece of state the reset forgets. The tables above
(the "chosen mechanism" section, and the explicit preserve-lists) are this plan's answer to that —
built by grepping every field declaration on each affected class (`ConsolePerceptionRunner`,
`CrewConsole`, `ContactStore`, `TaskStore`, `MissionMemory`), not by re-deriving the list from
`BL-B68`'s own enumeration, which was itself written from a single incident and is not guaranteed
complete (its own text says "not audited this session" for `CrewConsole`'s state, which is now
covered above with the same mechanism).

### Risks & Unknowns

- **The investigator's theatre-access finding** (see above) — if the answer is "not reachable at
  all without a live Windows probe," Stage 3 ships with theatre switching inert (always logs
  "theatre unknown, staying on configured theatre") until a probe resolves it. Not a blocker for
  Stages 1-2.
- **Per-run log files (`--detection-trace`, `--belief-truth-log`, `--mission-memory`,
  `--speech-log`) still write continuously across a mid-process mission reset.** This is a real,
  named risk, not an oversight: `run_log_paths.py`'s roll-per-run stamping happens once, at `logger.
  main`'s CLI boundary (its own docstring says so explicitly), and re-rolling each of four
  independently-wired writers to a fresh per-mission path mid-process is a larger, separate change
  than this plan's scope (reset state, not restructure log lifecycle) — `BL-15.md`'s own request
  text does not ask for it. **Recommendation, not a decision**: Stage 2 should have `_reset_mission_
  state` write one clearly-tagged marker line/event into whichever of these logs are open at reset
  time (cheap, a few lines), so a future debugging session sees the boundary explicitly instead of
  re-deriving it from a `t_sim` discontinuity the way `plans/position-belief-runaway/
  debug-2026-10-15.md` had to. Full re-rolling is a candidate follow-up item, not Stage 1.
- **`MissionMemory.reset_for_new_mission()` starts `_next_seq`/`_next_mark_index` back at 1 inside
  whatever log file is still open** (per the point above) — a debrief tool reading that file across
  a restart would see two entries with `seq=1`. Same risk, same recommendation (a marker line makes
  it detectable; full isolation needs the log-rolling follow-up).
- **Mid-flight false positive remains structurally possible, though the strongest candidate cause
  is now ruled out.** The vendored `Sim_ControlAPI.md` documents `onSimulationPause`/
  `onSimulationResume` as callbacks distinct from `onSimulationStart`/`onSimulationStop` (lines
  ~594-597), and the F10 research note's live probe (Finding 11) observed `onSimulationStart` fire
  exactly once per actual mission (re)start across two missions, never spuriously. Single-player
  only (root `CLAUDE.md` scope), so multiplayer reconnect is out of scope by construction. Residual,
  unverified: DCS's own single-player "restart mission" action is exactly the trigger this plan
  wants to catch (confirmed desired), but no source consulted this session confirms or denies
  whether anything else in single-player (e.g. a scripted `trigger.action.restartMission` inside an
  authored mission) also fires it without the pilot asking for a restart. Worth a one-line note in
  the investigator's own pass if it has spare scope, not worth blocking on.
- **`sources` list identity vs. contents.** `ConsolePerceptionRunner.reset_for_new_mission()` passes
  `sources=self.sources` through unchanged — the *list object* is preserved, only each source's own
  internal state is cleared (step 2's loop, which must run *before* this call). Get the order
  backwards and a source's dedup maps clear, then the runner's own `__init__` re-sets `self.sources`
  to the same list anyway — harmless either order for this specific field, but written out as an
  ordering rule in the mechanism section so a future edit to `__init__`'s defaults doesn't
  accidentally reorder it into a case where it matters.

### Decisions Requiring User Input

- **What happens when the live theatre has no built store** (no file at the resolved path, or it
  fails the mismatch guard)? This plan's working default is "keep running on the old theatre/store
  and log loudly" — never crash, never silently apply the wrong projection. Confirm, or specify a
  different degrade (e.g. Petrovich should say something specific, not just a log line).
- **What happens before the very first `onSimulationStart` of a process's life, if the process is
  started with a mission already running** (collector already holds a mission-start event from
  before body-layer connected)? This plan's design treats the first poll as "already clean, nothing
  to reset" regardless of the sequence number seen — confirm that's the wanted behaviour rather than
  "always reset once on first contact, to be sure."
- **Does Petrovich say anything at reset** (e.g. a short line acknowledging a fresh start)? Proposed
  as an open question per the brief, not decided here — this is a crew-interaction call, not an
  implementation one.
- **Should a pilot's `silenced` mute survive a mission restart?** Proposed default: yes (preserve
  it) — flag if that's wrong.
- **Should per-run log files re-roll to a fresh per-mission filename on reset, or is a marker line
  enough for now?** See Risks above; recommendation is marker-line-now, full re-roll as a later
  follow-up, but this trades off against exactly the kind of multi-flight-log confusion `BL-B68`'s
  own diagnosis took real time to untangle, so it's worth the user's explicit call rather than
  defaulting past it.

### Second-order effect

Closes the gap `BL-15.md` names between the Mission Interpreter (done, `MI-0`-`MI-6`) and a sortie
where nothing runs it automatically — Stage 2 (briefing on mission start) now has a signal to key
off that did not exist before this plan. It also removes the standing workaround ("restart
body-layer between missions") that every multi-sortie acceptance card for `BL-B64`/perception work
has had to carry as a caveat; once this lands, that caveat can come out of those cards.
