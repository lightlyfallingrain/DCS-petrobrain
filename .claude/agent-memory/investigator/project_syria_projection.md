---
name: project-syria-projection
description: Confirmed facts about DCS Syria's coordinate projection, established during M1 recon (2026-09-02, verified live 2026-09-03)
metadata:
  type: project
---

**2026-09-03 update — CONFIRMED against live DCS 2.9.29.27278 install.** pydcs's tmerc params below reproduce
live `coord.LOtoLL` output (226 points: origin + all Syria airbases) to 0.00-0.03m — treat as
`confidence="confirmed"`, not just community-derived, for the x/z<->lat/lon formula itself. Separately, true
real-world residual (live DCS vs 3 independently-published ARPs: Damascus, Latakia/OSLK, Beirut/OLBA) is
**~1.0-1.3 km, not ~1.6km** (the 1.6km figure below used pydcs's own imprecise hardcoded Damascus point, not a
live value) — and the residual vector direction/magnitude varies per-airport (not a constant datum shift), so
it's per-airport terrain-art placement error, not a projection-formula defect. `beacons.lua`'s `positionGeo`
field was checked as a candidate extra control point but is itself computed by the same tmerc projection
(matches transformed `position` to 0.03m) — NOT an independent real-world source, don't use it as one. Full
writeup: `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`. M1 milestone judged
satisfied by this investigator.

DCS Syria's local x/z grid is a **Transverse Mercator** projection (per pydcs source), NOT the commonly-repeated
"Lambert Conformal Conic per theatre" forum folklore — that claim appears unsupported by any source found (ED docs,
forums, or code). See [[reference_pydcs_prior_art]] and full writeup in
`world-model/research/2026-09-02-m1-coordinate-transform.md`.

Confirmed Syria tmerc params (from pydcs, community-fitted not ED-documented): central_meridian=39,
false_easting=282801.00000003993, false_northing=-3879865.9999999935, scale_factor=0.9996, lat_0=0,
ellps=WGS84, axis=neu (so input x=northing=DCS-native x, y=easting=DCS-native z).

ED officially documents (digitalcombatsimulator.com/en/support/faq/1256) the axis convention only: x=north,
z=east, y=up, meters, "DCS ground is an infinite plain" — no projection type stated.

Independent real-world cross-check: pydcs Damascus airbase point (x=-178652.320313, y=52081.296875) through the
above tmerc params -> 33.42551N, 36.51851E, vs published OSDI ARP 33.41139N, 36.51556E = ~1.6km error. Confirms
projection family is right (a wrong axis order gives 327km error) but exact params/point are not sub-km-verified
against the actual installed DCS copy yet — that requires running coord_probe.lua live in-game.

coord.LOtoLL / coord.LLtoLO (Hoggit-documented) are Mission Scripting environment only — require a running
mission, not callable offline. pydcs's own parameter-fitting tool (tools/coord_export.lua) works exactly this
way: DO SCRIPT FILE trigger, world.getAirbases() + coord.LOtoLL(), dumped to Saved Games/DCS/Logs/ as JSON.
