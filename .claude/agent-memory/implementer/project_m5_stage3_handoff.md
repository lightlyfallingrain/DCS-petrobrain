---
name: m5-stage3-handoff
description: M5 Stage 3 (elevation+surface_type probe) complete — all three live rungs ran, real store rebuilt; only the SRTM DEM tile is outstanding
metadata:
  type: project
---

M5 Stage 3 (`plans/m5-first-persistent-model/`) is **complete** on `feature/m5-first-persistent-model`
(2026-09-04). All three incremental-ladder rungs (smoke/121, ~500/441, full/1,681 points) ran live
against DCS via the `win-mac-sync/` round trip, were ingested and sanity-checked in turn
(commits `b534939`, `f363615`, `3834e85`, `ad85006`), and the real `latakia-20km.sqlite` was
rebuilt with the full probe grid wired in: **100% coverage, 1,681/1,681 cells for both `elevation`
and `surface_type`**. `land.getSurfaceType` is now a confirmed-working, DCS-authoritative source
for this install — three independent live runs returned bit-identical results for every
overlapping grid point (a real determinism finding, not just a repeat pass).

Full per-rung numbers, enum distributions, and `describe_position` spot-checks:
`world-model/research/2026-09-04-m5-stage3-smoke-rung.md` (one running note covering all three
rungs plus the final rebuild).

**What's still outstanding**: SRTM delta stats are `null` in the real store — `data/raw/dem/`
only has the Gemerek/M4 tile (`N39E036.hgt`), not one covering Latakia's envelope
(~35.0-35.5N, 35.85-35.95E, needs roughly `N35E035.hgt`). An automated fetch attempt was blocked
by sandbox network policy; per M4's own precedent this needs the *user* to manually fetch the
tile (viewfinderpanoramas.org, no-login). Once fetched, `build_world_model.py --srtm-tile <path>`
is a cheap rerun — the `ingest_probe`/`ElevationGrid.stats` SRTM code path is already implemented
and tested against a synthetic tile, no code changes needed.

**How to apply**: if the user later provides a Latakia-covering `.hgt` tile, just rerun the build
CLI with `--srtm-tile`; don't attempt another automated DEM fetch without checking whether network
policy has changed.
