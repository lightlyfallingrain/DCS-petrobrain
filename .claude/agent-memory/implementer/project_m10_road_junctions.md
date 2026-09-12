---
name: project_m10_road_junctions
description: M10 road-junction clustering real numbers, singleton-cluster filtering decision, and the coincident-road false-positive finding.
metadata:
  type: project
---

M10 (`world-model/src/roadnet/junctions.py`) clusters `road` feature endpoints/interior
vertices via grid-bucketed union-find; degree = sum of arms (endpoint=1, interior-attach=2).
Real `latakia-20km` numbers at default tolerance/min-degree (0.5m / 3): 3,266 roads, 6,496
endpoints, 155,900 interior vertices -> 3,980 clusters -> 3,634 junctions kept, 346 dropped
as degree-2 route continuation. Confirmed identical via both a read-only query and a real
full `build_region` rebuild (7m13s, dominated by the `Syria.routes` walk; the junction stage
itself took 0.6s) -- this also confirms `all_features`/`insert_features` read-back-in-same-
connection works for `feature`/`feature_bbox`, not just `grid`/`grid_sample` (a risk the plan
flagged as unconfirmed).

**Singleton-cluster filtering was necessary, not optional.** A union-find over every
endpoint+interior vertex naturally produces a "cluster" of size 1 for every non-coinciding
vertex. Without filtering these out, `latakia-20km` reports 157,625 "clusters" (99% noise,
mostly lone interior vertices of long polylines). `extract_clusters` now drops groups of
exactly 1 vertex before returning -- this doesn't change which coordinates become `junction`
features (`min_degree` filtering is unaffected either way), only what counts as a reportable
"cluster" in stats/tests. The plan's text didn't specify this; treat "cluster" as implying
actual multiplicity (2+) whenever writing a similar union-find-over-sparse-points module.

**Coincident-road false positive, not a tolerance/min-degree problem.** ~32 of 3,634 kept
junctions (all high-degree, up to 41) are cases where DCS represents one physical road
corridor as several long `.routes` polylines that are *exactly coincident* (not parallel) over
a shared stretch -- a bearing spot-check found e.g. 16 "different" roads all reporting the
identical bearing (123.3 deg) at one point, the signature of duplicate/overlapping route
entries rather than a real multi-way intersection. Because the roads are bit-exact coincident,
no tolerance value separates them from a genuine junction, and no min_degree value excludes
them without also excluding real high-arity intersections -- fixing this needs a different
signal entirely (dedupe arms by outgoing bearing before counting degree), which is an
arm-counting *design* change, not a threshold tune. Left as documented backlog in
`junctions.py`'s docstring rather than attempted. Affects <1% of kept junctions; the modal
degree-3 population spot-checked clean (genuinely distinct bearings at every sampled point).

See also [[feedback_verify_rebuild_row_counts]] (this session independently re-confirmed the
junction count two ways, consistent with that memory's advice) and
[[project_m9_direction]]-adjacent: this is the "bridges" backlog's stated reusable-clustering
precedent per the plan's "Second-order effect" section.
