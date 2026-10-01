### Implementation Summary

`WM-B1`: at OSM ingest, prefer a Latin-1-renderable `name:en`/`int_name` over a non-Latin-1 `name`,
and record which tag was used. No architect/plan.md preceded this — the roadmap entry itself was
the spec, per the task.

Branch `fix/latin-place-names`, from `main` at `d5bbdc9`.

### Files Changed

- `world-model/src/build/ingest_osm.py` — added `_NAME_TAG_PREFERENCE = ("name:en", "int_name",
  "name")`, `_is_latin1_renderable` (mirrors body-layer's `displayable_name` check), and
  `_select_name(tags) -> (name, name_source)`. Wired into all four name-producing call sites:
  `_ingest_node` (point `named_place`s — peak/place/dam), `_ingest_line`'s dam-point branch, the
  `_ingest_line` river/coastline LineString branch, and `_ingest_area`/`_ingest_ring` (settlement/
  landcover/water polygons). `_ingest_ring` gained a new `name_source: str | None` parameter, set on
  the stored feature's `tags["name_source"]` alongside the existing `area_m2`/`inner_rings`/
  `landcover_class` reserved keys. `CLASSIFIER_VERSION` bumped 4 → 5, with a changelog comment
  explaining why (both the name chosen and the new `name_source` tag are this module's output, so a
  stale cache must not be served).
- `world-model/src/store/models.py` — documented `name_source` as a new reserved `tags` key, in the
  same docstring section as `inner_rings`/`area_m2`/`landcover_class`.
- `world-model/tests/test_ingest_osm.py` — added `TestIsLatin1Renderable`, `TestSelectName`, and
  per-call-site integration tests (node, dam line, river line, settlement area, unnamed area/line).
  Updated three existing direct `_ingest_ring(...)` call sites (one shared helper, two inline) to
  pass the new `name_source` positional argument — required by the signature change, not a behaviour
  rewrite; each now passes a literal `"name"` to match the existing literal `"Test Name"` they
  already passed for `name`.
- `world-model/ROADMAP.md` — `WM-B1` marked `[x]`, with the implementation summary and the measured
  counts (below) appended in place.

### Tests Added

- `TestIsLatin1Renderable` (4 tests) — ASCII renders, Latin-1-extended (accented) renders, Arabic
  does not, a diacritic-heavy romanisation (the brief's own risk case: `name:en` can itself be
  unrenderable) does not.
- `TestSelectName` (7 tests) — no name tags at all; plain `name` only; `name:en` preferred over
  `name`; `int_name` preferred over `name` when `name:en` absent; `name:en` preferred over
  `int_name` when both exist; a non-renderable `name:en` is skipped in favour of a renderable
  `int_name` (not accepted just because the key matched); no candidate renders → falls back to the
  raw `name`.
- `TestIngestNode`: 4 new tests — `name:en` preferred over non-Latin-1 `name`; falls back to
  `int_name` when `name:en` absent; falls back to raw `name` (tagged `name_source="name"`) when
  nothing romanises; a plain-Latin1-`name`-only node also gets `name_source="name"` (one
  vocabulary, not a separate "no preference needed" marker).
- `TestIngestLine`: 3 new tests — river line prefers `name:en`; unnamed line has no `name_source`
  tag; dam-line point prefers `name:en`. (The pre-existing `test_named_dam_line_becomes_a_point_at_
  half_length` gained one assertion, `name_source == "name"`, since it already covered the
  plain-`name` dam path.)
- `TestIngestArea`: 2 new tests — named settlement area prefers `name:en`; unnamed area carries no
  `name_source` tag.

### Checks

world-model/ (only subproject touched):

- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (`--strict`): pass, 62 source files
- `pytest tests -q`: 511 passed, 3 skipped (491 passed, 3 skipped before this change — 20 new tests,
  no regressions, no existing test behaviour changed beyond the 3 call-site signature updates noted
  above)

Baseline note: the task briefed "494 passed, 3 skipped" as the main-checkout baseline; this
worktree's `main`-equivalent commit (`d5bbdc9`) collects exactly 494 tests total and reports 491
passed + 3 skipped (491 + 3 = 494) — the same number, read as "passed" vs. "total collected." Not a
discrepancy, just a different way of stating the same count; flagged here rather than silently
assumed.

### Notable Discoveries

- **The `osmium tags-filter`/`KeyFilter` pre-filters do not strip `name:en`/`int_name`.** Both
  filters operate at object granularity (which elements pass), not tag granularity — a matched
  node/way/area keeps every one of its original tags, including ones neither filter's key list
  mentions. Confirmed by scanning the real, already-filtered `syria-theatre.osm.pbf` directly (see
  measurement below): `name:en`/`int_name` were present on exactly the ids expected. No change to
  either filter's key list was needed or made.
- **`osm_cache/schema.py`'s warning about `StoredFeature` shape changes needing a cache-schema bump
  did not apply here.** `name_source` lives inside the existing generic `tags_json` blob column, not
  a new top-level column, so `OSM_CACHE_SCHEMA_VERSION` stays at 1 — only `CLASSIFIER_VERSION`
  needed bumping, and the module's own docstring's rule ("a rule change must force a rebuild") says
  so directly. Worth stating explicitly since the module's comment reads as if any `StoredFeature`
  field change triggers a schema bump; it doesn't, only a *shape* (column-set) change does.
- **Measured against the real theatre build**, per the task's point 5 (read-only copies in
  `/private/tmp/.../scratchpad/wmb1/`, originals untouched):
  - `syria-full.sqlite` currently holds 49,226 `named_place`/`settlement` rows; 19,553 of them
    (40%) store a non-Latin-1 name today. These aren't all Arabic — the merged seven-country extract
    also carries Greek (Cyprus), Hebrew (Israel/Palestine), and Turkish names, so this fix's reach
    is wider than "Syrian place names" alone.
  - Scanning the exact source `syria-theatre.osm.pbf` (the filtered, merged file M9's pipeline
    actually parses) for those 19,553 ids' tags: **13,073 (67%) have a usable romanisation** —
    12,926 via `name:en`, a further 864 via `int_name` where `name:en` was absent or itself failed
    the Latin-1 check. **6,480 (33%) have neither tag, or neither renders**, and will still store
    the raw non-Latin-1 name after this fix, same as before (`body-layer`'s render-time guard still
    catches them). This is the honest finding the task asked for: a clear majority wins, but a third
    of the affected features gain nothing — not "most of them have a romanisation."
  - All 19,553 referenced OSM ids were found in `syria-theatre.osm.pbf` (0 not-found) — no surprise,
    since the store was built from this exact file, but confirms the measurement methodology (direct
    id lookup via a one-pass `osmium.SimpleHandler` scan) is sound rather than silently missing
    elements.

### Not touched

- `feature/landform-geomorphons`'s files (`build/pipeline.py`, `build/ingest_terrain.py`,
  `terrain/`) — this fix never needed them; `build/pipeline.py` wasn't read beyond confirming where
  `CLASSIFIER_VERSION`/`OSM_CACHE_SCHEMA_VERSION` are consumed (`cache_meta_matches`), no edit made.
  No merge-order concern between the two branches.
- No full-theatre rebuild run — per the task and project rule, that is the user's to run, expected
  to ride along with the geomorphons work's own rebuild.
