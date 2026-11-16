from __future__ import annotations

import threading
import time
from pathlib import Path

from fixtures.synthetic_dds import build_multi_mip_dds

from raster_chart_viewer.cache import SMALL_MIP_MIN, TOTAL_MIPS, TileCache
from raster_chart_viewer.discovery import TileLocation
from raster_chart_viewer.tilename import TileKey
from raster_chart_viewer.warmup import WarmupScheduler


class _CountingReader:
    def __init__(self, data_by_entry: dict[str, bytes]) -> None:
        self._data_by_entry = data_by_entry
        self.open_count = 0

    def __call__(self, location: TileLocation) -> bytes:
        self.open_count += 1
        return self._data_by_entry[location.entry_name]


def _tiles(tmp_path: Path, count: int) -> dict[TileKey, TileLocation]:
    return {
        TileKey(scale_m=32, sheet="aa", level=0, x=0, z=i): TileLocation(
            zip_path=tmp_path / "fake.zip", entry_name=f"entry_{i}"
        )
        for i in range(count)
    }


def _wait_for(predicate: object, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for warm-up to complete")


def _wait_for_warmup_done(
    cache: TileCache, terrain: str, tier: str, tiles: dict[TileKey, TileLocation]
) -> None:
    """`reader.open_count` reaching N only proves every entry's *read*
    has started -- the small-mip *writes* for the last entry opened can
    still be in flight. Wait on the real completion signal (every key
    fully cached) instead, or `test_warmup_completes_and_populates_
    small_mips` below is a flaky test, not a correctness check."""
    _wait_for(
        lambda: all(cache.has_all_small_mips(terrain, tier, key) for key in tiles)
    )


def test_warmup_completes_and_populates_small_mips(tmp_path: Path) -> None:
    tiles = _tiles(tmp_path, 4)
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")
    scheduler = WarmupScheduler(cache, read_bytes=reader)

    scheduler.touch("Syria", "32m", tiles)
    _wait_for_warmup_done(cache, "Syria", "32m", tiles)

    assert reader.open_count == 4
    for key in tiles:
        for level in range(SMALL_MIP_MIN, TOTAL_MIPS):
            assert cache.has_small_mip("Syria", "32m", key, level)
        for level in range(SMALL_MIP_MIN):
            assert not cache.has_small_mip("Syria", "32m", key, level)


def test_warmup_never_starts_for_a_tier_nobody_touched(tmp_path: Path) -> None:
    tiles = _tiles(tmp_path, 4)
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")
    WarmupScheduler(cache, read_bytes=reader)

    time.sleep(0.05)  # give any (wrongly) auto-started thread a chance
    assert reader.open_count == 0


def test_second_warmup_after_restart_skips_already_cached_entries(
    tmp_path: Path,
) -> None:
    tiles = _tiles(tmp_path, 4)
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache_dir = tmp_path / "cache"
    cache = TileCache(cache_dir)
    scheduler = WarmupScheduler(cache, read_bytes=reader)
    scheduler.touch("Syria", "32m", tiles)
    _wait_for_warmup_done(cache, "Syria", "32m", tiles)

    # Simulate a process restart: a fresh TileCache/WarmupScheduler
    # against the same on-disk cache directory.
    cache2 = TileCache(cache_dir)
    reader2 = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    scheduler2 = WarmupScheduler(cache2, read_bytes=reader2)
    scheduler2.touch("Syria", "32m", tiles)
    time.sleep(0.1)  # let the no-op warm-up run its course
    assert reader2.open_count == 0


def test_warmed_tile_request_does_not_reopen_the_entry(tmp_path: Path) -> None:
    tiles = _tiles(tmp_path, 1)
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")
    scheduler = WarmupScheduler(cache, read_bytes=reader)
    scheduler.touch("Syria", "32m", tiles)
    _wait_for_warmup_done(cache, "Syria", "32m", tiles)

    key = next(iter(tiles))
    smallest_mip = cache.get_small_mip("Syria", "32m", key, TOTAL_MIPS - 1)
    assert smallest_mip is not None
    assert reader.open_count == 1  # reading from cache opened nothing new


def test_touch_is_a_noop_after_the_first_call(tmp_path: Path) -> None:
    tiles = _tiles(tmp_path, 2)
    data = build_multi_mip_dds(1024, 11)
    reader = _CountingReader({loc.entry_name: data for loc in tiles.values()})
    cache = TileCache(tmp_path / "cache")
    scheduler = WarmupScheduler(cache, read_bytes=reader)

    scheduler.touch("Syria", "32m", tiles)
    _wait_for(lambda: reader.open_count == 2)
    # A second touch for the same (terrain, tier) must start no thread.
    threads_before = threading.active_count()
    scheduler.touch("Syria", "32m", tiles)
    time.sleep(0.05)
    assert reader.open_count == 2
    assert threading.active_count() <= threads_before
