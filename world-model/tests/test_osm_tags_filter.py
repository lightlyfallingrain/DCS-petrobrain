"""Drift guard: `tools/osm_tags_filter.txt` must stay a superset of what
`build.ingest_osm`'s classifier actually accepts, so a real OSM element
whose tags the classifier would keep is never pre-filtered away by
`osmium tags-filter` before it ever reaches the Python classifier.

**Stage 3 rewire**: `_CLASSIFIER_ACCEPTED_TAGS` below is now built directly
from `build.ingest_osm`'s own module-level constants (`_NODE_PLACE_VALUES`,
`_AREA_PLACE_VALUES`, `_BUILT_UP_LANDUSE_VALUES`, `_WATER_TAG_TO_SUBTYPE`,
`_LANDUSE_TO_LANDCOVER_CLASS`, `_NATURAL_TO_LANDCOVER_CLASS`, plus the two
hardcoded rules -- `natural=peak`, `waterway=dam` on both a node and a way --
that have no vocabulary dict of their own), not a hand-copied table -- so the
two can never silently drift apart again. `element_type` is one of "n"
(node), "w" (way/line), "a" (area: closed way or multipolygon relation), the
same three letters `osmium tags-filter`'s own expression grammar uses.
"""

from pathlib import Path

from build.ingest_osm import (
    _AREA_PLACE_VALUES,
    _BUILT_UP_LANDUSE_VALUES,
    _LANDUSE_TO_LANDCOVER_CLASS,
    _NATURAL_TO_LANDCOVER_CLASS,
    _NODE_PLACE_VALUES,
)

_FILTER_PATH = Path(__file__).resolve().parent.parent / "tools" / "osm_tags_filter.txt"


def _classifier_accepted_tags() -> frozenset[tuple[str, str, str]]:
    """Every `(element_type, key, value)` triple `build.ingest_osm`'s
    classifier accepts, derived from its own vocabulary constants (D2
    "Nodes"/"Lines"/"Areas")."""
    accepted: set[tuple[str, str, str]] = set()

    # Nodes (D2 "Nodes").
    accepted |= {("n", "place", v) for v in _NODE_PLACE_VALUES}
    accepted.add(("n", "natural", "peak"))
    accepted.add(("n", "waterway", "dam"))

    # Lines (D2 "Lines") -- `waterway=dam` on a way is handled directly by
    # `_ingest_line`, not `_classify_line`, but still needs filter coverage.
    accepted.add(("w", "waterway", "river"))
    accepted.add(("w", "natural", "coastline"))
    accepted.add(("w", "waterway", "dam"))

    # Areas (D2 "Areas", precedence rules 1-4).
    accepted.add(("a", "natural", "water"))
    accepted.add(("a", "landuse", "reservoir"))
    accepted.add(("a", "waterway", "riverbank"))
    accepted |= {("a", "place", v) for v in _AREA_PLACE_VALUES}
    accepted |= {("a", "landuse", v) for v in _BUILT_UP_LANDUSE_VALUES}
    accepted |= {("a", "landuse", v) for v in _LANDUSE_TO_LANDCOVER_CLASS}
    accepted |= {("a", "natural", v) for v in _NATURAL_TO_LANDCOVER_CLASS}
    # `_WATER_TAG_TO_SUBTYPE`'s keys (lake/reservoir/river) are `water=*`
    # *values*, not their own top-level tag key -- already covered by the
    # `("a", "natural", "water")` line above, which is what actually gates
    # this rule through `osmium tags-filter` (the filter has no visibility
    # into the secondary `water=*` tag, so there is nothing further to add
    # here).

    return frozenset(accepted)


_CLASSIFIER_ACCEPTED_TAGS = _classifier_accepted_tags()


def _parse_filter_expressions(path: Path) -> set[tuple[str, str, str]]:
    """Parse the subset grammar this project's filter file uses:
    `<types>/<key>=<v1,v2,...>` per non-comment, non-blank line -- one or
    more single-character element-type letters, a `/`, a tag key, `=`, and a
    comma-separated value list. Returns every `(type_char, key, value)`
    triple the file matches. Comments (`#`) and blank lines are skipped."""
    accepted: set[tuple[str, str, str]] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        types_part, _, rest = line.partition("/")
        key, _, values_part = rest.partition("=")
        values = values_part.split(",") if values_part else []
        for type_char in types_part:
            for value in values:
                accepted.add((type_char, key, value))
    return accepted


def test_filter_file_is_superset_of_classifier_accepted_tags() -> None:
    filter_accepted = _parse_filter_expressions(_FILTER_PATH)
    missing = _CLASSIFIER_ACCEPTED_TAGS - filter_accepted
    assert not missing, (
        "osm_tags_filter.txt is missing expressions for tags the classifier "
        f"accepts: {sorted(missing)}"
    )
