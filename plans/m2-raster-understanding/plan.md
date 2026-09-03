### Goal
Read Syria's `RasterCharts` archive (tile hierarchy, dimensions, scales, registration) and render a known DCS coordinate onto the resulting raster, per `ROADMAP.md` Milestone 2.

### Revision (2026-09-03, this session)

Three further investigator sessions ran since this plan was first written, all appended to
`world-model/research/2026-09-03-m2-rastercharts-recon.md` (sessions 2–4). They resolved the
Stage 0 format unknowns and changed the registration picture materially:

- **Tile format is confirmed**: 1280 DXT5/BC3-compressed DDS tiles, 1024×1024, 11 mipmaps,
  named `{32|64}m{sheet}{level}_x{0-7}_z{0-7}.tif.dds` (sheet ∈ {aa,ab,xab,xac}, level ∈
  {-2,-1,00,01}). No ED-proprietary image encoding — standard NVTT-built DDS, openable by any
  general-purpose DDS decoder (confirmed: Pillow works). This resolves the old "library choice
  open decision" — see Dependency Decision below.
- **`.sup5` remains unresolved** (only first 64 bytes inspected; confirmed as an ED
  `landscape5::sup5File`-tagged generic-serialization manifest, structure otherwise unknown) and
  is no longer the only candidate registration source.
- **A second, independent registration path opened**: the tiles are scans of a real-world
  1:250,000-class military/aeronautical chart (JOG-A-class, moderate confidence) covering
  central-eastern Turkey (Sivas/Erzincan provinces), carrying its own printed UTM grid
  (confirmed zone 37S). That grid is, in principle, sufficient to derive a pixel→WGS84 transform
  via `pyproj` independent of any DCS-internal metadata — but no sampled tile yet has an
  unambiguous full-precision grid label, so it isn't executable yet from what's decoded so far.
- **This raster is scanned real-world cartography, not DCS-rendered or satellite imagery** —
  it feeds only DCS's F10 "paper map" mode (confirmed distinct from satellite-mode and the
  engine-only 3D-rendered map, per user domain knowledge, session 4). This raises a scope
  question about whether this asset belongs in a DCS-truth-first world model at all — see
  **Decisions Requiring User Input** below; this is flagged, not silently resolved.

The **Implementation Plan** below is rewritten accordingly. The old Stage 0 (probe-and-gate) is
done; a new gate now sits at Stage 1 (validate the registration hypothesis before writing
`registration.py` against it).

### Pre-Implementation Investigation (original, first session)

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

### Dependency Decision (this session)

**Add `pillow` to `world-model/pyproject.toml` as a real (non-dev) dependency.** Tile decoding is
not incidental tooling here — reading RasterCharts pixel content is the core of what M2 does, so
the decoder belongs with the pipeline, not scratch/dev-only tooling. Pillow's built-in DDS plugin
(9.1+) already decoded all 5 DXT5 samples this session with no extra native deps, which is the
simplest option that satisfies the confirmed format — no need for `rasterio`/GDAL weight for a
plain DXT5 DDS tile set. Record this in `world-model/CLAUDE.md`'s Tech stack section alongside
the M1 `pyproj` entry once implemented.

### Affected Modules / Files

- `world-model/tools/wsl/probe_syria_rastercharts.sh` — done (Stage 0 ran). May need a follow-up
  variant if the full `.sup5` dump (see Stage 2 fallback) or additional margin-tile sampling is
  needed — extend rather than replace.
- `world-model/data/raw/dcs/2026-09-03/` — already holds Stage 0 probe output (zip listing,
  5 sample `.tif.dds` tiles, `.sup5` hex dump). Gitignored; more samples may be added here by
  follow-up probes.
- `world-model/research/2026-09-03-m2-rastercharts-recon.md` — append Stage 1 validation findings
  (registration hypothesis confirmed/refuted, UTM-grid cross-check result if attempted) once run.
- `world-model/pyproject.toml` — add `pillow` as a real dependency (see Dependency Decision above).
- `world-model/tools/decode_raster_tile.py` — new. Promotes this session's ad hoc
  `.venv`-only Pillow decode (DDS → PNG) from scratch code into a committed probe script, reusable
  for sampling further tiles (margin/corner tiles, additional sheets) without re-deriving the
  one-liner each time.
- `world-model/src/raster/__init__.py` — new. Public API mirroring `src/coordinates/`'s shape:
  `load_raster(theatre: str) -> RasterChart` (or per-tile loader, given this is a tile set, not
  one image), `dcs_to_pixel(theatre: str, x: float, z: float) -> tuple[TileId, int, int]`,
  `pixel_to_dcs(theatre: str, tile: TileId, px: int, py: int) -> tuple[float, float]`. Loader
  itself is now straightforward (format is known — Pillow open + filename parse into
  scale/sheet/level/x/z fields); the open question is registration, not decoding.
