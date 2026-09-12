---
name: project_mi5_player_questions
description: MI-5 player-questions detector/console implementation notes -- ownship choice path is currently dead, main.py mirrors the live-ollama test's construction sequence.
metadata:
  type: project
---

MI-5 (`plans/mi5-player-questions/plan.md`, locked commit `9947c93`) implemented 2026-09-12,
4 commits: schema retype, detector+console, CLI entry point, ROADMAP update.

- `_build_ownship`'s `UNKNOWN` `Tagged.basis` is only a match-count string ("found N
  Player/Client-skill units..."), never candidate ids/names. So `questions.py`'s
  `kind="choice"` ownship-question path is unreachable through any real
  `detect_questions(understanding)` call today -- it always falls back to `free_text`. The
  `choice`-parsing code in `console.py`/`Question.options` is only exercised by hand-built
  `Question` fixtures in tests, not by the live detector. Revisiting requires `_build_ownship`
  to start recording enumerable candidates on `basis` (plan's own stage 5 refinement note, not
  a surprise this session found).
- No committed MI-3->MI-4->MI-5 CLI chain existed before this stage. `main.py` was built by
  copying `tests/test_synth_live_ollama.py`'s exact construction sequence (read_miz ->
  filter_crew_available -> enrich_mission -> build_mission_understanding ->
  derive_threat_signals -> enrich_threat_signals -> synthesize_mission_understanding) rather than
  inventing a second convention -- reusable pattern: check how the existing live-integration test
  builds the pipeline before writing a new entry point.
- `main.py` was never smoke-tested against a live Ollama/world-model instance (out of scope for
  this milestone per the task brief -- pure schema logic + deterministic console I/O). A future
  acceptance pass should run it for real before trusting the CLI wiring end to end.
- Test fixtures for `MissionUnderstanding` in both new test files needed `purpose`/`task` to
  default to resolved high-confidence `Tagged` values (not the dataclass's own `None` default) --
  otherwise a test overriding only one field accidentally also trips the other field's
  "still-None -> free_text" detector rule.
