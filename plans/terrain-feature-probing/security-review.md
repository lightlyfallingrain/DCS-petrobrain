## Security Deep Analysis: terrain-feature-probing (watershed basins)

Branch `feature/terrain-landform-features`, tip `7329ec3`. Range reviewed: `63916e1..7329ec3`.

### Dependency Status

First non-pyproj/pillow/osmium additions to world-model: `numpy>=1.26,<2.5` and `scipy>=1.11`,
scoped to `terrain/curvature.py`'s two functions (`scipy.ndimage.uniform_filter`/`minimum_filter`
for landform smoothing and basin-seed detection; basin growth and geometry extraction stay stdlib).
No CVE found affecting numpy 1.26-2.4.x or scipy >=1.11 in this usage pattern (no
pickle/deserialization, no network, no untrusted file format reaching numpy/scipy directly). The
`<2.5` ceiling is a mypy-stub-compatibility pin (numpy 2.5's bundled stubs use PEP 695 syntax mypy
rejects under `python_version = "3.11"`), not a security pin — it is the kind of pin that could
someday block a patched release, but there is no live advisory today that it does. Worth a glance
whenever that ceiling is revisited, not a blocker now.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `src/terrain/curvature.py` (smooth_grid/find_basin_seeds) | numpy/scipy ops over elevation grid | Grid size bounded by theatre extent (~2.5M cells, same bound the removed per-cell classifier already worked over) — no new resource-exhaustion surface. Gap-aware by construction (unsampled cells excluded via mask/`+inf`, never fabricated). | None |
| `src/terrain/features.py` grow_basins | hand-written heapq priority flood | O(n log n) over the same bounded grid; serial by design, not vectorizable, documented as such. No externally-controlled size input. | None |
| `src/terrain/features.py:511-521` `_build_component` | hard `ValueError` on <2-point multi-cell component | Belt half of a two-part fix for a rounding-tie defect the reviewer caught (`_round_half_away_from_zero` is the other half, at the source). Fails closed. | None |
| `src/store/writer.py:insert_features` | new `ValueError` guard, <2-point LineString/Polygon | Runs inside the same function that performs the whole-batch INSERT/R*Tree transaction — raising aborts the entire call, not just the bad row. Not triggerable by ordinary data; only a geometry-math defect upstream could produce the input, and that path is independently guarded at the source too. Confirmed fail-closed. | None |
| `tools/inspect_terrain.py` `_resolve_center`/SQL | parameterized `?` query against user-supplied `--near NAME` | Local diagnostic tool, user's own built sqlite, parameterized query — no injection surface. Not part of the pipeline. | None |
| `src/elevation/dem.py` | SRTM `.hgt` binary parsing | **Not touched by this feature** (no diff in this range) — pre-existing, already fails closed: filename regex validated, `ValueError` on non-square byte length, void-sample (`-32768`) raises rather than interpolating garbage. Threat model: user-downloaded files from viewfinderpanoramas.org on their own single-user machine, not a remote-attacker surface. Noted for completeness per the dispatch brief; no finding against this feature. | None |

### Verdict

APPROVED

No confirmed exploitable vulnerabilities, no probable risks, no new secrets/network/auth surface.
This is an offline, single-user, local-build pipeline change; the grid-size bound, the fail-closed
geometry guards, and the clean dependency-advisory check together leave nothing to escalate to the
user as a risk decision.
