### Implementation Summary — Stage 0 (census, no store code)

Derived the `latakia-20km` DCS-space envelope, confirmed both known `towns.lua` entries fall
inside it, picked the eastward offset, ran one widened Overpass fetch, and confirmed
`Syria.routes`'s local path/size. All four Stage 0 gate items pass. No `src/store/`,
`src/build/`, `src/roadnet/`, or `src/dcs_data/` code was written, per the checklist.

### Files Changed
- `world-model/src/osm/overpass.py` — added an optional `query: str | None = None` parameter to
  `fetch_bbox`, defaulting to the existing M3 query builder when omitted. Backward compatible
  (M3's call sites and tests are unaffected); lets Stage 0's widened-query census fetch reuse
  the cache-first/single-network-call/User-Agent discipline instead of reimplementing it.
- `world-model/tools/fetch_m5_stage0_census.py` — new throwaway census script. Computes the
  region envelope from the OSLK ARP centre + chosen offset via `coordinates.dcs_to_wgs84`,
  builds the widened Overpass query (M3's `highway`/`building`/`place` node/`waterway` set plus
  `landuse`, `natural=water`, `place` way/relation), fetches once via `osm.overpass.fetch_bbox`,
  and reports feature counts against the Stage 0 gate (water polygons, settlement polygons,
  named places all present).
- `world-model/research/2026-09-04-m5-stage0-census.md` — dated research note recording the
  envelope, offset choice and reasoning, fetch results, and gate pass/fail, plus the
  `Syria.routes` acquisition confirmation.

### Tests Added
None — Stage 0 is a census/verification stage with no pipeline code to unit-test. Existing
`tests/test_osm_overpass.py` continues to pass unmodified against the now-optional `query`
parameter (default behavior unchanged).

### Checks
- `ruff format --check world-model/src world-model/tests world-model/tools`: pass
- `ruff check world-model/src world-model/tests world-model/tools`: pre-existing findings in
  untouched files only (EXE001 non-executable shebangs in other `tools/*.py`, one I001 in
  `tools/report_control_point_errors.py`) — not introduced by this session; the two files
  touched here (`src/osm/overpass.py`, `tools/fetch_m5_stage0_census.py`) are clean except the
  same pre-existing EXE001 shebang convention every other `tools/` script also carries.
- `mypy --strict world-model/src`: pass (10 source files)
- `pytest world-model/tests -q`: pass (30 passed)

### Notable Discoveries
- **Network access requires `dangerouslyDisableSandbox: true` in this environment** — the
  default sandboxed Bash cannot reach `overpass-api.de` (connection times out). Flag for any
  future session needing an Overpass/network fetch.
- **The plan's "+3 km" Jablah-margin estimate was conservative.** Recomputing from `towns.lua`'s
  full-precision lat/lon (not the plan's rounded values) shows Jablah does not actually leave
  the box until roughly +5,941 m of eastward offset, not ~+3 km. This session still respected
  the checklist's explicit 0–+3 km cap rather than exploiting the larger margin — the cap is an
  instruction, not a derived limit, so it wasn't reopened. Worth noting in case a later stage
  needs to revisit the offset.
- **Chosen offset: +3,000 m** (the mandated cap). Both named places keep multi-kilometre margins
  at this offset (Jablah 2,940.97 m from the west edge, Al Hannadi 4,102.34 m from the east
  edge).
- **Widened Overpass fetch, offset region**: 13,618 elements total; 27 water polygons, 194
  settlement polygons (`place=*` or `landuse=residential`), 112 named places. Two named OSM
  nodes with an English name tag independently corroborate the two DCS gazetteer entries:
  "Jable" (`place=city`) ≈ `towns.lua`'s Jablah, "Hanadi" (`place=village`) ≈ `towns.lua`'s Al
  Hannadi. This was a sanity spot-check only, not used to satisfy the gate or to fuse datasets.
- **`Syria.routes` was already correctly staged** at
  `world-model/data/raw/dcs/syria/roads/Syria.routes`, exactly 2,251,462,776 bytes — no move or
  copy was needed this session.
- Raw fetch cache (19,631,612 bytes) lives at
  `world-model/data/raw/osm/2026-09-04/latakia_20km_widened.json`, correctly gitignored via
  `world-model/.gitignore`'s `data/raw/` rule — confirmed with `git check-ignore -v`, not staged.
