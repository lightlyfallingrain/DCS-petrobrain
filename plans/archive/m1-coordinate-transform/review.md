### Review Summary

Reviewed the M1 coordinate-transform implementation on `feature/m1-coordinate-transform` (all files staged, not committed) against `plans/m1-coordinate-transform/plan.md`, `plans/m1-coordinate-transform/implementation.md`, root/`world-model/CLAUDE.md`, and the two research notes.

The Implementer deviated from the plan's original "provisional now, confirm-later" staging because Stage 3 (Windows-side live-install probe) had already completed before implementation started, with the parameters reproduced to 0.00–0.03m against live `coord.LOtoLL` (226 points). This is a reasonable and well-documented deviation — `implementation.md` states the reason plainly, and the underlying evidence in `world-model/research/2026-09-03-m1-coordinate-transform-verification.md` genuinely supports going straight to `confidence="confirmed"` rather than papering over it.

Ran all four required checks myself from a fresh shell (not trusting the implementer's claim):
- `ruff format --check src tests` — pass (4 files already formatted)
- `ruff check src tests` — pass (all checks passed)
- `mypy --strict src` (per `world-model/CLAUDE.md`'s documented command) — pass, 2 source files
- `mypy --strict src tests tools` (full tree, exercising the new `mypy_path` config) — pass, 5 source files
- `pytest tests -q` — pass, 5 passed

Also ran `tools/report_control_point_errors.py` directly and cross-checked its output against the research note's table — transformed lat/lon and error-in-meters match exactly (Damascus 1137.5m, Latakia 1314.5m, Beirut 962.8m), confirming the control points and the code are self-consistent and not just plausible-looking.

**Module boundaries**: coordinate math is confined entirely to `src/coordinates/` (`projections.py` for the per-theatre parameter registry, `__init__.py` for the theatre-agnostic `dcs_to_wgs84`/`wgs84_to_dcs` functions). No Syria-specific logic leaked into the transform functions themselves — a second theatre only requires a new `THEATRE_PROJECTIONS` entry, as the plan required. `tests/control_points.py`'s `haversine_distance_m` is correctly kept out of `src/coordinates` (it's an error-measurement helper, not a DCS↔WGS84 transform) — good call, matches the plan's module-boundary intent.

**Provenance/confidence**: `TmercParams.source` and `confidence` fields are populated and the `"confirmed"` label is earned — Finding 1 of the verification note reproduces live DCS `coord.LOtoLL` output for 226 points to 0.00–0.03m residual, which is a legitimate live-install cross-check, not a forum claim taken on faith. The `Confidence` type correctly retains `"provisional"` for future theatres not yet probe-verified.

**Control-point threshold (1500m)**: honestly justified, not papering over a bug. The research note's Finding 4 shows the ~1.0–1.3km residuals are non-systematic in direction/magnitude across the theatre (Damascus ΔN+440/ΔE−1050, Latakia ΔN+1310/ΔE+116, Beirut ΔN−943/ΔE−200) — inconsistent with a projection-parameter defect (which Finding 1 already rules out directly via the 0.00–0.03m live-probe match) and consistent with per-airport terrain-art placement error. The test's inline comment states the measured values and explains the threshold leaves comfortable margin without masking a regression an order of magnitude larger (the prior ~327km wrong-axis-order failure mode is cited as the contrast case). This is a defensible, evidence-backed threshold.

**No scope creep**: no M2 raster work snuck in. `.venv` is correctly gitignored (`world-model/.gitignore:8`) and not staged. No `world-model/data/` files staged.

**Circularity risk**: correctly caught and documented — Finding 2 of the verification note explicitly flags that `beacons.lua`'s `positionGeo` is DCS-internal-projection-derived, not independent, and the control points instead use externally-published ARPs (SkyVector/Navigraph), which is the right independent source per the plan's own circularity concern.

### Required Fixes

None.

### Optional Refinements

- `implementation.md` notes a Latakia residual discrepancy: `report_control_point_errors.py` prints 1314.5m while the research note states 1314.1m, attributed to "a slightly different z-precision source value." Both are well inside the 1500m threshold and the difference is noise-level, so this isn't a correctness bug — but the fact that two supposedly-identical DCS-native `z` values differ slightly between the two documents is worth a one-line note in `control_points.py` or the research note clarifying which source value is authoritative, so a future reader doesn't have to re-derive that it's benign. (optional)
- `_theatre_crs` in `src/coordinates/__init__.py` rebuilds a `CRS`/`Transformer` from the proj4 string on every call to `dcs_to_wgs84`/`wgs84_to_dcs`. Irrelevant at M1's scale (single-point, offline, test-only usage), but if M2+ starts calling these in a raster-registration loop over many points, consider caching the `Transformer` per theatre. Not a fix now — just flagging so it isn't rediscovered as a "surprise" perf issue later. (optional)

### Verdict

APPROVED
