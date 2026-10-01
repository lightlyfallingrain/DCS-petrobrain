---
name: group-reporting-cohesion-scale
description: measured O(n^2) cost of belief.groups._cluster_contacts and where it starts to matter
metadata:
  type: project
---

`belief/groups.py::_cluster_contacts` (feature/group-reporting, reconciled once per `ContactStore.
tick()`, so on the live 5 Hz poll) does two O(n^2) all-pairs passes: a nearest-neighbour-gap median
computation, then the union-find cohesion test. Measured directly against the branch's own code
(uniform random positions, isolated `_cluster_contacts` calls, `body-layer/.venv`):

| n tracked contacts | per-call cost |
|---|---|
| 16 | 0.06 ms |
| 52 | 0.6 ms |
| 200 | 8.4 ms |
| 500 | 54 ms |
| 2000 | 879 ms |

Scaling is clean O(n^2) (4x n -> ~14x time). The 2026-09-28 sortie's peak was 52 total / 16
concurrent contacts (`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`) -> 0.6 ms,
trivial against a 200 ms poll budget. This needs roughly 300-400+ simultaneously tracked contacts
before it meaningfully eats the poll budget, and 500-2000 before it's a real problem -- 10-40x
today's observed peak. Verdict at review time: APPROVED -- MONITOR, no mitigation needed now; if a
future denser-scene milestone pushes tracked-contact counts into the low hundreds, the fix is a
spatial index (grid/k-d tree) for the nearest-neighbour pass, turning both loops roughly O(n log n).

See also [[project_watch_reporting_scale_notes]] for the git-archive isolated-snapshot benchmarking
technique this reused (build a minimal fixture via the dataclass constructors directly, skip full
`ContactStore.ingest`).

**2026-10-01 re-confirmation on `fix/group-undermerging`** (the cohesion-redesign's own
per-pair backstop, `_pair_backstop_m`): same quadratic shape, slightly updated numbers (22->0.17ms,
100->3ms, 300->25ms, 500->70ms, 800->180ms, 1200->406ms) -- the redesign's extra per-pair dict
lookups (installation cap, EAGER/STRICT policy) don't change the complexity class. The more
important finding from that pass isn't the per-tick contact count at all -- it's that
`ContactStore` never prunes `_contacts`, so this O(n^2) cost grows with every contact ever seen
across a sortie, not the live count. See [[contact_store_never_pruned]].
