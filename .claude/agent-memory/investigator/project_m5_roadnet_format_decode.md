---
name: project_m5_roadnet_format_decode
description: Byte-exact decode of DCS Syria/airfield .rn4/.routes "landscape4" containers, confirmed against real full/large-sample local files (not just small captured snippets)
metadata:
  type: project
---

Full findings/methodology: `world-model/research/2026-09-04-m5-roadnet-byte-decode.md`
(supersedes the byte-offset/structural claims in `world-model/research/2026-09-03-
m5-terrain-file-formats.md`, which was based on small hand-captured samples only).

**`.routes` — CORRECTED MODEL, confirmed against real bytes at scale:**
- Data-start offset is exactly **byte 93** (not 99, not the earlier vague "~80").
- **NOT a flat float64 triple array** (this overturns the 2026-09-03 finding).
  It's a sequence of length-prefixed blocks: `[int32 N][N × float64 xyz position]
  [int32 N][N × float64 xyz UNIT DIRECTION VECTOR]`, repeating per route. First
  Syria route: N=343, a closed-loop taxiway/road polyline near Damascus
  (x≈215000, z≈-45000..-50000), direction vectors verified magnitude==1.0
  exactly (impossible by chance for real coords → confidently tangent vectors).
- Block-boundary detection is NOT solved past the first route — a `0` then `341`
  anomaly appears right after route 1's direction array ends (byte 16561),
  meaning the `[N][pos][N][dir]` loop doesn't cleanly repeat as-is. Needs a few
  more blocks decoded by hand before writing a production parser.
- Latakia (x≈41935,z≈5685) NOT found in the 50MB head sample (closest ~5.3km,
  0 points within 5km) — inconclusive, sample is only ~2% of the 2.25GB file.

**`.rn4` — CORRECTED MODEL:**
- Header: after class-name string, TWO int32 fields precede the string table
  (an unidentified constant `5`, then the string count) — prior note's "one
  field" was off by 4 bytes. String counts confirmed unchanged: 23 Syria,
  7 Damascus, 8 Incirlik.
- The 32-byte/8×int32 record hypothesis IS confirmed at real scale (hundreds of
  rows in Syria sample, not just the earlier 8-64 row samples). Column 2 = self
  row/node index incrementing in PAIRS (0,0,1,1,2,2...); column 5 = paired index
  matching column2 but swapped in local pairs (1,0,3,2,5,4,7,6...) — directed
  edge-pair (forward/reverse) signature, now confirmed at scale not just 8 rows.
  Columns 0,3,6,7 vary, semantics UNRESOLVED (column6 shows round numbers like
  50/100 in Syria sample — doesn't match string-table index range 0-22, so
  "type index" hypothesis is NOT confirmed for any column).
- **MAJOR CORRECTION: the record region is NOT one flat table to EOF.** Damascus/
  Incirlik's clean topology table is only 79/132 rows (<1% of remaining file
  bytes) before column1 stops being constant. Syria's 50MB sample shows the
  same short-table pattern repeating >20,000 times (many separate per-segment
  sub-tables interleaved with other undecoded data), not one giant array.
- **Unresolved, important gap: airfield taxiway/runway POINT GEOMETRY source is
  unidentified.** Damascus.rn4/Incirlik.rn4 have no paired `.routes` file, and
  the >99%-of-file bytes past their short topology table don't decode as
  plausible float64 world coordinates under the tested offset. If Architect
  wants DCS-native airfield taxiway geometry, this needs a dedicated follow-up
  probe (different stride/encoding search) — not solved by anything so far.

**Go/no-go, revised 2026-09-04 Session 2 (supersedes Session 1's verdict
above)**: Full findings in `world-model/research/2026-09-04-m5-roadnet-byte-
decode.md` "Session 2" section.

- **`.routes` — GO, block-boundary bug now FUNCTIONALLY SOLVED (not just
  pending).** Each route = `[N][pos xyz][N][dir xyz]` + a trailer of several
  more `N`-sized arrays (per-point cumulative arc-length float64, an all-zero
  int32 flags array, a bounded float32 array ~curvature, plus an undecoded
  ~64-byte-record region) that scales ~156 bytes/point but was NOT fully
  field-decoded. **Production parser does not need to decode the trailer** —
  scan forward from dir-array-end for the next `[N][plausible xyz triples]`
  signature; validated clean across 15 consecutive whole-theatre routes, zero
  false positives. Use a 3-point (first/mid/last) pre-filter before full
  N-point unpack or it's too slow (naive full-unpack-per-candidate killed
  after 6+ CPU-min on 50MB).
- **Latakia coverage — REVERSED from Session 1's "not found."** Direct
  `array`-module bulk float64 scan (8 phase offsets) of the 50MB `.routes`
  sample, filtering `x` in Latakia bbox + denormal-rejected plausible
  `y`/`z`, found 17 candidate triples clustering into a few spatially
  coherent real coordinate sets (coastal near-0 elevation + nearby ~1046m
  high-ground point) — moderate confidence (not yet confirmed as belonging to
  a fully-walked route), but Session 1's "0 within 5km / inconclusive" no
  longer stands as the working assumption.
- **`.rn4` — MAJOR POSITIVE REVERSAL: airfield taxiway/runway point geometry
  DOES exist in the file, both Damascus and Incirlik confirmed.** It's NOT in
  the >99%-majority region right after the topology table (that region is a
  still-undecoded int32-pair adjacency/graph structure) — it's further into
  the file, using the exact same `[N][float64 xyz]` schema `.routes` uses.
  Damascus: smooth taxiway polylines at y=612.000612 constant (real airport
  elevation). Incirlik: smooth polylines at y≈69-70 (separate real airport,
  confirms generalization). Walked 222 blocks/1887 points (Damascus, N≥5
  filter) covering ~67% of the file before losing sync — not yet 100%, but
  feasibility is proven, this is no longer a genuine unsolved gap.
- **Topology-table column 6 CONFIRMED = string-table type index** (was
  unresolved in Session 1). Damascus: 71/79 rows type 0 (`taxiway_24m`), 8/79
  type 3 (`taxiway_52m`). Incirlik: 128/133 type 0 (`taxiway_61m`), 4/133
  type 3 (`taxiway_22m`). String table trailing number = segment width in
  meters. One sentinel/terminator row per file has anomalous col6 + col4=3,
  coincides with table-end boundary.
- **Still unresolved**: the int32-pair adjacency section between topology
  table and geometry blocks (schema unknown, currently must be brute-force
  skipped, not computed); whether topology row's col0/3/7 link a row to its
  specific geometry block (needed for per-segment-typed geometry, not just
  an undifferentiated point cloud); `.rn4` geometry walker not pushed to
  100% coverage; whole-theatre `Syria.rn4` geometry-region only spot-checked,
  not walked.

Terrain-mesh/elevation static files: unchanged from prior note, still NO-GO/
unread, not blocking (M4 already works via live land.getHeight + SRTM).
