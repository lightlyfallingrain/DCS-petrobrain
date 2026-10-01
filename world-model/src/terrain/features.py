"""Basin growth, divide (ridge) gating, and principal-axis line extraction
over a landform-scale-smoothed elevation grid -- Stage 1's Option C
(marker-controlled watershed), per `plans/terrain-feature-probing/plan.md`.

`curvature.smooth_grid`/`curvature.find_basin_seeds` (numpy/scipy-backed)
hand this module a smoothed `ElevationGrid` and a seed list; everything
from here on stays stdlib, per the plan's point 3:

1. **`grow_basins`** -- a hand-written `heapq` priority-flood (Vincent &
   Soille 1991's watershed-by-immersion) assigns every sampled cell to
   exactly one basin, growing outward from the seeds in ascending
   elevation order. This is the one step that does *not* vectorize (an
   inherently serial priority-queue traversal), so it is a plain Python
   loop, same tolerance for a full-theatre (~2.5M-cell) pure-Python pass
   this codebase already demonstrated for the old curvature classifier.
2. **`qualifying_ridges`** -- basin-pair boundaries, gated on their own
   divide prominence (the boundary's lowest cell -- the saddle/pass a
   route between the two basins must cross -- minus the lower of the two
   basins' own floors) independent of whether either basin qualifies as a
   `valley` below (point 4): this is what keeps an isolated ridge between
   two basins that are both too flat or too wide to be `valley`s still
   emitted as `ridge` (Palmyra's desert ridge chains).
3. **`qualifying_valleys`** -- basins gated on floor-to-rim relief *and* a
   width ceiling along their own low-elevation core's minor principal axis
   (point 5) -- the concrete, checkable form of the user's Bekaa exclusion
   ("kilometres wide flat bottom... meaningless in the Mi-24 flight profile
   scale").
4. **Geometry extraction reuses `_connected_components`/`_principal_axis`
   unchanged** (point 6), now operating over `GridCell` (a bare
   `(row, col)` pair) rather than `curvature.CellCurvature` -- there is no
   per-cell curvature value or classification left to carry, since basin
   membership, not a per-cell test, is what group cells now.

`to_stored_features` is unchanged in shape: same `StoredFeature` geometry
convention, `provenance = {"geometry": "dcs_derived"}`, `confidence =
{"geometry": "low"}`. It additionally sets the `basin_width_m` tag on
valley rows (see `store.models.StoredFeature`'s reserved-tags docstring) --
`adjacent_feature_ids` is Stage 3's, not populated here, but
`TerrainComponent.basin_ids` already carries the basin-adjacency structure
(point 7) a Stage 3 pass would need, computed once as a side effect of
`grow_basins`/`qualifying_ridges` rather than a separate geometric pass.
"""

import heapq
import math
from dataclasses import dataclass
from typing import Any

from store.models import ElevationGrid, StoredFeature

# Basin-growth size floor -- same role `curvature.DEFAULT_MIN_CELL_COUNT`
# played for the old per-cell classifier (a safety net against a single
# noisy-pixel local minimum producing a one-cell basin, point 8), retuned
# for basins/divides rather than curvature components; 6 matches the old
# `terrain.features.DEFAULT_MIN_CELL_COUNT`'s own tuned value (unrelated
# coincidence -- chosen independently against this mechanism's output). See
# `research/2026-10-01-terrain-feature-probing-watershed-sweep.md`.
DEFAULT_MIN_CELL_COUNT = 6

# Candidate range from the Explore conversation is 50-150 m (a form must
# rise this much over a short run to mask line of sight at Mi-24 flight
# profile scale); 100 m (midpoint) tuned against real `latakia-20km`/
# Baalbek/Palmyra output -- see the sweep note above for the values
# rejected.
DEFAULT_RELIEF_THRESHOLD_M = 100.0

# Candidate range ~2-3 km (the Bekaa's own width must fail this gate);
# 2.5 km (midpoint) tuned against the same sweep -- the Bekaa's own
# measured core width is ~8.6 km, well clear of this ceiling on either
# side of the 2-3 km range, so the exact value within that range is not
# load-bearing for the Bekaa case specifically.
DEFAULT_WIDTH_CEILING_M = 2500.0

