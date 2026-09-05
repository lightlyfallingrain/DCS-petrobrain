---
name: project_m6_terrain_semantics
description: M6 terrain-semantics results — tuned thresholds, real row counts, and the checkerboard-noise validation finding
metadata:
  type: project
---

M6 (ridge/valley extraction, `world-model/src/terrain/`) shipped with stdlib-only discrete
Laplacian + connected-components + closed-form principal axis — no numpy/scipy escalation
needed, the plan's stdlib approach worked end to end.

**Tuned defaults** (`terrain/curvature.py`, `terrain/features.py`): `DEFAULT_CURVATURE_THRESHOLD_M
= 20.0`, `DEFAULT_MIN_CELL_COUNT = 6`. Stage 1's first guess (3.0/4) classified ~71% of interior
cells as ridge/valley on the real `latakia-20km` grid — a checkerboard, not lines. Real rebuild
at tuned defaults: `ridge=12, valley=12`.

**Key validation finding** (see `world-model/research/2026-09-05-m6-terrain-semantics.md`): even
at the tuned threshold, per-cell classification still shows checkerboard-pattern noise across the
region's mountainous quadrant — raising the threshold further (tested to 120m) reduces but never
eliminates it. The classifier reliably catches the single most dominant peak/trough in-bbox
(~200m agreement against an independent elevation source) but misses/misclassifies secondary
bumps and troughs. This reads as a genuine grid-resolution-vs-feature-scale ceiling (500m probe
spacing), not a threshold-tuning bug — record this finding, don't re-tune trying to "fix" it
without a denser probe or a smoothing pre-filter (both explicitly deferred, would need a new
live-probe run or numpy/scipy respectively).

**Test fixture gotcha**: synthetic curvature-classification unit tests must pass an explicit
`threshold_m` decoupled from `DEFAULT_CURVATURE_THRESHOLD_M` — a fixture whose curvature
magnitude happens to equal the production default breaks silently (strict `<`/`>` comparison)
the next time the default gets re-tuned. See [[feedback_decouple_fixtures_from_tuned_defaults]].

**Independent (non-DCS) elevation cross-check without a staged SRTM tile**: no SRTM tile covers
Latakia (only `data/raw/dem/N39E036.hgt`, the Gemerek/M4 tile, exists). The public
`api.open-elevation.com` API (via WebFetch, pipe-separated `lat,lon` locations in the query
string) gave a legitimate, non-circular external elevation reference for one-off spot-checking —
DCS elevation agreed within ~30m at every checked point. Not wired into the pipeline, just a
research-note validation aid; reusable next time a region has no staged DEM tile.

**Environment note**: the `Syria.routes` roadnet parse (2.25GB) can look "stuck" (low CPU%, huge
wall-clock) when the host machine is under unrelated load (e.g. Spotlight/`corespotlightd`
indexing) — it was still progressing, not hung. Foreground-with-log-file rebuilds were more
reliable to observe to completion in this session than backgrounding/`nohup`, which appeared to
die partway through on multiple attempts (cause not fully isolated, but avoid backgrounding this
specific long-running command in future sessions — run foreground with output redirected to a
log file and check the log after, per [[feedback_agent_memory_path]]-adjacent caution about
verifying real state over assumed state).
