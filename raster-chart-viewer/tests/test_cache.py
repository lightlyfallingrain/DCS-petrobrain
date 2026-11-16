from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.synthetic_dds import build_multi_mip_dds
from PIL import Image

from raster_chart_viewer.cache import (
    CACHE_MAX_BYTES,
    SMALL_MIP_MIN,
    TileCache,
    compose_view_tile,
)
from raster_chart_viewer.discovery import TileLocation
from raster_chart_viewer.mosaic import MosaicGrid
from raster_chart_viewer.tilename import TileKey


def _full_8x8_grid(
    tmp_path: Path,
) -> tuple[MosaicGrid, dict[TileKey, TileLocation], list[TileLocation]]:
    """One sheet, full 8x8 coverage. `cache.py`/`ddsmip.py` hardcode the
    real 1024px base size (every measured RasterCharts tile shares it,
    research note section C), so fixture entries must use it too --
    `decode_mip`'s offset formula otherwise reads past the fixture's own
    (smaller) data."""
    keys: dict[TileKey, TileLocation] = {}
    locations: list[TileLocation] = []
    for x in range(8):
        for z in range(8):
            key = TileKey(scale_m=32, sheet="aa", level=0, x=x, z=z)
            location = TileLocation(
                zip_path=tmp_path / "fake.zip", entry_name=f"entry_{x}_{z}"
            )
            keys[key] = location
            locations.append(location)
    grid = MosaicGrid(list(keys))
    return grid, keys, locations


class _CountingReader:
    """Stands in for `discovery.read_tile_bytes` -- counts how many
    times each entry is actually opened/inflated, by location, so a
    test can assert a cache hit opened nothing."""

    def __init__(self, data_by_entry: dict[str, bytes]) -> None:
        self._data_by_entry = data_by_entry
        self.open_count = 0
        self.opened_entries: list[str] = []

    def __call__(self, location: TileLocation) -> bytes:
        self.open_count += 1
        self.opened_entries.append(location.entry_name)
        return self._data_by_entry[location.entry_name]


def test_repeated_full_res_request_opens_no_entry_twice(tmp_path: Path) -> None:
    grid, tiles, _locations = _full_8x8_grid(tmp_path / "terrain")
    # Every real entry carries the full 11-level mip chain (research note
    # section C); any inflate opportunistically populates every small
    # mip (cache.py's `_read_and_populate_small_mips`), so a fixture
    # missing levels would fail decode even though this test only reads
    # mip 0 directly.
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")

    first = compose_view_tile(
        cache,
        "Syria",
        "32m",
        grid,
        tiles,
        level=grid.max_level,
        vx=0,
        vy=0,
        read_bytes=reader,
    )
    opened_after_first = reader.open_count
    assert opened_after_first > 0

    second = compose_view_tile(
        cache,
        "Syria",
        "32m",
        grid,
        tiles,
        level=grid.max_level,
        vx=0,
        vy=0,
        read_bytes=reader,
    )
    assert second == first
    assert reader.open_count == opened_after_first  # served from cache, no new opens


def test_small_mip_request_after_any_inflate_opens_nothing(tmp_path: Path) -> None:
    grid, tiles, _locations = _full_8x8_grid(tmp_path / "terrain")
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")

    # Touch every entry at full res (one view tile per native tile at
    # k=0) -- each inflate opportunistically populates every small mip
    # (>= SMALL_MIP_MIN) of that same entry.
    for vx in range(8):
        for vy in range(8):
            compose_view_tile(
                cache,
                "Syria",
                "32m",
                grid,
                tiles,
                level=grid.max_level,
                vx=vx,
                vy=vy,
                read_bytes=reader,
            )
    opened_after_full_res = reader.open_count
    assert opened_after_full_res == 64  # one open per entry, the full sheet

    # A request at the smallest zoom level (k = SMALL_MIP_MIN, the most
    # zoomed-out small-mip tier -- here, one view tile covers the whole
    # 8x8 sheet) must now serve entirely from the small-mip cache -- no
    # new opens, since every entry it covers was already inflated above.
    small_mip_level = grid.max_level - SMALL_MIP_MIN
    compose_view_tile(
        cache,
        "Syria",
        "32m",
        grid,
        tiles,
        level=small_mip_level,
        vx=0,
        vy=0,
        read_bytes=reader,
    )
    assert reader.open_count == opened_after_full_res


def test_middle_zoom_never_uses_small_mip_cache_as_ingredient(tmp_path: Path) -> None:
    grid, tiles, _locations = _full_8x8_grid(tmp_path / "terrain")
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")

    middle_level = grid.max_level - 1  # k = 1, a middle zoom
    compose_view_tile(
        cache,
        "Syria",
        "32m",
        grid,
        tiles,
        level=middle_level,
        vx=0,
        vy=0,
        read_bytes=reader,
    )
    # k=1 means this one view tile covers a 2x2 block of native tiles --
    # exactly the entries it touches, and no others, must now have every
    # small mip (>= SMALL_MIP_MIN) populated; no mip below SMALL_MIP_MIN
    # is ever written to the small-mip cache at all.
    covered_keys = [grid.key_at(col, row) for col in (0, 1) for row in (0, 1)]
    assert all(key is not None for key in covered_keys)
    for key in covered_keys:
        assert key is not None
        for level in range(SMALL_MIP_MIN):
            assert not cache.has_small_mip("Syria", "32m", key, level)
        for level in range(SMALL_MIP_MIN, 11):
            assert cache.has_small_mip("Syria", "32m", key, level)

    first_open_count = reader.open_count
    assert first_open_count == 4  # one open per entry in the 2x2 block

    # Repeating the *same* middle-zoom view tile must still be served
    # from the composed-tile cache (no re-opens) -- "middle zooms
    # re-inflate" means a different request at that tier, not every
    # repeat of the identical one.
    compose_view_tile(
        cache,
        "Syria",
        "32m",
        grid,
        tiles,
        level=middle_level,
        vx=0,
        vy=0,
        read_bytes=reader,
    )
    assert reader.open_count == first_open_count


def test_small_mip_put_rejects_mip_below_min(tmp_path: Path) -> None:
    cache = TileCache(tmp_path / "cache")
    key = TileKey(scale_m=32, sheet="aa", level=0, x=0, z=0)
    image = Image.new("RGBA", (4, 4))
    with pytest.raises(ValueError):
        cache.put_small_mip("Syria", "32m", key, SMALL_MIP_MIN - 1, image)


def test_cache_eviction_removes_oldest_file_first(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    # A tiny cap so eviction actually fires within this test.
    cache = TileCache(cache_dir, max_bytes=2000)

    cache.put_composed_tile("Syria", "32m", 0, 0, 0, b"a" * 900)
    oldest_path = cache._composed_tile_path("Syria", "32m", 0, 0, 0)
    assert oldest_path.is_file()

    cache.put_composed_tile("Syria", "32m", 0, 1, 0, b"b" * 900)
    # Still both under the 2000-byte cap (1800 total).
    assert oldest_path.is_file()

    # This write pushes the total past the cap -- the oldest file (the
    # first one written) must be evicted first.
    cache.put_composed_tile("Syria", "32m", 0, 2, 0, b"c" * 900)
    assert not oldest_path.is_file()
    assert cache._composed_tile_path("Syria", "32m", 0, 1, 0).is_file()
    assert cache._composed_tile_path("Syria", "32m", 0, 2, 0).is_file()


def test_default_cache_cap_matches_plan() -> None:
    assert CACHE_MAX_BYTES == 1_000_000_000
