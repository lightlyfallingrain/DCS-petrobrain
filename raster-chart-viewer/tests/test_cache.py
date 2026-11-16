from __future__ import annotations

import threading
import zipfile
from pathlib import Path

import pytest
from fixtures.synthetic_dds import build_multi_mip_dds
from PIL import Image

from raster_chart_viewer import discovery
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


def test_compose_view_tile_opens_its_zip_once_across_many_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Performance review Finding 1: within one `compose_view_tile`
    call, consecutive entries sharing the same zip must not reopen it
    once per entry. The `_CountingReader` tests above always inject
    `read_bytes`, so they exercise entry-level dedup but never the real
    zip -- this test leaves `read_bytes` at its production default
    (`None`, now a call-scoped `discovery.BatchZipReader`) against a
    real on-disk zip, and watches the real `zipfile.ZipFile`
    construction count rather than trusting the reader's own
    book-keeping."""
    grid, tiles, _locations = _full_8x8_grid(tmp_path / "terrain")
    data = build_multi_mip_dds(1024, 11)
    zip_path = tmp_path / "terrain" / "fake.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for location in tiles.values():
            zf.writestr(location.entry_name, data)
    cache = TileCache(tmp_path / "cache")

    open_count = 0
    real_zip_file = zipfile.ZipFile

    def counting_zip_file(*args: object, **kwargs: object) -> zipfile.ZipFile:
        nonlocal open_count
        open_count += 1
        return real_zip_file(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(discovery.zipfile, "ZipFile", counting_zip_file)

    # k = SMALL_MIP_MIN -- the most zoomed-out small-mip tier, one view
    # tile covering the whole 8x8 sheet, so this one call touches all 64
    # entries (same level used by test_small_mip_request_after_any_
    # inflate_opens_nothing above).
    small_mip_level = grid.max_level - SMALL_MIP_MIN
    jpeg_bytes = compose_view_tile(
        cache, "Syria", "32m", grid, tiles, level=small_mip_level, vx=0, vy=0
    )

    assert len(jpeg_bytes) > 0  # the composition itself still worked
    assert open_count == 1  # one open for all 64 entries this call touched


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


def test_eviction_sweep_descends_to_low_water_mark_not_just_under_cap(
    tmp_path: Path,
) -> None:
    """Performance review Finding 2: a sweep that stops the instant the
    total drops back under the cap pays its full rglob+stat+sort scan on
    every single write once the cache is steady-state-full, since the
    very next write crosses straight back over. Sweeping down to a
    margin below the cap instead means several writes can land before
    the next sweep is needed. Equal-size files make the result exact, so
    this distinguishes the fix from the old "stop at/under the cap"
    behaviour rather than merely tolerating either."""
    cache_dir = tmp_path / "cache"
    cache = TileCache(cache_dir, max_bytes=10_000)

    for i in range(10):
        cache.put_composed_tile("Syria", "32m", 0, i, 0, b"x" * 1000)
    assert cache._total_bytes == 10_000  # exactly at the cap, no sweep yet

    # One more write crosses the cap and triggers a sweep.
    cache.put_composed_tile("Syria", "32m", 0, 10, 0, b"x" * 1000)

    actual_total = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
    assert cache._total_bytes == actual_total
    assert actual_total <= 10_000
    # The distinguishing claim: the pre-fix "stop at/under the cap"
    # behaviour would evict exactly one 1000-byte file here (11,000 ->
    # 10,000, already <= the 10,000 cap) and stop -- this fixed version
    # must keep going past that point, down to the 90% low-water mark,
    # which costs a second eviction (11,000 -> 10,000 -> 9,000). Asserted
    # via the fraction itself rather than importing the private constant,
    # so this fails if the margin is ever widened or narrowed without
    # updating this test's own expectation.
    low_water_mark = int(10_000 * 0.9)
    assert actual_total == low_water_mark == 9_000


def test_concurrent_writes_under_a_forcing_cap_never_raise_and_respect_cap(
    tmp_path: Path,
) -> None:
    """Reviewer-reproduced defect: `ThreadingHTTPServer`'s request threads
    and `warmup.WarmupScheduler`'s background thread write into one
    shared `TileCache`. Before the lock, concurrent `put_composed_tile`
    calls under a cap small enough to force constant eviction reliably
    raised `FileNotFoundError` out of `_enforce_cap` (one thread's
    `unlink()` removing a file another thread's `sorted(...,
    key=...stat()...)` was still calling `.stat()` on) -- 31/3200 writes
    failed this way across 3 runs per the review. This pins both: no
    exception escapes, and the cache ends at or under its cap with the
    tracked total matching the real on-disk size (the lost-update race
    on `_total_bytes` the review also flagged)."""
    cache_dir = tmp_path / "cache"
    max_bytes = 20_000
    cache = TileCache(cache_dir, max_bytes=max_bytes)

    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def worker(thread_id: int) -> None:
        try:
            for i in range(100):
                data = bytes([thread_id % 256]) * 200
                cache.put_composed_tile("Syria", "32m", 0, thread_id, i, data)
        except BaseException as exc:  # noqa: BLE001 -- the test wants to see any escape
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    actual_total = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
    assert actual_total <= max_bytes
    assert cache._total_bytes == actual_total
