# M5 — .routes/.rn4 byte-exact decode against real full/large-sample files

**Date:** 2026-09-04
**DCS version:** 2.9.29.27278 (per M0) — this session used already-extracted local
files, no live DCS access
**Theatre:** Syria (whole-theatre `.rn4`/`.routes` head-50MB samples, plus full
`Damascus.rn4` and `Incirlik.rn4` airfield files)

### Question

Continuing `2026-09-03-m5-terrain-file-formats.md`: with real, large/full local
files now available (`world-model/data/raw/dcs/syria/roadnet-samples/`, gitignored),
resolve the two open items that session left unconfirmed against real bytes at scale:
1. The exact `.routes` float64-triple data-start offset (prior "hint" of 99 was
   wrong; a brute-force scorer existed but had only run on synthetic fixtures).
2. Whether `.rn4`'s apparent fixed 32-byte/8×int32 record hypothesis (previously
   verified only against a 64-int32 sample) holds at real scale, and what the 8
   fields mean.

Also: does this resolve the format well enough to write a production parser for
M5 Stage 2?

### Findings

**`.routes` — data-start offset CONFIRMED, and the file's structure is corrected**

- **Data-start offset is exactly byte 93**, not 99 (prior wrong hint) and not the
  vaguely-remembered "~80". Found by scanning every byte offset near the header
  for one that reads as a plausible-magnitude `float64` (`1e-3 < |x| < 1e7`) with
  no assumption of triple/envelope structure — offset 93 is the unique clean hit,
  and decoding forward from it reproduces the exact same first-four-triple values
  recorded in the prior session's hand-decode (`(214985.70, 18.74, -45079.89)`,
  ...). — **evidence: reproduced-locally** — **source:** ad hoc scripts, this
  session, against `Syria.routes.head50m`.
- **Correction to the prior "flat float64 array" model: `.routes` is not one
  homogeneous array of (x,y,z) triples.** It is a sequence of length-prefixed
  blocks. The first block at offset 93: an `int32` count field at byte 89 reads
  `343`, followed by exactly 343 `float64` (x,y,z) position triples (bytes 93 to
  8325, `343 × 24 = 8232` bytes, closing exactly on the observed boundary). The
  343 points decode as a smooth, physically plausible road/taxiway-loop
  polyline near Damascus (x≈215000, z≈-45000..-50000) — deltas between
  consecutive points are all under ~300 m and mostly under 100 m, and the last
  3 points closely repeat the first 3 (`214985.70/-45079.89` at the start vs.
  `214985.65/-45079.88` and `214982.84/-45078.98` near the end) — i.e. this is
  a **closed-loop route**, not corruption. — **evidence: reproduced-locally**
  — **source:** same scripts, byte offsets and values recorded above.
- **Immediately after that position block, at offset 8325, there is a second
  `int32` count field (also reading `343`) followed by 343 more `float64`
  triples — but these are unit-length vectors** (magnitude computed as exactly
  `1.0` for every one of the first 5 checked, e.g. `(-0.291, 0.0, -0.957)`,
  magnitude `1.0000000000000002`). This is essentially impossible to occur by
  chance for real-world DCS coordinates (which run in the tens/hundreds of
  thousands), so this is confidently a **per-point direction/tangent vector
  array**, not more position data. — **evidence: reproduced-locally** —
  **source:** same.
- **Working model so far: each "route" block = `[int32 N][N × float64 xyz
  position][int32 N][N × float64 xyz unit direction]`.** This is a real,
  positive structural finding — `.routes` encodes not just centerline points
  but a per-point heading/tangent, which is exactly what a "taxi/road-following"
  runtime query would want (no need to numerically differentiate the polyline
  for heading). — **evidence: reproduced-locally, one block fully verified —
  evidence: inferred for "this pattern repeats for every route" (see next
  finding, which complicates it)**.
