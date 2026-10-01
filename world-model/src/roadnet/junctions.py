"""Road-junction detection over the already-ingested `road` feature layer --
pure geometry, no store I/O, mirroring `terrain/features.py`'s two-function
shape (`extract_components` / `to_stored_features`) for the same testability
reason: a pure-geometry intermediate object (`JunctionCluster`) tests can
assert on directly, before `to_stored_features` wraps it with store-facing
provenance/confidence.

**Design decision -- what "degree" counts** (see
`plans/m10-road-junctions/plan.md`'s "Design decision" section for the full
reasoning): two distinct road-vertex match shapes exist and are not
comparable by raw feature-id count.

- **Endpoint-endpoint**: N distinct roads' endpoints coincide. Each
  contributes one "arm". A plain two-road endpoint coincidence (degree 2) is
  very likely one physical road split into two `.routes` polylines
  continuing through the same point, not a landmark.
- **Endpoint-interior (T-junction)**: one road's endpoint lands on a second
  road's interior vertex. The second road does not terminate there -- it
  continues through the point in both directions, contributing **two** arms
  (in + out), while the terminating road contributes **one**. A T-junction is
  therefore degree 3 (2 arms from the through-road + 1 from the branch) even
  though only two distinct `road` feature ids are involved.

Junction degree is the sum of arms at a clustered coordinate. A junction
feature is emitted only where degree >= `min_degree` (first-guess 3, tuned in
Stage 2 -- see `DEFAULT_JUNCTION_MIN_DEGREE`).

Interior-vertex-to-interior-vertex matches (two roads crossing mid-span with
neither having an endpoint there -- a true grade crossing) are out of scope
for this pass: never unioned, not tested for, flagged in the plan's "Risks &
Unknowns" as backlog.

Clustering uses grid-bucketed union-find (bucket cells sized a small multiple
of `tolerance_m`, 3x3 neighbourhood scan) rather than naive O(n^2) all-pairs,
per the recon's own proven approach -- a single `syria-full`-scale region can
carry >14,000 `road` features and correspondingly ~30k+ endpoints.

**Stage 2 real-data validation (`latakia-20km`, 3,266 `road` features, 6,496
endpoints, 155,900 interior vertices).** At `DEFAULT_JUNCTION_TOLERANCE_M`/
`DEFAULT_JUNCTION_MIN_DEGREE`'s first-guess values: 3,980 clusters (groups of
2+ coincident vertices; a lone, non-coinciding vertex is not surfaced as a
cluster at all -- see `extract_clusters`), of which 346 are degree-2 (dropped
as route continuation) and 3,634 kept as `junction` features. 3,905 of the
3,980 clusters are bit-exact (max intra-cluster distance < 1e-6 m); the
tolerance/min-degree first guesses needed no adjustment against this real
output -- a bearing spot-check of 5 random degree-3 clusters all showed two
genuinely distinct road bearings meeting at the point (real T-junctions/
crossings, not near-parallel-road false positives).

**Known false-positive population, not fixed by tolerance/min-degree
tuning.** A small number of the kept clusters (~32 of 3,634, all at
unusually high degree -- the histogram's tail above degree 10) are DCS
representing one physical road corridor as several long, distinct `.routes`
polylines that run coincident (not merely parallel) over a shared stretch --
e.g. a cluster of 16 roads with degree 41, bearing spot-checked and found to
report the *same* bearing (123.3 deg) at every one of the 16 roads' nearby
vertex, not the differing bearings a genuine multi-way intersection would
show. Because these roads are exactly coincident (not just close), no
`tolerance_m` value distinguishes them from a true multi-way junction, and no
`min_degree` value excludes them without also excluding real high-arity
intersections -- fixing this would require a different signal (e.g.
deduplicating arms by outgoing bearing before counting degree), which is a
change to the arm-counting rule itself, not a threshold tune, and is left as
backlog rather than attempted in this pass. See
`plans/m10-road-junctions/implementation.md` for the full finding.

**`vertex_bbox` (junctions-streaming-fix)**: `collect_endpoints`,
`collect_interior_vertices` and `extract_clusters` all take an additive,
opt-in `vertex_bbox: Bbox | None = None` parameter that restricts which
vertices are collected/clustered to those whose point falls inside it.
`None` preserves the original whole-layer behaviour exactly. This exists so
`build.ingest_junctions.ingest_junctions_streaming` can run this module's
grid-bucketed union-find over one padded spatial tile at a time (bounded
memory) instead of the whole theatre's road layer at once -- see that
function's docstring and `plans/junctions-streaming-fix/plan.md` for the
padding/ownership-by-centroid scheme that makes per-tile clustering
equivalent to one whole-layer pass.
"""

from dataclasses import dataclass

from geometry import distance_point_point
from store.chunks import Bbox
from store.models import Point, StoredFeature

# First-guess value (Stage 1), tuned against real `latakia-20km` output in
# Stage 2 -- see this module's own docstring update once Stage 2 lands, same
# discipline a tuned threshold constant elsewhere in this codebase follows
# (`terrain/curvature.py`'s, before it was deleted on
# `feature/landform-geomorphons`). Chosen conservatively below the recon's
# observed clean gap at 1.4 m between genuinely-coincident vertices and the
# nearest unrelated vertex.
DEFAULT_JUNCTION_TOLERANCE_M = 0.5

