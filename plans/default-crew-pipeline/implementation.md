### Implementation Summary

BL-B96: the crew pipeline (belief + `CrewConsole` + speech in/out) is now what `body-layer`
simply does, unconditionally — every mode flag (`--console`, `--crew-text`, `--overlay`,
`--f10-commands`, `--speech-audio`, `--speech-input`) is gone, as is the plain-text logger
`PerceptionLogger`/`format_observation_line` branch they used to select between. The F10
radio-menu command input and the in-cockpit text overlay are removed from every layer
(aircraft-layer's Hook scripts/collector receivers, body-layer's client/dispatch side).
`body-layer/src/logger.py` is renamed `body.py`.

Ten stage commits plus two follow-on commits for backlog/docs bookkeeping and a full-repo sweep,
all on `worktree-agent-a44154a8eb7919c1c`:

1. `57cb4176` — rename `logger.py` → `body.py` (`git mv`), fix imports/`known-first-party`/doc
   mentions touched by that stage.
2. `eee149b8` — delete `--console`, the plain-text-logger `else:` branch, `PerceptionLogger`,
   `format_observation_line`, `belief/console.py` (`Console`/`format_event_for_overlay`), and
   `tests/test_console.py` (879 lines) outright. `test_logger.py` → `test_body.py`, −758/+… net
   lines as console-only tests were deleted or ported.
3. `f3c89f8c` — make `--crew-text`, `--speech-audio`, `--speech-input` unconditional: deleted as
   flags, their behaviour becomes what `main()` always does. `--audio-adapter-url` becomes
   required (`parser.error` if absent).
4. `5c1673f6` — warn-and-keep-trying for an unreachable audio adapter (user direction, BL-B96
   plan): new `connection_reporter.ConnectionReporter` class, shared by `CrewConsole._print`'s push
   path and `_poll_transcripts`'s poll path via one instance (`audio_adapter_reporter`).
5. `db603344` + `41ce71eb` — remove F10 radio-menu command input: aircraft-layer side deletes the
   Hook script, `F10CommandReceiver`/`F10CommandQueue`, the schema, `GET /f10_commands/poll`, and
   their tests (1295 deleted lines); body-layer side deletes `aircraft_client.get_f10_commands`
   and the `_poll_f10_commands` call site.
6. `91224b93` + `9011b6fa` — remove the in-cockpit text overlay: aircraft-layer side deletes the
   overlay Hook script/`.dlg`, `TextOverlaySender`, `POST /text/push`, and their tests (910 deleted
   lines); body-layer side deletes `aircraft_client.push_text_line`, `CrewConsole.overlay_client`
   and its push block, `_format_gaze_line`/`_push_gaze_line`, `_URGENT_OVERLAY_PREFIX`, and
   14+1 overlay-only/overlay-mixed tests (triaged individually — see "Notable Discoveries" below
   for the one that needed more than a mechanical strip).
