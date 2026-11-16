from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from fixtures.fake_terrain_trees import build_single_zip_terrain, full_sheet_entries
from fixtures.synthetic_dds import build_multi_mip_dds
from PIL import Image

from raster_chart_viewer.cache import TileCache
from raster_chart_viewer.discovery import discover_terrains
from raster_chart_viewer.server import RasterChartViewerServer


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[RasterChartViewerServer]:
    dcs_install = tmp_path / "dcs"
    tile_data = build_multi_mip_dds(1024, 11)
    entries = full_sheet_entries(32, "aa", 0, lambda _x, _z: tile_data)
    build_single_zip_terrain(dcs_install, "Syria", entries)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html><body>viewer</body></html>")
    (static_dir / "openseadragon").mkdir()
    (static_dir / "openseadragon" / "openseadragon.min.js").write_text("/* osd */")

    terrains = discover_terrains(dcs_install)
    cache = TileCache(tmp_path / "cache")
    server = RasterChartViewerServer(
        terrains, cache, static_dir, host="127.0.0.1", port=0
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.close()
        thread.join(timeout=5)


def _get(server: RasterChartViewerServer, path: str) -> tuple[int, bytes, str]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")


def test_terrains_lists_every_discovered_terrain(
    running_server: RasterChartViewerServer,
) -> None:
    status, body, content_type = _get(running_server, "/terrains")
    assert status == 200
    assert "json" in content_type
    assert json.loads(body) == {"terrains": ["Syria"]}


def test_tiers_lists_every_discovered_tier(
    running_server: RasterChartViewerServer,
) -> None:
    status, body, _ct = _get(running_server, "/terrains/Syria/tiers")
    assert status == 200
    assert json.loads(body) == {"tiers": ["32m"]}


def test_tiers_unknown_terrain_404(running_server: RasterChartViewerServer) -> None:
    status, body, _ct = _get(running_server, "/terrains/Nowhere/tiers")
    assert status == 404
    assert "error" in json.loads(body)


def test_tile_request_returns_valid_jpeg(
    running_server: RasterChartViewerServer,
) -> None:
    # One sheet, 8x8 -> max_level = 3. Full-res tile at (0, 0).
    status, body, content_type = _get(running_server, "/tile/Syria/32m/3/0/0.jpg")
    assert status == 200
    assert content_type == "image/jpeg"
    image = Image.open(io.BytesIO(body))
    assert image.format == "JPEG"
    assert image.size == (1024, 1024)


def test_tile_request_level_out_of_range_404(
    running_server: RasterChartViewerServer,
) -> None:
    status, _body, _ct = _get(running_server, "/tile/Syria/32m/99/0/0.jpg")
    assert status == 404


def test_tile_request_unknown_tier_404(
    running_server: RasterChartViewerServer,
) -> None:
    status, _body, _ct = _get(running_server, "/tile/Syria/999m/0/0/0.jpg")
    assert status == 404


def test_tile_request_out_of_bounds_xy_is_blank_not_error(
    running_server: RasterChartViewerServer,
) -> None:
    # vx/vy outside the grid's extent compose to an all-blank tile
    # (every covered cell's MosaicGrid.key_at returns None), same as a
    # sparse-sheet gap -- never an error.
    status, body, _ct = _get(running_server, "/tile/Syria/32m/3/99/99.jpg")
    assert status == 200
    image = Image.open(io.BytesIO(body))
    assert image.size == (1024, 1024)


def test_static_index_served_at_root(running_server: RasterChartViewerServer) -> None:
    status, body, content_type = _get(running_server, "/")
    assert status == 200
    assert "html" in content_type
    assert b"viewer" in body


def test_static_vendored_asset_served(
    running_server: RasterChartViewerServer,
) -> None:
    status, body, content_type = _get(
        running_server, "/openseadragon/openseadragon.min.js"
    )
    assert status == 200
    assert "javascript" in content_type
    assert b"osd" in body


def test_static_path_traversal_rejected(
    running_server: RasterChartViewerServer,
) -> None:
    status, _body, _ct = _get(running_server, "/../pyproject.toml")
    assert status in (403, 404)


def test_unknown_path_returns_404(running_server: RasterChartViewerServer) -> None:
    status, _body, _ct = _get(running_server, "/nope-not-a-real-path")
    assert status == 404
