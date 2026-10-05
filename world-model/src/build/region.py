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
    "baalbek-20km": RegionDefinition.square(
        theatre="Syria",
        name="baalbek-20km",
        # terrain-feature-probing Stage 1's Bekaa-equivalent test region:
        # the width gate's falsifiable test is that this basin produces no
        # `valley` row (see plans/terrain-feature-probing/plan.md). Centred
        # on the `named_place` "Baalbek" row already in `syria-full.sqlite`
        # (centroid of its stored vertices), same half-extent convention as
        # `latakia-20km`.
        centre_x=-114453.77304029558,
        centre_z=25280.763382998703,
        half_extent_m=10000.0,
    ),
    "palmyra-20km": RegionDefinition.square(
        theatre="Syria",
        name="palmyra-20km",
        # terrain-feature-probing Stage 1's regression check for the one
        # thing the old per-cell detector got right: flat desert with
        # isolated ridge chains, "located correctly, shaped badly" per
        # `research/2026-10-01-terrain-features-full-build-inspection.md`.
        # Centred on the `named_place` "Palmyra" row in `syria-full.sqlite`.
        centre_x=-54775.02454323182,
        centre_z=217141.70638191345,
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
    "afghanistan-full": RegionDefinition(
        theatre="Afghanistan",
        name="afghanistan-full",
        # Padded (+30 km/side) DCS-space bbox from the **union** of
        # towns.lua (n=1225, projected via the provisional Afghanistan
        # tmerc fit) and beacons.lua (n=49, native x/z) -- not beacons
        # alone (main-loop amendment 2026-10-05, see
        # plans/multi-theatre-afghanistan/plan.md Stage 2: Afghanistan's
        # 49 beacons are all airfield-tied, and the investigator found
        # towns.lua the safer lower-bound source). Derived by
        # tools/derive_afghanistan_full_region.py (this session's run):
        #   raw union x: [-498,489.9, 525,448.8] -> padded [-528,489.9, 555,448.8]
        #   raw union z: [-513,487.2, 745,003.2] -> padded [-543,487.2, 775,003.2]
        # giving a padded footprint of ~1,083.9 x 1,318.5 km (aspect ratio
        # ~0.82) -- this is a point-cloud lower bound, not a
        # corner-verified terrain edge; see
        # world-model/research/2026-10-04-multi-theatre-afghanistan-
        # caucasus-recon.md Q1 and this plan's "Risks & Unknowns".
        centre_x=13479.5,
        centre_z=115758.0,
        half_extent_x_m=541969.3,
        half_extent_z_m=659245.2,
    ),
}
