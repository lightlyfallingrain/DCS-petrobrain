### Review Summary

Reviewed `feature/m3-osm-overlay` against `plans/m3-osm-overlay/plan.md` and CLAUDE.md/AGENTS.md
conventions. Read `world-model/src/osm/{__init__.py,overpass.py,features.py}`,
`world-model/tools/inspect_osm_overlay.py`, all three new test files, the research note, and the
`todo/todo.md`/`world-model/CLAUDE.md` diffs. Ran the full verification sequence directly
(`ruff format --check`, `ruff check`, `mypy --strict`, `pytest`) — all pass, 21 tests.

The implementation matches the plan closely: single one-shot Overpass fetch with disk cache,
in-memory dataclasses mirroring `coordinates/`/`raster/`'s shape, no new persistent-storage
machinery, `src/coordinates/` and `src/raster/` consumed as-is (confirmed via `git diff` — no
changes to either), Gemerek control point reused correctly, storage-deferral rationale recorded
and `todo.md`/`world-model/CLAUDE.md` updated as planned. Test fixtures are genuinely
hand-copied real data with provenance comments matching `tests/control_points.py`'s pattern, not
synthetic. Network discipline is solid: `fetch_bbox` has exactly one call site to
`urllib.request.urlopen`, `test_fetch_bbox_returns_cached_path_without_network_call` proves the
cache-hit path never touches it (monkeypatched to raise), and no other code path in the codebase
calls Overpass.

Two required fixes below — one is a genuine gap against the plan's own explicit attribution
requirement, the other is a working-tree hygiene issue that will block a clean DoD handoff.

### Required Fixes

- **OSM attribution is not carried on the rendered overlay image itself** — the plan states
  "the cached-data README/research note and any rendered overlay image must carry an '© OpenStreetMap
  contributors' attribution line" (plan.md, "Data source..." section). `world-model/tools/inspect_osm_overlay.py`
  prints `_ATTRIBUTION` to stdout (`cmd_overlay`, line 122) but never draws it onto the saved PNG
  (`img.save(out_path)`, line 120, happens before the print and with no `draw.text(...)` call
  anywhere in the file). If `out.png` is extracted from the console it carries session context;
  the image file alone does not. This is an ODbL compliance requirement the plan called out
  explicitly as "easy to forget" — needs a `draw.text(...)` (or equivalent) attribution burned
  into the saved image before `img.save`.

- **Working tree is not clean — new implementer agent-memory files are unstaged** — `git status`
  shows `.claude/agent-memory/implementer/MEMORY.md` modified but not staged, and
  `.claude/agent-memory/implementer/project_overpass_user_agent.md` untracked. All other new
  files for this feature are staged. CLAUDE.md's Definition of Done requires "All new/modified
  files staged and committed... confirm a clean working tree" — these two files need `git add`
  before this goes to DoD.

### Optional Refinements

- The displacement report (`inspect_osm_overlay.py` and the research note's table) uses
  different columns than `docs/concept/WORLD_MODEL_BUILDER.md`'s Validation format (`DCS
  coordinate / F10 raster location / lat-lon / OSM location / error distance`) — it omits a DCS
  x/z column and compares against a by-eye chart reading rather than an independent ground-truth
  location, which the research note explicitly discloses as an "internal-consistency sanity
  check," not a new registration validation. The disclosure is honest and the deviation is
  reasonable given M3's diagnostic scope, but adding the DCS x/z column would make it a drop-in
  fit with the concept doc's format for any future consumer skimming research notes for
  consistent structure. Optional — not required for M3's stated diagnostic goal.

- `overpass.py`'s client-side `_TIMEOUT_S = 60` doesn't match the Overpass QL query's own
  `[timeout:25]` server-side budget. Harmless (client timeout is just a safety upper bound) but a
  one-line comment noting the two are independent would save a future reader a double-take.
  Optional.

### Verdict

APPROVED WITH MINOR FIXES
