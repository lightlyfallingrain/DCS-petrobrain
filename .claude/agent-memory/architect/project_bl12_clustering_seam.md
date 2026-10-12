---
name: bl12-clustering-seam
description: belief/groups.py — _cluster_contacts decides membership and reconcile's four phases only assign identity; why a membership fix belongs upstream, and the prior-roster ordering that makes it possible
metadata:
  type: project
---

**`GroupStore.reconcile`'s four phases do not form membership. `_cluster_contacts` does.** By the
time phase 1 (highest-overlap match) runs, the cluster is already a `frozenset` of contact ids;
phase 1 only decides which remembered `Group` id it inherits. Established 2026-10-12 planning
`BL-B58`, where the finding described the absorption as happening "via plain overlap-match" and the
code says otherwise.

**So a membership defect is never fixable in `reconcile`'s phases**, for three reasons worth keeping:

1. `cluster_props` is a dict keyed on the `frozenset`, so mutating a cluster invalidates the key.
2. Removing a member can split the remainder, which would require a second clustering pass inside
   `reconcile`.
3. **Decisive:** a phase-1 gate misses the founding case. The same geometry with no remembered group
   resolves through **phase 3 (found)**, which a phase-1 check never sees. Measured — delete the
   group from the scenario and the identical drift founds a corrupted one.

**The ordering fact that makes an upstream fix cheap.** `ContactStore.tick` calls `reconcile` *after*
`ingest`, and `reconcile` calls `_cluster_contacts` **before** it reassigns `self._groups`. So at the
moment clustering runs, `self._groups` still holds the *previous* reconcile's rosters — the only
membership statement that exists before this tick's clustering. Pass them in as an explicit
parameter rather than reaching for state; `_cluster_contacts` stays a pure function.

**Two currencies that were measured and rejected for membership questions here**, so they are not
re-proposed:

- **Cluster extent / diameter.** Cannot discriminate: a wrongly-widened cluster and its correct
  subset can have *identical* extent when the widest pair is a legitimate one. Extent is the right
  instrument for *spoken width* (A6's Stage 4 guard) and the wrong one for *who is a member*.
- **Centroid distance** (any complete-link or centroid-link admission test). Breaks an
  incrementally-observed convoy tail — each new member is one gap from its neighbour but many gaps
  from the centroid — i.e. re-creates the undermerging `plans/group-undermerging/` fixed.
- `Contact.position.radius_m()` was already rejected for this function
  (see [[project_groups_cohesion_uncertainty_budget_reverted]]) and argues the *wrong way* in these
  incidents: at 213–300 m RMS two contacts 82 m apart are indistinguishable, which is an argument
  for merging.

**A per-edge veto in the union-find is the composable shape.** Single-link then routes around a
vetoed edge through an un-tainted member if a clean path exists, so one bad member does not freeze a
group's legitimate growth. Measured as row F of
`plans/group-cohesion-admission-gate/scratchpad/probe_b58_candidate.py`.
