"""CLI entry point: discover a DCS install's RasterCharts and serve them.

Strictly read-only of the DCS install -- discovery only ever opens zips
for reading (`zipfile.ZipFile(..., "r")`'s default mode), never writes
into `Mods/terrains/` or anywhere else under `--dcs-install`.

Run (Windows `python.exe`, launched from WSL bash -- see `README.md`):

    .venv-win/Scripts/python.exe -m raster_chart_viewer \\
        --dcs-install "F:\\Games\\DCS World"
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from raster_chart_viewer.cache import CACHE_MAX_BYTES, TileCache
from raster_chart_viewer.discovery import discover_terrains
from raster_chart_viewer.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    RasterChartViewerServer,
)
from raster_chart_viewer.warmup import WarmupScheduler

#: `raster-chart-viewer/static/`, sibling to `src/` and `tests/` -- the
#: OpenSeadragon viewer page and its vendored assets. `__file__` is
#: `src/raster_chart_viewer/__main__.py`, so two parents up is the
#: subproject root.
_DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

#: `<cache-dir>/raster-chart-viewer-cache` by default -- a dedicated
#: subdirectory rather than the bare cache dir itself, so pointing
#: `--cache-dir` at a shared temp folder doesn't scatter files directly
#: into it.
_DEFAULT_CACHE_SUBDIR = "raster-chart-viewer-cache"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="raster_chart_viewer",
        description=(
            "Serve an installed DCS World terrain's RasterCharts as a "
            "pan/zoom tiled map on the LAN."
        ),
    )
    parser.add_argument(
        "--dcs-install",
        type=Path,
        required=True,
        help='DCS install root (e.g. "F:\\Games\\DCS World" on Windows).',
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help=(
            "Tile/mip disk cache directory. Defaults to a platform temp "
            f"directory's {_DEFAULT_CACHE_SUBDIR!r} subdirectory."
        ),
    )
    parser.add_argument(
        "--cache-cap-bytes",
        type=int,
        default=CACHE_MAX_BYTES,
        help=f"Cache size cap in bytes (default: {CACHE_MAX_BYTES}).",
    )
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=_DEFAULT_STATIC_DIR,
        help="Viewer page + vendored assets directory (for development).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable DEBUG logging."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    terrains = discover_terrains(args.dcs_install)
    if not terrains:
        logger.warning(
            "no RasterCharts discovered under %s -- is --dcs-install correct?",
            args.dcs_install,
        )
    else:
        logger.info(
            "discovered %d terrain(s): %s", len(terrains), ", ".join(sorted(terrains))
        )

    cache_dir = args.cache_dir
    if cache_dir is None:
        import tempfile

        cache_dir = Path(tempfile.gettempdir()) / _DEFAULT_CACHE_SUBDIR
    cache = TileCache(cache_dir, max_bytes=args.cache_cap_bytes)
    warmup = WarmupScheduler(cache)

    server = RasterChartViewerServer(
        terrains, cache, args.static_dir, host=args.host, port=args.port, warmup=warmup
    )
    server.open()
    logger.info(
        "serving on http://%s:%d/ (cache: %s)", args.host, server.port, cache_dir
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
