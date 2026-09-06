---
name: project_m8_geofabrik_recon
description: Geofabrik OSM extract format/coverage findings for M8, and that download.geofabrik.de is unreachable via this session's WebFetch/curl.
metadata:
  type: project
---

Session 2026-09-06, `world-model/research/2026-09-06-m8-geofabrik-osm-recon.md`.

- **download.geofabrik.de is not reliably fetchable from this environment**: WebFetch failed
  5/5 (two 502, one 503, two timeouts) across asia.html/asia/syria.html/europe.html; outbound
  `curl` via Bash is sandboxed/denied for the coordinator. Unlike forum.dcs.world (403, known
  blocked), this looked transient but never succeeded across ~5 retries in one session — treat
  similarly: ask the user to open the page and paste/report contents rather than retrying
  indefinitely. All Geofabrik-specific facts below come from WebSearch snippets only, not a
  direct page read — one evidence tier weaker than usual, flagged as such in the research file.
- **`.osm.bz2` (raw XML) is deprecated at Geofabrik** — `.osm.pbf` is the only full-data format
  now realistically offered; `.shp.zip` (and apparently `.gpkg.zip` for at least Turkey) are
  explicitly filtered subsets per Geofabrik's own docs, not complete extracts. Kills the
  "stdlib bz2 + iterparse, zero new deps" path M3's Overpass/OSM work might have suggested —
  M8 must decide between hand-rolling a `.pbf` parser (stdlib zlib+struct+varints, no protobuf
  compiler needed, ~200-400 LOC, same tier of effort as the M5 `.rn4`/`.routes` binary-scan
  precedent) or accepting a new dependency (pyosmium BSD-2 compiled-wheel; pyrosm MIT but pulls
  GeoPandas, ruled out by existing project policy; osmread/osmiter MIT pure-Python but slow).
- **Turkey is filed under `europe/turkey.html` at Geofabrik, not asia/** — easy wrong guess.
  Reportedly no official sub-national Turkey split exists (unconfirmed — flagged as the single
  highest-value thing for the user to check by hand), meaning the theatre envelope (which only
  needs Turkey down to ~Konya) may force downloading the whole country (~612MB pbf, reported)
  with no smaller server-side option — clip client-side with `osmium extract --bbox` instead.
- **`osmium-tool` (GPLv3, `brew install osmium-tool`) is a manually-run CLI**, not a Python
  dependency — same execution-boundary pattern as M7_RUN_INSTRUCTIONS.md. Recommended as a
  pre-processing step (merge extracts + bbox-clip) regardless of which Python-side parsing
  option gets chosen, since it shrinks the hand-rolled-parser input dramatically.
- **OSM layer will almost certainly need its own filtering/decimation design** — order-of-
  magnitude reasoning (not measured) suggests roads alone could be 10x+ M7's 14,833-road store
  once clipped to envelope, more before clipping. Get real counts via `osmium fileinfo -e` once
  an extract exists, before Architect sets decimation thresholds.
