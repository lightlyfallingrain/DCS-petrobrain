### Review Summary

Reviewed `fix/latin-place-names` (tip `bbdb1ef`, confirmed via `git rev-parse HEAD` before reading
anything) against `world-model/ROADMAP.md`'s `WM-B1` entry and `plans/latin-place-names/implementation.md`.
One commit: `build.ingest_osm._select_name` prefers `name:en` → `int_name` → raw `name`, accepting a
candidate only if it Latin-1-encodes, applied uniformly across every name-producing classifier branch
(node, dam-point, line, ring/area), recording the winning tag as a new reserved `tags["name_source"]`,
with `CLASSIFIER_VERSION` bumped 4 → 5.

All checks independently reproduced inside the worktree (not taken from the implementer's report):

- `ruff format --check src tests`: pass (104 files)
- `ruff check src tests`: pass
- `mypy src --strict`: pass, 62 source files
- `pytest tests -q`: **511 passed, 3 skipped** — matches the claim exactly
- Independently built a `main`-tip (`d5bbdc9`) venv via `git archive` and ran its own suite:
  **491 passed, 3 skipped** (494 collected) — confirms the branch adds exactly 20 new passing tests
  with zero regressions, and confirms the implementer's note that "494" (total collected) and "491"
  (passed) describe the same baseline, not a discrepancy.

Cache invalidation (the failure mode that would make this silently do nothing) was verified by
construction, not by reading the comparison: built an `OsmCacheMeta` stamped `classifier_version=4`
and one stamped `5` with otherwise-identical fields, called `cache_meta_matches` directly —
`False` for the stale-vs-current pair, `True` for current-vs-current. Also confirmed
`build/pipeline.py`'s `expected_meta` reads the live `CLASSIFIER_VERSION` module constant at build
time (not a captured/stale value), so every fresh build computes the current expectation correctly.

Call-site coverage was walked directly in `ingest_osm.py` rather than trusted from the file list:
all four `StoredFeature(name=...)` constructions (node, dam-point line branch, river/coastline line
branch, ring) route through `_select_name`/its result — no fifth name-producing site exists.
`_ingest_area` calls `_select_name` once and passes the result through to every ring, so
landcover/water/settlement areas only ever get a different stored name string and `name_source` tag,
never a change to classification, geometry, or any other field.

Downstream tag-key consumers checked for breakage from the new `name_source` key: `query/describe.py`
and `tools/export_geojson.py` only use `.get("<specific-key>")` lookups or serialize the whole `tags`
dict wholesale — no enumerate-all-keys pattern that a new key could break. `osm_cache`'s
writer/reader round-trip `tags` as an opaque JSON blob column, so no cache schema bump was needed,
confirming that part of the implementation report too.

Measured counts spot-checked against `world-model/ROADMAP.md`'s own `WM-B1` entry (not re-derived
against the live `syria-full` store myself, per the task's explicit prohibition on running a
full-theatre build): 19,553/49,226 (40%) non-Latin-1 named rows, 13,073 (67%) gain a usable
romanisation, 6,480 (33%) gain nothing — the roadmap entry states this plainly as "a real
improvement, not a complete fix," which is the honest framing the task asked for.

### Required Fixes

None.

### Optional Refinements

- **The implementer's claim that "both docstrings point at each other with a keep-in-sync note" is
  only half true.** `world-model`'s new `_is_latin1_renderable` docstring does say to keep the two
  checks in sync by hand. `body-layer/src/belief/enrichment.py`'s `displayable_name` docstring (not
  touched by this branch, confirmed by diff) was written before `WM-B1` existed and still reads "the
  real fix belongs upstream in the world model... recorded in `world-model/ROADMAP.md`" — it points
  at an open backlog item that is now closed, and carries no reciprocal "mirrored in
  `build.ingest_osm._is_latin1_renderable`, keep in sync" note. The two checks *do* agree today
  (`name.encode("latin-1")` / `UnicodeEncodeError`, identical both places) — this is a documentation
  staleness gap, not a behavioural one, and `body-layer` is outside this branch's touched subproject.
  Worth a one-line follow-up in `body-layer` (update the docstring to point at the now-implemented
  fix and name the mirrored function) so the "keep in sync by hand" safeguard the architecture relies
  on actually exists on both sides, rather than being a one-way reference that already reads as
  wrong.

### Verdict

APPROVED

### Review Confidence

Full read. All claims in the implementation log were independently verified rather than trusted:
cache invalidation reproduced by construction, call-site coverage walked directly in the source,
test counts reproduced in a fresh venv against both the branch and an independently-archived `main`
baseline, and downstream tag-consumer code read for enumeration risk. The one gap — the real
`syria-full` store's measured counts — was spot-checked against the roadmap entry's own numbers only,
per the task's explicit instruction not to run a full-theatre build myself; those numbers were not
independently re-derived from raw data.
