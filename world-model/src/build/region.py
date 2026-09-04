"""Region definitions: DCS-space squares, and their derived lat/lon envelope.

Regions are defined as squares in **DCS x/z**, the authoritative space --
not as a lat/lon bbox. For Gemerek the four corners' latitudes disagree by
~0.008 deg, so defining a region by lat/lon first would silently produce a
different shape than the DCS-space square it claims to be. The lat/lon
envelope used for the Overpass fetch is always a *derived* padded box around
the four corners, computed by `to_wgs84_envelope`.

`REGIONS` mirrors the `THEATRE_PROJECTIONS` / `THEATRE_RASTER_REGISTRATIONS`
registry pattern from `coordinates/` and `raster/`.
"""

from dataclasses import dataclass

from coordinates import dcs_to_wgs84


@dataclass(frozen=True)
class RegionDefinition:
    """A square region in DCS x/z metres, centred at `(centre_x, centre_z)`
    with `half_extent_m` in each direction."""

    theatre: str
    name: str
    centre_x: float
    centre_z: float
    half_extent_m: float

    def to_wgs84_envelope(self) -> tuple[float, float, float, float]:
        """The region's four DCS-space corners, converted to WGS84 and
        reduced to a padding lat/lon bbox `(south, west, north, east)`.

        This is a *derived* envelope for the Overpass fetch, never the
        region's definition -- see the module docstring.
        """
        corners = [
            (self.centre_x - self.half_extent_m, self.centre_z - self.half_extent_m),
            (self.centre_x - self.half_extent_m, self.centre_z + self.half_extent_m),
            (self.centre_x + self.half_extent_m, self.centre_z - self.half_extent_m),
            (self.centre_x + self.half_extent_m, self.centre_z + self.half_extent_m),
        ]
        lat_lon_corners = [dcs_to_wgs84(self.theatre, x, z) for x, z in corners]
        lats = [lat for lat, _ in lat_lon_corners]
        lons = [lon for _, lon in lat_lon_corners]
        return (min(lats), min(lons), max(lats), max(lons))


REGIONS: dict[str, RegionDefinition] = {
    "latakia-20km": RegionDefinition(
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
    "gemerek-20km": RegionDefinition(
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
}
