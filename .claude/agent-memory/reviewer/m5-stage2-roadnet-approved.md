---
name: m5-stage2-roadnet-approved
description: M5 Stage 2 (src/roadnet/ DCS-native road parsing) review outcome — approved with minor fixes
metadata:
  type: project
---

M5 Stage 2 (`src/roadnet/`, `build/ingest_roadnet.py`, `query/describe.py` wiring), commits
`1720b77`/`1812166` on `feature/m5-first-persistent-model`, reviewed 2026-09-04. Approved with
minor fixes (only blocker: unstaged agent-memory files — the recurring pattern, see
[[feedback_check_agent_memory_staged]]).

**Why this one is worth remembering beyond the routine memory-staging gap:** the scan-forward
resync test (`test_find_next_point_block_resyncs_past_garbage`) and the subtype-null scope-guard
test (`test_ingested_road_features_never_carry_a_subtype`) both genuinely prove what they claim —
checked by reading them, not just trusting the names. The resync pre-filter-then-full-validate
two-stage order (not pre-filter-only) was confirmed load-bearing for correctness, not just
performance, per implementation.md's own notable-discoveries note — worth checking this specific
ordering again if `container.py` is ever touched.

**Gate/coverage honesty confirmed real, not glossed over:** walked route count (14,861) vs.
header's speculated total (11,464) is ~30% *higher*, left as an explicitly unresolved discrepancy
with two candidate explanations, neither confirmed. `sync_loss_events=302` (~2%) reported
alongside it. This is the kind of finding that's tempting to quietly resolve into a confident
number — it wasn't, and that's correct per the plan's own risk framing.

**How to apply:** for any future `.rn4`/`.routes` follow-up work (M6 pathfinding, airfield
taxiway geometry), re-check whether this route-count discrepancy was ever explained before
trusting the DCS roadnet layer's *count* for anything beyond point-distance queries.