# Fraction of a basin's own relief (floor to rim) its "core" -- the
# low-elevation body a pilot would actually call the valley, as opposed to
# the basin's full extent which reaches all the way up to the surrounding
# divide crest -- is allowed to span. Lowered from an initial 0.5 guess to
# 0.1 after the sweep showed 0.5 pulls in cells more than halfway up a
# basin's own flanks (still a legitimate slope, not a valley floor by the
# user's own "between hills" framing) and measurably worsens both
# fragmentation and sinuosity versus a tighter core. See the sweep note.
DEFAULT_VALLEY_CORE_FRACTION = 0.1


@dataclass(frozen=True)
class GridCell:
    """A bare `(row, col)` grid-index pair -- the generic structural
    carrier `_connected_components`/`_principal_axis` operate over (a
    basin-pair's shared boundary cells, or one basin's low-elevation core
    cells). Replaces `curvature.CellCurvature` now that there is no
    per-cell curvature value or classification: basin membership groups
    cells here, not a per-cell test."""

    row: int
    col: int


@dataclass
class Basin:
    """One basin grown by `grow_basins`: every cell assigned to it, plus
    the extremes of its own (smoothed) elevation. `relief_m` is the
    floor-to-rim relief `qualifying_valleys` gates on -- the basin's full
    extent reaches up to the surrounding divide crest, so this is a real
    relief-amplitude measure, not a within-core figure."""

    id: int
    cells: list[tuple[int, int]]
    min_elevation: float
    max_elevation: float

    @property
    def relief_m(self) -> float:
        return self.max_elevation - self.min_elevation


@dataclass(frozen=True)
class TerrainComponent:
    """One extracted ridge/valley line -- the pure-geometry intermediate
    this module's tests exercise directly, before `to_stored_features`
    wraps it with store-facing provenance/confidence.

    `basin_ids` is the basin (valley: one id) or basin-pair (ridge: two
    ids) this component was extracted from -- the adjacency seam Stage 3
    would read, per the module docstring. `width_m` is the valley width
    gate's own measured minor-axis extent (`None` for ridges, which are
    not width-gated)."""

    kind: str
    cells: list[GridCell]
    points: list[tuple[float, float]]
    elevation_range_m: tuple[float, float]
    orientation_deg: float
    basin_ids: tuple[int, ...]
    width_m: float | None = None


def _connected_components(
    cells_by_rc: dict[tuple[int, int], GridCell],
) -> list[list[GridCell]]:
    """4-connectivity flood-fill grouping of `cells_by_rc` -- unchanged
    from the old curvature-cell version, operating over `GridCell` instead
    (point 6: "reuses `_connected_components`... unchanged")."""
    visited: set[tuple[int, int]] = set()
    components: list[list[GridCell]] = []
    for start in cells_by_rc:
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        component: list[GridCell] = []
        while stack:
            rc = stack.pop()
            component.append(cells_by_rc[rc])
            row, col = rc
            for neighbour in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            ):
                if neighbour in cells_by_rc and neighbour not in visited:
                    visited.add(neighbour)
                    stack.append(neighbour)
        components.append(component)
    return components


def _principal_axis(component: list[GridCell]) -> tuple[float, float]:
    """Unit vector `(row_component, col_component)` of the largest
    eigenvector of `component`'s cell-coordinate covariance matrix, solved
    in closed form -- unchanged from the old curvature-cell version."""
    n = len(component)
    mean_row = sum(c.row for c in component) / n
    mean_col = sum(c.col for c in component) / n
    cov_rr = sum((c.row - mean_row) ** 2 for c in component) / n
    cov_cc = sum((c.col - mean_col) ** 2 for c in component) / n
    cov_rc = sum((c.row - mean_row) * (c.col - mean_col) for c in component) / n

    trace = cov_rr + cov_cc
    determinant = cov_rr * cov_cc - cov_rc * cov_rc
    discriminant = max(trace * trace / 4.0 - determinant, 0.0)
    lambda_max = trace / 2.0 + math.sqrt(discriminant)

    if cov_rc != 0.0:
        row_component, col_component = lambda_max - cov_cc, cov_rc
    elif cov_rr >= cov_cc:
        row_component, col_component = 1.0, 0.0
    else:
        row_component, col_component = 0.0, 1.0

    length = math.hypot(row_component, col_component)
    if length == 0.0:
        return 1.0, 0.0
    return row_component / length, col_component / length


