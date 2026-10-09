# WM-W7 — Road-junction detection memory fix

- [x] **Road-junction detection memory fix (no M-number — a bug fix on WM-M10, not a milestone; done,
  merged 2026-09-13).** #status/done A real `syria-full` rebuild (with WM-M9's OSM roads folded into the DCS
  `road` layer) died at Stage 5 ("road junctions") with a silent OOM-kill after OSM ingest
  completed. Root cause: WM-M10's junction detector (`roadnet.junctions.extract_clusters` +
  `ingest_junctions.ingest_junctions`) bulk-loaded the entire combined `road` feature layer
  into one Python list before clustering — a size (~500K+ vertices at `syria-full` scale with
  OSM) that the pipeline had never actually run against, only extrapolated for. Fixed: spatial
  chunking reuses WM-M8's existing chunk lattice (`store/chunks.py`), walking the theatre in 5 km
  tiles, querying padded-bbox per tile (`padding_m = max(tolerance_m * 10.0, 10.0)` = 10 m at
  defaults), clustering only within that tile's padded extent, keeping only clusters whose
  centroid falls in the tile's unpadded core (centroid-in-core ownership — no double-count,
  guaranteed exhaustive coverage). `roadnet/junctions.py` gains an additive, opt-in
  `vertex_bbox` parameter; `ingest_junctions` (bulk) is untouched; new
  `ingest_junctions_streaming` generator walks chunks. Planning deviation (discovered during
  implementation): region nominal bbox does not include all stored road features; fixed with
  new `feature_layer_bbox(conn, kinds)` MIN/MAX aggregate for actual data extent. Post-merge
  verification: all 341 tests pass (333 pre-existing + 8 new streaming/boundary/memory-bound
  tests), no regressions. Reviewer independently validated chunking correctness against
  `latakia-20km.sqlite` and confirmed the deviation's fix (MIN/MAX query prevents silent
  skipping of roads outside region bbox). Wall-clock time for Stage 5 may increase (roads
  are re-fetched once per chunk that overlaps them) but completion instead of OOM is the
  fundamental win. **Follow-up validation now done:** the user's `syria-full` rebuild of
  2026-09-15/16 completed Stage 5 in 2,885 s over 24,600 chunks (8,732 junctions kept) with no
  OOM — the fix holds at full theatre scale. That run also exposed a separate problem the
  streaming fix does not address: a handful of chunks take 330+ s each (~28 of the 48 minutes),
  with nothing logged during a single slow chunk and a badly swinging ETA. Filed to
  `todo/todo.md`. See `plans/junctions-streaming-fix/plan.md`,
  `plans/junctions-streaming-fix/review.md`, `plans/junctions-streaming-fix/dod-check.md`,
  and `plans/junctions-streaming-fix/implementation.md`.

This subproject's Backlog section carried its own record of the same fix, as a resolved prose
bullet rather than a checkbox item. It is folded in here verbatim rather than minted as a separate
backlog ID: the two records agree on every fact (a bulk-load OOM at `syria-full`-plus-OSM scale,
fixed by `junctions-streaming-fix`, merged 2026-09-13, chunked output proven byte-identical to the
bulk path), and minting a second permanent ID for one piece of work is exactly what
`plans/obsidian-links-and-tags/plan.md` rules out. Neither copy was dropped, because each holds
material the other does not — the Status record above has the implementation and post-merge
verification detail, the backlog record below has how the problem was raised during the OSM
streaming-ingest memory audit. Its original no-checkbox bullet form is preserved; the conversion
minted no marker for it.

- **RESOLVED: `roadnet/junctions.py` memory issue at `syria-full`+OSM scale (2026-09-13).**
  Raised 2026-09-12 during the OSM streaming-ingest memory audit (`plans/osm-streaming-ingest/plan.md`
  addendum): WM-M10's bulk-load approach (`store.reader.all_features`) failed in practice when that
  `"road"` layer grew to include both DCS `.routes` and OSM `highway` ways (~500K vertices at
  theatre scale), causing a silent OOM-kill of the actual `syria-full` rebuild at Stage 5.
  **Fixed by junctions-streaming-fix (merged 2026-09-13):** spatial chunking walks the theatre
  in 5 km tiles with padded-bbox queries and centroid-ownership filtering, keeping peak
  vertex memory bounded to one tile's content instead of the whole layer. Correctness validated:
  synthetic and real-store (`latakia-20km`) tests prove chunked path produces byte-identical
  output to bulk path; Reviewer independently verified against real data. User's next real
  `syria-full` rebuild is the natural follow-up to confirm end-to-end completion (expected
  to complete, wall-clock time for Stage 5 may increase due to per-chunk road re-fetching).