- **Unresolved wrinkle: the block immediately following the direction array
  does not fit the same two-count-fields-then-N-points model cleanly.** At
  byte offset 16561 (right after the direction array ends), the next `int32`
  reads `0`, and the `int32` right after that (offset 16565) reads `341`. If
  the model were "next route: `[posCount][pos][dirCount][dir]`" we'd expect a
  real position count there, not `0`. This could mean: (a) a genuine
  zero-length/degenerate route exists in the data, (b) there is an additional
  field (e.g. a route ID, a road-type index, or a "closed-loop" flag) between
  routes that this session did not identify, shifting field alignment by a few
  bytes, or (c) the two-array-per-route model is itself wrong past the first
  route. **This was not resolved this session** — evidence: reproduced-locally
  (the anomaly itself is real and reproducible) but its interpretation is
  **inferred/unresolved**.
- **Latakia coordinates were not found in the 50MB head sample.** Scanning all
  ~2.08M decoded records (using the corrected block-aware understanding, this
  scan was actually done under the old flat-array assumption before the block
  structure was found — see Reproducible Test for the caveat) for proximity to
  the Latakia ARP (x≈41935, z≈5685, per `plans/m5-first-persistent-model/plan.md`)
  found a closest approach of ~5.3 km, with zero points within 5 km. This is
  **inconclusive**, not a negative result: the head-50MB sample is only ~2% of
  the full 2.25 GB `.routes` file, and there is no reason to expect route
  ordering in the file to start near Latakia. — **evidence: reproduced-locally
  (the scan ran and gives this number), but evidentially inconclusive** for the
  question "does `.routes` cover Latakia" — needs either the full file or a
  targeted seek.
- The flat-array assumption's apparent breakdown partway through the 50MB
  sample (record ~343 as decoded under the old model) is now **explained**, not
  a mystery: it's exactly the position/direction block boundary described
  above, not file corruption or a truncation artifact.

**`.rn4` — 32-byte/8×int32 record hypothesis confirmed at real scale, with
column semantics partially resolved, and an important structural correction**

- **Header layout refined.** After the length-prefixed class name
  (`landscape4::lRoadNetwork`), there are **two** `int32` fields before the
  string table, not one: an unidentified field (`5` in all three files checked
  — Damascus, Incirlik, Syria) then the string-table entry count. The entry
  count matches prior findings exactly: **7** for Damascus, **8** for
  Incirlik, **23** for Syria — confirming agent-memory
  `project_m5_roadnet_format_decode.md`'s numbers were right, but the field
  offset immediately preceding the count needed correcting (it's `field_a`
  then `count`, not `count` alone). — **evidence: reproduced-locally**.
- **The fixed 32-byte/8×int32 record region is real and reproduces at scale**,
  not just in the 64-int32 sample from the prior session. Decoding hundreds of
  consecutive rows from all three files' record regions shows the same pattern
  previously seen in miniature:
  - Column 1 is constant `1` within a run.
  - Column 4 is mostly constant `2` (Syria's larger sample also shows brief
    runs of `3`, suggesting more than one record subtype sharing the same
    8-int32 shape).
  - **Column 2 is a self-referential row/node index that increments in pairs**
    (`0,0,1,1,2,2,3,3,...` — confirmed cleanly in the Syria sample's first 15
    rows).
  - **Column 5 is a paired index matching column 2's value but with local
    swaps** (`1,0,3,2,5,4,7,6,9,8,...`) — the same "reversed-pair-index"
    signature flagged in the prior session's 8-row sample, now confirmed
    across hundreds of rows in real data. This strongly supports a
    **directed-edge-pair encoding**: each physical road segment is stored as
    two directed edges (forward/reverse), each referencing its sibling.
  - Columns 0, 3, 6, 7 vary per row and their exact meaning is **not**
    resolved this session. Column 6 in the Syria sample takes small
    round-number values (`50`, `100`, ...) that don't match the string-table's
    index range (0–22) directly, so "string-table type index" is not
    confirmed for any column — this remains a real open question, contra the
    plan's hope that a column's range would obviously match the string table.
    Columns 0/3/7 have magnitudes (hundreds to over a million) that are
    plausible as byte offsets or point-indices into a `.routes`-style array,
    but this is **speculative, not verified** — no cross-reference to an
    actual `.routes` file was attempted this session for `.rn4`'s fields (and
    Damascus/Incirlik have no paired `.routes` file at all — see below).
  — **evidence: reproduced-locally for the structural pattern; evidence:
  inferred (unverified) for all specific field-semantics guesses**.