# First-guess threshold (Stage 1): a plain two-road endpoint meeting (degree
# 2) is route continuation, not a landmark; a genuine T-junction or multi-way
# meeting (degree >= 3) is. See the module docstring's "Design decision".
DEFAULT_JUNCTION_MIN_DEGREE = 3

_EXACT_MATCH_TOLERANCE_M = 1e-6


@dataclass(frozen=True)
class Vertex:
    """One road vertex: `feature_id` is the owning `StoredFeature.id`,
    `point` its `(x, z)` coordinate. `is_endpoint` distinguishes a route's
    first/last point (contributes 1 arm) from an interior point (contributes
    2 arms when another road's endpoint attaches to it -- see module
    docstring)."""

    feature_id: int
    point: Point
    is_endpoint: bool


@dataclass(frozen=True)
class JunctionCluster:
    """One clustered group of coincident/near-coincident road vertices -- the
    pure-geometry intermediate this module's tests exercise directly, before
    `to_stored_features` wraps it with store-facing provenance/confidence."""

    centroid: Point
    degree: int
    connecting_road_ids: list[int]
    max_intra_cluster_distance_m: float


def _in_bbox(point: Point, vertex_bbox: Bbox | None) -> bool:
    """`True` if `vertex_bbox` is `None` (no filtering) or `point` falls
    inside it, inclusive on both ends. Inclusive (not half-open like
    `store.chunks.chunk_bounds`) deliberately: over-inclusion at a padded
    chunk's boundary is safe here -- the caller's downstream centroid-
    ownership filter is what must be exact, not this pre-filter."""
    if vertex_bbox is None:
        return True
    min_x, max_x, min_z, max_z = vertex_bbox
    x, z = point
    return min_x <= x <= max_x and min_z <= z <= max_z


def collect_endpoints(
    roads: list[StoredFeature], vertex_bbox: Bbox | None = None
) -> list[Vertex]:
    """Return the first and last point of every `LineString` road, as
    `is_endpoint=True` vertices. Roads must have `id` set (post-insertion) and
    at least one point; a road with only one point contributes that single
    point once, not twice.

    `vertex_bbox`, if given, drops any vertex whose point falls outside it --
    an additive, opt-in filter used by the chunked streaming ingest path
    (`build.ingest_junctions.ingest_junctions_streaming`) to restrict
    clustering to one spatial tile at a time. `None` (the default) preserves
    exactly the original whole-layer behaviour."""
    vertices: list[Vertex] = []
    for road in roads:
        if road.id is None or road.geom_type != "LineString" or not road.geometry:
            continue
        first, last = road.geometry[0], road.geometry[-1]
        if _in_bbox(first, vertex_bbox):
            vertices.append(Vertex(feature_id=road.id, point=first, is_endpoint=True))
        if last != first and _in_bbox(last, vertex_bbox):
            vertices.append(Vertex(feature_id=road.id, point=last, is_endpoint=True))
    return vertices


def collect_interior_vertices(
    roads: list[StoredFeature], vertex_bbox: Bbox | None = None
) -> list[Vertex]:
    """Return every interior (non-endpoint) vertex of every `LineString`
    road, as `is_endpoint=False` vertices. `vertex_bbox` behaves exactly as
    in `collect_endpoints`."""
    vertices: list[Vertex] = []
    for road in roads:
        if road.id is None or road.geom_type != "LineString" or len(road.geometry) < 3:
            continue
        for point in road.geometry[1:-1]:
            if _in_bbox(point, vertex_bbox):
                vertices.append(
                    Vertex(feature_id=road.id, point=point, is_endpoint=False)
                )
    return vertices


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, i: int) -> int:
        root = i
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[i] != root:
            self._parent[i], i = root, self._parent[i]
        return root

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_a] = root_b


