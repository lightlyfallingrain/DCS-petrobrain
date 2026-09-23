### Implementation Summary

Implemented Stages 1-4 of `plans/voice-command-completeness/plan.md` (Stage 5 explicitly out of
scope, per instruction). Wired the 20 previously-dead voice tokens (`report_all`,
`report_clock_1..12`, `report_bearing_*`, `report_bearing_deg`, `scan_bearing_deg`) into
`CrewConsole.handle_command` (renamed from `handle_f10_command`), added the numeric-bearing wire
fix in `audio-adapter`, and updated prose/roadmap.

Before starting: confirmed `plans/voice-command-completeness/plan.md`'s named test files against
the real tree (see "Notable Discoveries" — one file name was wrong) and grepped the modules being
touched for tests the plan didn't name (none found beyond the incorrect file reference).

### Files Changed

**body-layer**
- `src/belief/crew_console.py` — Stage 1: `handle_f10_command` → `handle_command`,
  `_F10_SCAN_REASON` → `_SCAN_COMMAND_REASON`, unknown-token branch now `logger.warning`s instead
  of silently returning `[]`, new `DISPATCHED_COMMAND_TOKENS` frozenset. Stage 2: `_handle_report`
  (the report-family dispatcher — read-only, no `AttentionArea`/task/gaze change), new dispatch
  tables `_CLOCK_REPORT_TOKENS`/`_CLOCK_REPORT_LABELS`/`_BEARING_REPORT_TOKENS`, `REPORT_MAX_GROUPS`
  constant. Stage 3: `_nearest_sector` (22.5° half-bucket quantisation onto the 8 compass
  `Sector`s), `scan_bearing_deg`/`report_bearing_deg` dispatch entries, `bearing_degrees` threaded
  through `handle_command`/`handle_transcript`/`_act_on_voice_decision`/`_describe_token_for_confirm`,
  `!voice` harness gained an optional trailing-integer bearing argument (peeled off the transcript's
  last word, so every pre-existing invocation is unaffected).
- `src/belief/speech.py` — `render_clear`, `render_no_view`, `render_report` (Stage 2).
- `src/belief/callouts.py` — extracted `group_facts` (the bucket+chain merge rule, now facts-only
  and generic via a `TypeVar` on `_chain_by_clock`) out of `group_candidates`, which is now a thin
  event→facts→`group_facts`→events wrapper (identity-mapped back via `id(facts)`, since
  `group_facts` never copies the dicts it reorganises). Added `report_priority` (facts-only sibling
  of `callout_priority`, drops the `-event.t_sim` term) and `CalloutScheduler.note_reply`
  (extends `busy_until_sim` via `max`, never preempts — contrast `note_urgent`, which resets).
- `src/belief/voice_commands.py` — `PendingConfirmation.bearing_degrees: int | None = None`.
- `src/logger.py` — `_poll_f10_commands`/`_poll_transcripts` call `handle_command`; `_poll_transcripts`
  validates and threads `bearing_degrees` from the wire (a wrong-typed value is skipped, matching
  the existing per-field validation posture). `--f10-commands` help text renamed.
- `body-layer/CLAUDE.md` — new "surface is commands, not F10 commands" framing paragraph after
  "What this is"; the `crew_console.py`/`voice_commands.py` Structure entries updated to describe
  the report families, bearing quantisation, `DISPATCHED_COMMAND_TOKENS`, and `note_reply`, and to
  stop claiming the 20 tokens are still a documented no-op.
- `body-layer/ROADMAP.md` — new Status entry for this milestone (Stages 1-4, unflown as of merge).

**audio-adapter**
- `src/transcript_queue.py` — `TranscriptEvent.bearing_degrees: int | None = None` + `to_dict` key
  (eight fields, not seven).
- `src/server.py` — `_handle_transcribe` passes `match.bearing_degrees` into the enqueued event.
- `src/vocabulary.py` — docstring-only note on `BEARING_RESOLUTION_DEG`: the 5° slot is a
  recognition checksum, independent of the later act-time quantisation onto compass sectors.

**Cross-cutting**
- `docs/concept/STATE_TRANSITIONS.md` — short addendum on the "Player commands" section noting the
  F10-primary framing has inverted (voice primary, F10 legacy transport).
- `todo/todo.md` — two new deferred items under "Cross-cutting / unscoped backlog": compass/absolute
  scans still not reaching `_active_gaze` (re-measured, not newly discovered), and the
  ownship-relative o'clock scan token family — both explicitly Stage 5 of this plan, sequenced
  together since the clean fix is the same `ScanPlan`-carries-legs generalisation for both.

### Tests Added