- `world-model/src/raster/registration.py` — new. Per-theatre registration parameters, structured
  like `coordinates/projections.py`'s dataclass-plus-`confidence` pattern (`source`,
  `confidence: Literal["provisional","confirmed"]`). **Do not write this file until Stage 1's
  registration-hypothesis validation (below) actually confirms or refutes the x/z-arithmetic
  hypothesis** — writing it against an untested arithmetic guess would be exactly the kind of
  unverified-DCS-internals claim this project's process exists to prevent.
- `world-model/tools/inspect_raster.py` — new, Mac-side. Human-inspectable diagnostic: dumps tile
  dimensions/format/grid layout, and (once registration exists) draws a marker for a given DCS
  coordinate — satisfies the concept doc's "Testing Philosophy" and directly delivers "render a
  known DCS coordinate onto the raster."
- `world-model/tests/test_raster_registration.py` — new. Control-point test: known DCS coordinate
  (reuse M1's Damascus/Latakia/Beirut control points, or Erzincan/Sivas if those turn out to be
  the actual anchors used in the empirical fit) maps to the correct approximate pixel location,
  with an explicit, documented error tolerance — mirrors `tests/test_coordinates.py`'s pattern.
- `world-model/CLAUDE.md` — record the Pillow dependency decision (Tech stack section) once
  implemented, same pattern as M1's pyproj entry.
- `world-model/ROADMAP.md` — flip M2 checkbox only once Stage 3 (render + control-point test)
  passes.

### Implementation Plan

1. **Stage 0 — done.** Probe ran; tile format confirmed (1280 DXT5 DDS tiles per the naming
   scheme above). Superseded as the active gate by Stage 1 below.

2. **Stage 1 — Validate the registration hypothesis (investigator, blocking; no pipeline code yet).**
   Before `registration.py` is written, confirm or refute the x/z-arithmetic hypothesis against
   real content — writing registration code against an untested arithmetic guess is exactly the
   unverified-DCS-internals situation this project's process exists to prevent. Concrete steps
   (`investigator`, using `tools/decode_raster_tile.py` from this plan and ad hoc scripts, output
   appended to the research doc, not committed as pipeline code):
   - Decode a small set of additional tiles beyond the 5 already sampled, prioritizing sheet
     corner/margin tiles (`x0_z0` across other sheets, `x7_z*`/`x*_z7`) — margin tiles are the
     most likely place to find a full-precision UTM grid label or a legend/title block.
   - **Primary path**: pick one visible feature with a well-known real-world WGS84 location (e.g.
     Erzincan VOR/DME/NDB, or Sivas city center — both already identified on sampled tiles), look
     up its published coordinates, locate its approximate pixel position by inspection, and
     combine with the x/z-arithmetic hypothesis (32m/64m ground sample distance × tile index) to
     produce a candidate affine. This reuses M1's control-point methodology directly and does not
     require disambiguating the UTM grid's truncated labels — treat it as the primary route since
     it's executable today.
   - **Secondary/cross-check path**: if a margin tile yields an unambiguous full-precision UTM
     label, independently derive a transform straight from the chart's own printed grid via
     `pyproj` (zone 37S), and compare it against the primary path's result. Agreement within a
     documented tolerance upgrades both to higher confidence; disagreement is a serious flag worth
     surfacing before continuing, not silently averaging.
   - If both paths fail or disagree badly, fall back to the full `.sup5` byte dump (reproducible
     test already documented in the research doc's session 2) — walk it as a
     length-prefixed-string-plus-fields record stream, searching for embedded tile-name substrings.
   - Append findings to `world-model/research/2026-09-03-m2-rastercharts-recon.md` before proceeding.

3. **Stage 2 — Minimal working version: loader + registration.** Once Stage 1 confirms a working
   hypothesis:
   - `src/raster/__init__.py`: Pillow-based loader, tile enumeration by parsed filename fields
     (scale, sheet, level, x, z). Straightforward now that the format is known.
   - `src/raster/registration.py`: implement whichever path Stage 1 validated, `confidence`
     matching what was actually established (`"provisional"` for the empirical-fit path unless/
     until cross-checked; `"confirmed"` only if read directly from a resolved `.sup5` field or
     an unambiguous chart-grid label), `source` citing the exact tiles/features used.
   - Add `tools/inspect_raster.py`'s dimension/format/grid-layout dump as the first diagnostic.

4. **Stage 3 — Validate: render a known coordinate onto the raster.** Add `tests/test_raster_registration.py` with a control-point test (pixel-space error tolerance, documented). Extend `tools/inspect_raster.py` to draw a marker (e.g. a small crosshair) at the pixel location for a given DCS coordinate and save a PNG — this is the concrete "render a known DCS coordinate onto the raster" deliverable, and the primary human-inspectable diagnostic per the concept doc's Testing Philosophy. Run `ruff format`/`check`, `mypy --strict`, `pytest` before considering this stage done.

5. **Stage 4 — Refine.** Extend `inspect_raster.py` to show the full multi-sheet/multi-level tile layout and confirm the rendering step correctly picks the right tile(s) for a given coordinate (including choosing a sensible default `level` when more than one exists at the same sheet/x/z, per session 2's unresolved "what does level mean" question). If registration was empirically fit, add a held-out third control point as an independent accuracy check and report the residual, same spirit as M1's error report.

6. **Close out.** Update `world-model/CLAUDE.md` (Pillow dependency, registration approach), flip `ROADMAP.md` M2 checkbox, update the recon research file with final confirmed findings.

### Risks & Unknowns

- **The x/z-arithmetic registration hypothesis is still unconfirmed against actual pixel content** — it's arithmetically self-consistent (order-of-magnitude match to Syria's known extent) but has not been checked against a real feature or the UTM grid. Stage 1 exists specifically to close this before any registration code is written.
- **`.sup5`'s deeper structure remains unread** (only first 64 bytes inspected) — it may still hold an explicit registration table that would obsolete the empirical-fit path entirely. The full-dump fallback in Stage 1 stays available if the empirical/UTM paths fail or disagree.
- **The UTM-grid cross-check path depends on finding a tile with an unambiguous full-precision grid label**, which none of the 5 samples so far provide — if margin/corner tiles also fail to show one, this path stays unavailable and the plan leans entirely on the empirical known-feature fit, with correspondingly lower achievable confidence (`"provisional"`, likely indefinitely, absent a held-out third point).
- **Chart-series identification (JOG-A-class) is pattern-matched, not confirmed against a primary spec** — this doesn't block registration (which doesn't depend on knowing the exact series name) but could matter if grid-interval or false-easting/northing assumptions differ from a standard JOG-A sheet.
- **No community prior art confirmed** (weak negative finding, GitHub code search was blocked in the first session) — worth a follow-up targeted GitHub search (via `gh` CLI, authenticated) before committing significant further effort to from-scratch reverse-engineering, if Stage 1's paths both prove difficult.
- **Syria's simple single-archive layout may not generalize** to Caucasus or other tiled theatres. M2 is scoped to Syria only (per ROADMAP), but `src/raster/` should avoid hardcoding single-sheet/single-level assumptions where cheap to avoid, so a later multi-theatre pass isn't a rewrite.
- **Scope tension: this raster is scanned real-world cartography (Turkish JOG-A-class chart), not DCS-authoritative geometry** — see Decisions below. Building `registration.py` against it means the world model would carry a raster layer whose own internal geodesy is real-world, corrected only by an empirical link to DCS x/z, rather than DCS-generated data being augmented by it. This doesn't violate "DCS geometry is authoritative" in the literal sense (nothing here overrides DCS truth — vector features stay DCS/OSM/DEM-derived) but it is a data-provenance category the invariant wasn't written with in mind, and needs explicit sign-off rather than being folded silently into "external GIS augmentation."