- **Important correction: the 32-byte record region is NOT one flat table
  spanning to end-of-file.** This is new and changes the go/no-go picture.
  Scanning `Damascus.rn4` and `Incirlik.rn4` end-to-end for where column 1
  stops being the constant value `1` finds the clean table breaks down after
  only **79 rows (Damascus, 2,528 of 375,828 remaining bytes — 0.67%)** and
  **132 rows (Incirlik, 4,224 of 825,165 remaining bytes — 0.51%)**
  respectively. After that point, the byte stream under the 8-int32-stride
  model no longer shows the constant/self-index/paired-index pattern at all —
  it looks like something structurally different, not a corrupted or
  misaligned continuation of the same table. A direct scan for
  plausible-magnitude `float64` coordinate values immediately after the
  Damascus break found none, so this majority-of-file data is **not**
  obviously raw world-coordinate geometry in the same encoding `.routes` uses.
  — **evidence: reproduced-locally (the table's real extent and the absence
  of an obvious coordinate re-encoding just past it)**.
  For the whole-theatre `Syria.rn4.head50m` sample, the same "short table"
  pattern **repeats many times throughout the file** rather than occurring
  once: scanning the first 50 MB for runs of ≥5 consecutive rows matching the
  column-1/column-4 signature finds over 20,000 separate such runs, of highly
  variable length (5 rows up to several thousand). This is consistent with
  the file being organized as **many separate per-road-segment topology
  sub-tables interleaved with other, still-undecoded data** — the same
  "count/type-tagged block" design philosophy `.routes` turned out to use,
  rather than one homogeneous array. — **evidence: reproduced-locally**.
- **Net effect on the airfield files specifically: `.rn4` alone does not
  obviously contain the taxiway/runway centerline geometry.** Since
  Damascus.rn4/Incirlik.rn4 have no paired `.routes` file (confirmed by
  directory listing — only whole-theatre `Syria.routes` exists), and the
  >99%-of-file byte range past their short topology table doesn't decode as
  plausible float64 coordinates under the tested offset, **the actual source
  of airfield taxiway point geometry remains unidentified**. This is the
  single most important open gap from this session.

### Reproducible Test

All analysis this session was done with short, throwaway Python scripts run
directly against the local files (no DCS access needed for any of this — the
files are already extracted to `world-model/data/raw/dcs/syria/roadnet-samples/`,
gitignored). None of the scripts were persisted as repo artifacts; they are
trivial to reconstruct from the byte offsets and `struct` format strings
documented in Findings above. Key reusable steps, for whoever picks this up
next:

