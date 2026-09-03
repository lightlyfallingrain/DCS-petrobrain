# NOTES.md

Knowledge harvested from feature work and investigation. Short, factual, one idea per bullet. Obvious patterns from code or CLAUDE.md belong in CLAUDE.md, not here — these are insights earned by doing.

## Coordinate Transforms & Projections

- **Syria's projection is Transverse Mercator, not Lambert Conformal Conic.** Community folklore said "Lambert per theatre" but investigation found pydcs (LGPL-3.0, empirically fitted) uses `+proj=tmerc` with fitted parameters, confirmed via 226-point live `coord.LOtoLL` reproductions to 0.00–0.03m residual (Finding 1 of M1 verification note). ED doesn't document this directly in terrain Lua; empirical fitting is the only practical approach.

- **DCS internal geodesy vs. real-world misalignment is per-airport terrain-art placement error, not a projection defect.** Three independent real-world ARPs (Damascus 1137.5m, Latakia 1314.1m, Beirut 962.8m residual) show non-systematic direction/magnitude across ~250km, ruling out datum shift/parameter error. Consistent with terrain artists placing each airbase independently against satellite imagery without ARP-grade surveying (Finding 4 of M1 verification note). Budget ~1–1.3km expected displacement in M2/M3 when registering DCS geometry against OSM/real-world features; do not assume DCS airbase points line up with published ARPs better than that.

- **`beacons.lua` positionGeo is not an independent ground-truth source.** Every beacon entry's `positionGeo` is computed by ED's internal projection (baked at terrain build time), matching `coord.LOtoLL` to within 0.03m — it's a *free, offline* source equivalent to `coord.LOtoLL` itself, not a real-world cross-check (Finding 2 of M1 verification note). Useful for offline pipeline development, but evidence-wise belongs in the same category as `coord.LOtoLL`, not as external validation.

- **Theatre-agnostic transform design means adding a second theatre requires only a registry entry.** `src/coordinates/` layer doesn't encode Syria-specific logic — the `dcs_to_wgs84`/`wgs84_to_dcs` functions are theatre-agnostic. New theatres need only a new `TmercParams` entry in `THEATRE_PROJECTIONS` dict with `source` and `confidence` fields populated. Confidence starts `"provisional"` for unprobe-verified theatres; flips to `"confirmed"` only after live `coord.LOtoLL` cross-check.

## Testing & Provenance

- **Control-point tests must use externally-published ARPs, not DCS-derived points.** Early approach using pydcs's hardcoded `Damascus` point inflated the residual by ~1741m (the pydcs point itself was imprecise vs. live `coord.LOtoLL` output). M1 control points use SkyVector/eAIP real-world ARPs instead, avoiding circularity (Finding 3 of M1 verification note). Lesson: when validating a DCS extraction pipeline against external truth, ensure the external truth is actually independent, not recalculated from the same source.

- **Confidence field distinguishes third-party-fitted from live-install-verified parameters.** Syria's registry entry is `confidence="confirmed"` because Finding 1 reproduced 226 live DCS points to sub-cm residual; future theatres can be added with `confidence="provisional"` without code changes. This protects against silently encoding unverified community claims as fact, per project invariant (docs/CONVENTIONS.md).

## Raster Charts & Registration

- **RasterCharts tile axes are asymmetric relative to DCS's x/z convention.** z-tile-index increases east (same direction as DCS +z), but x-tile-index increases south (opposite DCS +x=north) — this is not derivable from filename grammar alone and must be applied explicitly in coordinate math. Session 8 finding: failure to encode the asymmetry propagates a sign error through half the transformation (M2 registration fitting against real-world control points confirmed this empirically; the mistake would have been caught only by cross-checking residuals per axis, not by inspection alone).

- **RasterCharts storage structure is theatre-specific, not uniform.** Syria uses a single `rasterCharts.zip` archive containing all tiles; Caucasus uses a genuine multi-scale tile pyramid with per-scale subdirectories and many small per-tile `.zip` files. The pipeline must not assume single-archive layout generalizes to all theatres (M0 finding from `DCS-files.txt`). Theatre-to-archive-structure detection belongs in the probe/extraction layer, not the registration math.

- **Registration parameters must be fitted to a specific scale/sheet/level combination; do not assume portability across variants.** M2 fitted `origin_x`/`origin_z` against Syria's `64m` sheet `aa` level `00` only — other scales (`32m` tier) and other levels/sheets for the same scale are untested. Cross-validating registration against a second sheet (e.g. `64m` `ab`, or the `32m` tier) before upgrading `confidence` from `"provisional"` is a Stage 4 task, not automatic (M2 implementation summary, session 29).

- **Per-sheet/level registration independence mirrors the multi-projection pattern from M1.** Just as different theatres need separate `TmercParams` entries, different RasterCharts sheets/scales need separate registration entries if confidence is to be meaningfully tracked. The registry structure (`THEATRE_RASTER_REGISTRATIONS: dict[str, RasterRegistration]`) is sufficient for per-theatre but not per-sheet; extending it to handle sheets (e.g. dict-of-dicts or a composite key) is left to when multi-sheet support is actually needed, not pre-built on speculation.