7. `19e7183b` (this session) — backlog/docs bookkeeping: obsolescence notes on `BL-B7`/`BL-B8`/
   `BL-B9` (the retired F10 backlog entries, IDs kept per root `CLAUDE.md`'s "Numbers are never
   reused"); `body-layer/CLAUDE.md`'s "## What this is" surface count and "## Commands" flag
   narrative rewritten; `body-layer/RUN.md`'s "## 2. Run the crew session" (renamed) example/
   Arguments table/"## 3. Reading the output" rewritten; `run-scripts/run-console.sh` deleted,
   `run-crew-text.sh`/`run-crew-text-debug-view.sh` drop the removed flags.
8. `27c6fa53` + `e39dc3f0` (this session) — full-repo grep sweep, see "Notable Discoveries".

### Files Changed

Renamed: `body-layer/src/logger.py` → `body.py`; `body-layer/tests/test_logger.py` →
`test_body.py`.

Deleted: `body-layer/src/belief/console.py`, `body-layer/tests/test_console.py`,
`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua`,
`aircraft-layer/dcs-export/petrobrain-f10-probe-hook.lua`,
`aircraft-layer/src/collector/f10_command_receiver.py`, `aircraft-layer/src/schema/f10_command.py`,
`aircraft-layer/tests/test_f10_command_{api,queue,receiver,schema}.py`,
`aircraft-layer/dcs-export/petrobrain-overlay-hook.lua`,
`aircraft-layer/dcs-export/petrobrain-overlay.dlg`, `aircraft-layer/src/collector/text_sender.py`,
`aircraft-layer/tests/test_text_{push_api,sender}.py`, `run-scripts/run-console.sh`.

New: `body-layer/src/connection_reporter.py` (`ConnectionReporter`, promoted out of `body.py` so
every caller — `CrewConsole._print`'s push path and `_poll_transcripts`'s poll path — can share one
instance and therefore one tri-valued connected/disconnected state).

Everything else modified: see the per-stage commit list above for the production-code shape; this
session's own two commits (Stage 7/8) additionally touched, for a stale reference sweep (`logger.py`
→ `body.py`, `logger._x` → `body._x`, and the handful of comments making now-false current-tense
claims about deleted flags/functions): `body-layer/CLAUDE.md`, `body-layer/RUN.md`,
`body-layer/docs/STRUCTURE.md`, `body-layer/config/defaults.toml` (regenerated, never hand-edited),
`body-layer/ROADMAP/BL-B{7,8,9}.md`, `run-scripts/run-crew-text{,-debug-view}.sh`, and ~30 `src`/
`tests` files across `body-layer` (`aircraft_client.py`, `group_trace_log.py`,
`detection_trace_writer.py`, `belief_truth_log.py`, `speech_log.py`, `eyesight_view.py`,
`sight_trace_writer.py`, `run_log_paths.py`, `belief/{tasks,attention,brain_client,contacts,
attack_run,effector_registry,crew_console,mission_phase,effector_sequences,sight_effector,
optic_policy,effector_engine,percept,position_belief,callouts,escalation}.py`,
`mission_memory/{admission,store}.py`, `perception/{gaze,hybrid_source,visibility,source,
naked_eye_source,motion}.py`), plus `audio-adapter/CLAUDE.md` and
`audio-adapter/src/audio_adapter/__main__.py` (cross-subproject references to body-layer's removed
F10 path / renamed module).

### Tests Added

- `tests/test_body.py` — `ConnectionReporter`-based tests for the warn-and-keep-trying posture
  (Stage 4).
- `tests/test_crew_console.py` — `audio_adapter_reporter` sharing tests (Stage 4); the thread-
  affinity fix test for `_run_crew_text_repl` (see "Notable Discoveries").
- `tests/test_body.py`/`tests/test_mock_flight_chain.py` — ported console-path regression tests
  that proved a genuine gap in the crew-text path rather than a duplicate (same thread-affinity fix).

### Tests Deleted (and why)

- `tests/test_console.py` (879 lines, 55 tests) — tested `belief/console.py`'s `Console`/
  `format_event_for_overlay` only; both deleted.
- `PerceptionLogger`/`format_observation_line` tests in `test_logger.py`/`test_body.py` (7+1
  tests) — the plain-text-logger branch they tested is deleted.
- Pure overlay-only tests in `test_crew_console.py`/`test_body.py` (14+1) — overlay push on
  readback/contact-report/lifecycle-event/urgent-prefix/inject-urgent-usage/failed-push-isolation,
  the no-op-when-unset test, and the "pushes via print funnel" test, plus `FakeOverlayClient` —
  the behaviour they proved no longer exists.
- `test_get_f10_commands_returns_parsed_list`, `test_get_f10_commands_raises_on_unreachable_host`,
  `test_push_text_line_posts_to_text_push`, `test_push_text_line_raises_on_unreachable_host`
  (`test_aircraft_client.py`) — the methods they tested are deleted.
- aircraft-layer: `test_f10_command_{api,queue,receiver,schema}.py`,
  `test_text_{push_api,sender}.py` in full — the channels they tested are deleted.

### Tests Rewritten

