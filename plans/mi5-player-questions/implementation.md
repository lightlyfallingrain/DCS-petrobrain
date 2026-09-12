### Implementation Summary

Implemented MI-5 (player questions, text console MVP) per the locked plan (commit `9947c93`):
a deterministic ambiguity detector over `MissionUnderstanding`, a typed console loop mirroring
`body-layer`'s `CrewConsole` shape without importing it, and a minimal CLI entry point wiring
MI-1 through MI-5 end to end. Four commits, matching the plan's stage breakdown.

### Files Changed
- `mission-interpreter/src/schema/understanding.py` — added `PlayerAnswer` dataclass
  (`question_id`, `question_text`, `question_kind: Literal["free_text", "bool", "choice"]`,
  `parsed: bool | str | int`); retyped `player_intent` from the unused MI-3 placeholder
  `Tagged[str] | None` to `tuple[Tagged[PlayerAnswer], ...] = field(default=())`.
- `mission-interpreter/tests/test_schema_understanding.py` — updated the `player_intent is None`
  assertion to `== ()`; added `test_populated_player_intent_round_trips_through_json`.
- `mission-interpreter/src/player_intent/__init__.py` — new package docstring only.
- `mission-interpreter/src/player_intent/questions.py` — `Question` dataclass + `detect_questions`,
  a pure function reading only `MissionUnderstanding`. Rules: ownship `UNKNOWN` → `choice` (falls
  back to `free_text` today since `_build_ownship`'s UNKNOWN basis carries only a match count, no
  enumerable candidate ids/names — see the plan's stage 5 refinement note); `purpose`/`task`
  `confidence == "low"` → `bool`; `purpose`/`task` `None` → `free_text`; per-`known_threats` item
  `confidence == "low"` → `bool` (`id=f"threat_{index}"`). No question for
  `route`/`mission_phases`/`important_locations`, per the plan.
- `mission-interpreter/src/player_intent/console.py` — `PlayerIntentConsole` (`input_`/`output`
  `TextIO` pair). `.run()` asks each detected question, parses per `kind` (bool: y/yes/true/1 vs
  n/no/false/0 case-insensitive; choice: 1-based index or case-insensitive exact match; free_text:
  verbatim including blank), re-prompts once on a parse failure, then records the raw line as
  unparsed `free_text` while preserving the original `question_kind` on give-up. Returns
  `dataclasses.replace(understanding, player_intent=tuple(answers))`.
- `mission-interpreter/src/player_intent/main.py` — `main()`/CLI entry point: `read_miz` →
  `filter_crew_available` → `enrich_mission` → `build_mission_understanding` →
  `derive_threat_signals` → `enrich_threat_signals` → `synthesize_mission_understanding` →
  `PlayerIntentConsole.run` (real stdin/stdout) → JSON dump to stdout. Mirrors
  `tests/test_synth_live_ollama.py`'s construction sequence exactly, since no prior committed
  MI-3→MI-4→MI-5 CLI chain existed to extend.
- `mission-interpreter/pyproject.toml` — added `player_intent` to `known-first-party` (ruff isort).
- `mission-interpreter/ROADMAP.md` — marked MI-5 done with a "does this change what's next" note
  (narrows, doesn't change, MI-6's scope: `bool`/`choice` answers already structured by
  `question_kind`; only the two genuinely free-text purpose/task-still-`None` questions remain
  fully free-form for MI-6 to interpret).

### Tests Added
- `mission-interpreter/tests/test_player_intent_questions.py` — one case per detector rule
  (unresolved ownship, low-confidence purpose/task, purpose/task still `None`, low-confidence
  threat), a medium/high-confidence-produces-no-question case, and a fully-resolved
  no-questions-at-all case.
- `mission-interpreter/tests/test_player_intent_console.py` — `io.StringIO`-driven: no-questions
  pass-through, free_text (blank + verbatim), bool (yes/no variants, second-attempt success), the
  re-prompt-once-then-give-up path for both `bool` and `choice` (via a hand-built `Question` since
  today's ownship question never actually reaches `kind="choice"`), and multi-question ordering.
- `mission-interpreter/tests/test_schema_understanding.py::test_populated_player_intent_round_trips_through_json`
  — a populated `player_intent` tuple survives `dataclasses.asdict()` → `json.dumps` → `json.loads`.

### Checks
(mission-interpreter/)
- ruff format --check: pass
- ruff check: pass
- mypy --strict src: pass (28 source files)
- pytest -q: pass (93 passed)

### Notable Discoveries
- `_build_ownship`'s `UNKNOWN` `basis` today is only a match-count string (e.g. `"found 2
  Player/Client-skill units, expected exactly 1"`), never candidate ids/names — so the plan's
  `kind="choice"` path for the ownship question is currently unreachable in practice; every real
  ownship-ambiguity case falls back to `free_text`. This was anticipated by the plan's own stage 5
  refinement note, not a surprise, but worth flagging plainly: the `choice`-parsing code in
  `console.py`/`questions.py.Question.options` is only exercised by hand-built `Question` fixtures
  in tests right now, not by any live path through `detect_questions`. Revisiting this needs
  `_build_ownship` to start recording enumerable candidates on `basis` (or a dedicated field) —
  explicitly deferred, per the plan.
- No committed MI-3→MI-4→MI-5 CLI chain existed before this stage, confirming the plan's own
  expectation; `main.py` follows `test_synth_live_ollama.py`'s exact construction sequence rather
  than inventing a second convention, and was not smoke-tested against a live Ollama/world-model
  instance (no live-network/live-model dependency was in scope for this milestone, per the task
  brief) — that's a real gap for a future acceptance pass to close, not a hidden assumption.
