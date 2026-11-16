"""Discover every installed terrain's RasterCharts and index its tiles.

Terrains are discovered from `Mods/terrains/*/RasterCharts/`, never listed
in code (MI-B4: "any terrain folder that is on disk can be opened").

**Caucasus's special case turns out to be only "which zip paths to scan",
not a second discovery algorithm.** Four of five terrains have one root
`rasterCharts.zip`; Caucasus has no root zip and instead one small zip per
sheet under `RasterCharts/{0.25M,0.5M,1M,2M,5M}/`. But in both layouts the
scale tier and sheet come from the zip **entry** names via the same
universal regex (`tilename.parse_tile_name`), never from the zip's own
filename or its containing folder -- confirmed inconsistent in case and
underscore (research note section D). So once the right zip paths are
found, indexing is identical for every terrain.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from raster_chart_viewer.tilename import TileKey, parse_tile_name

#: The label shown for Mariana's 62 scale-prefix-less tiles (U2, answered
#: 2026-11-16: "expose as an 'unscaled' tier" rather than drop them).
UNSCALED_TIER_LABEL = "unscaled"


@dataclass(frozen=True, slots=True)
class TileLocation:
    """Where one tile's raw DDS bytes live on disk: a zip file and the
    exact (case-as-stored) entry name inside it."""

    zip_path: Path
    entry_name: str


def tier_label(scale_m: int | None) -> str:
    """The tier label as shown in the terrain/tier picker and used in
    cache paths. `None` (Mariana's unscaled tiles, U2) renders as
    `"unscaled"`, never dropped."""
    return UNSCALED_TIER_LABEL if scale_m is None else f"{scale_m}m"


@dataclass(frozen=True, slots=True)
class TerrainIndex:
    """One terrain's discovered tiles, grouped by tier (`scale_m`, with
    `None` meaning the unscaled tier). Built once at discovery time from
    exactly what is on disk -- sparse/partial tiers and sheets are
    structural, not an error path."""

    name: str
    tiers: dict[int | None, dict[TileKey, TileLocation]]

    def tier_labels(self) -> list[str]:
        """Every tier this terrain has, in a stable (sorted) order --
        scaled tiers ascending by metres-per-pixel, "unscaled" last."""
        scales = sorted(scale for scale in self.tiers if scale is not None)
        labels = [tier_label(scale) for scale in scales]
        if None in self.tiers:
            labels.append(tier_label(None))
        return labels

    def tiles_for_label(self, label: str) -> dict[TileKey, TileLocation] | None:
        """The tile map for the tier shown as `label`, or `None` if this
        terrain has no such tier."""
        for scale in self.tiers:
            if tier_label(scale) == label:
                return self.tiers[scale]
        return None


#: The shape `cache.compose_view_tile` expects for its injectable
#: `read_bytes` parameter -- the production default is `read_tile_bytes`
#: itself; tests inject a counting wrapper of the same shape instead of
#: monkeypatching this module.
ReadTileBytes = Callable[[TileLocation], bytes]


def read_tile_bytes(location: TileLocation) -> bytes:
    """Read one tile's raw (inflated) DDS bytes from its zip. Opening a
    fresh `ZipFile` per read costs re-parsing that zip's central
    directory, which is negligible next to the ~1.4MB inflate itself
    (research note section F timing) -- not worth holding file handles
    open across requests for a service this size."""
    with zipfile.ZipFile(location.zip_path) as zf:
        return zf.read(location.entry_name)


def _candidate_zip_paths(rastercharts_dir: Path) -> list[Path]:
    """Every zip this terrain's `RasterCharts/` folder should be indexed
    from. The single-zip layout (four of five terrains) has exactly one;
    Caucasus's zip-per-sheet layout has many, nested one level under a
    scale-named subfolder -- scanned generically (`*/*.zip`) rather than
    a hardcoded `{0.25M,0.5M,1M,2M,5M}` list, so a future terrain using a
    differently-named scale subfolder still discovers correctly."""
    root_zip = rastercharts_dir / "rasterCharts.zip"
    if root_zip.is_file():
        return [root_zip]
    return sorted(rastercharts_dir.glob("*/*.zip"))


def _index_terrain(name: str, rastercharts_dir: Path) -> TerrainIndex | None:
    zip_paths = _candidate_zip_paths(rastercharts_dir)
    if not zip_paths:
        return None

    tiers: dict[int | None, dict[TileKey, TileLocation]] = {}
    for zip_path in zip_paths:
        with zipfile.ZipFile(zip_path) as zf:
            for entry_name in zf.namelist():
                key = parse_tile_name(entry_name)
                if key is None:
                    continue
                tiers.setdefault(key.scale_m, {})[key] = TileLocation(
                    zip_path, entry_name
                )

    if not tiers:
        return None
    return TerrainIndex(name=name, tiers=tiers)


def _terrain_dirs(dcs_install: Path) -> Iterator[Path]:
    terrains_root = dcs_install / "Mods" / "terrains"
    if not terrains_root.is_dir():
        return
    for entry in sorted(terrains_root.iterdir()):
        if entry.is_dir():
            yield entry


def discover_terrains(dcs_install: Path) -> dict[str, TerrainIndex]:
    """Walk `<dcs_install>/Mods/terrains/*/RasterCharts/` and build one
    `TerrainIndex` per terrain that has any. A terrain folder with no
    `RasterCharts/` directory, or one whose zips contain nothing the
    universal grammar recognises, is silently absent from the result --
    not an error, since `Mods/terrains/` also holds terrains with no
    chartable content at all."""
    result: dict[str, TerrainIndex] = {}
    for terrain_dir in _terrain_dirs(dcs_install):
        rastercharts_dir = terrain_dir / "RasterCharts"
        if not rastercharts_dir.is_dir():
            continue
        index = _index_terrain(terrain_dir.name, rastercharts_dir)
        if index is not None:
            result[terrain_dir.name] = index
    return result
