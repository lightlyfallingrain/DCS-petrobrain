"""Disk cache plus tile composition -- wires `discovery`/`mosaic`/`ddsmip`
together into "answer one HTTP tile request".

**Cache shape, amended 2026-11-16** (plan, "Cache: served tiles plus
small mips only"): a superseded first design cached *every* mip of every
inflated entry as PNG under a 2GB cap; rejected because mip 0 as PNG
costs about as much disk as the raw DDS, and the warm-up design already
contradicted "never inflated twice" anyway. This is the replacement:

- **Composed-tile cache**: the literal JPEG bytes of one HTTP response,
  keyed by `(terrain, tier, level, vx, vy)` -- written once per distinct
  view tile ever requested.
- **Small-mip cache**: individual mip images, PNG, keyed by `(terrain,
  tier, TileKey, mip)`, for `mip >= SMALL_MIP_MIN` only (128px and
  smaller). Written whenever an entry is inflated for any reason.
- **Middle zooms (`1 <= k < SMALL_MIP_MIN`) always re-inflate** -- no
  ingredient cache for those mips at all; the assembled result still
  lands in the composed-tile cache, so a *repeat* of the same view tile
  never re-inflates anything.
- **One shared byte cap**, evicted oldest-file-first ("LRU-by-mtime" in
  the plan's words -- the file's own write-time `mtime`, not a touched-
  on-read access time, which keeps this independent of filesystem
  atime/noatime settings) whenever a write pushes the cache over it.
"""

from __future__ import annotations

import io
import math
import threading
from pathlib import Path

from PIL import Image

from raster_chart_viewer import discovery
from raster_chart_viewer.ddsmip import TILE_BASE_SIZE_PX, decode_mip
from raster_chart_viewer.discovery import TileLocation
from raster_chart_viewer.mosaic import TILE_SIZE_PX, MosaicGrid
from raster_chart_viewer.tilename import TileKey

#: 128px and smaller only -- see this module's own docstring.
SMALL_MIP_MIN = 3

#: One shared cap across both the composed-tile and small-mip caches.
#: Not behaviour-affecting in the project's tuning sense (it changes disk
#: usage, not what Petrovich does -- this service has no Petrovich
#: involvement at all), so a plain constant: `body-layer`'s tuning
#: mechanism does not exist outside `body-layer` (root `CLAUDE.md`).
CACHE_MAX_BYTES = 1_000_000_000

#: Fraction of `CACHE_MAX_BYTES` a sweep evicts down to, rather than
#: stopping the instant the total drops back under the cap. Without
#: this, once the cache is actually at its cap, every single write
#: thereafter crosses straight back over on its own and pays the full
#: `rglob`+`stat`+`sort` scan again to evict exactly one file (measured
#: ~280ms at ~24.6k files -- performance review Finding 2, RC-1,
#: 2026-11-16). Sweeping to a margin below the cap instead amortizes that
#: scan over the many writes that follow. 90%: enough headroom that an
#: ordinary panning/warm-up session doesn't re-trigger a sweep every few
#: writes, without giving up much of the 1GB budget (10%, ~100MB). Same
#: non-tuning reasoning as `CACHE_MAX_BYTES` above -- a plain constant.
_CACHE_LOW_WATER_MARK_FRACTION = 0.9

#: Total mip levels in a full chain down to 1x1px -- 11 for the 1024px
#: base every measured RasterCharts tile uses (research note section C).
TOTAL_MIPS = int(math.log2(TILE_BASE_SIZE_PX)) + 1

#: Defensive cap on how far out a view tile's mip selection can reach --
#: the plan's own `k` never exceeds 6 for any terrain measured (Afghanistan
#: 32m, the largest grid, is 48x64 tiles), so this never actually binds;
#: it exists so a future, much larger terrain degrades to "blurriest mip
#: available" instead of indexing past the mip chain.
MAX_MIP_LEVEL = TOTAL_MIPS - 1

#: JPEG quality for composed-tile encoding -- generous enough that chart
#: text stays legible, far below the ~95+ where file size stops shrinking.
_JPEG_QUALITY = 85


def _mip_cell_name(key: TileKey) -> str:
    """Directory name for one tile's small-mip cache cell. `key.level`'s
    sign is part of the string (`"-1"`), not stripped -- different levels
    must never collide."""
    return f"{key.sheet}{key.level}_x{key.x}_z{key.z}"