1. **`.routes` block reader**: given a file handle, find the class-name string
   (`data.find(b"landscape4")`), read its 4-byte length prefix to get its end
   offset; from there the reproducible constant is **data-start = end-of-class-
   -string-region + 34 bytes = absolute byte 93** for `Syria.routes` (the
   intervening 34 bytes — offsets 59 through 92 — contain a `3`, an `11464`
   (plausibly total route count for the whole file — not verified), several
   sentinel-looking int32s (`-65536`, `-1`, `65535`), and finally the first
   block's own `int32` position-count at byte 89). A route block reader should
   be: read `int32 N` (position count), read `N × float64×3`, read `int32 M`
   (direction count — seen equal to N once, not verified as always equal),
   read `M × float64×3`, then the next `int32` is the following route's own
   count — **except this loop broke on the 3rd block (see Findings "unresolved
   wrinkle")**, so this reader is not yet trustworthy for a full run without
   more validation.
2. **`.rn4` topology-table reader**: after the length-prefixed class name, read
   `int32 field_a` (seen `5` in all 3 files, meaning unknown), `int32
   string_count`, then `string_count` length-prefixed ASCII strings (4-byte
   length + bytes each) — this is the corrected string-table offset
   calculation (prior session's `after_str` position was off by 4 extra
   bytes for `field_a`). Immediately after the string table, read rows of
   `8×int32` (32 bytes) while column 1 (`row[1]`) stays a small constant
   (`1`) and column 4 (`row[4]`) stays in `{2,3}` — the run ends when column 1
   jumps to a large/garbage-looking value, and that end offset is the true
   extent of that particular topology sub-table (not the whole record
   region).
3. To reproduce the "20,608 runs" periodicity finding: scan every 4-byte
   offset (aligned to `table_end mod 4`, since the true table start is not
   generally a multiple of 4 from file-start) in the 50MB `Syria.rn4.head50m`
   sample, testing `row[1]==1 and row[4] in (2,3)` at each candidate 32-byte
   window, then cluster consecutive hits spaced exactly 32 bytes apart into
   runs.

### Possible Approaches

**`.routes` point/direction geometry — recommendation: GO for the position
array specifically, with one more confirmation pass before writing the
production parser.**

1. The position-array-with-length-prefix pattern is solid, reproducible, and
   gives exactly what M5 Stage 2 wants (dense, DCS-authoritative road-centerline
   points) — arguably better than previously known, since the direction-vector
   array (if the "always paired with positions" pattern holds) would let a
   parser get per-point heading for free instead of numerically differentiating
   the polyline.
2. **Before writing the production parser**, the "row 341→0" anomaly needs one
   more look — ideally by reading several more consecutive route blocks by
   hand (as this session did for block 0 and block 1) to see whether the
   `[N][pos][M][dir]` model holds once the ambiguity at the 3rd block is
   correctly explained, or whether there's a 3rd field per route (route ID?
   road-type index — cross-referenceable against `.rn4`'s string table if so)
   that shifts the boundary. This is a bounded, cheap follow-up (a few more
   hours of the same kind of local analysis, no DCS access needed) — not a
   new investigation.
3. Confirming actual Latakia coverage needs either downloading/reading more of
   the 2.25 GB `.routes` file (beyond the 50MB head sample already available)
   or a targeted approach — e.g. scan for the byte pattern of a plausible
   Latakia-range x value (`41935 ± 500`, encoded as its raw float64 bit
   pattern) directly, without needing to correctly parse every preceding block.

**`.rn4` graph/topology — recommendation: PARTIAL GO. The short per-segment
topology tables (connectivity, forward/reverse edge pairing) are well
understood; the geometry question is NOT resolved, especially for airfields.**

1. For the whole-theatre `Syria.rn4`, it's plausible (not yet verified) that
   the unresolved numeric columns (0, 3, 7) are indices/offsets into
   `Syria.routes`' point array — if so, `.rn4` supplies graph structure
   (which road connects to which, road type via some not-yet-identified
   field) and `.routes` supplies the actual point geometry, which would be a
   clean and sensible design. This cross-reference was **not tested** this
   session (would need decoding a `.rn4` sub-table and a `.routes` block from
   the same byte region and checking whether an `.rn4` field value matches a
   real `.routes` byte offset or point index) — this is the single highest-
   value follow-up probe for confirming the whole-theatre pipeline design.
2. For **airfield-only `.rn4` files** (Damascus, Incirlik, and presumably
   every other airfield), there is no paired `.routes` file, and this session
   found no obvious embedded coordinate data in the >99% of file bytes past
   the short topology table. **This is a real gap, not a formality** — if
   Architect wants DCS-native (rather than OSM-derived) taxiway geometry for
   airfields specifically, this needs a dedicated follow-up probe (systematic
   scan of the untouched majority-of-file byte range for a different
   coordinate encoding — e.g. scaled/fixed-point int32 rather than float64,
   or a different stride).
3. Given the OSM-for-attributes/DCS-for-geometry split already established in
   M3, and given `.routes` alone already supplies whole-theatre road-centerline
   geometry with headings, Architect may reasonably decide airfield taxiway
   detail specifically isn't worth chasing further right now — M5's own scope
   is a 20×20 km region around Latakia (an airbase, `plans/m5-first-persistent-
   model/plan.md`), so this gap is directly relevant to that milestone, not a
   hypothetical.

### Unresolved

- **The `.routes` block sequence past the first route is not fully modeled**
  (the `0`/`341` anomaly at byte 16561) — needs a few more route blocks decoded
  by hand to resolve before a production parser can loop over the whole file
  with confidence.
- **`.routes`' actual coverage of the Latakia region is unconfirmed** — the
  50MB head sample doesn't reach it (or route ordering doesn't put Latakia
  early in the file); needs either more of the file or a targeted byte-pattern
  search.
- **No `.rn4` numeric column has been confirmed to be a string-table type
  index, a `.routes` cross-reference, or a length/width value** — columns 0,
  3, 6, 7's semantics are still open. Column 6's small-round-number values
  (`50`, `100` in the Syria sample) are a lead worth following (could be a
  coarse-grained road class code, independent of the fine-grained string
  table) but wasn't chased further this session.
- **Airfield taxiway/runway point geometry source is unidentified.** This is
  the most significant unresolved item — Damascus.rn4/Incirlik.rn4's bulk
  content (>99% of file bytes) is completely undecoded, and no companion
  `.routes`-style file exists for airfields. Whether this is even needed
  depends on Architect's scope decision (see Possible Approaches item 3).
- **The meaning of the `.routes` header's intervening fields (bytes 59–92,
  including the `11464` value speculated as "total route count") was not
  investigated this session** — would help validate whether the file can be
  parsed as "N routes, each self-describing its own length" without needing
  brute-force block-boundary detection.

