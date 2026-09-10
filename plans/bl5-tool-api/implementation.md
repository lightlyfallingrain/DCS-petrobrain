### Implementation Summary

Implemented `plans/bl5-tool-api/plan.md` in full: world-model's `find_place_by_name` (Decision
2), the three net-new body-layer tools (`find_place`/`get_situation`/`describe_our_position`,
Decision 3's required-not-optional `EnrichmentContext`), `poll_events` as a one-line wrapper
(Decision 4), the transport-agnostic `tool_api.TOOL_SET` registry (Decision 1: no HTTP this
milestone), and `console.py`'s `place`/`situation`/`position` commands. Manually verified the
full flow against a real in-memory world-model store + `Console` (see below) -- all three new
commands answer correctly end to end, not just against mocked fixtures.

### Files Changed
- `world-model/src/query/search.py` (new) -- `find_place_by_name`/`PlaceMatch`: case-insensitive
  substring match over place-shaped features (`settlement`/`named_place`/`airfield`/`navaid`),
  representative point (first vertex for `Point`, centroid for `LineString`/`Polygon`), simple
  confidence (1.0 exact, 0.6 substring), provenance from `feature.provenance["name"]` falling
  back to `["geometry"]`.
- `world-model/src/query/__init__.py` -- exports `find_place_by_name`/`PlaceMatch` alongside
  `describe_position`.
- `world-model/tests/test_query_search.py` (new) -- 8 tests: exact/substring match, centroid vs.
  point representative-point logic, default-kinds exclusion of roads/water, empty text, unnamed
  feature, no match, dataclass shape.
- `body-layer/src/belief/tools.py` -- added `ToolResult` TypedDict (same shape as `ContactResult`,
  kept separate so a reader isn't misled about `facts`' shape), `find_place`, `describe_our_
  position`, `_our_position_summary`, `_highest_attention_contact`, `get_situation`,
  `poll_events`.
- `body-layer/tests/test_tools.py` -- 15 new tests covering all four additions (wrapping/
  confidence-label logic for `find_place`, semantic-fact fallback for `describe_our_position`,
  priority>watch>visible ordering and unacknowledged-event count for `get_situation`, and
  `poll_events`'s equivalence to `list_events(unacknowledged_only=True)`).
- `body-layer/src/belief/tool_api.py` (new) -- `ToolSpec`/`TOOL_SET`: all twelve BL-5 tools named
  with a plain-language description and the `tools.py` callable each maps to.
- `body-layer/tests/test_tool_api.py` (new) -- 5 registry-completeness tests (exact name set, no
  duplicates, every `fn` callable, every description non-empty, dataclass shape).
- `body-layer/src/belief/console.py` -- `place <text>`/`situation`/`position` commands, guarded
  the same way `watch-area` already is (`Console.enrichment` required, error line not a crash
  when unset). Module docstring's command table and `HELP_TEXT` updated; `poll_events`'s
  equivalence to the existing `events`/`ack` commands documented rather than duplicated
  (Decision 4).
- `body-layer/tests/test_console.py` -- 8 new tests for the three commands (enrichment-required
  guards, usage messages, match/summary formatting).

### Tests Added
- World-model: 8 tests in `test_query_search.py` (listed above).
- Body-layer: 15 in `test_tools.py`, 5 in `test_tool_api.py`, 8 in `test_console.py` -- 28 new
  tests total.
- Test counts: world-model 244 -> 252 passing; body-layer 333 -> 355 passing (22 new -- includes
  one pre-existing structural test, `test_console_module_contains_no_belief_logic`, which now
  additionally verifies the three new tool functions are referenced from `console.py`).

### Checks
- World-model: `ruff format --check` pass, `ruff check` pass, `mypy world-model/src` pass (48
  source files), `pytest world-model/tests -q` pass (252 passed).
- Body-layer: `ruff format --check` pass, `ruff check` pass, `cd body-layer && mypy src` pass (24
  source files), `pytest body-layer/tests -q` pass (355 passed).

### Notable Discoveries
- **A concurrent process committed alongside this work.** The third commit (console.py wiring +
  its tests) landed in history under commit `176fa2c`, whose message is about an unrelated
  `/merge` skill rewrite -- another session/process was evidently working in this same checkout
  at the same time and its `git commit` swept up my already-`git add`-staged `console.py`/
  `test_console.py` changes alongside its own `.claude/skills/merge.md` edit. Verified via
  `git show 176fa2c -- body-layer/src/belief/console.py` that the diff content is exactly what
  was implemented here (62 insertions matching this session's edits) -- nothing was lost or
  altered, just bundled under a commit message that doesn't describe it. Left as-is per the
  project's "never rewrite history unless asked" default; flagging here since a future `git log`
  reader won't find "wire place/situation/position" in that commit's subject line.
  world-model's two commits and body-layer's `tools.py`/`tool_api.py` commits landed cleanly
  under this session's own messages, unaffected.
- `describe_our_position` reuses `belief.enrichment.semantic_facts_for` directly (with
  `position_conf=1.0`, since ownship telemetry is ground truth, not a decaying belief estimate)
  rather than re-deriving semantic text from a second `describe_position` call -- avoids
  duplicating `enrichment.py`'s settlement/road/water/ridge/valley -> text mapping, at the cost
  of one redundant `describe_position` DB query per `describe_our_position` call (not perf-
  sensitive at console-command scale).
- `get_situation`'s highest-attention selection ties break on `last_seen_sim` (most recent
  first) within a tier -- an explicit, if arbitrary, deterministic choice since the plan doesn't
  specify a tie-break and there is no relevance score to fall back on (BL-6).