class TileCache:
    """Owns the on-disk cache directory: composed-tile JPEGs plus small-
    mip PNGs, one shared size cap. Safe to construct against an existing
    cache directory from a previous run -- `__init__` sweeps it down to
    the cap immediately, in case the cap was lowered since.

    **Thread-safe**: `ThreadingHTTPServer`'s request threads and the
    background `warmup.WarmupScheduler` thread share one `TileCache`
    instance, so every operation that touches `_total_bytes` or the
    cache directory's contents -- including reads, which can otherwise
    race a concurrent eviction -- holds `self._lock` (reviewer fix,
    2026-11-16: a direct concurrency stress test crashed `_enforce_cap`
    reliably without it)."""

    def __init__(self, cache_dir: Path, max_bytes: int = CACHE_MAX_BYTES) -> None:
        self._cache_dir = cache_dir
        self._max_bytes = max_bytes
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._total_bytes = self._measure_total()
        with self._lock:
            self._enforce_cap_locked()

    def _measure_total(self) -> int:
        return sum(f.stat().st_size for f in self._cache_dir.rglob("*") if f.is_file())

    def _composed_tile_path(
        self, terrain: str, tier_label: str, level: int, vx: int, vy: int
    ) -> Path:
        return self._cache_dir / terrain / tier_label / str(level) / f"{vx}_{vy}.jpg"

    def _small_mip_path(
        self, terrain: str, tier_label: str, key: TileKey, mip: int
    ) -> Path:
        return (
            self._cache_dir
            / terrain
            / tier_label
            / _mip_cell_name(key)
            / f"mip{mip}.png"
        )

    def get_composed_tile(
        self, terrain: str, tier_label: str, level: int, vx: int, vy: int
    ) -> bytes | None:
        path = self._composed_tile_path(terrain, tier_label, level, vx, vy)
        with self._lock:
            return path.read_bytes() if path.is_file() else None

    def put_composed_tile(
        self,
        terrain: str,
        tier_label: str,
        level: int,
        vx: int,
        vy: int,
        data: bytes,
    ) -> None:
        self._write(self._composed_tile_path(terrain, tier_label, level, vx, vy), data)

    def has_small_mip(
        self, terrain: str, tier_label: str, key: TileKey, mip: int
    ) -> bool:
        with self._lock:
            return self._small_mip_path(terrain, tier_label, key, mip).is_file()

    def has_all_small_mips(self, terrain: str, tier_label: str, key: TileKey) -> bool:
        """True if every small mip (`>= SMALL_MIP_MIN`) of this entry is
        already cached -- `warmup.py`'s own skip check, so a restart
        re-warms nothing it already has without re-opening the zip just
        to find that out."""
        return all(
            self.has_small_mip(terrain, tier_label, key, level)
            for level in range(SMALL_MIP_MIN, TOTAL_MIPS)
        )

    def get_small_mip(
        self, terrain: str, tier_label: str, key: TileKey, mip: int
    ) -> Image.Image | None:
        path = self._small_mip_path(terrain, tier_label, key, mip)
        with self._lock:
            if not path.is_file():
                return None
            return Image.open(path).convert("RGBA")

    def put_small_mip(
        self,
        terrain: str,
        tier_label: str,
        key: TileKey,
        mip: int,
        image: Image.Image,
    ) -> None:
        if mip < SMALL_MIP_MIN:
            raise ValueError(
                f"mip {mip} is below SMALL_MIP_MIN ({SMALL_MIP_MIN}) -- "
                "never written to the small-mip cache as an ingredient"
            )
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        self._write(self._small_mip_path(terrain, tier_label, key, mip), buf.getvalue())

    def _write(self, path: Path, data: bytes) -> None:
        """Acquires `self._lock` itself -- callers (`put_composed_tile`,
        `put_small_mip`) must not already hold it, since `Lock` is not
        reentrant."""
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            existing_size = path.stat().st_size if path.is_file() else 0
            path.write_bytes(data)
            self._total_bytes += len(data) - existing_size
            if self._total_bytes > self._max_bytes:
                self._enforce_cap_locked()

    def _enforce_cap_locked(self) -> None:
        """Assumes `self._lock` is already held. Stats every file once,
        up front, before sorting -- `__init__` holds the lock across this
        call too, so no concurrent writer/evictor can make a file vanish
        between that stat and this method's own `unlink()` below; the
        `try/except` remains only for ordinary filesystem failures (not a
        concurrent-eviction race, which the lock now rules out). Sweeps
        down to `_CACHE_LOW_WATER_MARK_FRACTION` of the cap, not merely
        back under it -- see that constant's own comment for why."""
        if self._total_bytes <= self._max_bytes:
            return
        low_water_mark = int(self._max_bytes * _CACHE_LOW_WATER_MARK_FRACTION)
        entries: list[tuple[float, int, Path]] = []
        for candidate in self._cache_dir.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                stat = candidate.stat()
            except OSError:
                continue
            entries.append((stat.st_mtime, stat.st_size, candidate))
        entries.sort(key=lambda entry: entry[0])
        for _mtime, size, stale_path in entries:
            if self._total_bytes <= low_water_mark:
                break
            try:
                stale_path.unlink()
            except OSError:
                continue
            self._total_bytes -= size


