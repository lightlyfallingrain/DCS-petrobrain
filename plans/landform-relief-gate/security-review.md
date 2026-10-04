## Security Deep Analysis: landform-relief-gate

### Dependency Status
No dependency change. `pyproject.toml` diff against `main` is empty; decimation reuses the
existing `geometry.simplify_polyline` (already present pre-branch, used elsewhere for OSM
geometry).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `terrain_cache/models.py:79` `cache_meta_matches` | cache invalidation | Exact per-field equality over `_INVALIDATION_KEY_FIELDS`, now including `min_relief_m`/`decimation_tolerance_fraction`. Verified independently (not just re-reading Reviewer's claim): a v1 meta table has no rows for either new key, `reader.load_cache_meta` returns `None` on the first missing `META_FIELDS` key (schema.py/reader.py both updated consistently), forcing a full rebuild rather than silently reusing a stale 8.1 GB ungated cache. `EXTRACTOR_VERSION` 1→2 is redundant belt-and-suspenders on top of this, not the only guard. | None |
| `terrain/features.py` `_decimate_for_storage` | geometric deviation guard | Checks **every** original sampled point against the **whole** decimated polyline (`distance_point_polyline`, not a windowed/support-slice proxy) and only returns the decimated geometry if all points are within `cap_m` (the same half-cell bound `_smooth_for_storage` already enforces); otherwise falls back to the full smoothed geometry. Direction is correct — a decimation that would exceed the bound is rejected, not silently accepted. The tip commit (`01a36c3`) is a ROADMAP wording fix only; the actual deviation-check code was unchanged by it and was already correct in the prior commit. | None |
| `terrain/features.py` `filter_by_relief` | input filtering | Pure function, no side effects, applied before features reach cache/store. Reduces, never expands, attack surface. | None |
| `tools/inspect_terrain.py` | rewritten CLI tool | Local developer tool, reads DEM files from a path given on the command line, writes a PNG to a path given on the command line — same trust model as the rest of the build tooling (operator-controlled args, not externally-supplied). No new risk. | None |

### Resource behaviour (point 3 of the brief)
No state accumulates across tiles — `filter_by_relief`/`to_stored_features`/
`_decimate_for_storage` are pure per-call functions, called fresh per tile in `_process_tile`.

Tested `_decimate_for_storage` directly against degenerate inputs:
- 2000 collinear points → decimates to 2 points, <2ms.
- A 2-point line → short-circuits (`len(smoothed) < 3`), returned unchanged.
- An adversarial 5000-point alternating zig-zag (Douglas-Peucker's actual worst case, every
  point a local extremum) → no reduction, ~2.3s.

Douglas-Peucker is worst-case O(n²); the zig-zag case demonstrates it. This is **not a security
finding**: the input is SRTM DEM-derived, Chaikin-smoothed terrain geometry on an offline,
single-player, build-time pipeline the user runs on his own machine — there is no external or
adversarial party who controls tile content, and Chaikin smoothing structurally damps the kind of
extreme local alternation that triggers the worst case. Real traced lines are "tens to a few
hundred" cells per the function's own docstring, consistent with the already-reviewed performance
budget (~14 min / 1.75 GB peak for 131 tiles) and the dispatcher's framing that this change
strictly reduces work in that stage. Noting it for the record per the brief's instruction, not
blocking on it.

### Verification run (cwd `world-model/`, fresh `.venv` built from `pyproject.toml`)
- `ruff format --check src tests` — clean (116 files)
- `ruff check src tests` — all checks passed
- `mypy src` — success, 71 source files
- `pytest tests -q` — 539 passed, 3 skipped (matches expected)

### Verdict
APPROVED

No required fixes.