---

## Session 2 (2026-09-04, same day, follow-up)

**Question (restated from task):** resolve two specific loose ends before
implementation: (1) the `.routes` per-route block-boundary bug past route 1,
and (2) what the >99% undecoded majority of airfield `.rn4` files actually is
— specifically, does DCS-native airfield taxiway/runway *point geometry*
exist anywhere in these files at all. Both threads investigated against the
same real local files (`Damascus.rn4`, `Incirlik.rn4`, `Syria.rn4.head50m`,
`Syria.routes.head50m`).

### Findings

**Thread 1 — `.routes` block boundary: SOLVED functionally (scan-forward),
per-route trailer partially decoded, not fully.**

- **The `[N][pos][N][dir]` model is correct but incomplete: each route carries
  additional trailer arrays after the direction array, all sized off the same
  point count `N` (or `N`±1/2/3), before the next route's own `[N][pos]...`
  begins.** Decoded by hand for route 1 (`N=343`), in order after the
  direction array (ending at byte 16561):
  1. `int32 flag=0` (byte 16561), `int32 count=341` (byte 16565), then **341
     `float64` scalars** (not triples) starting at byte 16569, values
     monotonically increasing from `0.0` to `16677.16` — a near-perfect
     cumulative-arc-length curve along the route. **Confidently: per-point
     cumulative distance-along-route**, evidence: reproduced-locally (found
     by brute-force scoring the start offset against "full array must be
     monotonic" — offset 16569, not 16577 as a naive read would suggest, is
     the true start; the header's placement of the `0` flag byte and count
     field is off by 4 bytes from a naive guess).
  2. Immediately after (byte 19297): `int32 count=341` followed by **341
     `int32` values, all exactly `0`** in this sample. Evidence:
     reproduced-locally for structure; semantics **inferred** (a flags/reserved
     column — possibly "is-intersection" or "is-explicit-waypoint", untestable
     with an all-zero sample).
  3. Immediately after (byte 20665): `int32 count=340` followed by **340
     `float32` scalars**, bounded roughly `[-121, +71]` — plausibly per-point
     curvature or bank angle. Evidence: reproduced-locally for structure,
     semantics **inferred/speculative**.
  4. After that, a further region of repeating ~64-byte float32 records (12
     non-zero float32 + 4 always-zero float32) whose own count field and exact
     extent were **not resolved** this session — this region was *not*
     hand-parsed field-by-field; it was only established that walking past it
     via brute-force search successfully finds the next route.
  - **Net trailer size scales linearly with N, not fixed and not fully
    decoded.** Measured across the first 15 whole-theatre routes: trailer
    byte-count from end-of-direction-array to start-of-next-route's `N` field
    divided by that route's `N` is **consistently ~155.7–156.2 bytes/point**
    across all 15 samples (`N=209..405`, trailer `32493..61679` bytes) — a
    tight, reproducible ratio, strong evidence the trailer is a deterministic
    function of `N` (several fixed-multiplier per-point arrays), not padding
    or variable garbage. — **evidence: reproduced-locally** (the ratio
    itself; **inferred** that this generalizes to all routes, not just these
    15).
