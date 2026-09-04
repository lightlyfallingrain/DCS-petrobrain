---
name: m5-roadnet-stage2
description: M5 Stage 2 roadnet parser results — gate/coverage numbers, resync pre-filter correctness trap, real container header layout.
metadata:
  type: project
---

Stage 2 (`src/roadnet/`) landed on `feature/m5-first-persistent-model`. Key facts for anyone
continuing roadnet work (M6 pathfinding, `.rn4` type-join, etc.):

- **Real container header layout** (confirmed against real files, not just the research note):
  8 x int32 `[2, 48, <byte_count>, 0,0,0,0,0]` then a length-prefixed ASCII class name.
  `.routes` class name is `landscape4::lRoutesFile` (data starts at byte 59 after the class
  name, byte 93 after the file's own intervening sentinel bytes); `.rn4` class name is
  `landscape4::lRoadNetwork` (data offset 60). `byte_count` overflows a signed int32 for
  `Syria.routes` (reads as -2045825944, not a bug — the real file is 2.25GB).
- **Resync pre-filter-only is unsafe; full N-point validation after the pre-filter is
  load-bearing, not redundant.** An early test that accepted a resync candidate after only the
  first/middle/last pre-filter (skipping full validation) produced false-positive matches
  within a handful of blocks on the real 50MB sample. Always pre-filter *then* fully validate,
  never pre-filter *instead of* validate.
- **`.rn4` topology row termination rule, confirmed against real Damascus (79 rows) and
  Incirlik (132 rows)**: a data row has `column[1]==1 and column[4]==2`; the table's own
  sentinel/terminator row (not a data row) has `column[4]==3`. Column 6 is the confirmed
  string-table type index.
- **Full-file walk of the real `Syria.routes` (2.25GB): 14,861 whole-file routes, 131 intersect
  the Latakia bbox (gate PASSED), 99.92% of bytes covered, 302 sync_loss_events (~2%), wall time
  ~1034s (~17.2 min) for an unoptimized pure-Python walk with per-route progress printing.**
  The header's speculated "total route count" field (11464 at byte ~63) does NOT match the
  walked total — walked count is ~30% higher, not lower. This is an open, unresolved
  discrepancy (see `plans/m5-first-persistent-model/implementation.md` Stage 2 section) —
  don't assume the header field means "route count" without more evidence.
- `roadnet/extract.py` was built per the plan but never wired into the pipeline —
  `build/ingest_roadnet.py` walks the real `.routes` file directly every rebuild (no caching).
  `tools/extract_roadnet_region.py` and `tools/inspect_roadnet.py` were deliberately not built
  (out of Stage 2's explicit task scope) — cheap to add later since `extract.py` does the real
  work already.
