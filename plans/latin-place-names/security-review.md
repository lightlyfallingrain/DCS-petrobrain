## Security Deep Analysis: WM-B1 latin-place-names

Branch `fix/latin-place-names`, tip `2453b11` (verified via `git rev-parse HEAD` before any other
command).

### Dependency Status

No dependency change. `pyproject.toml` unchanged — `pyproj`, `pillow`, `osmium`, `numpy<2.5`,
`scipy` are all pre-existing. `_select_name`/`_is_latin1_renderable` are pure stdlib (`str.encode`).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `src/build/ingest_osm.py` `_select_name` | Untrusted OSM tag value becomes `StoredFeature.name` | `name`/`name:en`/`int_name` are free-text Geofabrik-extract content, in principle attacker-influencable (OSM is community-edited). Traced every consumer: `store/writer.py` inserts via parameterized `?` SQL (`json.dumps(feature.tags)` for the blob) — no string interpolation into SQL anywhere in the path. `tools/export_geojson.py` writes via `json.dumps(geojson, ensure_ascii=False)` — standard JSON escaping, not hand-built. `body-layer`'s `belief/enrichment.py` renders the name only inside plain f-strings (`f"on {label}"`, `f"near {label} ({distance_m:.0f}m)"`) — Python f-string interpolation of a *value*, not of a format string the attacker controls, so no format-string injection is possible regardless of content. No sink found that treats the name as SQL, shell, or a Lua string built by concatenation; `aircraft_client.push_text_line`/the mission-bridge HTTP path are pre-existing, JSON-bodied, and unaffected by this diff. | None. |
| `_is_latin1_renderable` / `displayable_name` (body-layer, pre-existing) | Character-set narrowing | The ingest-side Latin-1 filter is *incidental* to security, not load-bearing for it — `body-layer/belief/enrichment.py::displayable_name` independently re-applies the identical `encode("latin-1")` check at render time (duplicated by design, documented in both docstrings, since the two subprojects don't share imports). Nothing downstream *depends* on the ingest-side filter alone; it's defense-in-depth for display correctness, and the real motivation (per the plan) is DCS overlay rendering, not an injection concern. | None. |
| `_ingest_node`/`_ingest_line`/`_ingest_area` — `tags={"name_source": ...}` construction | New reserved tag key | Confirmed the `tags` dict for a named node/dam/line/area is built fresh (`{"name_source": ...} if ... else {}`), never by spreading the raw OSM `tags` dict — so a hostile OSM tag literally named `name_source` cannot collide with or overwrite this key. `store/models.py`'s reserved-tag list has exactly one other reserved-key family (`inner_rings`/`landcover_class`/`adjacent_feature_ids`, ridge/valley), no name collision. Grepped for any code that enumerates `tags.keys()`/`tags.items()` across `src/`: none found that would break on an added key (`query/describe.py` only does targeted `.get()` lookups). | None. |
| `CLASSIFIER_VERSION = 5` bump + `osm_cache/models.py::cache_meta_matches` | Cache invalidation correctness | Verified independently, not just taken from the reviewer's note. `cache_meta_matches` does `all(getattr(stored, f) == getattr(expected, f) for f in _INVALIDATION_KEY_FIELDS)` — an equality check over every key field including `classifier_version`; any single mismatch is a full miss, there is no field-by-field partial reuse path. Checked the failure direction too: `load_cache_meta` returns `None` only on `path.exists() is False` (forces rebuild, correct); if the file exists but is missing a required meta key (unreadable/partially-written cache) it raises `ValueError` rather than returning a degraded/partial `OsmCacheMeta` — also forces the caller to fail or rebuild, never a silent partial serve. Fail-closed on both axes. | None. |
| `body-layer/src/belief/enrichment.py` docstring diff (in `main..fix/latin-place-names`) | Branch-divergence artifact, not feature code | This branch forked before `main`'s `4f44b2b` ("Point displayable_name at the upstream fix that shipped"), a doc-only commit made directly on `main` per the project's own non-code-cross-cutting-commit convention. Diffing against current `main` makes it look like this branch *removes* that commit's text; it's actually just pre-`4f44b2b` content on an older fork point. No logic in `displayable_name` differs between the two versions — comment-only. Will self-resolve on merge/rebase; not a security finding. | None (note for whoever merges: expect a trivial doc-only conflict in this docstring). |

### Performance note

Agreed with the dispatch brief's judgement: a per-feature `dict.get` + one `encode("latin-1")` call
is unmeasurable against a 25-30 minute ingest, and the only scaling-relevant question (does the
`CLASSIFIER_VERSION` bump force a full re-classify) is the correctness property covered above, not
a performance one. Nothing in the diff contradicts that.

### Verification run

From `world-model/` (worktree had no `.venv`; built one against the pinned tool versions in
`world-model/.venv`'s main checkout — `mypy 2.3.1`, `pytest 9.1.1`, `ruff 0.16.5`):

- `ruff format --check src tests` — 104 files already formatted
- `ruff check src tests` — all checks passed
- `mypy src` — no issues found in 62 source files
- `pytest tests -q` — 511 passed, 3 skipped

Matches the expected count from the dispatch brief.

### Verdict

APPROVED

No security-relevant finding. This is offline, build-time code on a single-user machine; the one
real surface (a third-party, community-editable OSM name string) reaches only parameterized SQL,
standard JSON serialization, and plain-value f-string interpolation downstream — no SQL/shell/Lua
construction by concatenation anywhere on the path. The new `name_source` tag cannot collide with
existing reserved keys or raw OSM tags. Cache invalidation is fail-closed in both the version-bump
and corrupt-cache directions.