- `test_mock_flight_chain.py` — rewritten against the crew-text model per the plan.
- `test_drain_brain_speaks_stand_by_once_at_the_threshold` — the mechanical overlay-strip failed
  for the right reason on first run: `drain_brain`'s own docstring states `_speak_stand_by_if_due`
  speaks through `_print` directly and is **not** part of `drain_brain`'s return value. Switched
  the observable to `speech_client.pushed`.
- ~6 mixed overlay+speech_client/return-value tests in `test_crew_console.py` — dropped the overlay
  construction/assertion, kept the speech_client or return-value proof that was each test's real
  subject (refusal-mode silence, silence-command suppression).
- 5 tests in `test_main_rejects_neither_theatre_pair_nor_mission_understanding`'s family — making
  `--audio-adapter-url` required meant these tests' argv hit the *new* required-flag check before
  ever reaching the theatre-pair rejection they claim to test ("right conclusion, unearned reason").
  Fixed by adding `--audio-adapter-url` to each test's argv.
- `test_sight_effector.py`/`test_sight_head.py` — hardcoded `"logger.py"` string literals in
  `FileNotFoundError`-path assertions, not named in the plan's own test-impact list (the risk my
  role instructions flag explicitly: a test the plan forgot is silent, not loud). Found via pytest
  failure, fixed to `"body.py"`.

### Checks