def _bucket_key(point: Point, cell_size: float) -> tuple[int, int]:
    x, z = point
    return int(x // cell_size), int(z // cell_size)


def _cluster_vertices(
    endpoints: list[Vertex], interior: list[Vertex], tolerance_m: float
) -> list[list[Vertex]]:
    """Grid-bucketed union-find over: (a) endpoint<->endpoint pairs within
    `tolerance_m`, and (b) endpoint<->interior-vertex pairs (different
    feature id) within `tolerance_m`. Interior<->interior pairs are never
    unioned (see module docstring)."""
    all_vertices = endpoints + interior
    n_endpoints = len(endpoints)
    n = len(all_vertices)
    if n == 0:
        return []

    # Bucket cell size a small multiple of tolerance -- large enough that a
    # 3x3 neighbourhood scan always covers every point within tolerance_m,
    # small enough to keep buckets from ballooning at syria-full scale.
    cell_size = max(tolerance_m * 3.0, 1.0)
    buckets: dict[tuple[int, int], list[int]] = {}
    for index, vertex in enumerate(all_vertices):
        buckets.setdefault(_bucket_key(vertex.point, cell_size), []).append(index)

    uf = _UnionFind(n)
    for index, vertex in enumerate(all_vertices):
        is_endpoint = index < n_endpoints
        bx, bz = _bucket_key(vertex.point, cell_size)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for other_index in buckets.get((bx + dx, bz + dz), []):
                    if other_index <= index:
                        continue
                    other = all_vertices[other_index]
                    other_is_endpoint = other_index < n_endpoints
                    if not is_endpoint and not other_is_endpoint:
                        # Interior<->interior: never unioned (out of scope).
                        continue
                    if vertex.feature_id == other.feature_id:
                        # Same road never unions with itself.
                        continue
                    if distance_point_point(vertex.point, other.point) <= tolerance_m:
                        uf.union(index, other_index)

    groups: dict[int, list[Vertex]] = {}
    for index, vertex in enumerate(all_vertices):
        groups.setdefault(uf.find(index), []).append(vertex)
    return list(groups.values())


def _arm_count(cluster: list[Vertex]) -> int:
    """Sum of arms per the module docstring's rule: every endpoint vertex
    contributes 1 arm, every interior-vertex vertex contributes 2 arms (the
    through-road continues in both directions)."""
    return sum(1 if vertex.is_endpoint else 2 for vertex in cluster)


def extract_clusters(
    roads: list[StoredFeature],
    tolerance_m: float = DEFAULT_JUNCTION_TOLERANCE_M,
    vertex_bbox: Bbox | None = None,
) -> list[JunctionCluster]:
    """Cluster `roads`' endpoints and interior vertices within `tolerance_m`
    and return one `JunctionCluster` per resulting group of 2 or more
    vertices, regardless of degree -- `to_stored_features`'s `min_degree`
    filter is applied separately so tests can inspect the full cluster
    population. A group of exactly one vertex is not a cluster at all (no
    coincidence occurred) and is dropped here rather than surfaced as
    meaningless degree-1/2 noise -- the vast majority of a real road layer's
    endpoints/interior vertices never coincide with anything.

    `vertex_bbox`, if given, is threaded through to both collectors (see
    `collect_endpoints`); `None` (the default) preserves exactly the
    original whole-layer behaviour, so every existing caller/test is
    unaffected."""
    endpoints = collect_endpoints(roads, vertex_bbox)
    interior = collect_interior_vertices(roads, vertex_bbox)
    groups = _cluster_vertices(endpoints, interior, tolerance_m)

    clusters: list[JunctionCluster] = []
    for group in groups:
        if len(group) < 2:
            continue
        n = len(group)
        centroid_x = sum(v.point[0] for v in group) / n
        centroid_z = sum(v.point[1] for v in group) / n
        centroid = (centroid_x, centroid_z)
        max_distance = max(
            (
                distance_point_point(a.point, b.point)
                for i, a in enumerate(group)
                for b in group[i + 1 :]
            ),
            default=0.0,
        )
        connecting_road_ids = sorted({v.feature_id for v in group})
        clusters.append(
            JunctionCluster(
                centroid=centroid,
                degree=_arm_count(group),
                connecting_road_ids=connecting_road_ids,
                max_intra_cluster_distance_m=max_distance,
            )
        )
    return clusters


def to_stored_features(
    clusters: list[JunctionCluster],
    source_id: int | None,
    min_degree: int = DEFAULT_JUNCTION_MIN_DEGREE,
    position_uncertainty_m: float | None = None,
) -> list[StoredFeature]:
    """Wrap each `JunctionCluster` with degree `>= min_degree` into a
    store-facing `StoredFeature`: `kind="junction"`, `Point` geometry,
    `provenance={"geometry": "dcs_derived"}` (mirrors M6's ridge/valley -- the
    source vertices are DCS-native but the junction *fact* is this module's
    derived analysis, not something DCS reports directly), `confidence=
    {"geometry": "high"}` when the cluster's max intra-cluster distance is
    bit-exact (< 1e-6 m, matching the recon's own exact-match finding) else
    `"medium"`. `position_uncertainty_m` defaults to the cluster's own
    measured max intra-cluster distance (an honest, measured value, not a
    placeholder) when not overridden by the caller."""
    features: list[StoredFeature] = []
    for index, cluster in enumerate(clusters):
        if cluster.degree < min_degree:
            continue
        is_exact = cluster.max_intra_cluster_distance_m < _EXACT_MATCH_TOLERANCE_M
        features.append(
            StoredFeature(
                kind="junction",
                geom_type="Point",
                geometry=[cluster.centroid],
                name=None,
                subtype=None,
                tags={
                    "degree": cluster.degree,
                    "connecting_road_ids": cluster.connecting_road_ids,
                },
                source_id=source_id,
                source_ref=f"junction_{index}",
                provenance={"geometry": "dcs_derived"},
                confidence={"geometry": "high" if is_exact else "medium"},
                position_uncertainty_m=(
                    cluster.max_intra_cluster_distance_m
                    if position_uncertainty_m is None
                    else position_uncertainty_m
                ),
            )
        )
    return features
