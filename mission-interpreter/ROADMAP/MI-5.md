# MI-5 — Player questions — text console MVP

- [x] **MI-5 — Player questions (text console MVP).** #status/done Completed 2026-09-12
  (`plans/mi5-player-questions/plan.md`, locked commit `9947c93`). **Delivered:** `PlayerAnswer`
  dataclass (`question_id`, `question_text`, `question_kind`, `parsed: bool | str | int`);
  `MissionUnderstanding.player_intent` retyped from the unused MI-3 placeholder `Tagged[str] |
  None` to `tuple[Tagged[PlayerAnswer], ...]`, mirroring `known_threats`'s per-item-tagged-tuple
  shape; new `src/player_intent/` package -- `questions.py`'s `detect_questions` (a pure,
  deterministic detector grounded in what MI-3/MI-4 actually produce today: ownship `UNKNOWN`,
  `purpose`/`task` `None` or `confidence == "low"`, per-threat `confidence == "low"` -- not the
  concept doc's three literal worked examples, which need schema fields that don't exist yet, see
  Decision 1); `console.py`'s `PlayerIntentConsole` (typed `bool`/`choice`/`free_text` parsing over
  a `TextIO` pair, one re-prompt on a parse failure then give-up-as-unparsed-`free_text` with the
  original `question_kind` preserved, mirroring `body-layer`'s `CrewConsole` shape without
  importing it); `main.py`'s `main()` (a plain script wiring MI-1 through MI-5 end to end, same
  construction sequence `test_synth_live_ollama.py` already used, not a new subcommand framework).
  93 unit tests (detector: one case per rule + a no-questions case; console: `io.StringIO`-driven,
  including both re-prompt-once-then-give-up paths). **Does not change what MI-6 should be**, but
  narrows its scope: `player_intent`'s new tagged shape means `bool`/`choice` answers reach MI-6
  already structured (`PlayerAnswer.parsed` typed by `question_kind`), leaving only the two
  genuinely free-text questions (`purpose`/`task` when MI-4 produced nothing) and the runtime
  block's specific field-name/enum mapping as MI-6's remaining interpretation work.