- **Practical resolution: a production parser does not need to fully decode
  the trailer to walk the file correctly.** Scanning forward byte-by-byte
  from the end of the direction array for the next offset whose `int32`
  reads as a plausible route-point-count `N` (5–20000) followed by `N`
  `float64` xyz triples that are all within DCS's real coordinate envelope
  (`|x|,|z| < 1e6`, `-2000 < y < 6000`) reliably and unambiguously finds the
  true next route boundary — verified for **15 consecutive whole-theatre
  routes** with zero false positives (this is the same technique used
  successfully for the `.rn4` geometry blocks, see Thread 2). — **evidence:
  reproduced-locally**, walked and printed all 15 routes' offsets/`N`/trailer
  sizes in this session.
- **Latakia coverage: reversed from Session 1's "not found."** Session 1's
  negative result was against the old, incorrect flat-array indexing and is
  superseded. This session ran a direct, index-agnostic scan of the full
  50MB `Syria.routes.head50m` sample for any 8-byte-aligned `float64` triple
  whose `x` falls in the Latakia region (`41934.892 ± 10000`) with a
  plausible non-denormal `y` (elevation) and `z` in the matching region
  bound, using the `array` module for fast bulk reinterpretation (8 phase
  passes for byte-alignment) rather than a full route walk. Found **17
  candidate triples**, clustering into a handful of distinct, spatially
  coherent coordinate sets — e.g. `(50665.2, -0.56, -38.8)` and
  `(51747.0, -0.00002, -15.6)` (near-zero elevation — consistent with
  Mediterranean coastal terrain) and `(36793.8, 1046.5, -14.6)` (consistent
  with nearby high ground, the Jabal Ansariyah range reaches >1000 m near
  Latakia). — **evidence: reproduced-locally, moderate confidence** (the
  scan is sound and denormal-filtered, but these 17 raw triple-hits were not
  each confirmed to belong to a coherent walked route block — a handful could
  still be coincidental if a non-route part of the file happens to contain a
  matching triple). This is enough to say **`.routes` plausibly does cover
  the Latakia region within the 50MB head sample**, reversing Session 1's
  "not found" — full confirmation would mean walking a complete route
  containing one of these points end-to-end.

**Thread 2 — `.rn4`: MAJOR POSITIVE FINDING. The bulk of the file is not
one flat topology table — it is (a) a graph/adjacency section, then (b)
embedded route-block geometry using the same schema as `.routes`. Airfield
taxiway/runway geometry DOES exist in these files.**

- **String table confirmed to be road/segment *type* labels, not generic
  identifiers.** Damascus: `taxiway_24m, taxiway_61m, taxiway_15m,
  taxiway_52m, taxiway_36m, taxiway_41m, runway_65m`. Incirlik: `taxiway_61m,
  runway_65m, taxiway_52m, taxiway_22m, taxiway_40m, taxiway_15m,
  taxiway_23m, taxiway_24m`. The trailing number is almost certainly segment
  *width in meters*. — **evidence: documented** (read directly, ASCII
  strings, no inference needed).
- **Topology-table column 6 CONFIRMED as the string-table type index** (this
  resolves a Session 1 open question). Distribution: Damascus 71/79 rows
  `col6=0` (`taxiway_24m`), 8/79 rows `col6=3` (`taxiway_52m`); Incirlik
  128/133 rows `col6=0` (`taxiway_61m`), 4/133 `col6=3` (`taxiway_22m`). One
  boundary/sentinel row per file has an out-of-range `col6` value and a
  different `col4` (`3` instead of `2`), coinciding exactly with where the
  clean-table scan stops — this row is the table's own terminator/sentinel,
  not a data row. The type distribution (a dominant common width plus a
  minority of one specific wider type) is exactly what a real airfield's
  taxiway network looks like. — **evidence: reproduced-locally**.
- **Immediately after the topology table (Damascus: byte 2732 onward) is a
  second, much larger region of small-integer `int32` pairs** (`(9,81),
  (9,1), (75,160), (3,79), ...` — hundreds of pairs, first-of-pair values
  mostly small (`0-20`ish) with occasional larger jumps up to ~175, matching
  magnitude range of the unresolved topology-table columns 0/3/7). This
  looks like a node/edge adjacency or index-reference structure, **not**
  coordinate data (confirmed no plausible float64/float32 triples decode in
  this specific sub-region). Its exact schema was **not** resolved this
  session — flagged as the next open item, see Unresolved. — **evidence:
  reproduced-locally (structure); inferred (its role as adjacency data)**.
