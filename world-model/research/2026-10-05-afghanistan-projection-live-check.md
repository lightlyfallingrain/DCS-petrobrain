# Afghanistan projection — live `coord.LOtoLL` check

**Date:** 2026-10-05
**Machine:** the Windows box (DCS installed); probe run by the user.
**Theatre:** Afghanistan.
**Plan:** `plans/multi-theatre-afghanistan/plan.md` Stage 4.

### Question

`THEATRE_PROJECTIONS["Afghanistan"]` was fitted from `beacons.lua` position/positionGeo pairs
(`2026-10-04-multi-theatre-afghanistan-caucasus-recon.md` Q1) and marked provisional. Does it
match DCS's own live `coord.LOtoLL`?

### Findings

**1. The beacon fit was right in shape and off by a constant 5 cm.**

- **evidence: reproduced-locally** — **source:** `tools/dcs-mission-probe/coord_probe.lua` output,
  `data/raw/dcs/2026-10-05/coord_probe_output.json` (gitignored): map origin + 29 airbases from
  `world.getAirbases()`, each with DCS x/z and DCS's own `coord.LOtoLL` lat/lon.
- With the fitted params (`false_easting=-300149.9912, false_northing=-3759656.9499`) every real
  point has a residual of 0.050–0.051 m. A residual that uniform is a constant offset, not noise.

**2. Three unplaced FOBs pin the false northing exactly.**

- **evidence: reproduced-locally** — same file.
- `FOB Thunder`, `FOB Camp Dubs` and `FOB Clark` report `x=-3759657.000, z=-9428368.000` and
  lat/lon `0.0, 0.00000198`. These are airbases with no placed position; DCS returns the frame
  point that maps to lat 0. With `lat_0=0` that x is the false northing itself: **-3759657**,
  a round number like Syria's (-3879866).

**3. Round values fit to under a millimetre.**

- **evidence: reproduced-locally** — pyproj with `+proj=tmerc +lat_0=0 +lon_0=63 +k_0=0.9996
  +x_0=-300150 +y_0=-3759657 +ellps=WGS84 +axis=neu`, compared against all 30 points.
- Worst residual **0.0007 m** (flat-earth distance; haversine agrees). `false_easting` of
  -300150.0 and -300149.9999999864 are indistinguishable at this precision; the round value is
  registered.

### Consequences

- `THEATRE_PROJECTIONS["Afghanistan"]` updated to the round values, `confidence="confirmed"`.
  New test `test_afghanistan_matches_live_coord_lotoll` (8 points spread across the map, 1 cm
  bound) fails on the old fitted values and passes on the new ones.
- `afghanistan-full.sqlite` is not rebuilt: a 5 cm shift is far below its 500 m grid and every
  stored feature's own uncertainty.
- The probe file is the first complete Afghanistan airfield list: 26 real airbases with
  positions (the 3 FOBs above must be filtered — position 0,0 means "not placed"). The world
  model knows 7 today (beacon-derived only).
- For the beacon-fit method generally: it gets the projection right to centimetres, but the
  false easting/northing should be rounded to the nearest metre when the fit lands within a few
  centimetres of one — every confirmed DCS theatre so far uses round values.
