---
name: multi-theatre-afghanistan-caucasus
description: Afghanistan/Caucasus recon (2026-10-04) -- beacon-fit tmerc technique, the off-map-navaid trap in beacons.lua, DEM3 block formula, Syria-hardcoded parser guards
metadata:
  type: project
---

Full note: `world-model/research/2026-10-04-multi-theatre-afghanistan-caucasus-recon.md`.

**Technique worth reusing for any future theatre with no pydcs entry (e.g. a theatre
newer than pydcs's last update): fit tmerc params from `beacons.lua`'s own
`position`<->`positionGeo` pairs.** No numpy/scipy needed -- candidate `central_meridian`
values are the standard UTM-zone-centre series (odd multiples of 3, spaced 6 deg: Syria=39,
Caucasus=33, Kola=21, Afghanistan=63 fitted this session) so the search space is tiny (a
handful of candidates), and for each candidate the shared-scale-factor fit (`x=k0*N+false_
northing`, `z=k0*E+false_easting`) is a 3-unknown linear least squares solvable by hand-
derived normal equations. **Validated by reproducing Syria's and Caucasus's already-known
parameters to 0.03m / <0.01m before trusting it on Afghanistan (no other source existed).**
Caveat unchanged from M1: `positionGeo` is DCS's own internal-projection output, so this
confirms internal self-consistency, not live `coord.LOtoLL` or real-world ARP accuracy.

**Trap: `beacons.lua`'s full point set is NOT a reliable tight lower bound on theatre
extent, and this is theatre-dependent, not a Syria-generalizable assumption.** Caucasus's
beacon set includes `world_*` (enroute-navaid, not airfield-colocated) beacons at real
Ukrainian/Russian cities (Taganrog, Mariupol, Rostov, Grozny) hundreds of km past the real
map edge -- full-beacon bbox there (612x1309km) wildly overshoots ED's own marketing figure
(700x400km), while the `airfield_group`-filtered subset (beaconId prefix `airfield<N>_<M>`
vs `world_<N>` -- `dcs_data/beacons.py` already encodes this) lines up closely (368x665km).
Afghanistan's `world_*` beacons (Peshawar, Dushanbe, Quetta) sit just across the border, so
its full-beacon bound stays close to towns.lua there -- the pollution is real but
theatre-specific. **Always split by `airfield_group` and compare both the full and
filtered bbox against a marketing-area sanity check before trusting either.**

**DEM3 block-code formula** (viewfinderpanoramas.org never states it readably --
`WebFetch` strips the interactive image map): `lat band letter = chr(ord('A') +
floor(lat/4))`, `lon band number = floor((lon+180)/6)+1`, each band 4 deg lat x 6 deg lon.
Cross-validated 5 ways this session (one direct fact, 4 changelog mentions, the user's own
downloaded tile counts for both Afghanistan [H40-J43 predicts exactly 288 tiles, matches]
and Caucasus [K36-L38 predicts <=144, 123 present = sea-tile gap]). Treat as settled for
any theatre with real downloaded data to cross-check; otherwise spot-check against the
site's own interactive map first.

**`EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT` in `world-model/src/dcs_data/{towns,
beacons}.py` are Syria-hardcoded exact-match guards (1182/151) that WILL raise on every
other theatre even though the regex/format itself is theatre-generic** -- confirmed by
running both parsers unmodified against real Afghanistan (1225 towns, 49 beacons) and
Caucasus (1759 towns, 164 beacons) files: zero format/shape errors, only the count
mismatch. Also found: `build/pipeline.py`'s roadnet-ingest stage hardcodes the `Source.name`
string literally as `"Syria.routes"` instead of deriving it from `routes_path.name` --
silently mislabels provenance on any non-Syria build. `.routes`/`.rn4` binary parsers
(`roadnet/routes.py`, `roadnet/rn4.py`) work completely unmodified on both theatres
(identical `landscape4::` container header, zero sync-loss on a 20-route partial walk).

**Known dead end this session: `tools/probe_surface5_elevation.py`'s `walk_descriptors`
does NOT scale to Afghanistan's `.surface5` (41.5GB) at the same 150MB scan budget that
worked for Syria** -- 20MB scanned in 0.21s, 50MB took 31.25s (far worse than linear),
killed before 150MB. Likely cause (inferred, not fixed): an unbounded `buf.find(TRITYPE,
...)` forward search from a spurious byte-pattern match with no real descriptor following
costs O(remaining-buffer); Afghanistan's descriptor region is ~5.5x denser per MB than
Syria's. Don't re-attempt at the same budget -- bound the forward search or skip it.
