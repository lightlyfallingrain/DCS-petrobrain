# M1 — DCS x/z ↔ WGS84 transform (Syria): live-install verification

**Date:** 2026-09-03
**DCS version:** 2.9.29.27278
**Theatre:** Syria

### Question

Follow-up to `2026-09-02-m1-coordinate-transform.md`. Two things were unresolved there: (1) whether pydcs's fitted Transverse Mercator parameters for Syria actually match the installed DCS copy's real `coord.LOtoLL` output, and (2) what the true real-world residual is (the earlier ~1.6 km Damascus figure used a pydcs-internal point, not a live DCS value, and was based on a single control point). Both probes prepared in the prior session have now been run against the live Windows install.

### Findings

1. **pydcs's Syria `tmerc` parameters are confirmed correct for DCS 2.9.29.27278 — evidence: reproduced-locally.** Transforming all 226 live `coord.LOtoLL` samples (theatre origin + every airbase from `world.getAirbases()`, captured by `coord_probe.lua` — `world-model/data/raw/dcs/2026-09-03/coord_probe_output.json`) through the pydcs parameters (`central_meridian=39, false_easting=282801.00000003993, false_northing=-3879865.9999999935, scale_factor=0.9996`, `+proj=tmerc +axis=neu`) reproduces the live `lat/lon` DCS itself reports, with residuals of **0.00–0.03 m** across the board (float-rounding noise only, no systematic error at any point, including theatre edges ~450 km from the origin). This upgrades pydcs's parameters from "forum-claim/community-tool-derived, plausibility-checked" to **reproduced-locally against DCS's own live scripting API** — `world-model/src` may treat these Syria parameters as `confidence="confirmed"` for the x/z↔lat/lon transform itself (not for real-world accuracy, see Finding 3).
2. **`beacons.lua`'s `positionGeo` field is computed by the same projection, not an independent source — evidence: reproduced-locally.** Every `beacons.lua` entry carries both a DCS-native `position = {x, y_alt, z}` and a `positionGeo = {latitude, longitude}`. Transforming three widely-separated beacons' `position` (Damascus DAM VOR/DME, Latakia LTK VOR/DME, Gaziantep GAZ VOR/DME) through the pydcs `tmerc` parameters reproduces their stored `positionGeo` to within **0.03 m** — i.e. `positionGeo` in the terrain files is itself an output of ED's internal projection (presumably baked in at terrain-build time), not an independently-sourced real-world beacon database entry. **This means the beacon check requested in this task's step 4 does not provide a new, independent control point** — it is a third confirmation of the same self-consistent DCS-internal geodesy already covered by Finding 1, and must not be reported as "independent ground truth." (Flagging explicitly per the circularity-risk caveat in the prior note's Finding 6.)
3. **True independent real-world residual: DCS's coordinate system is offset from published ARPs by roughly 1.0–1.3 km, not ~1.6 km.** Three real-world-published Aerodrome Reference Points (ARPs), cross-referenced via SkyVector/eAIP-class sources (independent of DCS/pydcs), compared against the corresponding **live** `coord.LOtoLL` output for the same airbase:

   | Airbase | Live DCS `coord.LOtoLL` | Published ARP | Residual |
   |---|---|---|---|
   | Damascus (OSDI) | 33.41534001, 36.50425483 | 33.41139, 36.51556 (33°24'41"N 36°30'56"E, [SkyVector](https://skyvector.com/airport/OSDI/Damascus-International-Airport)) | **1137.5 m** |
   | Bassel Al-Assad / Latakia (OSLK) | 35.41286632, 35.94995412 | 35.40109, 35.94868 (35°24'03"N 35°56'55"E, [SkyVector](https://skyvector.com/airport/OSLK/Latakia-Basel-Al-Assad-Airport)) | **1314.1 m** |
   | Beirut–Rafic Hariri (OLBA) | 33.81242852, 35.48624229 | 33.82090, 35.48840 (33°49'15"N 35°29'18"E, [OLBA charts](https://navigraph.com/airport/OLBA/Beirut-Rafic-Hariri-International)) | **962.8 m** |

   This supersedes the prior note's single-point ~1.6 km Damascus estimate (which used pydcs's own `Damascus` `Point` object, not a live-DCS value — the pydcs point and the live `coord.LOtoLL` Damascus airbase point are themselves ~1741 m apart in DCS-native x/z, i.e. pydcs's hardcoded airport point was itself imprecise, inflating the earlier residual). Using live DCS ground truth against three points instead of one, the real-world residual is consistently in the **~1.0–1.3 km** range, evidence: reproduced-locally.
4. **The residual is not a simple global datum shift/rotation — evidence: inferred.** Converting each residual to a local north/east vector (meters):
   - Damascus: ΔN +440, ΔE −1050
   - Bassel Al-Assad: ΔN +1310, ΔE +116
   - Beirut: ΔN −943, ΔE −200

   The direction and magnitude vary substantially across only ~250 km of theatre — a systematic geodetic datum shift or projection-parameter error would produce a roughly constant offset vector across the theatre; this doesn't. This is consistent with **per-airport terrain-art placement error** (each airbase modeled/placed independently against satellite imagery by ED's terrain artists, not surveyed to ARP-grade precision) rather than a projection-formula defect — supporting explanation (a)/(c) from the prior note's Finding 7, and arguing against (b) (pydcs fitting error), which Finding 1 above already rules out directly.
5. **`entry.lua` (Syria terrain root) confirmed to contain no projection/coordinate keywords at all — evidence: reproduced-locally.** Full-file grep (`lambert|mercator|tmerc|proj|meridian|false_east|false_north|scale_factor|origin|latitude|longitude|centerPoint|zone`) against the installed `Mods/terrains/Syria/entry.lua` (35 lines) returned zero matches — source: `world-model/data/raw/dcs/2026-09-03/syria_terrain_lua_probe_20260903T075625Z.txt`. This closes the prior note's open question: Syria's terrain Lua does **not** state its projection directly; the empirical/fitted approach (pydcs's method, now confirmed accurate — Finding 1) remains the only practical way to obtain the transform.

### Reproducible Test

Python, `pyproj`, against the committed raw files (no live DCS access needed to re-run this check — only to regenerate the raw JSON):

```python
from pyproj import CRS, Transformer
import json, math

proj4 = ("+proj=tmerc +lat_0=0 +lon_0=39 +k_0=0.9996 "
         "+x_0=282801.00000003993 +y_0=-3879865.9999999935 "
         "+units=m +ellps=WGS84 +axis=neu +no_defs")
to_ll = Transformer.from_crs(CRS.from_proj4(proj4), CRS.from_epsg(4326))

data = json.load(open("world-model/data/raw/dcs/2026-09-03/coord_probe_output.json"))
for p in [data["origin"], *data["airbases"]]:
    lat, lon = to_ll.transform(p["x"], p["z"])
    # compare to p["lat"], p["lon"] -> residual ~0.00-0.03 m for all 226 points
```

Real-world ARP residuals (Finding 3/4) computed with a standard haversine distance between the live `coord.LOtoLL` lat/lon and the published ARP lat/lon per airbase above.

### Possible Approaches

- **Adopt pydcs's Syria `tmerc` parameters as `confidence="confirmed"`** in `world-model/src`'s projection subsystem (per Finding 1) — no need to re-derive or re-fit; the live install matches them exactly.
- **Do document the ~1–1.3 km DCS-vs-real-world residual as an inherent property of DCS's geography, not a bug in our transform.** Any pipeline stage that reconciles DCS geometry with OSM/DEM data should expect this order of local misalignment per feature and should not assume DCS airbase points line up with real-world ARPs to better than ~1 km. If sub-km alignment is ever needed (e.g. runway threshold matching for M2/M3), a per-feature local correction/anchor approach will likely be needed rather than trusting the global projection alone.
- **Do not use `beacons.lua`'s `positionGeo` as an independent validation source** — per Finding 2 it is DCS-internal-projection-derived, not real-world-sourced. It remains useful as a *free, already-computed* second live source for coord.LOtoLL-equivalent points without a running mission (e.g. for offline pipeline development), but must be labeled evidence-wise the same as `coord.LOtoLL` itself, not as an external check.
- For M2/M3 (raster/OSM overlay), expect and budget for ~1 km class local displacement between DCS terrain art and OSM/real-world features; do not treat the projection transform itself as the error source once M2/M3 diagnostics show discrepancies of this order.

### Unresolved

- Whether the ~1–1.3 km per-airport residual is dominated by DCS terrain-art placement error specifically (vs. e.g. real-world ARP definitions themselves shifting over time, or differing WGS84 realizations) is still inferred, not proven — would need a fourth independent source (e.g. a DCS-placed non-airport landmark with precisely surveyed real-world coordinates, such as a well-known monument) to further triangulate. Not pursued further here; the magnitude and non-systematic direction are sufficient for M1's "measure error" bar.
- Whether other Syria-region theatres/extensions (if any exist) or DCS terrain updates could change these parameters in future patches was not tested — this finding is specific to 2.9.29.27278.

### M1 milestone verdict

ROADMAP.md's M1 bar is "Prove DCS x/z ↔ lat/lon for Syria against a known real-world control point. Measure error." Both are now satisfied: the transform is proven against DCS's own live `coord.LOtoLL` (sub-meter, Finding 1) and independently measured against three real-world ARPs (~1.0–1.3 km, Finding 3). **M1 can be considered satisfied** — the transform formula is confirmed accurate to the DCS-internal geodesy, and the real-world residual is now a known, quantified, and explained (not mysterious) property rather than an open question. Recommend Architect close M1 and proceed to M2, carrying forward the ~1 km expected-displacement figure as a design input.
