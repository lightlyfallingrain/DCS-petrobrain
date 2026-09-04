---
name: m5-acquisition-decision
description: User chose full 2.25 GB local copy of Syria.routes over remote-extract-and-sync-back, against the architect recommendation
metadata:
  type: project
---

M5 acquires `Syria.routes` (2,251,462,776 bytes) as a **full local copy** on the Mac
(`world-model/data/raw/dcs/syria/roads/`), not by running an extractor on the Windows DCS
box and syncing back a small region extract. User decision, 2026-09-04 — the **opposite**
of the plan's stated recommendation.

**Why:** Local iteration speed. A walker bug becomes a local edit rather than a
cross-machine round trip, which materially de-risks the Stage 2 coverage gate. Cost is
2.25 GB of already-gitignored disk.

**How to apply:** Do not re-propose remote extraction for large static terrain files
unless the user raises disk pressure. `tools/wsl/run_roadnet_extract.sh` was dropped and
the "does WSL have python3" prerequisite is moot. The region-extract format and its
manifest are kept, but demoted from cross-machine transport to an optional local cache in
`data/processed/`.

Generalizable: this user weights fast local iteration above avoiding a large one-time
copy. Worth assuming as the default for similar logistics calls.

Also settled: the full `Syria.rn4` (2.28 GB) is **not** needed. M5 uses `.rn4` only for its
string table (type vocabulary) and topology rows, both of which live in the file header and
are fully covered by the existing 50 MB head sample. The parts needing the whole file —
geometry region and adjacency section — are exactly what M5 deliberately does not use.

Related: [[m5-roads-source-reversal]], [[m5-airfield-layer]].