def read_and_populate_small_mips(
    cache: TileCache,
    terrain: str,
    tier_label: str,
    key: TileKey,
    location: TileLocation,
    read_bytes: discovery.ReadTileBytes,
) -> bytes:
    """Read one entry's raw bytes, and -- since the cost of inflating it
    is already paid -- populate every small mip (`>= SMALL_MIP_MIN`) not
    already cached, whatever mip this particular call actually needs
    (plan: "written whenever an entry is inflated for any reason", not
    only when the small-mip cache itself was consulted). Returns the raw
    bytes so the caller decodes whichever mip it needs from them."""
    data = read_bytes(location)
    for level in range(SMALL_MIP_MIN, TOTAL_MIPS):
        if not cache.has_small_mip(terrain, tier_label, key, level):
            cache.put_small_mip(
                terrain, tier_label, key, level, decode_mip(data, level)
            )
    return data


def compose_view_tile(
    cache: TileCache,
    terrain: str,
    tier_label: str,
    grid: MosaicGrid,
    tiles: dict[TileKey, TileLocation],
    level: int,
    vx: int,
    vy: int,
    *,
    read_bytes: discovery.ReadTileBytes | None = None,
) -> bytes:
    """Compose one OpenSeadragon view tile into JPEG bytes, serving the
    composed-tile cache first. `read_bytes` is injectable so tests can
    count zip opens without monkeypatching `discovery` itself; left at
    its default (`None`), this call opens a fresh `discovery.
    BatchZipReader` scoped to itself, so its own entry loop below reuses
    one `ZipFile` handle per distinct zip across however many entries
    this one view tile needs (performance review Finding 1, RC-1,
    2026-11-16) -- 4 of 5 terrains have exactly one zip per tier, so a
    middle-zoom or full-tier-overview request that touches many entries
    no longer reopens it once per entry."""
    cached = cache.get_composed_tile(terrain, tier_label, level, vx, vy)
    if cached is not None:
        return cached

    if read_bytes is not None:
        return _compose_view_tile_uncached(
            cache, terrain, tier_label, grid, tiles, level, vx, vy, read_bytes
        )
    with discovery.batch_tile_reader() as reader:
        return _compose_view_tile_uncached(
            cache, terrain, tier_label, grid, tiles, level, vx, vy, reader
        )


def _compose_view_tile_uncached(
    cache: TileCache,
    terrain: str,
    tier_label: str,
    grid: MosaicGrid,
    tiles: dict[TileKey, TileLocation],
    level: int,
    vx: int,
    vy: int,
    read_bytes: discovery.ReadTileBytes,
) -> bytes:
    """The actual composition loop, factored out of `compose_view_tile`
    so the caller can decide once, up front, whether `read_bytes` is a
    caller-supplied reader (used exactly as given) or the production
    default (a fresh call-scoped `BatchZipReader`) -- this function
    itself does not care which."""
    k = grid.max_level - level
    mip = min(k, MAX_MIP_LEVEL)
    block = 2**k
    slot_size = TILE_SIZE_PX // block

    canvas = Image.new("RGB", (TILE_SIZE_PX, TILE_SIZE_PX))
    for dy in range(block):
        for dx in range(block):
            key = grid.key_at(vx * block + dx, vy * block + dy)
            if key is None:
                continue  # sparse-sheet/partial-grid gap -- leave blank
            location = tiles[key]
            if mip >= SMALL_MIP_MIN:
                sub_image = cache.get_small_mip(terrain, tier_label, key, mip)
                if sub_image is None:
                    data = read_and_populate_small_mips(
                        cache, terrain, tier_label, key, location, read_bytes
                    )
                    sub_image = cache.get_small_mip(terrain, tier_label, key, mip)
                    assert sub_image is not None, "just populated this mip"
            else:
                # Below SMALL_MIP_MIN, the small-mip cache is never
                # consulted as the *source* for this request -- but an
                # inflate triggered here still opportunistically fills
                # it for later small-mip requests (same helper as above).
                # A different middle-zoom view tile touching this same
                # entry still re-inflates it (plan: "repeated inflation
                # of the same entry at different middle zooms is
                # accepted") -- this function never checks the small-mip
                # cache before inflating when `mip < SMALL_MIP_MIN`.
                data = read_and_populate_small_mips(
                    cache, terrain, tier_label, key, location, read_bytes
                )
                sub_image = decode_mip(data, mip)
            canvas.paste(sub_image.convert("RGB"), (dx * slot_size, dy * slot_size))

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    jpeg_bytes = buf.getvalue()
    cache.put_composed_tile(terrain, tier_label, level, vx, vy, jpeg_bytes)
    return jpeg_bytes
