# WM-B16 — Incremental per-layer pipeline builds

Promoted to an entry by the 2026-10-09 conversion of `world-model/ROADMAP.md`, on the same
reasoning as [[WM-B15]]: a prose bullet in the Backlog section with no checkbox and no ID, but a
distinct outstanding action rather than orientation prose. It takes the next unused number in the
`WM-B<n>` space that section's own preamble declares. The `[ ]` marker and its `#status/open` tag
are the only text the conversion added to the source line.

- [ ] **Incremental per-layer pipeline builds.** #status/open `build_region` deletes and recreates the entire `.sqlite` on every call, forcing a full rebuild of all layers each time. Wanted: run individual pipeline sections (roads only, elevation only, validation only) and *add* that data into an existing store — staged builds, partial re-runs when debugging a single layer. Raised during WM-M7 DoD acceptance testing (2026-09-06), explicitly considered for WM-M8 and dropped from it to keep that milestone scoped to the probe store. WM-M9 (OSM) would also benefit — see `plans/m9-osm-geofabrik/plan.md` design decision 4. See `plans/m7-full-theatre-pipeline/` and `src/build/pipeline.py`'s `build_region`.
