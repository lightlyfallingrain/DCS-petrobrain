### Review Summary

Reviewed BL-5 (deterministic tool API surface) across all four commits (fc48d0c, a59d83f,
b1efd36, 561de10) against `plans/bl5-tool-api/plan.md` and `plans/bl5-tool-api/implementation.md`.

- `world-model/src/query/search.py` (`find_place_by_name`/`PlaceMatch`): follows the
  `describe.py`/`store.reader` seam exactly — goes through `store.reader.all_features`, no new
  dependency, no direct SQL. Provenance recorded per-match (`feature.provenance["name"]` falling
  back to `"geometry"` then `"unknown"`), confidence is a simple discrete value (1.0 exact / 0.6
  substring), documented as deliberately non-fuzzy. `PLACE_KINDS` list is hand-duplicated from
  `describe.py`'s own place-kind set rather than shared, but this is called out in the module
  docstring as a deliberate, acknowledged tradeoff, and the two lists are in fact currently in
  sync (checked against `describe.py`). Exported correctly via `query/__init__.py`.
  `world-model/tests/test_query_search.py` has 8 control-point-style tests (exact/substring,
  centroid vs. point, default-kind exclusion, empty text, unnamed feature, no match, shape) — not
  decorative.
- `body-layer/src/belief/tools.py`: `describe_our_position` and `get_situation` both take
  `enrichment: EnrichmentContext` as a required positional parameter (confirmed by reading the
  signatures directly, lines 591 and 641-643) — genuinely required, not optional-with-a-default,
  and this is a deliberate, documented asymmetry vs. the contact-facing tools' optional
  `enrichment` (Decision 3: there is no smaller "BL-2-shape" fallback for these two). Not an
  inconsistency.
- `poll_events` (lines 681-688) is exactly `list_events(store, unacknowledged_only=True)` under a
  new name — no duplicated logic, docstring explicitly cross-references Decision 4.
- `tool_api.py`'s `TOOL_SET` names exactly the twelve tools from the milestone brief
  (`get_contacts`, `describe_contact`, `get_contact_history`, `find_contact`, `find_place`,
  `set_attention`, `watch_area`, `get_attention_state`, `get_situation`, `describe_our_position`,
  `poll_events`, `acknowledge_event`) — cross-checked programmatically against the brief's list,
  exact match, no extras (`get_stats`/`list_areas`/`watch_contact` correctly excluded — they're
  console-support functions, not named BL-5 tools). `test_tool_api.py` verifies name-set,
  no-duplicates, callability, non-empty descriptions, and dataclass shape.
- `console.py`'s `place`/`situation`/`position` commands (diff read directly) dispatch 1:1 into
  `tools.py` functions, same enrichment-required guard pattern as the existing `watch-area`
  command, no belief logic inline — `test_console_module_contains_no_belief_logic` covers this
  structurally and was extended to reference the three new functions.
- No HTTP transport was added anywhere in the diff (grepped for `requests`/`flask`/`fastapi`/
  `http.server` — none found); `tool_api.py`'s registry is plain dataclasses, in-process only,
  matching Decision 1.
- No debug code, `TODO`/`FIXME`/`XXX` left in any of the four touched files.

**Concurrent-session race (console.py/test_console.py) — verified, no corruption.** Diffed
176fa2c (the commit that briefly swept up this session's staged console.py/test_console.py
changes into the unrelated `/merge` skill rewrite) against 561de10 (the final recommit) for
exactly those two files: the diff is empty — byte-identical content. 68c455b (the other session's
corrected recommit after `reset --soft`) touches only `.claude/skills/merge.md`, confirming the
other session's file was cleanly separated back out. No missing content, no duplication, no
botched merge of two concurrent edits. The implementer's log claim is accurate.

**Verification run directly (not just trusted from the log):**
- World-model: `ruff format --check`, `ruff check`, `mypy world-model/src` (48 files) all clean;
  `pytest world-model/tests -q` — 252 passed.
- Body-layer: `ruff format --check`, `ruff check`, `mypy src --strict` (24 files) all clean;
  `pytest body-layer/tests -q` — 355 passed.
Both match the implementer's reported counts exactly.

### Required Fixes

None.

### Optional Refinements

- No automated integration-style test exercises a realistic multi-tool sequence (e.g.
  `get_situation` -> `describe_contact` -> `set_attention` -> `poll_events`) in one test —
  coverage today is per-tool unit tests plus manual console verification. This gap is explicitly
  named and accepted in the plan's own "Risks & Unknowns" ("Console acceptance testing is
  manual... no automated end-to-end 'full conversation' test"), consistent with how BL-4's
  acceptance was verified, so it is not a defect relative to the plan — but a single
  `test_tools.py` or `test_console.py` test chaining 3-4 of the twelve tools against one shared
  fixture store would cheaply catch a future regression where two tools' outputs stop composing
  (e.g. a `facts` shape change in `describe_contact` that `get_situation`'s embedding of
  `highest_attention_contact` silently breaks). Optional — not required for this milestone.
- `search.py`'s `PLACE_KINDS` and `describe.py`'s equivalent place-kind list are hand-duplicated
  rather than sharing one constant, acknowledged in the docstring. Low risk today (both currently
  in sync), but worth a shared constant if a third place-kind consumer appears, to remove the
  "kept in sync by hand" maintenance burden. Optional.

### Verdict
APPROVED

### Review Confidence
Full read — plan, implementation log, all four commits' diffs, the new/changed source files in
both subprojects, the concurrent-race git history reconstruction (reflog + commit diffs), and
live re-run of both subprojects' full format/lint/type/test suites.