### Decisions Requiring User Input

- **Scope/provenance tension (flagged, not resolved here):** root `CLAUDE.md` says DCS geometry is
  authoritative and external GIS augments but never overrides. A scanned real-world military chart
  is neither DCS-internal geometry nor a typical "external GIS augmentation" source like OSM/DEM —
  it's DCS's own shipped asset, but its content is independently-surveyed real-world cartography of
  a place (central-eastern Turkey) offset from where DCS's simulated "Syria" theatre puts it,
  registered only by an empirical link back to DCS x/z. Two reasonable framings exist and
  `CLAUDE.md` doesn't decide between them:
  1. Treat it as a legitimate third provenance category ("DCS-shipped but real-world-sourced
     raster") — proceed with M2 as planned, document the category explicitly in
     `registration.py`'s provenance fields, and revisit `docs/concept/WORLD_MODEL_BUILDER.md`'s
     provenance taxonomy later to name it properly.
  2. Reconsider whether decoding/registering this specific raster belongs in the World Model
     Builder's current scope at all — it doesn't feed the "truth" layer (roads/settlements/terrain
     already come from DCS extraction + OSM/DEM per the M3 plan) so much as it enables a *future*
     capability (rendering the F10 "paper map" for kneeboard-style output), which may be more of a
     Mission Interpreter / Petrobrain Runtime concern than a World Model Builder one.
  Recommend deciding before Stage 1 proceeds, since it determines whether Stage 1's investigation
  effort is worth spending now or should wait until that future capability is actually scoped.
- Once Stage 1's registration path is confirmed, `registration.py`'s `confidence` value and
  `source` citation need to accurately reflect which path (empirical-fit vs. UTM-grid vs. `.sup5`)
  was actually used — do not default to `"confirmed"` for an empirical fit just because it looks
  plausible.