**body-layer**
- `tests/test_crew_console.py` — `DISPATCHED_COMMAND_TOKENS` completeness (every member returns
  non-empty or is `stop_talking`'s documented no-op); unknown-token warning; `report_all` clear/
  configured-contact/lost-contact-dropped/no-enrichment cases; `report_clock_3` clear and
  contact-match cases; `report_bearing_n`/`report_bearing_s` clear vs. rear-hemisphere refusal, and
  that a believed rear-hemisphere contact is still reported; `report_bearing_deg` quantisation
  (including the rear-hemisphere path) and no-bearing say-again; `scan_bearing_deg` quantised task
  registration and readback; `_nearest_sector` bucket boundaries; `_describe_token_for_confirm`
  sector-not-number wording for every new family; a confirm-band bearing round trip surviving
  "affirm" (the test that would fail if `PendingConfirmation.bearing_degrees` were removed); a
  reply extending `CalloutScheduler.busy_until_sim`.
- `tests/test_callouts.py` — `report_priority` ordering (mirrors the three `callout_priority`
  tests); `group_facts` chaining/non-chaining/no-relative_now-singleton; `group_candidates` proven a
  thin wrapper (still returns `Event`s, still chains); `note_reply` extends/never-shortens/extends-
  past-a-shorter-existing-budget.
- `tests/test_speech.py` — `render_clear` (bare vs. capitalized-directional), `render_no_view`
  (lowercase mid-sentence, contrasted explicitly with `render_clear`'s capitalization), `render_report`
  (join, and the truncation suffix).
- `tests/test_logger.py` — `_poll_transcripts` threading `bearing_degrees` through to
  `handle_transcript` (via a small recording double, since exercising the real dispatch needs a
  full `EnrichmentContext`/`TaskStore` that belongs to `test_crew_console.py`'s own tests) and
  skipping a wrong-typed `bearing_degrees`.

**audio-adapter**
- `tests/test_transcribe_api.py` — the `bearing_degrees` field now asserted in the round-trip
  test's field set; a new test posting a real "scan bearing three two zero" transcript through the
  real `command_matcher.match_transcript` path and asserting `bearing_degrees == 320` survives
  `POST /transcribe` → `GET /transcripts/poll` (the regression this stage exists to fix).

### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict, `PYTHONPATH=src:../world-model/src`): pass, no issues in 45 source files
- `pytest tests -q`: **1051 passed, 4 xfailed** (baseline 1016 passed / 4 xfailed — 35 new tests,
  no regressions)

**audio-adapter/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict): pass, no issues in 15 source files
- `pytest tests -q`: **179 passed, 1 skipped** (baseline 178 passed / 1 skipped — 1 new test, no
  regressions)

### Notable Discoveries

- **The plan named the wrong audio-adapter test file.** It says
  `audio-adapter/tests/test_transcript_queue.py`/`test_server.py` for the wire changes, but neither
  `TranscriptEvent` nor `POST /transcribe` is tested there — `test_server.py` only covers `/speak`/
  `/stop`. The real coverage lives in `audio-adapter/tests/test_transcribe_api.py`, confirmed by
  grep before writing anything. No file the plan named was missing entirely, unlike the two prior
  incidents this role's memory records (a phantom test name, and a file left off the list
  completely) — this was a real file, just named wrong, likely a stale reference to an earlier
  restructuring of that test suite.
- **`_terrain_aware_world_position`'s test-fixture stub ignores bearing/range entirely.** Every
  existing enrichment-based test in this codebase (`_enrichment_context` + `project_terrain_aware`
  monkeypatched to identity) reports a contact's `relative_now` from the *observing ownship's own
  position at the time of the contributing observation*, not from the percept's `bearing_deg`/
  `range_m` projected outward. This was not obvious from reading the source and cost real time to
  reverse-engineer empirically (a throwaway script in the scratchpad, deleted afterwards) before
  the report-family tests' expected clock/range values could be constructed correctly. Worth
  knowing for any future test needing a contact at a controlled bearing/range under this fixture:
  control it via `ownship_at_observation`'s x/z, not via the observation's own `bearing_deg`/
  `range_m` fields.
- **`DISPATCHED_COMMAND_TOKENS` intentionally excludes `wake_petrovich`/`cancel_nevermind`/
  `say_again`** — all three are handled above `handle_command` (per the module's own pre-existing
  docstring) and never reach it as a dispatched token at all. The set totals 38 of the vocabulary's
  41 tokens; the remaining 3 are those routing tokens, not a gap.
- **`note_reply` is called unconditionally on every non-urgent `_print` line**, including a line
  `CalloutScheduler.tick` itself just drained and already accounted for in its own
  `busy_until_sim` update. This is deliberately redundant rather than conditioned on the call site —
  `max()` makes the second call a no-op in that case — because the plan's own instruction is to call
  it from `_print`'s non-urgent path, not to special-case which callers of `_print` should skip it.
