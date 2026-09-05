"""Region definitions: DCS-space rectangles, and their derived lat/lon
envelope.

Regions are defined as axis-aligned rectangles in **DCS x/z**, the
authoritative space -- not as a lat/lon bbox. For Gemerek the four corners'
latitudes disagree by ~0.008 deg, so defining a region by lat/lon first
would silently produce a different shape than the DCS-space rectangle it
claims to be. The lat/lon envelope used for the Overpass fetch is always a
*derived* padded box around the four corners, computed by
`to_wgs84_envelope`.

**Rectangular, not square, half-extents** (M7 Stage 0 generalization): a
square region -- every M1-M6 region so far -- is the trivial case where
`half_extent_x_m == half_extent_z_m`. The generalization exists because
theatre map-footprint elongation is real and varies per theatre (confirmed
for Kola, see `world-model/research/2026-09-05-m7-kola-square-vs-rectangle-
stress-test.md`) -- a square-only model would force an oversized region to
cover an elongated theatre's short axis. This is a robustness fix to the
abstraction, not tmerc projection distortion (checked and ruled out as a
mechanism in that same note).

`REGIONS` mirrors the `THEATRE_PROJECTIONS` / `THEATRE_RASTER_REGISTRATIONS`
registry pattern from `coordinates/` and `raster/`.
"""

from dataclasses import dataclass

from coordinates import dcs_to_wgs84


@dataclass(frozen=True)
class RegionDefinition:
    """A rectangular region in DCS x/z metres, centred at
    `(centre_x, centre_z)` with independent `half_extent_x_m`/
    `half_extent_z_m` in each axis. A square region sets both equal --
    see `square()`."""

    theatre: str
    name: str
    centre_x: float
    centre_z: float
    half_extent_x_m: float
    half_extent_z_m: float

    @classmethod
    def square(
        cls,
        theatre: str,
        name: str,
        centre_x: float,
        centre_z: float,
        half_extent_m: float,
    ) -> "RegionDefinition":
        """Convenience constructor for the equal-extents (square) case --
        every region before M7's `syria-full`."""
        return cls(
            theatre=theatre,
            name=name,
            centre_x=centre_x,
            centre_z=centre_z,
            half_extent_x_m=half_extent_m,
            half_extent_z_m=half_extent_m,
        )

    def to_wgs84_envelope(self) -> tuple[float, float, float, float]:
        """The region's four DCS-space corners, converted to WGS84 and
        reduced to a padding lat/lon bbox `(south, west, north, east)`.

        This is a *derived* envelope for the Overpass fetch, never the
        region's definition -- see the module docstring.
        """
        corners = [
            (
                self.centre_x - self.half_extent_x_m,
                self.centre_z - self.half_extent_z_m,
            ),
            (
                self.centre_x - self.half_extent_x_m,
                self.centre_z + self.half_extent_z_m,
            ),
            (
                self.centre_x + self.half_extent_x_m,
                self.centre_z - self.half_extent_z_m,
            ),
            (
                self.centre_x + self.half_extent_x_m,
                self.centre_z + self.half_extent_z_m,
            ),
        ]
        lat_lon_corners = [dcs_to_wgs84(self.theatre, x, z) for x, z in corners]
        lats = [lat for lat, _ in lat_lon_corners]
        lons = [lon for _, lon in lat_lon_corners]
        return (min(lats), min(lons), max(lats), max(lons))


REGIONS: dict[str, RegionDefinition] = {
    "latakia-20km": RegionDefinition.square(
        theatre="Syria",
        name="latakia-20km",
        # OSLK ARP centre (x=41934.892, z=5685.076) plus the +3,000 m
        # eastward offset Stage 0 chose to trade sea coverage for land
        # coverage -- see world-model/research/2026-09-04-m5-stage0-census.md
        # "Offset" section. The offset is baked into this stored centre, not
        # applied at query time.
        centre_x=44934.892,
        centre_z=5685.076,
        half_extent_m=10000.0,
    ),
    "gemerek-20km": RegionDefinition.square(
        theatre="Syria",
        name="gemerek-20km",
        # Kept registered for M1-M4 continuity/comparison, per
        # plans/m5-first-persistent-model/plan.md "Region — DECIDED:
        # Latakia" -- this region is empty of towns.lua entries and OSM
        # waterways (Finding B), which is exactly why M5 moved to Latakia.
        centre_x=461319.5,
        centre_z=29815.4,
        half_extent_m=10000.0,
    ),
    "syria-full": RegionDefinition(
        theatre="Syria",
        name="syria-full",
        # Padded (+30 km/side) DCS-authoritative airbase+beacon point-cloud
        # bbox from world-model/research/2026-09-05-m7-syria-theatre-extent.md
        # ("Best-available DCS-authoritative bounding box" table -- the
        # wider of the two independent sources on each edge):
        #   x: [-421,912.2, 345,432.4] m -> padded [-451,912.2, 375,432.4] m
        #   z: [-320,441.1, 390,774.9] m -> padded [-350,441.1, 420,774.9] m
        # giving a padded footprint of ~827.3 x 771.2 km (aspect ratio
        # ~1.07) -- this is a point-cloud lower bound, not a
        # corner-verified terrain edge; see that note's "Risks & Unknowns".
        centre_x=-38239.9,
        centre_z=35166.9,
        half_extent_x_m=413672.3,
        half_extent_z_m=385608.0,
    ),
}
