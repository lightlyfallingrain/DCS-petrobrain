"""Drift guard: `tools/osm_tags_filter.txt` must stay a superset of what
`build.ingest_osm`'s classifier actually accepts, so a real OSM element
whose tags the classifier would keep is never pre-filtered away by
`osmium tags-filter` before it ever reaches the Python classifier.

**Stage 0 status**: the classifier itself has not been rewritten yet
(`CLASSIFIER_VERSION` is still 1's road/water/settlement rules) -- so the
"classifier accepts" side of this test is a **hard-coded table** of D2's
*planned* rules (`plans/osm-landcover-optimization/plan.md` Design D2), not
yet read from `build.ingest_osm` itself. Stage 3 rewires this test to
import that module's own constants once the classifier rewrite lands, so
the two can never drift apart silently after that point.
"""

from pathlib import Path

_FILTER_PATH = Path(__file__).resolve().parent.parent / "tools" / "osm_tags_filter.txt"

# `(element_type, key, value)` triples D2's classifier accepts -- see the
# plan's Design D2 "Nodes"/"Lines"/"Areas" sections. `element_type` is one
# of "n" (node), "w" (way/line), "a" (area: closed way or multipolygon
# relation) -- the same three letters `osmium tags-filter`'s own expression
# grammar uses.
_CLASSIFIER_ACCEPTED_TAGS: frozenset[tuple[str, str, str]] = frozenset(
    {
        # Nodes (D2 "Nodes").
        ("n", "place", "city"),
        ("n", "place", "town"),
        ("n", "place", "village"),
        ("n", "natural", "peak"),
        ("n", "waterway", "dam"),
        # Lines (D2 "Lines").
        ("w", "waterway", "river"),
        ("w", "natural", "coastline"),
        ("w", "waterway", "dam"),
        # Areas (D2 "Areas", precedence rules 1-4).
        ("a", "natural", "water"),
        ("a", "landuse", "reservoir"),
        ("a", "waterway", "riverbank"),
        ("a", "place", "city"),
        ("a", "place", "town"),
        ("a", "place", "village"),
        ("a", "landuse", "residential"),
        ("a", "landuse", "commercial"),
        ("a", "landuse", "retail"),
        ("a", "landuse", "industrial"),
        ("a", "landuse", "military"),
        ("a", "landuse", "construction"),
        ("a", "landuse", "forest"),
        ("a", "landuse", "orchard"),
        ("a", "landuse", "vineyard"),
        ("a", "landuse", "plantation"),
        ("a", "landuse", "farmland"),
        ("a", "landuse", "meadow"),
        ("a", "landuse", "grass"),
        ("a", "landuse", "quarry"),
        ("a", "natural", "wood"),
        ("a", "natural", "scrub"),
        ("a", "natural", "heath"),
        ("a", "natural", "grassland"),
        ("a", "natural", "sand"),
        ("a", "natural", "bare_rock"),
        ("a", "natural", "scree"),
    }
)


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
