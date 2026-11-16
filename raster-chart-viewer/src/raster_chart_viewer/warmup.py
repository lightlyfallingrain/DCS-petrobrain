"""Background warm-up: mitigates the slow first fully-zoomed-out view of
a tier, without a server-start cost paid for terrains nobody opens.

A background thread per `(terrain, tier)`, started the first time that
terrain/tier is actually touched (its first tile or tier-listing
request), not for every terrain at server start -- warming all five
installed terrains would inflate about 12,500 entries on every launch
for terrains the user may never open. It inflates each entry once and
keeps only its small mips (`cache.SMALL_MIP_MIN` and above), skipping
entries whose small mips are already cached, so a restart re-warms
nothing it already has. The server keeps accepting requests while it
runs -- nothing here blocks `server.py`'s request handling, and a real
visitor's own request for an entry still mid-warm-up just inflates it
itself (same cost as today, simply not pre-paid).
"""

from __future__ import annotations

import logging
import threading

from raster_chart_viewer import discovery
from raster_chart_viewer.cache import TileCache, read_and_populate_small_mips
from raster_chart_viewer.discovery import TileLocation
from raster_chart_viewer.tilename import TileKey

logger = logging.getLogger(__name__)


class WarmupScheduler:
    """Starts at most one warm-up thread per `(terrain, tier)` per
    process lifetime. `touch` is cheap and safe to call on every request
    -- it is a no-op after the first call for a given `(terrain, tier)`."""

    def __init__(
        self,
        cache: TileCache,
        *,
        read_bytes: discovery.ReadTileBytes | None = None,
    ) -> None:
        self._cache = cache
        self._read_bytes = read_bytes
        self._started: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def touch(
        self,
        terrain: str,
        tier_label: str,
        tiles: dict[TileKey, TileLocation],
    ) -> None:
        """Called whenever a request touches `(terrain, tier)`. Starts
        the warm-up thread the first time; every later call is a no-op."""
        key = (terrain, tier_label)
        with self._lock:
            if key in self._started:
                return
            self._started.add(key)
        thread = threading.Thread(
            target=self._warm_up,
            args=(terrain, tier_label, tiles),
            name=f"warmup-{terrain}-{tier_label}",
            daemon=True,
        )
        thread.start()

    def _warm_up(
        self,
        terrain: str,
        tier_label: str,
        tiles: dict[TileKey, TileLocation],
    ) -> None:
        """Dispatches to `_run_warm_up` with whichever reader this pass
        should use. Left at its default (`None`), a warm-up pass opens
        one `discovery.BatchZipReader` scoped to itself, so a whole tier
        -- thousands of entries, almost always sharing one zip -- opens
        that zip once instead of once per entry (performance review
        Finding 1, RC-1, 2026-11-16). A caller-supplied `self._read_bytes`
        (tests) is used exactly as given, per entry, unwrapped."""
        if self._read_bytes is not None:
            self._run_warm_up(terrain, tier_label, tiles, self._read_bytes)
            return
        with discovery.batch_tile_reader() as reader:
            self._run_warm_up(terrain, tier_label, tiles, reader)

    def _run_warm_up(
        self,
        terrain: str,
        tier_label: str,
        tiles: dict[TileKey, TileLocation],
        read_bytes: discovery.ReadTileBytes,
    ) -> None:
        logger.info(
            "warm-up started: %s/%s (%d entries)", terrain, tier_label, len(tiles)
        )
        inflated = 0
        already_cached = 0
        failed = 0
        for key, location in tiles.items():
            if self._cache.has_all_small_mips(terrain, tier_label, key):
                already_cached += 1
                continue
            try:
                read_and_populate_small_mips(
                    self._cache,
                    terrain,
                    tier_label,
                    key,
                    location,
                    read_bytes,
                )
            except Exception:
                # A warm-up failure on one entry must not abort the rest
                # of the tier, and must not crash this background
                # thread -- a real request for this same entry still
                # inflates it itself later, same as if warm-up had never
                # run at all.
                logger.exception(
                    "warm-up failed to read %s/%s entry %s",
                    terrain,
                    tier_label,
                    location.entry_name,
                )
                failed += 1
                continue
            inflated += 1
        logger.info(
            "warm-up complete: %s/%s -- %d inflated, %d already cached, %d failed",
            terrain,
            tier_label,
            inflated,
            already_cached,
            failed,
        )
