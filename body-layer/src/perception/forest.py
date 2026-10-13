"""Forest occlusion -- the simple binary model, `plans/forest-occlusion/
plan.md` Stage 1. Specification: `docs/acceptance/2026-10-13-tree-cover-
direction.md` (user direction, verbatim): *"Basically no unit that is
among trees can be detected ... Proceed with simple model of anything in
forest is not seen"*.

`ForestOcclusion.occluded(x, z)` answers one question -- is this position
inside a mapped `landcover` polygon whose class is in
`FOREST_LANDCOVER_CLASSES` -- and nothing else. No directionality, no
altitude term, no optic dependence (the module docstring in
`visibility.py`'s gate 5 note explains why this gate is identical for
`UNAIDED_OPTIC` and `BINOCULAR_OPTIC`: magnification does not see through
canopy).

**`None` landcover is NOT forest.** `world-model/query/describe.py`'s
`inside_landcover` contract: `None` means "no mapped landcover (open
ground or simply unmapped)." Measured against the real `syria-full` store
(`plans/forest-occlusion/plan.md` Decision 2), unmapped is 42-96% of
ground positions depending on region -- treating it as forest would blind
Petrovich on the overwhelming majority of ground units, not a
conservative choice. The gate fires only on a positive
`landcover_class == "forest"` containment.

**`forest` only -- not `orchard`.** `FOREST_LANDCOVER_CLASSES` is the one
place that decision lives; widening it to include `"orchard"` is a user
decision (plan Decision 6), not made here.

**Cheap path, not `describe_position`.** `describe_position` is 84.6 ms
per call in situ (`BL-11` amendment A7) and is not used here.
`store.reader.containing_polygons(conn, ["landcover"], x, z)` measures
0.075 ms median on the real `syria-full` store (plan's "Measured cost"
section) -- one degenerate-bbox R*Tree prune plus `polygon_contains`,
which already honours a polygon's `inner_rings` (a clearing inside a wood
is not forest; `store.reader.containing_polygons`'s own docstring).

**The memo is keyed on the quantised position cell itself, not on
`object_id`.** The plan's "Affected Modules" section fixes this class's
only public method as `occluded(x, z) -> bool` -- no `object_id` is ever
passed to it, so there is nothing to key a per-object cache on. Keying on
the 50 m cell directly (mirroring `belief.enrichment.
ENRICHMENT_CACHE_POSITION_GRID_M`'s cell-key arithmetic, dropping the
altitude term since forest containment is a 2D test) is strictly cheaper
than a per-object cache would be: any candidate landing in an
already-resolved cell hits regardless of which object it is. Ground units
are static or slow -- a 50 m cell at 10 m/s takes 5 s to cross, many polls
at this project's own 1.0 s poll interval -- so the steady-state cost of
this gate is a dict lookup.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from typing import Final

from store.reader import containing_polygons

#: The one place "forest" is decided to mean exactly `landcover_class ==
#: "forest"` and nothing wider -- `orchard` is deliberately excluded (plan
#: Decision 6, "Decisions Requiring User Input" item 1). Widening this set
#: is the only change needed to bring orchard in later.
FOREST_LANDCOVER_CLASSES: Final[frozenset[str]] = frozenset({"forest"})

#: Same grid as `belief.enrichment.ENRICHMENT_CACHE_POSITION_GRID_M` --
#: deliberately the same magnitude, not re-derived, per the plan's
#: instruction to mirror that cache's cell-key arithmetic rather than
#: inventing a new one. No altitude term here: forest containment is a 2D
#: point-in-polygon test, unlike the enrichment cache's 3D cell.
FOREST_CACHE_GRID_M: Final[float] = 50.0


def _cache_cell_key(x: float, z: float) -> tuple[int, int]:
    """`(x, z)` snapped to `FOREST_CACHE_GRID_M` -- integer cell indices,
    the same `math.floor` convention `belief.enrichment._cache_position_key`
    uses, so the key is exactly comparable and cannot reintroduce a
    float-equality miss."""
    grid = FOREST_CACHE_GRID_M
    return (math.floor(x / grid), math.floor(z / grid))


@dataclass
class ForestOcclusion:
    """Holds the world-model connection, theatre, and a quantised-position
    memo of this poll's (and prior polls') `occluded` verdicts. Constructed
    once by `NakedEyePerceptionSource` and reused across polls, exactly as
    `WorldEnrichmentCache` is reused across `tick()` calls -- see that
    class's own docstring for the staleness this kind of cache accepts."""

    conn: sqlite3.Connection
    theatre: str
    _cache: dict[tuple[int, int], bool] = field(default_factory=dict, repr=False)

    def occluded(self, x: float, z: float) -> bool:
        """`True` iff `(x, z)` falls inside a mapped `landcover` polygon
        whose `landcover_class` is one of `FOREST_LANDCOVER_CLASSES` --
        `inner_rings` honoured by `containing_polygons` itself, so a
        clearing inside a wood correctly answers `False`. `theatre` is
        held but not yet consulted -- `containing_polygons` takes no
        theatre argument; kept on this dataclass for the same reason
        `check_visibility`'s own `conn`/`theatre` parameters exist, so a
        future multi-theatre store selection has somewhere to read it
        from without a signature change."""
        key = _cache_cell_key(x, z)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        candidates = containing_polygons(self.conn, ["landcover"], x, z)
        result = any(
            feature.tags.get("landcover_class") in FOREST_LANDCOVER_CLASSES
            for feature in candidates
        )
        self._cache[key] = result
        return result
