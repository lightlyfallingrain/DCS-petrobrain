"""The LAN-facing HTTP server: tile requests, terrain/tier listing, and
the OpenSeadragon viewer page's static assets.

Read-only, and read-only of the DCS install in particular -- nothing
here ever writes into `Mods/terrains/`. Runs `http.server.
ThreadingHTTPServer` (stdlib only, no third-party web framework),
mirroring `aircraft-layer`'s LAN API shape (`api/server.py`): a thin
class owning `open`/`close`/`port`/`serve_forever`, a handler factory
closing over whatever state this server needs.

- `GET /terrains` -> `{"terrains": [name, ...]}`, sorted.
- `GET /terrains/<terrain>/tiers` -> `{"tiers": [label, ...]}` in the
  order `discovery.TerrainIndex.tier_labels` gives (scaled tiers
  ascending by metres-per-pixel, "unscaled" last); `404` for an unknown
  terrain.
- `GET /terrains/<terrain>/tiers/<tier>` -> `{"tiles_wide", "tiles_tall",
  "max_level", "tile_size_px"}` -- the grid metadata the viewer page
  needs to configure OpenSeadragon's custom `TileSource` for this
  (terrain, tier) (plan Stage 5, "custom TileSource"; not named in the
  plan's own endpoint list, which predates writing the client against
  it). `404` for an unknown terrain or tier.
- `GET /tile/<terrain>/<tier>/<level>/<x>/<y>.jpg` -> the composed JPEG
  for that OpenSeadragon view tile (`cache.compose_view_tile`); `404` for
  an unknown terrain/tier or a `level` outside `[0, grid.max_level]`.
  `x`/`y` outside the grid's own extent are not range-checked -- they
  compose to an all-blank tile (every covered cell's `MosaicGrid.key_at`
  returns `None`), the same path a sparse-sheet gap already takes, never
  an error.
- Anything else is served as a static file from `static_dir` (the
  OpenSeadragon viewer page and its vendored assets) -- `/` maps to
  `index.html`.

An optional `warmup.WarmupScheduler` is touched from the tier-info and
tile handlers -- the two requests that name a specific `(terrain, tier)`
(plan, "started the first time that terrain/tier is actually touched (its
first tile or tier-listing request)"); the plural `/terrains/<t>/tiers`
listing never names one tier, so it is not a touch point.
"""

from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

from raster_chart_viewer.cache import TileCache, compose_view_tile
from raster_chart_viewer.discovery import TerrainIndex, tier_label
from raster_chart_viewer.mosaic import TILE_SIZE_PX, MosaicGrid
from raster_chart_viewer.warmup import WarmupScheduler

logger = logging.getLogger(__name__)

#: LAN-facing by design, same posture as `aircraft-layer/src/api/
#: server.py`'s own `DEFAULT_HOST`.
DEFAULT_HOST = "0.0.0.0"

#: 7800 was the first choice but collides with audio-adapter's Piper TTS
#: server (`audio-adapter/src/tts_engine.py` `DEFAULT_PIPER_URL`,
#: `audio-adapter/RUN.md`), which runs on the same Windows box -- missed
#: by the original `DEFAULT_PORT`-only grep because Piper's port is a
#: bare URL string, not a `DEFAULT_PORT` constant (reviewer fix,
#: 2026-11-16; `.claude/agent-memory/architect/
#: feedback_grep_default_port_before_assigning_one.md`). **7801**: one
#: past the aircraft-layer family (7790-7799, 7794 retired) *and* past
#: Piper, re-grepped for 7801-7809 repo-wide with no hits.
DEFAULT_PORT = 7801

_TERRAINS_PATH = "/terrains"
_TIERS_RE = re.compile(r"^/terrains/(?P<terrain>[^/]+)/tiers$")
_TIER_INFO_RE = re.compile(r"^/terrains/(?P<terrain>[^/]+)/tiers/(?P<tier>[^/]+)$")
_TILE_RE = re.compile(
    r"^/tile/(?P<terrain>[^/]+)/(?P<tier>[^/]+)/(?P<level>\d+)/"
    r"(?P<vx>\d+)/(?P<vy>\d+)\.jpg$"
)

_STATIC_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".css": "text/css",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".map": "application/json",
    ".json": "application/json",
}


def _guess_static_content_type(path: Path) -> str:
    return _STATIC_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _build_grids(
    terrains: dict[str, TerrainIndex],
) -> dict[tuple[str, str], MosaicGrid]:
    """One `MosaicGrid` per (terrain, tier) -- built once at server
    construction from the already-discovered `TileKey`s, never per
    request. Cheap: pure coordinate math, no zip/Pillow involved."""
    grids: dict[tuple[str, str], MosaicGrid] = {}
    for name, index in terrains.items():
        for scale, tiles in index.tiers.items():
            grids[(name, tier_label(scale))] = MosaicGrid(list(tiles))
    return grids