**body-layer/**
- `ruff format --check`: pass (173 files already formatted)
- `ruff check`: pass (All checks passed!)
- `mypy src`: pass (Success: no issues found in 74 source files)
- `mypy tools`: pass (Success: no issues found in 10 source files)
- `pytest tests -q`: pass (2576 passed, 4 xfailed)

**aircraft-layer/**
- `ruff format --check`: pass (72 files already formatted)
- `ruff check`: pass (All checks passed!)
- `mypy src`: pass (Success: no issues found in 25 source files)
- `pytest tests -q`: pass (581 passed)

**audio-adapter/** (comment-only changes, two files)
- `ruff format --check`: pass (31 files already formatted)
- `ruff check`: pass (All checks passed!)
- `mypy src`: pass (Success: no issues found in 16 source files)
- `pytest tests -q`: pass (349 passed, 2 skipped)

**Lua**: no `.lua` file was modified in this feature, only deleted (the F10/overlay Hook scripts)
— nothing to `luac5.1 -p`/GETGLOBAL-scan.

**Command map**: `python3 .claude/scripts/command-map-check.py` reports "command map current (67
tokens)" — no redraw needed (the spoken vocabulary itself is unchanged; only its transport
narrowed to voice-only).

**`body.py --help`**: rendered usage/option help contains no mention of `--console`/`--crew-text`/
`--f10-commands`/`--overlay`/`--speech-audio`/`--speech-input` anywhere.

### Notable Discoveries

- **A genuine pre-existing bug, found while porting rather than discarding a `--console`-path
  regression test**: `_run_crew_text_repl` copied `crew_console.enrichment` straight from
  `runner.enrichment`, which is built by the poll thread and holds *that thread's*
  `sqlite3.Connection` — thread-affine, so any enrichment-aware command run from the REPL thread
  raised `sqlite3.ProgrammingError` on first use. The same bug class the old `--console` REPL was
  fixed for (BL-5) had never been ported to its `--crew-text` twin. Before BL-B96 this only fired
  when `--console` was used (a debug path); making `--crew-text` the *only* REPL widens the blast
  radius to "every player-issued report command touching terrain," so it was fixed in scope rather
  than carried forward. Fix mirrors the old `--console` REPL's fix exactly: a REPL-thread-local
  `sqlite3.Connection`/`EnrichmentContext`, built lazily and refreshed per command.
- **The plan's test-impact list (role-mandated check, confirmed per instance)**: `test_sight_
  effector.py`/`test_sight_head.py`'s hardcoded `"logger.py"` string-literal assertions were not
  named anywhere in the plan and were found only by a pytest `FileNotFoundError` after the rename —
  the "missing entry is the dangerous one" case my role instructions warn about (a phantom test is
  loud; a forgotten file is silent until something fails).
- **A second rename-sweep gap, found only by this session's own Stage 8 grep**: Stage 1's rename
  touched the file, its imports, and the handful of places already flagged, but ~119 docstring/
  comment cross-references to the literal filename `logger.py` (not an import, just prose: "see
  `logger.py`'s poll loop") survived across `src/`/`tests/`, plus a mechanically distinct second
  form — `logger._function_name`/`logger.main` module-attribute references with no `.py` — in
  ~45 more places including `CLAUDE.md` and `docs/STRUCTURE.md`. Both were mechanical string
  substitutions, confirmed clean by grep afterward (see Stage 8 commit message for the full
  account). One of the 45 was not purely cosmetic: `MISSION_START_RESOLVE_FALLBACK_S`'s tuning key
  was the literal string `"logger.MISSION_START_RESOLVE_FALLBACK_S"`, which is the real
  `config/tuning.toml` override key, not just a doc reference — renamed to
  `"body.MISSION_START_RESOLVE_FALLBACK_S"` for consistency with every other module's own-
  namespaced key, and `config/defaults.toml` regenerated via `tools/generate_defaults.py --write`
  (never hand-edited) to pick up the renamed `[body]` section. No test and no committed
  `config/tuning.toml` referenced the old key string, so this is a clean rename, not a breaking
  change to anything in this repo — but it is a behaviour-relevant key name, worth flagging because
  anyone's *local*, gitignored `config/tuning.toml` using the old key would now silently fail to
  apply (the loader warns on an unknown key rather than refusing to start, per the existing Decision
  4/4a posture, so this degrades loudly rather than silently breaking the sortie).
- **Six production-code docstrings/comments made now-false current-tense claims**, beyond the
  mechanical filename rename, caught during the Stage 8 sweep rather than left as the kind of stale
  comment the "prune the comment you are standing next to" rule is meant to prevent accumulating:
  `crew_console.py`'s module docstring and `handle_command`/`drain_brain` docstrings described
  `belief.console.Console`, `aircraft_client.get_f10_commands`, and `_poll_f10_commands` as live;
  `belief/tasks.py`'s note on `unwatch_area`'s reachability claimed it was reached from
  `belief.console`'s now-deleted `unwatch-area` developer command — since that module is gone,
  `unwatch_area` is now reachable from no command surface at all, only `tests/test_tools.py`'s
  direct calls, which the note now says explicitly rather than leaving a false claim about where
  the degradation this fallback guards against could actually occur.
- **`docs/STRUCTURE.md`'s `body.py` entry narrates the module's evolution through every one of the
  now-deleted mode flags in detail (~100 lines).** Left as the historical record per root
  `CLAUDE.md`'s doc convention for decision logs, with one dated obsolescence note appended
  pointing at `CLAUDE.md`'s current "## Commands" section, rather than rewritten in place — the
  sequence of *why* each piece was added is still the right account of how the module got here, and
  rewriting a historical narrative to read as if it always described the final state would be the
  wrong kind of edit.

### Windows steps for the user

1. **Delete from `Saved Games\DCS\Scripts\Hooks\`** (if present from an earlier flight): the F10-
   commands Hook script and the overlay Hook script/`.dlg` — their source files no longer exist in
   this branch (`petrobrain-f10-commands-hook.lua`, `petrobrain-overlay-hook.lua`,
   `petrobrain-overlay.dlg`); leaving stale copies deployed is harmless (nothing on the collector
   side listens for their traffic any more) but they are dead weight.
2. **Restart the aircraft-layer collector** (`python -m collector`) to pick up the removed
   `F10CommandReceiver`/`TextOverlaySender`/`text_sender` wiring and reduced route table.
3. **Restart `body.py`** with `--audio-adapter-url` now required (it was optional-but-needed-for-
   `--speech-audio` before) — any existing run script that did not already pass it will now fail
   fast with a clear `parser.error` rather than silently running with speech off.
4. No other DCS-side change: the mission-start Hook and the telemetry/line-of-sight/firing Hooks
   are untouched by this feature.
