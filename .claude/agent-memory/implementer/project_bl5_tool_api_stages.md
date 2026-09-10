---
name: bl5-tool-api-stages
description: what BL-5's four implementation stages built and where, for anyone extending TOOL_SET before BL-7's freeze point
metadata:
  type: project
---

`plans/bl5-tool-api/plan.md` was implemented in four commits matching its own stage boundaries:

1. `world-model/src/query/search.py` (`find_place_by_name`/`PlaceMatch`) + `query/__init__.py`
   export + `world-model/tests/test_query_search.py`. Substring match only, over
   `settlement`/`named_place`/`airfield`/`navaid` (`query.search.PLACE_KINDS`).
2. `body-layer/src/belief/tools.py`: `find_place`, `describe_our_position`, `get_situation`,
   `poll_events`, plus a new `ToolResult` TypedDict (same shape as `ContactResult`, kept separate
   on purpose). `describe_our_position`/`get_situation` take `EnrichmentContext` **required**, not
   optional (plan Decision 3) -- they raise/have no meaning without it, unlike every contact tool.
3. `body-layer/src/belief/tool_api.py` (new): `TOOL_SET`, a transport-agnostic
   name->description->callable registry over all twelve BL-5 tools. No HTTP this milestone
   (Decision 1) -- this registry is what a future thin adapter wraps.
4. `body-layer/src/belief/console.py`: `place <text>`/`situation`/`position` commands, guarded
   like `watch-area` (`Console.enrichment` required, error line not a crash).

**BL-5's tool-set freeze point is BL-7, not BL-5** -- `TOOL_SET` is expected to grow (BL-5a's
`say`/`ask_player`, BL-7's `scan_area`/`get_task_status`/`cancel_task`), not be treated as final.

See [[feedback_verify_git_log_after_commit]] for a concurrent-session git incident during this
task (resolved cleanly, no content lost, but worth knowing about for future multi-session work in
this repo without worktree isolation).