def _make_handler(
    terrains: dict[str, TerrainIndex],
    grids: dict[tuple[str, str], MosaicGrid],
    cache: TileCache,
    static_dir: Path,
    warmup: WarmupScheduler | None,
) -> type[BaseHTTPRequestHandler]:
    resolved_static_dir = static_dir.resolve()

    class RasterChartViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == _TERRAINS_PATH:
                self._respond_json(200, {"terrains": sorted(terrains)})
                return

            tiers_match = _TIERS_RE.match(path)
            if tiers_match is not None:
                self._handle_tiers(tiers_match.group("terrain"))
                return

            tier_info_match = _TIER_INFO_RE.match(path)
            if tier_info_match is not None:
                self._handle_tier_info(
                    tier_info_match.group("terrain"), tier_info_match.group("tier")
                )
                return

            tile_match = _TILE_RE.match(path)
            if tile_match is not None:
                self._handle_tile(tile_match)
                return

            self._serve_static(path)

        def _handle_tiers(self, terrain: str) -> None:
            index = terrains.get(terrain)
            if index is None:
                self._respond_json(404, {"error": f"unknown terrain: {terrain}"})
                return
            self._respond_json(200, {"tiers": index.tier_labels()})

        def _handle_tier_info(self, terrain: str, tier: str) -> None:
            """Grid metadata the viewer page needs to configure
            OpenSeadragon's custom `TileSource` for this (terrain, tier).
            Also the viewer's own first touch of a (terrain, tier) --
            triggers warm-up here, before the first tile is ever
            requested."""
            index = terrains.get(terrain)
            grid = grids.get((terrain, tier))
            tiles = None if index is None else index.tiles_for_label(tier)
            if index is None or grid is None or tiles is None:
                self._respond_json(
                    404, {"error": f"unknown tier {tier!r} for terrain {terrain!r}"}
                )
                return
            if warmup is not None:
                warmup.touch(terrain, tier, tiles)
            self._respond_json(
                200,
                {
                    "tiles_wide": grid.tiles_wide,
                    "tiles_tall": grid.tiles_tall,
                    "max_level": grid.max_level,
                    "tile_size_px": TILE_SIZE_PX,
                },
            )

        def _handle_tile(self, match: re.Match[str]) -> None:
            terrain = match.group("terrain")
            tier = match.group("tier")
            level = int(match.group("level"))
            vx = int(match.group("vx"))
            vy = int(match.group("vy"))

            index = terrains.get(terrain)
            if index is None:
                self._respond_json(404, {"error": f"unknown terrain: {terrain}"})
                return
            tiles = index.tiles_for_label(tier)
            grid = grids.get((terrain, tier))
            if tiles is None or grid is None:
                self._respond_json(
                    404, {"error": f"unknown tier {tier!r} for terrain {terrain!r}"}
                )
                return
            if warmup is not None:
                warmup.touch(terrain, tier, tiles)
            if not (0 <= level <= grid.max_level):
                self._respond_json(
                    404,
                    {
                        "error": (
                            f"level {level} out of range "
                            f"[0, {grid.max_level}] for {terrain}/{tier}"
                        )
                    },
                )
                return

            jpeg_bytes = compose_view_tile(
                cache, terrain, tier, grid, tiles, level, vx, vy
            )
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpeg_bytes)))
            self.end_headers()
            self.wfile.write(jpeg_bytes)

        def _serve_static(self, path: str) -> None:
            relative = "index.html" if path == "/" else path.lstrip("/")
            candidate = (resolved_static_dir / relative).resolve()
            try:
                candidate.relative_to(resolved_static_dir)
            except ValueError:
                self._respond_json(403, {"error": "forbidden"})
                return
            if not candidate.is_file():
                self._respond_json(404, {"error": f"not found: {path}"})
                return

            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", _guess_static_content_type(candidate))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _respond_json(self, status: int, body: Any) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), format % args)

    return RasterChartViewerHandler


class RasterChartViewerServer:
    """Owns the LAN-facing HTTP server; mirrors `aircraft-layer/src/api/
    server.py`'s `TelemetryAPIServer` shape."""

    def __init__(
        self,
        terrains: dict[str, TerrainIndex],
        cache: TileCache,
        static_dir: Path,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        warmup: WarmupScheduler | None = None,
    ) -> None:
        self._terrains = terrains
        self._grids = _build_grids(terrains)
        self._cache = cache
        self._static_dir = static_dir
        self._host = host
        self._port = port
        self._warmup = warmup
        self._httpd: ThreadingHTTPServer | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def port(self) -> int:
        """Bound port. Useful when constructed with `port=0` (OS-assigned)."""
        if self._httpd is None:
            raise RuntimeError("call open() before reading port")
        return int(self._httpd.server_address[1])

    def open(self) -> None:
        """Bind and start listening. Does not block."""
        self._httpd = ThreadingHTTPServer(
            (self._host, self._port),
            _make_handler(
                self._terrains,
                self._grids,
                self._cache,
                self._static_dir,
                self._warmup,
            ),
        )
        logger.info("raster chart viewer listening on %s:%d", self._host, self.port)

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def serve_forever(self) -> None:
        """Serve requests until `close()` is called from another thread."""
        if self._httpd is None:
            raise RuntimeError("call open() before serve_forever()")
        self._httpd.serve_forever()
