### Review Summary

Reviewed MI-5 (player questions, text console MVP) on `feature/mi5-player-questions` against the
locked plan (`plans/mi5-player-questions/plan.md`, commit `9947c93`, including its three inline-
resolved decisions) and `plans/mi5-player-questions/implementation.md`. Read `questions.py`,
`console.py`, `main.py`, the `understanding.py`/`PlayerAnswer` retype, both new test files, the
updated `test_schema_understanding.py`, `schema/build.py::_build_ownship`, and the ROADMAP.md
diff. Ran `mission-interpreter`'s own commands directly rather than trusting the reported numbers:
`ruff format --check` (40 files already formatted), `ruff check` (all checks passed), `mypy
--strict src` (no issues, 28 source files), `pytest -q` (93 passed). All four independently
reproduced.

1. **Detector rule set vs. plan spec** — matches exactly. `detect_questions` in `questions.py`
   produces: ownship `UNKNOWN` → choice-with-empty-candidates-so-free_text-fallback; purpose/task
   `None` → `free_text`; purpose/task `confidence == "low"` → `bool`; per-threat `confidence ==
   "low"` → `bool` (`id=f"threat_{index}"`); no rule for route/mission_phases/important_locations.
   Mutual exclusivity is real, not just commented: `_detect_purpose_or_task_question` returns
   immediately in the `tagged is None` branch before ever touching `.confidence`, so a `None`
   value can never fall through to the low-confidence-bool branch — verified by reading the
   control flow, not just the docstring.

2. **Choice-path-unreachable disclosure** — accurate. Read `schema/build.py::_build_ownship`
   directly: the `UNKNOWN` `Tagged`'s `basis` is exactly `(f"found {len(matches)} Player/Client-
   skill units, expected exactly 1",)` — a match-count string, never candidate ids/names. So
   `_ownship_candidates()` in `questions.py` is correctly a permanent no-op today (hardcoded `()`,
   with a docstring pointing at the real fix — `_build_ownship` needs to start recording
   candidates), and `_detect_ownship_question` deliberately chooses `free_text` when `candidates`
   is empty rather than leaving it to the `console.py` layer to paper over a bad `choice` with no
   options. This is a deliberate, disclosed design choice — not an accident of what happened to be
   in `basis` — which is exactly the higher bar the task asked to check for. Matches the plan's own
   Stage 5 "deferred refinement" framing. The `choice`-parsing code path in `console.py` is
   confirmed exercised only by hand-built `Question` fixtures in both test files, never through a
   real `detect_questions` call — correctly disclosed, not hidden.

3. **Re-prompt-once-then-give-up loop** — `console.py::_ask` re-prompts once (`_RETRY_PROMPT`) on
   a parse failure, and on a second failure records the raw line as `PlayerAnswer.parsed` while
   copying `question.kind` unchanged into `question_kind` (never re-derived from the give-up
   value). `test_bool_question_reprompts_once_then_gives_up_as_free_text` and
   `test_choice_question_reprompts_once_then_gives_up_as_free_text` both assert `question_kind`
   still equals the original kind (`"bool"`/`"choice"`) while `parsed` holds the raw second-attempt
   string — exactly the "tell a real typed answer from leftover unparsed text" property the plan
   requires.

4. **`bool` parsing** — `_BOOL_TRUE = ("y", "yes", "true", "1")`, `_BOOL_FALSE = ("n", "no",
   "false", "0")`, matched case-insensitively via `.strip().lower()`. Exact match to the plan.
   `test_bool_question_parses_yes_variants`/`_no_variants` cover this; an out-of-set token
   (`"maybe"`) correctly returns `None` from `_parse_bool`, driving the re-prompt path, not a wrong
   answer — confirmed by `test_bool_question_reprompts_once_then_gives_up_as_free_text`.

5. **`choice` parsing** — `_parse_choice` accepts a 1-based digit index (bounds-checked,
   out-of-range → `None`) or a case-insensitive exact text match against `options`; anything else →
   `None` (re-prompt, no crash, no silent acceptance). Covered directly in
   `test_choice_question_parses_1_based_index` (index, lowercase text, and nonsense-returns-None
   all in one test).

6. **`PlayerAnswer`/`player_intent` schema shape** — `test_populated_player_intent_round_trips_
   through_json` round-trips a populated `Tagged[PlayerAnswer]` through `asdict()` → `json.dumps` →
   `json.loads` and checks every field survives, mirroring MI-3/MI-4's convention. Every
   `Tagged[PlayerAnswer]` built by `console.py::_ask` uses `epistemic_status="FACT"`,
   `basis=("player:console",)` — confirmed at the one construction site, no other path builds this
   type.

7. **No live dependency** — `test_player_intent_questions.py` and `test_player_intent_console.py`
   build `MissionUnderstanding` fixtures directly and drive I/O through `io.StringIO`; neither
   touches Ollama or a world-model server. Confirmed no live-network skip-guard exists in either
   file (unlike MI-4's `test_synth_live_ollama.py`).

8. **`main.py`'s untested live wiring** — plausible on inspection: the construction sequence
   (`read_miz` → `filter_crew_available` → `WorldModelClient`/`enrich_mission` →
   `build_mission_understanding` → `derive_threat_signals`/`enrich_threat_signals` →
   `OllamaClient`/`synthesize_mission_understanding` → `PlayerIntentConsole.run` → JSON dump) uses
   real imports/signatures that all resolve under `mypy --strict`, and matches
   `test_synth_live_ollama.py`'s own construction order. Genuinely untested against a live
   Ollama/world-model pair, honestly disclosed in `implementation.md`. Optional note only, per the
   task's own framing — nothing about it looks wrong.

Scope check: no MI-5b (web form) work, no MI-6 (runtime compilation) work snuck in — `player_intent`
is populated but nothing consumes/compiles it further. `ROADMAP.md`'s MI-5 entry answers the
"does this change what's next" question (narrows, doesn't change, MI-6's scope) as required by root
`CLAUDE.md`'s Milestone Completion note. No world-model/DCS-installation/provenance invariants are
implicated by this milestone (no DCS extraction, no coordinate work, no GIS mixing) — confirmed by
scope, not by a targeted invariant script (none applies here). Git status is clean on this branch;
all files from `git diff main...feature/mi5-player-questions --stat` are already committed across
the four reported commits.

### Required Fixes

None.

### Optional Refinements

- `ROADMAP.md`'s MI-5 entry says "93 unit tests," which is the whole subproject's suite total
  (`pytest -q` reports 93 passed overall), not the count of tests added by this milestone
  specifically (23 across the two new files plus 2 in `test_schema_understanding.py`). Cosmetic
  wording only — doesn't affect correctness or any decision-log value — worth a one-word fix
  ("93 total" or the actual added-test count) next time this file is touched, not worth a re-pass
  on its own.
- `_ownship_candidates()` in `questions.py` is a permanent no-op today (`return ()`, unconditionally).
  It reads as a clean placeholder given the docstring pointing at `_build_ownship` as the real
  follow-up, but a future reader skimming the file without the docstring could mistake it for dead
  code. No action needed now — flagging only so it isn't forgotten if `_build_ownship` is ever
  revisited without also revisiting this call site.

### Verdict
APPROVED

### Review Confidence
Full read — plan, implementation log, all five touched source files, both new test files, the
updated schema test, `_build_ownship`, and the ROADMAP diff were read in full; all four
mission-interpreter verification commands (ruff format --check, ruff check, mypy --strict,
pytest -q) were run directly rather than trusted from the implementation report.