- **CONFIRMED, both files: real point geometry — the same `[int32 N][N ×
  float64 xyz]` schema `.routes` uses — is embedded later in the `.rn4`
  file, after the adjacency-like section.** For Damascus, hand-decoded
  blocks starting at byte 20213 (`N=6`) and 20913 (`N=7`) etc. decode as
  smooth, closely-spaced (sub-20 m point spacing) polylines at
  `x≈-180500..-182700, y=612.000612 (constant), z≈49400..52400` — a flat,
  single-elevation taxiway apron, exactly as expected for a real airfield
  surface. Same pattern generalized to **Incirlik** (a separate airfield):
  hand-decoded block at byte 34277 (`N=6`) decodes as `x≈221860..221880,
  y≈69.3..70.3, z≈-33756..-33869` — again smooth, tightly-spaced, flat-ish
  elevation matching Incirlik's known low altitude. — **evidence:
  reproduced-locally, both files** — this reverses Session 1's conclusion
  that "no obvious coordinate data" exists in the post-table majority of the
  file; Session 1's scan did not search far enough into the file / used
  bounds too loose or too tight in the wrong place to find it.
- **Coverage of the embedded geometry is only partially walked, not
  exhaustively confirmed for 100% of segments.** A scan-forward walker (same
  technique as `.routes` Thread 1) starting at Damascus's first geometry
  block (byte 16398) and requiring a minimum `N≥5` (to suppress noise — see
  below) found **222 blocks, summing 1887 points**, before losing sync at
  byte 251721 of the 376000-byte file (~67% coverage). With no minimum-`N`
  filter, brute-force byte-scanning the *whole* file for any plausible
  small tight-bounded triple run found up to **610 raw hits**, but many of
  these (`N=2,3`) are very weak evidence individually and likely include
  false positives from the still-undecoded adjacency/trailer regions — the
  222-block, `N≥5` figure is the more trustworthy number. **This gap (33%
  of file un-walked, and the true block-separator logic in this
  region not fully reverse-engineered) means a production parser needs a
  slightly more robust walker than what this session built**, not a
  fundamentally different approach. — **evidence: reproduced-locally
  (the walk and its numbers); the walker's completeness is
  inferred-incomplete, not a hard blocker**.
- **This resolves the single most significant open gap from Session 1: DCS
  Mission-Scripting-independent, static-file airfield taxiway/runway point
  geometry is real and extractable**, at least for a substantial majority of
  segments in both airfield files tested. The earlier "no `.routes`-style
  companion file, no coordinate data found" conclusion is **superseded**.

### Reproducible Test

All work this session again used short throwaway Python scripts (stdlib
only: `struct`, `array`) run directly against the local files — no DCS
access needed, nothing persisted as a repo artifact. Key reusable recipes:

1. **`.routes` route-boundary walker** (validated for 15 consecutive
   routes): from a route's direction-array end offset, scan forward
   byte-by-byte for the next offset `off` where `struct.unpack_from("<i",
   data, off)` gives `5 <= N <= 20000` **and** the following `N × float64×3`
   all satisfy `-1e6 < x,z < 1e6` and `-2000 < y < 6000`. For performance,
   pre-filter candidates with a cheap 3-point check (first/middle/last
   triple only) before paying for the full `N`-point unpack — this is what
   made scanning several MB tractable in a few seconds instead of minutes.
   A naive full-unpack-every-candidate-offset version was killed after 6+
   CPU-minutes on a 50MB buffer — **do not reuse that naive form**.
2. **Latakia/region coverage scan**: use the `array` module to bulk-reinterpret
   the whole buffer as `float64` at all 8 phase offsets (`array.array('d');
   arr.frombytes(data[phase : phase + aligned_len])` for `phase in range(8)`)
   — this is far faster in CPython than per-offset `struct.unpack_from` in a
   Python loop. Filter candidate `x` values into the target bbox, then verify
   `y`/`z` at `off+8`/`off+16` with `struct.unpack_from`, **rejecting any
   value that is nonzero but has magnitude `< 1e-6`** (denormalized-float
   garbage from misaligned reads — without this filter the scan returns
   thousands of false positives with `y`/`z` values like `1e-312`).
