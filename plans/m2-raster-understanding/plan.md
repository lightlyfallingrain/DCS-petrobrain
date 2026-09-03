### Goal
Read Syria's `RasterCharts` archive (tile hierarchy, dimensions, scales, registration) and render a known DCS coordinate onto the resulting raster, per `ROADMAP.md` Milestone 2.

### Pre-Implementation Investigation (done this session)

Invoked `investigator` before finalizing this plan — M2 depends entirely on unverified DCS-internals claims (RasterCharts file format, tile hierarchy, registration scheme). Findings written to `world-model/research/2026-09-03-m2-rastercharts-recon.md` (staged). Summary:

- **Location confirmed** (reproduced-locally, from M0's real `DCS-files.txt` listing of the installed DCS 2.9.29.27278 tree): `Mods/terrains/Syria/RasterCharts/` contains exactly two files — `rasterCharts.zip` and `rasterCharts.sup5`. No scale-tiered subdirectories. Afghanistan, Kola, MarianaIslands match this pattern; **Caucasus does not** — it has a genuine `{0.25M,0.5M,1M,2M,5M}/` tile-pyramid with many small per-tile zips. Syria is the simple case among theatres seen; the pipeline must not assume this generalizes to a tiled theatre later.
- **Unresolved, genuine gaps (not yet probed against the live install):**
  - What's inside `rasterCharts.zip` — tile image format (DDS/TIF/JPG/other), filenames, whether it's one large image or many tiles in a flat archive.
  - What `.sup5` is — likely an index/manifest by file-size/sibling-pattern inference only; a relevant ED forum thread exists but returned HTTP 403 to automated fetch this session, so unconfirmed either way. (A related-but-distinct `.surface5` terrain-mesh format exists elsewhere — do not conflate.)
  - Whether **any georeferencing/registration metadata exists at all** (world file, embedded extent, sidecar, or something readable inside `.sup5`). If none exists, registration must be empirically fit the same way M1 fit the coordinate transform — against known DCS x/z control points (reusing M1's three ARP control points) — rather than read from a stated scale/origin.
  - No open-source community tool was confirmed to parse `RasterCharts` directly (weak negative finding — GitHub code search was blocked this session, only plain web search was done). Treat M2 as first-of-its-kind work for this pipeline, unlike M1 where pydcs gave a strong starting hypothesis.
- **Confirmed:** reading RasterCharts needs only read-only filesystem access — no live-mission Mission Scripting escape hatch required (unlike M1's `coord.LOtoLL`). This is a WSL filesystem probe, the same class as M0/M1's Lua probes.
- **Probe script already written, staged, not yet run:** `world-model/tools/wsl/probe_syria_rastercharts.sh` — lists `rasterCharts.zip` contents (`unzip -l`), hex-dumps the first 64 bytes of `rasterCharts.sup5`, extracts up to 5 sample entries into `wsl-output/` for local format inspection. Read-only against the DCS install.

Because the tile format and registration scheme are still unknown, this plan is staged: **Stage 0 is a required, user-run probe step that gates everything after it.** The implementation stages below branch on what that probe reveals rather than assuming a specific format up front.

### Affected Modules / Files

- `world-model/tools/wsl/probe_syria_rastercharts.sh` — already written (investigator, staged). No change needed unless Stage 0 results require a follow-up probe (e.g. deeper `.sup5` inspection).
- `world-model/data/raw/dcs/<date>/` — gitignored destination for probe output (zip listing, sample tile files, `.sup5` bytes) once synced back from `win-mac-sync/wsl-output/`.
- `world-model/research/2026-09-03-m2-rastercharts-recon.md` — update with Stage 0 findings (tile format confirmed, `.sup5` purpose resolved or still open, registration metadata present/absent) once the probe runs.
- `world-model/src/raster/__init__.py` — new. Public API mirroring `src/coordinates/`'s shape: something like `load_raster(theatre: str) -> RasterChart`, `dcs_to_pixel(theatre: str, x: float, z: float) -> tuple[int, int]`, `pixel_to_dcs(theatre: str, px: int, py: int) -> tuple[float, float]`. Exact shape depends on Stage 0 findings (single image vs. tile set) — finalize signatures once format is known, don't lock them in this plan.
- `world-model/src/raster/registration.py` — new. Per-theatre registration parameters, structured like `coordinates/projections.py`'s dataclass-plus-`confidence` pattern (`source`, `confidence: Literal["provisional","confirmed"]`). If no metadata is found inside the archive, this file holds the empirically-fit affine/scale parameters instead of read-from-file ones — the confidence field is what distinguishes the two cases honestly.
- `world-model/tools/inspect_raster.py` — new, Mac-side. Human-inspectable diagnostic: dumps raster dimensions, format, tile layout, and (once registration exists) draws a marker for a given DCS coordinate — satisfies the concept doc's "Testing Philosophy" (visual diagnostics per stage) and directly delivers "render a known DCS coordinate onto the raster."
- `world-model/tests/test_raster_registration.py` — new. Control-point test: known DCS coordinate (reuse M1's Damascus/Latakia/Beirut control points) maps to the correct approximate pixel location, with an explicit, documented error tolerance — mirrors `tests/test_coordinates.py`'s pattern.
- `world-model/pyproject.toml` — add whatever raster/image library Stage 1 settles on (see Decisions below — not yet chosen, depends on tile format).
- `world-model/CLAUDE.md` — record the raster-library decision once made (same pattern as M1's pyproj entry).
- `world-model/ROADMAP.md` — flip M2 checkbox only once Stage 3 (render + control-point test) passes.

### Implementation Plan

1. **Stage 0 — Run the probe (user, blocking).** Deploy `probe_syria_rastercharts.sh` per `WORKFLOW.md`: copy into `win-mac-sync/run-wsl/`, run in WSL with `DCS_INSTALL_PATH` set, sync `wsl-output/` back, copy the report + sample files into `world-model/data/raw/dcs/<date>/`. This resolves the format/hierarchy/`.sup5` unknowns and is a hard prerequisite — do not write parsing code against a guessed format.

2. **Stage 1 — Minimal working version: read and enumerate.** Once Stage 0 confirms the tile format:
   - If it's a standard raster format (DDS/TIFF/JPG/PNG) openable by an existing Python library (Pillow, rasterio, or a DDS-specific reader if needed), write `src/raster/__init__.py`'s loader against that library — prefer the simplest option that opens the format; don't add `rasterio`/GDAL weight if Pillow suffices for a single large image.
   - If it's a single large image: loader returns one `RasterChart` (image + pixel dimensions). If it's a flat set of tiles: loader enumerates them and records naming/index pattern (mirrors Caucasus's apparent `AA00`-style grid code, if Syria's archive turns out to follow something similar internally even without top-level subdirectories).
   - No registration yet at this stage — just prove the archive can be opened and its raw structure inspected. Add `tools/inspect_raster.py`'s dimension/format dump as the first diagnostic.

3. **Stage 2 — Registration.** Branches on Stage 0's finding:
   - **If georeferencing metadata exists** (inside `.sup5`, embedded in image metadata, or a sidecar): parse it directly into `registration.py`, `confidence="confirmed"` (documented, not inferred), `source` citing the exact file/field.
   - **If no metadata exists**: empirically fit registration the same way M1 fit the coordinate transform — take 2+ known DCS x/z control points (reuse M1's Damascus/Latakia/Beirut, since their DCS-native x/z are already established and `confidence="confirmed"`), locate their approximate pixel position on the raster by visual inspection (a human step, likely done once by the user via `inspect_raster.py`'s dump), and fit a scale+offset (or affine, if there's rotation) transform. `confidence="provisional"` until cross-checked against a third point not used in the fit.
   - Either way, this stage produces `dcs_to_pixel`/`pixel_to_dcs` and is the first point at which a spatial-library decision might matter (e.g. if an affine fit needs a proper `Affine`/`GDAL`-style transform object) — record that choice in `world-model/CLAUDE.md` when made, same pattern as M1's pyproj entry.

4. **Stage 3 — Validate: render a known coordinate onto the raster.** Add `tests/test_raster_registration.py` with a control-point test (pixel-space error tolerance, documented). Extend `tools/inspect_raster.py` to draw a marker (e.g. a small crosshair) at the pixel location for a given DCS coordinate and save a PNG — this is the concrete "render a known DCS coordinate onto the raster" deliverable, and the primary human-inspectable diagnostic per the concept doc's Testing Philosophy. Run `ruff format`/`check`, `mypy --strict`, `pytest` before considering this stage done.

5. **Stage 4 — Refine.** If Stage 0 revealed multiple tiles/scales rather than a single image, extend `inspect_raster.py` to show the full tile layout and confirm the rendering step correctly picks/stitches the right tile(s) for a given coordinate. If registration was empirically fit (Stage 2's second branch), add the held-out third control point as an independent accuracy check and report the residual, same spirit as M1's error report.

6. **Close out.** Update `world-model/CLAUDE.md` (raster/registration library decisions), flip `ROADMAP.md` M2 checkbox, update the recon research file with final confirmed findings if anything changed since Stage 0.

### Risks & Unknowns

- **Format is genuinely unknown until Stage 0 runs** — Stage 1's library choice, and possibly the whole shape of `src/raster/`, cannot be finalized before that. This plan intentionally leaves those signatures loose rather than guessing.
- **`.sup5` may or may not hold registration data.** If it turns out to be a proprietary ED chart-renderer format (not a plain manifest), the empirical-fit fallback (Stage 2, second branch) becomes the only path — worth confirming Stage 0's `.sup5` hex dump and forum-thread content (try a non-automated fetch of `forum.dcs.world/topic/226463-`) before assuming it's a dead end.
- **No community prior art confirmed** (weak negative finding, GitHub code search was blocked this session) — unlike M1, there's no known parameter/approach to fall back on if Stage 0/2 prove difficult. Worth a follow-up targeted GitHub search (via `gh` CLI, authenticated) before committing significant effort to a from-scratch binary-format reverse-engineering path, if `.sup5`/zip contents turn out to be non-trivial.
- **Syria's simple single-archive layout may not generalize** to Caucasus or other tiled theatres. M2 is scoped to Syria only (per ROADMAP), but `src/raster/` should avoid hardcoding "one image per theatre" assumptions where cheap to avoid, so a later multi-theatre pass isn't a rewrite. Do not over-engineer for tiling now — just don't paint into a single-image-only corner.
- **Empirical registration fit (if needed) inherits M1's ~1.0-1.3 km DCS-vs-real-world control point residual** — that's fine for DCS-native x/z-to-pixel fitting (control points are DCS-native, not real-world-ARP-based, so this residual doesn't directly enter), but if real-world/OSM overlay is eventually checked against the raster too (M3), expect the same order of displacement and don't misattribute it to a raster registration bug.

### Decisions Requiring User Input

- Confirm it's acceptable to gate this plan on Stage 0 (user runs the probe script per `WORKFLOW.md`) before any raster-parsing code is written, rather than speculatively implementing against a guessed format (e.g. assuming DDS) — consistent with how M1 staged provisional-vs-confirmed work, but M2 has no fallback "provisional" parameters to implement against in the meantime since the format itself is unknown, not just unverified.
- Once Stage 0 results are in, the raster/image library choice (Pillow vs. rasterio/GDAL vs. a DDS-specific reader) will need a quick decision — flagging now that this is still open and will come back for confirmation rather than being silently picked.
