---
name: m5-airfield-layer
description: M5 airfields are beacons.lua-derived reference points, not .rn4 taxiway geometry — user decision 2026-09-04
metadata:
  type: project
---

M5 includes airfields as **reference points only**, sourced from
`Mods/terrains/Syria/map/beacons.lua`. Feature kinds: `navaid` (verbatim beacon
transcription, provenance `dcs`, uncertainty 0), `runway` (2-point segment between a
same-system ILS or PRMG localizer/glideslope pair, provenance
`derived_from_dcs_beacons`, uncertainty 300 m), `airfield` (runway-axis midpoint or
beacon centroid, uncertainty 500/1000 m). Taxiways, structures and airfield extents are
explicit non-goals.

**Why:** User framing — "airfields are important as a whole, not so much as individual
taxiways or structures." Narrower than extracting `AirfieldsTaxiways/*.rn4` geometry
(walker only reaches ~67% and the type→geometry join is unconfirmed), wider than pure
deferral.

**How to apply:** When a future milestone wants airfield detail, the upgrade path is
either a surveyed airdrome table (unverified whether one ships — a recursive `ls` of the
Syria terrain root was folded into `probe_syria_terrain_lua.sh` to find out) or the
deferred `.rn4` walker. Do not reopen the beacon derivation itself.

Non-obvious facts established while deciding this, worth not re-deriving:

- `towns.lua` does **not** contain airfields. Its `Latakia` entry is the city, ~14 km NNW
  of the airfield and outside the `latakia-20km` region.
- `beacons.lua` is a global `beacons = {...}` list, 151 entries for Syria,
  `beaconsTableFormat = 2`. Multi-line blocks (unlike towns.lua's one-per-line). Each has
  `position = {x, y, z}` in DCS metres where **the middle value is elevation, not z**, plus
  `positionGeo`, `display_name`, `beaconId`, `type`, `callsign`, `frequency`, `direction`.
  `beaconId` groups as `airfield<N>_<M>` or `world_<N>`.
- **`positionGeo` must never be used for coordinate-transform validation** — DCS shipping
  both `position` and `positionGeo` makes that circular. See
  `research/2026-09-03-m1-coordinate-transform-verification.md` Finding 2.
- Latakia = group `airfield21`, 8 beacons, all inside the region. ILS pair spans 2635 m at
  bearing 0.31°; PRMG pair 2278 m at 0.96°; beacon `direction` field -1.444. All three
  agree, and match published OSLK 17/35 (2797 m). Derived airfield point (41740.5, 5697.8)
  sits **1504 m** from `control_points.py`'s in-game airbase position — expected, not an
  error: runway midpoint vs tower/ramp reference.

Related: [[m5-roads-source-reversal]], [[dcs-offline-sources]].
