# BL-5 — Deterministic tool API (= PB-5)

- [x] **BL-5 — Deterministic tool API (= PB-5, done, merged to main, `288e31d`).** #status/done
  `feature/bl5-tool-api`. Formalizes `belief/tools.py`'s functions into a named, documented,
  fixed tool surface (`belief/tool_api.py`'s `TOOL_SET: list[ToolSpec]`; twelve at BL-5, 15 once BL-6 added `scan_area`/`get_task_status`/`cancel_task`) a human can hold a
  full tactical conversation against by hand, no LLM involved. Nine tools already existed; three
  net-new: `find_place` (new `world-model/src/query/search.py`'s `find_place_by_name`,
  case-insensitive substring match over settlements/named places/airfields/navaids,
  confidence-ranked), `describe_our_position`, `get_situation` (aggregates contact counts,
  highest-attention contact, unacknowledged event count, position summary — deterministic, no
  relevance scoring since BL-6 hasn't built one). Three new console commands (`place`, `situation`,
  `position`). 252 world-model tests (+8), 356 body-layer tests (+23). **One live bug found and
  fixed**: `situation` crashed on first live run — `sqlite3.ProgrammingError` from BL-3's
  `ConsolePerceptionRunner.enrichment` holding a poll-thread `sqlite3.Connection` the REPL thread
  then read (same defect class as BL-2 Stage 6, in a field that fix didn't cover). Fixed: the REPL
  now lazily builds its own thread-local connection/`EnrichmentContext`. Harvested to NOTES.md:
  sqlite3 thread-affinity is a recurring defect class in this codebase's polling/REPL architecture.
  **The tool-set freeze point was BL-6, not BL-7** (moved 2026-09-11 when BL-6's investigation
  resolved what it needed to add — see that entry below) — §3.3's tool list is the API's intended
  final shape, delivered incrementally; a brain-layer prototype can start against the BL-5 subset
  now but should expect the surface to grow through BL-6. Full history: `plans/bl5-tool-api/`.

