---
name: project-m7-stage1-vector-layers
description: M7 Stage 1 (DCS-native vector layers, no elevation) implementation results
metadata:
  type: project
---

M7 Stage 1 (2026-09-05) wired `build_region`/CLI/validation for `syria-full` without running
the real build (per plan's Execution boundary — only the user runs it, on their own machine).

- `build_region`'s `osm_cache_path` was a **required** positional param before this stage (no
  absence handling, unlike `routes_path`/`probe_output_path`). Since M7 drops OSM entirely
  (clarification 2) and `syria-full` has no cache file at all, this was a real blocker the plan
  didn't call out explicitly under "Affected Modules." Fixed by making it optional with the
  same skip-not-error pattern, `BuildReport.osm_skipped`. **Why it matters**: when a plan lists
  affected files for one concern (SRTM wiring), check sibling required-parameter constraints
  the new region actually needs to satisfy — they don't always get named.
- The raw files Stage 1 needs (`towns.lua`, `beacons.lua`, `Syria.routes`) were **already
  locally staged on the Mac** from M5/Stage 0 — confirmed by `ls` before writing run
  instructions. They're whole-theatre files already (M5 finding), so Stage 1's real build may
  need zero new Windows/WSL round-trips, contrary to what "run on your Windows DCS machine"
  framing might suggest. Always check `data/raw/` for what's already there before assuming a
  fresh extraction step is needed in run-instructions docs.
- `parse_towns_lua`/`parse_beacons_lua` hard-fail unless given *exactly* 1,182/151 entries —
  this makes a real end-to-end `build_region` test with hand-written fixture files impossible;
  monkeypatch the parse functions instead (`monkeypatch.setattr("build.pipeline.parse_*", ...)`)
  to test `build_region`'s own wiring/branching logic, not the parsers (which have their own
  fixture tests already).
- Added a 4th coordinate control point (Aleppo) sourced from `beacons.lua`'s already-decoded
  `position` field (not a fresh live `coord.LOtoLL` probe — none available this session) cross-
  checked against SkyVector via WebSearch/WebFetch for the independent real-world ARP. Stayed
  non-circular (M1 Finding 2) since the beacon's own `positionGeo` was never used as the
  real-world reference. `beacons.lua`'s `position` field is a legitimate source for future
  control points when live-probe access isn't available.
- `src/` must never import `tests/control_points.py` — built a separate minimal
  `build.validate.SpotCheckPoint` (just name/x/z) for store-content sanity checks instead of
  reusing the test-only `ControlPoint` dataclass (which carries published real-world lat/lon,
  irrelevant to a store-content check).
