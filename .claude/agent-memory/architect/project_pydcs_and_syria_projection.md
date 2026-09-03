---
name: pydcs-and-syria-projection
description: pydcs (GitHub, LGPL-3.0) is the strongest prior-art source for DCS per-theatre coordinate projections; Syria uses Transverse Mercator, not Lambert Conformal Conic folklore.
metadata:
  type: project
---

**pydcs** (github.com/pydcs/dcs, LGPL-3.0) already solved the DCS x/z ↔ lat/lon
projection problem per-theatre, by calling `coord.LOtoLL` live in-game on the
theatre origin and every airbase, then curve-fitting a `+proj=tmerc` (Transverse
Mercator) PROJ4 string (`tools/export_map_projection.py` /
`dcs/terrain/<theatre>/projection.py`). Syria's fitted params:
`central_meridian=39, false_easting=282801.0, false_northing=-3879865.9999999935,
scale_factor=0.9996`. Axis convention: DCS `x`=north, `z`=east (ED-documented via
FAQ), wired as PROJ `+axis=neu`.

The "DCS uses Lambert Conformal Conic per theatre" claim circulating in the
community is **not supported** by any ED/forum/code source found — likely a
conflation with the real-world aeronautical charts DCS terrain art is sourced
from. Do not repeat this claim as fact in future planning.

**Why:** Full investigation done 2026-09-02 for M1 (coordinate transform), see
`world-model/research/2026-09-02-m1-coordinate-transform.md`. `coord.LOtoLL`/
`coord.LLtoLO` are Mission Scripting-only (need a running mission, not callable
offline) — so pydcs's own airbase "ground truth" is circular (derived from the
same function being fitted), meaning pydcs's parameters must still be
cross-checked against an independently-sourced real-world point (e.g. published
airport ARP), not trusted on pydcs's internal self-consistency alone. One such
check (Damascus/OSDI) gave ~1.6 km residual — plausible but not yet confirmed
against the actually-installed DCS copy.

**How to apply:** For any future theatre (Caucasus, etc.), check pydcs first for
existing fitted projection parameters before re-deriving from scratch — but
always pair with an independent real-world control point before treating as
confirmed, and always run the live-install `coord.LOtoLL` probe pattern
(`world-model/tools/dcs-mission-probe/coord_probe.lua`) before flipping any
per-theatre parameter's confidence from "provisional" to "confirmed." pydcs
license (LGPL-3.0) means reuse the *parameter values*, not the code, unless the
project is willing to take on copyleft obligations.