3. **`.rn4` geometry-block finder**: after locating the topology table's end
   (walk `8×int32` rows while `row[1]==1 and row[4] in (2,3)`, per Session
   1's method), the geometry region does **not** start immediately — there
   is an intervening adjacency-like section (see Findings) of unknown exact
   length. This session located the geometry region's start empirically (by
   brute-force scanning a wide byte range for the first plausible tight-bbox
   `[N][xyz]` block) rather than computing it from a header field — **this
   is a gap a production parser will need to close more rigorously** (e.g.
   by decoding the adjacency section's own length, not by scanning).

### Possible Approaches

**`.routes` — recommendation: GO, upgraded from Session 1's "GO pending
one more check."** The scan-forward boundary-finding technique is validated
across 15 real consecutive routes with no false positives, and is cheap
enough (with the 3-point pre-filter) to run over the full file. A production
parser should:
1. Extract point-array + direction-array data (both solid).
2. **Treat the trailer as an opaque, skippable blob** located by scan-forward
   rather than attempting to parse it field-by-field — the ~156 bytes/point
   ratio is a good sanity check/progress estimate but not a substitute for
   the scan.
3. If the trailer's arc-length array (item 1 in Findings) is wanted (e.g. to
   avoid recomputing cumulative distance), it can be decoded on demand using
   the offsets documented above; this is optional, not required for basic
   centerline extraction.

**`.rn4` — recommendation: UPGRADE from Session 1's "PARTIAL GO, geometry
gap" to GO for geometry too, pending a slightly more robust walker.**
1. The type-index confirmation (column 6) means whole-theatre road/segment
   *classification* is solid for at least the topology-table prefix of each
   file — combined with the geometry-block finding, both (b) road
   type/classification and (c) airfield taxiway/runway geometry are now
   **positively answered "extractable without live-mission polling,"**
   reversing Session 1's stance on (c).
2. Before writing the production parser, the adjacency-like section between
   the topology table and the geometry blocks should get one more decode
   pass — right now the parser has to brute-force-search past it, which
   worked for two files at small scale but is not provably robust for every
   airfield or for the much larger whole-theatre `Syria.rn4`. This is a
   bounded follow-up (a few more hours of the same technique), not a new
   investigation.
3. Given time spent, this session did not push the `.rn4` geometry walker to
   100% coverage or cross-validate it against the topology table's row count
   (i.e., confirm exactly one geometry block per topology row) — Architect/
   Implementer should treat "222 blocks found, ~67% of file walked" as
   good-enough proof of feasibility, not a finished extraction, and budget a
   validation pass before relying on segment counts for anything
   correctness-sensitive.

### Unresolved

- **The `.rn4` adjacency-like int32-pair section's exact schema is still
  undecoded** — this is now the single largest true gap in both files
  (Thread 1's `.routes` trailer is decently understood and safely
  skippable; this section's role/boundaries are not).
- **The `.rn4` geometry walker does not yet reach 100% of either file** —
  67% for Damascus in this session's run; Incirlik and the whole-theatre
  `Syria.rn4` sample were spot-checked (one block each) but not walked
  exhaustively.
- **The `.routes` Latakia-coverage finding (17 candidate triples) is
  moderate-, not high-confidence** — none of the 17 were confirmed to
  belong to a fully walked, self-consistent route block; a follow-up should
  pick one candidate offset and walk its full enclosing route to confirm.
- **Column 6's confirmation is strong but the topology table's other
  unresolved columns (0, 3, 7) were not connected to the newly-found
  adjacency section or geometry blocks** — e.g., whether a given topology
  row's `col0`/`col3`/`col7` values index into a specific geometry block
  (which would let a parser map "this is a `taxiway_52m` segment" directly
  onto "these are its N points") is still open. Without this link, type and
  geometry are each independently extractable but not yet provably
  joinable per-segment — this matters if Architect wants
  per-segment-typed geometry rather than an undifferentiated point cloud.
