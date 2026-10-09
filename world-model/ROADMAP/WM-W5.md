# WM-W5 — `feature/multi-theatre-afghanistan` — Afghanistan projection live-confirmed

- [x] **`feature/multi-theatre-afghanistan` — Afghanistan projection live-confirmed 2026-10-05.** #status/done
  The user ran `coord_probe.lua` on the Afghanistan terrain (map origin + 29 airbases). The beacon
  fit was off by a uniform 0.051 m everywhere; three unplaced FOBs that DCS reports at lat/lon 0,0
  sit at exactly x=-3759657, which pins the false northing. With round `false_easting=-300150`,
  `false_northing=-3759657` the worst residual is under 1 mm, and `confidence` is now `"confirmed"`
  (`world-model/research/2026-10-05-afghanistan-projection-live-check.md`). The 5 cm change does
  not warrant a rebuild of `afghanistan-full.sqlite` (500 m grid). The probe output
  (`data/raw/dcs/2026-10-05/coord_probe_output.json`, gitignored) holds 26 real airbase
  positions, the seed for widening airfields beyond the 7 beacon-derived ones; the three FOBs at
  0,0 have no real position and must be filtered. Block 2 (Bagram sortie) remains optional.

  **Performance Reviewer finding #3 — fixed, merged 2026-10-05 (`feature/terrain-tile-region-filter`,
  merge `6867903`).** The terrain-semantics (ridge/valley) stage used to process every `.hgt` tile
  staged in `--srtm-dir` (288 for this build, 158 needed; 44.0 of 82 min). `build.ingest_terrain.
  tiles_for_region` now keeps only tiles within the ~1.8 km processing margin of the region's DCS
  x/z rectangle: 160 of 288 on the real Afghanistan staging, a superset of all 158 grid tiles.
  Staging a bounding rectangle of tiles for Kola/Caucasus is therefore fine. First rebuild of any
  theatre resets its terrain cache once (the cache key hashes the tile list). Reviewer:
  `plans/terrain-tile-region-filter/review.md` (APPROVED; two optional refinements recorded there —
  a pipeline-level wiring test, and a note that a kept tile's far out-of-region overhang can now be
  neighbour-starved, truncating geometry that was already out of scope). Merged on user direction
  after review, no DoD pass.