def _minor_axis_extent_m(cells: list[GridCell], spacing_m: float) -> float:
    """Extent, in metres, of `cells` along the axis perpendicular to their
    own principal (major) axis -- `qualifying_valleys`'s width gate (point
    5). A basin's own *length* along its major axis can be arbitrarily
    long without disqualifying it; a basin wide across its *minor* axis
    past `width_ceiling_m` reads as a macro-basin, not one feature a pilot
    would call "the valley" (the Bekaa case)."""
    axis_row, axis_col = _principal_axis(cells)
    minor_row, minor_col = -axis_col, axis_row  # 90-degree rotation
    projections = [c.row * minor_row + c.col * minor_col for c in cells]
    return (max(projections) - min(projections)) * spacing_m


def _seed_groups(seeds: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Merge mutually-4-adjacent seed cells into one group before basin
    growth starts. A flat regional minimum (an exact plateau) can satisfy
    `curvature.find_basin_seeds`'s minimum-filter test at every one of its
    own cells; without this merge, those cells would race during growth to
    claim the plateau as several separate, arbitrarily-bordered basins
    instead of the one basin the surface actually has."""
    seed_set = set(seeds)
    visited: set[tuple[int, int]] = set()
    groups: list[list[tuple[int, int]]] = []
    for start in seeds:
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        group: list[tuple[int, int]] = []
        while stack:
            cell = stack.pop()
            group.append(cell)
            row, col = cell
            for neighbour in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            ):
                if neighbour in seed_set and neighbour not in visited:
                    visited.add(neighbour)
                    stack.append(neighbour)
        groups.append(group)
    return groups


def grow_basins(
    grid: ElevationGrid, seeds: list[tuple[int, int]]
) -> tuple[dict[tuple[int, int], int], list[Basin]]:
    """Marker-controlled watershed over `grid` (typically `curvature.
    smooth_grid`'s output), grown from `seeds` (typically `curvature.
    find_basin_seeds`'s output) by a priority-flood-style flood fill in
    ascending elevation order (Vincent & Soille 1991's watershed-by-
    immersion, adapted to grid cells rather than image intensity) -- every
    sampled cell reachable from a seed ends up assigned to exactly one
    basin. A hand-written `heapq` loop, not vectorized: this is an
    inherently serial priority-queue traversal (point 3).

    Returns `(labels, basins)`: `labels` maps every assigned `(row, col)`
    to its basin's `id`; `basins` is the list of grown `Basin`s, one per
    (possibly plateau-merged, see `_seed_groups`) seed group that claimed
    at least one sampled cell.
    """
    labels: dict[tuple[int, int], int] = {}
    basin_cells: dict[int, list[tuple[int, int]]] = {}
    basin_min: dict[int, float] = {}
    basin_max: dict[int, float] = {}
    heap: list[tuple[float, int, int]] = []

    for basin_id, group in enumerate(_seed_groups(seeds)):
        cells: list[tuple[int, int]] = []
        for row, col in group:
            if (row, col) in labels:
                continue
            value = grid.samples[row][col]
            if value is None:
                continue
            labels[(row, col)] = basin_id
            cells.append((row, col))
            heapq.heappush(heap, (value, row, col))
        if not cells:
            continue
        basin_cells[basin_id] = cells
        values = [v for r, c in cells if (v := grid.samples[r][c]) is not None]
        basin_min[basin_id] = min(values)
        basin_max[basin_id] = max(values)

    while heap:
        _elevation, row, col = heapq.heappop(heap)
        basin_id = labels[(row, col)]
        for n_row, n_col in (
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ):
            if not (0 <= n_row < grid.n_rows and 0 <= n_col < grid.n_cols):
                continue
            if (n_row, n_col) in labels:
                continue
            value = grid.samples[n_row][n_col]
            if value is None:
                continue
            labels[(n_row, n_col)] = basin_id
            basin_cells[basin_id].append((n_row, n_col))
            basin_min[basin_id] = min(basin_min[basin_id], value)
            basin_max[basin_id] = max(basin_max[basin_id], value)
            heapq.heappush(heap, (value, n_row, n_col))

    basins = [
        Basin(
            id=basin_id,
            cells=cells,
            min_elevation=basin_min[basin_id],
            max_elevation=basin_max[basin_id],
        )
        for basin_id, cells in basin_cells.items()
    ]
    return labels, basins


def _basin_boundaries(
    labels: dict[tuple[int, int], int],
) -> dict[tuple[int, int], set[tuple[int, int]]]:
    """Every pair of basins that share a border, keyed `(lower_id,
    higher_id)`, to the set of cells on either side of that border -- the
    boundary-cell set `qualifying_ridges` gates and `_connected_components`
    splits into separate ridge lines where two basins touch at more than
    one disjoint stretch (point 6)."""
    boundaries: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for (row, col), basin_id in labels.items():
        for n_row, n_col in (
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ):
            neighbour_id = labels.get((n_row, n_col))
            if neighbour_id is None or neighbour_id == basin_id:
                continue
            key = (min(basin_id, neighbour_id), max(basin_id, neighbour_id))
            boundaries.setdefault(key, set()).add((row, col))
    return boundaries


def _build_component(
    grid: ElevationGrid,
    cells: list[GridCell],
    kind: str,
    basin_ids: tuple[int, ...],
    width_m: float | None = None,
) -> TerrainComponent:
    axis_row, axis_col = _principal_axis(cells)
    mean_row = sum(c.row for c in cells) / len(cells)
    mean_col = sum(c.col for c in cells) / len(cells)
    ordered = sorted(
        cells,
        key=lambda c: (c.row - mean_row) * axis_row + (c.col - mean_col) * axis_col,
    )

    points = [
        (grid.origin_x + c.row * grid.spacing_m, grid.origin_z + c.col * grid.spacing_m)
        for c in ordered
    ]
    sampled_elevations = [
        elevation
        for c in ordered
        if (elevation := grid.samples[c.row][c.col]) is not None
    ]
    if not sampled_elevations:
        raise ValueError(
            f"{kind} component at cells {[(c.row, c.col) for c in ordered]} has no "
            "sampled elevation -- inconsistent with basin/boundary cell sets "
            "always being built from already-sampled grid cells"
        )

    if len(points) >= 2 and points[0] != points[-1]:
        dx = points[-1][0] - points[0][0]
        dz = points[-1][1] - points[0][1]
        orientation_deg = math.degrees(math.atan2(dz, dx)) % 180.0
    else:
        orientation_deg = 0.0

    return TerrainComponent(
        kind=kind,
        cells=ordered,
        points=points,
        elevation_range_m=(min(sampled_elevations), max(sampled_elevations)),
        orientation_deg=orientation_deg,
        basin_ids=basin_ids,
        width_m=width_m,
    )


def qualifying_ridges(
    grid: ElevationGrid,
    labels: dict[tuple[int, int], int],
    basins_by_id: dict[int, Basin],
    relief_threshold_m: float = DEFAULT_RELIEF_THRESHOLD_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
) -> list[TerrainComponent]:
    """Ridge lines: a basin-pair's shared boundary qualifies as `ridge`
    only if its saddle (the lowest boundary cell -- the pass a route
    between the two basins must cross) rises `relief_threshold_m` above the
    *lower* of the two basins' own floors (point 4). Evaluated independent
    of whether either basin itself qualifies as a `valley`
    (`qualifying_valleys`) -- this is what keeps an isolated ridge between
    two basins that are both too flat or too wide to be `valley`s still
    emitted as `ridge` (Palmyra's desert ridge chains: "located correctly,
    shaped badly" under the old detector)."""
    components: list[TerrainComponent] = []
    for (basin_a, basin_b), boundary_cells in _basin_boundaries(labels).items():
        elevations = [
            elevation
            for row, col in boundary_cells
            if (elevation := grid.samples[row][col]) is not None
        ]
        if not elevations:
            continue
        saddle_elevation = min(elevations)
        lower_floor = min(
            basins_by_id[basin_a].min_elevation, basins_by_id[basin_b].min_elevation
        )
        if saddle_elevation - lower_floor < relief_threshold_m:
            continue

        cells_by_rc = {(row, col): GridCell(row, col) for row, col in boundary_cells}
        for component_cells in _connected_components(cells_by_rc):
            if len(component_cells) < min_cell_count:
                continue
            components.append(
                _build_component(
                    grid, component_cells, kind="ridge", basin_ids=(basin_a, basin_b)
                )
            )
    return components


def qualifying_valleys(
    grid: ElevationGrid,
    basins: list[Basin],
    relief_threshold_m: float = DEFAULT_RELIEF_THRESHOLD_M,
    width_ceiling_m: float = DEFAULT_WIDTH_CEILING_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
    core_fraction: float = DEFAULT_VALLEY_CORE_FRACTION,
) -> list[TerrainComponent]:
    """Valleys: basins that pass two gates (point 5) -- `relief_threshold_m`
    (basin floor-to-rim relief, same 50-150 m family as the ridge gate) and
    a width ceiling along the minor principal axis of the basin's own
    low-elevation "core" (its cells within `core_fraction` of its own
    relief above its floor -- a basin's full extent reaches up to the
    surrounding divide crest, which is not the body a pilot would call the
    valley). A basin that fails either gate contributes no `valley` row,
    but can still have a qualifying `ridge` on one of its boundaries
    (`qualifying_ridges`, evaluated independently)."""
    components: list[TerrainComponent] = []
    for basin in basins:
        if basin.relief_m < relief_threshold_m:
            continue
        core_ceiling = basin.min_elevation + core_fraction * basin.relief_m
        core_cells = {
            (row, col): GridCell(row, col)
            for row, col in basin.cells
            if (value := grid.samples[row][col]) is not None and value <= core_ceiling
        }
        for component_cells in _connected_components(core_cells):
            if len(component_cells) < min_cell_count:
                continue
            width_m = _minor_axis_extent_m(component_cells, grid.spacing_m)
            if width_m > width_ceiling_m:
                continue
            components.append(
                _build_component(
                    grid,
                    component_cells,
                    kind="valley",
                    basin_ids=(basin.id,),
                    width_m=width_m,
                )
            )
    return components


def extract_components(
    grid: ElevationGrid,
    basins: list[Basin],
    labels: dict[tuple[int, int], int],
    relief_threshold_m: float = DEFAULT_RELIEF_THRESHOLD_M,
    width_ceiling_m: float = DEFAULT_WIDTH_CEILING_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
    core_fraction: float = DEFAULT_VALLEY_CORE_FRACTION,
) -> list[TerrainComponent]:
    """Entry point for the gating + geometry-extraction half of the
    pipeline, given `grow_basins`'s output -- reworked from the old
    curvature-cell version to call `qualifying_valleys`/`qualifying_ridges`
    instead of grouping `classify_curvature`'s per-cell output."""
    basins_by_id = {basin.id: basin for basin in basins}
    valleys = qualifying_valleys(
        grid, basins, relief_threshold_m, width_ceiling_m, min_cell_count, core_fraction
    )
    ridges = qualifying_ridges(
        grid, labels, basins_by_id, relief_threshold_m, min_cell_count
    )
    return valleys + ridges


def to_stored_features(
    components: list[TerrainComponent],
    source_id: int | None,
    position_uncertainty_m: float,
) -> list[StoredFeature]:
    """Wrap each `TerrainComponent`'s pure geometry into a store-facing
    `StoredFeature`: `kind="ridge"`/`"valley"`, `LineString` geometry,
    `provenance={"geometry": "dcs_derived"}`, `confidence={"geometry":
    "low"}` -- unchanged from before. Valley rows additionally carry the
    `basin_width_m` reserved tag (`store.models.StoredFeature`'s
    docstring) for inspectability of the width gate; `adjacent_feature_ids`
    is Stage 3's and not populated here."""
    features: list[StoredFeature] = []
    for index, component in enumerate(components):
        min_elevation, max_elevation = component.elevation_range_m
        tags: dict[str, Any] = {
            "elevation_range_m": [min_elevation, max_elevation],
            "orientation_deg": component.orientation_deg,
            "cell_count": len(component.cells),
        }
        if component.kind == "valley" and component.width_m is not None:
            tags["basin_width_m"] = component.width_m
        features.append(
            StoredFeature(
                kind=component.kind,
                geom_type="LineString",
                geometry=component.points,
                name=None,
                subtype=None,
                tags=tags,
                source_id=source_id,
                source_ref=f"{component.kind}_{index}",
                provenance={"geometry": "dcs_derived"},
                confidence={"geometry": "low"},
                position_uncertainty_m=position_uncertainty_m,
            )
        )
    return features
