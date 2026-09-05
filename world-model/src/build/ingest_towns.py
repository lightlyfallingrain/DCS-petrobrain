"""`towns.lua` -> `named_place` features, clipped to a region.

**Positional uncertainty is a deliberate, documented compromise, not a
guess.** `towns.lua`'s lat/lon values are DCS-shipped data (so `provenance
= {"geometry": "dcs", ...}` is true -- the geometry is not copied from an
external source), but *what those coordinates actually represent* is an
open question this plan carries as risk and does not resolve: are they
DCS's in-game label positions (positional uncertainty near 0, since
`coordinates.wgs84_to_dcs` is confirmed to sub-centimetre accuracy), or a
real-world gazetteer coordinate a terrain artist pasted in (uncertainty on
the order of the ~1.0-1.3 km M1 terrain-art placement residual)? See
`plans/m5-first-persistent-model/plan.md`'s "towns.lua positional semantics
are unresolved" risk entry.

A one-sample spot-check run during this stage (Jablah vs. OSM's "Jable",
~466 m apart) is suggestive of the smaller figure but is a sample of one and
not decisive (a second candidate match, Al Hannadi vs. an OSM "Hanadi" node,
came out ~6 km apart -- almost certainly a wrong name match rather than a
real residual, illustrating exactly why n=1 is not evidence). Rather than
assert either bound, this module reports the **conservative** figure
(matching OSM's ~1300 m residual) and downgrades `confidence["geometry"]`
from `"high"` to `"medium"` to make the uncertainty visible rather than
overclaiming precision the diagnostic did not establish. A future session
with a larger matched sample can tighten this without changing the ingest
shape.
"""

from coordinates import wgs84_to_dcs
from dcs_data.towns import TownEntry
from store.models import StoredFeature

_POSITION_UNCERTAINTY_M = 1300.0


def _within_region(
    x: float,
    z: float,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
) -> bool:
    return (
        centre_x - half_extent_x_m <= x <= centre_x + half_extent_x_m
        and centre_z - half_extent_z_m <= z <= centre_z + half_extent_z_m
    )


def ingest_towns(
    entries: list[TownEntry],
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
) -> list[StoredFeature]:
    """Convert `towns.lua` entries into `named_place` features clipped to
    the rectangular region `(centre_x, centre_z) +/- (half_extent_x_m,
    half_extent_z_m)`.

    Every `TownEntry` becomes its own feature regardless of duplicate
    names -- `towns.lua` has 31 real places sharing a name with another
    entry at a different coordinate, and deduplicating by name would
    silently discard real places (see `dcs_data.towns`'s module docstring).
    """
    features: list[StoredFeature] = []
    for entry in entries:
        x, z = wgs84_to_dcs(theatre, entry.lat, entry.lon)
        if not _within_region(
            x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m
        ):
            continue
        features.append(
            StoredFeature(
                kind="named_place",
                geom_type="Point",
                geometry=[(x, z)],
                name=entry.name,
                subtype=None,
                tags={"display_name": entry.display_name},
                source_id=source_id,
                source_ref=entry.name,
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=_POSITION_UNCERTAINTY_M,
            )
        )
    return features
