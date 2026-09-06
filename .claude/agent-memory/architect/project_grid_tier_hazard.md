---
name: grid-tier-hazard
description: store/reader._load_grid_meta picks grids by "newest id wins", which silently blanks theatre-wide elevation when a second grid of the same kind is added
metadata:
  type: project
---

`world-model/src/store/reader.py`'s `_load_grid_meta` resolves a grid with
`SELECT ... FROM grid WHERE kind = ? ORDER BY id DESC LIMIT 1` — "most recently
inserted row of this kind wins". Every `grid`-kind read (`sample_grid`,
`load_full_grid`, `grid_spacing_m`, `grid_provenance`) inherits this.

**Why:** it was fine through M7, where a build inserted at most one meaningful
grid per kind. It becomes a correctness trap the moment a *second* grid of the
same kind exists — e.g. a small chunk-scoped DCS-probe elevation grid added to a
store that already holds M7's whole-theatre SRTM grid. The small grid wins for
the entire theatre and the 591,732-point SRTM baseline goes silently dark. There
is no error; queries just start returning `None` outside the small grid's footprint.
`build/pipeline.py`'s `build_region` docstring already notes this ordering
hazard for the SRTM-plus-probe case and sidesteps it by never supplying both.

**How to apply:** any plan that adds a second grid of an existing `kind` must
address this *in the same change*, never as a follow-up. M8 ended up dodging the
whole bug class rather than patching it: probe-tier grids live in a separate
`.sqlite` entirely, so the base store's `grid` table physically cannot hold a
second grid of a kind, and existing readers stay correct unmodified (see
[[m8-plan-shape]]). The in-file alternative — a `grid.tier` column with
probe-then-base fallback — was rejected partly because it leaves every existing
unfiltered call site a latent bug requiring individual audit, and does not
*prevent* two same-tier grids coexisting. If a second grid of a kind ever must
share one file, add a `UNIQUE(kind)`-style constraint rather than relying on
callers to filter correctly. The trap remains live in `_load_grid_meta` for any
future change; it is currently only unreachable, not fixed.
