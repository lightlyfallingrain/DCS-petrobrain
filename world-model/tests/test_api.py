"""Tests for `api.server.WorldModelAPIServer` -- MI-2
(`plans/mi2-world-enrichment/plan.md`), world-model's first HTTP seam.

Spins up a real server on an OS-assigned port against a small on-disk
fixture store built directly from `store.writer` (same posture as
`test_describe_position.py`'s Stage 1 smoke tests -- no real DCS/OSM raw
files, which are gitignored), and queries it with `urllib.request`,
mirroring `aircraft-layer/tests/test_api.py`'s established pattern for
exactly this kind of test.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from api.server import WorldModelAPIServer
from store.models import Region, StoredFeature
from store.writer import insert_features, insert_region, open_for_build

_THEATRE = "Syria"


def _fixture_conn(tmp_path: Path) -> sqlite3.Connection:
    """Builds the fixture store, then reopens it with
    `check_same_thread=False` -- the running server's `serve_forever()` runs
    on a background thread (started by the `running_server` fixture below),
    a different thread than the one that opens this connection, and a plain
    `sqlite3.connect()` refuses to let a connection be used outside its
    creating thread. Safe here because `WorldModelAPIServer` deliberately
    uses a single-threaded `HTTPServer` (see `api.server`'s module
    docstring) -- exactly one thread ever touches this connection at a
    time, `check_same_thread=False` just lets that thread be a different
    one than the connection's own creation thread."""
    db_path = tmp_path / "fixture.sqlite"
    conn = open_for_build(db_path)
    insert_region(
        conn,
        Region(
            name="latakia-20km",
            theatre=_THEATRE,
            centre_x=44934.892,
            centre_z=5685.076,
            half_extent_x_m=10000.0,
            half_extent_z_m=10000.0,
            built_at="2026-09-04T00:00:00+00:00",
        ),
    )
    insert_features(
        conn,
        [
            StoredFeature(
                kind="named_place",
                geom_type="Point",
                geometry=[(41934.892, 5685.076)],
                name="Jablah",
                subtype=None,
                tags={"display_name": "Jablah"},
                source_id=None,
                source_ref="Jablah",
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=1300.0,
            ),
        ],
    )
    conn.close()
    return sqlite3.connect(db_path, check_same_thread=False)


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[WorldModelAPIServer]:
    conn = _fixture_conn(tmp_path)
    server = WorldModelAPIServer(conn, _THEATRE, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.close()
        thread.join(timeout=5)
        conn.close()


def _get(server: WorldModelAPIServer, path: str) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_describe_position_happy_path(running_server: WorldModelAPIServer) -> None:
    status, body = _get(
        running_server,
        f"/describe_position?x=41934.892&z=5685.076&theatre={_THEATRE}",
    )
    assert status == 200
    assert isinstance(body, dict)
    assert body["theatre"] == _THEATRE
    names = [p["name"] for p in body["named_places_within_radius"]]
    assert "Jablah" in names


def test_describe_position_missing_x_returns_400(
    running_server: WorldModelAPIServer,
) -> None:
    status, body = _get(
        running_server, f"/describe_position?z=5685.076&theatre={_THEATRE}"
    )
    assert status == 400
    assert isinstance(body, dict)
    assert "x" in body["error"]


def test_describe_position_non_numeric_x_returns_400(
    running_server: WorldModelAPIServer,
) -> None:
    status, _body = _get(
        running_server,
        f"/describe_position?x=not-a-number&z=5685.076&theatre={_THEATRE}",
    )
    assert status == 400


def test_describe_position_theatre_mismatch_returns_400(
    running_server: WorldModelAPIServer,
) -> None:
    status, body = _get(
        running_server, "/describe_position?x=41934.892&z=5685.076&theatre=WrongTheatre"
    )
    assert status == 400
    assert isinstance(body, dict)
    assert "theatre" in body["error"]


def test_find_place_by_name_happy_path(running_server: WorldModelAPIServer) -> None:
    status, body = _get(running_server, "/find_place_by_name?text=Jablah")
    assert status == 200
    assert isinstance(body, list)
    assert body[0]["name"] == "Jablah"


def test_find_place_by_name_missing_text_returns_400(
    running_server: WorldModelAPIServer,
) -> None:
    status, _body = _get(running_server, "/find_place_by_name")
    assert status == 400


def test_line_of_sight_happy_path(running_server: WorldModelAPIServer) -> None:
    status, body = _get(
        running_server,
        f"/line_of_sight?ox=0&oz=0&oalt=1000&tx=100&tz=100&talt=1000&theatre={_THEATRE}",
    )
    assert status == 200
    assert isinstance(body, dict)
    assert body["clear"] is True


def test_line_of_sight_missing_param_returns_400(
    running_server: WorldModelAPIServer,
) -> None:
    status, _body = _get(
        running_server,
        f"/line_of_sight?ox=0&oz=0&oalt=1000&tx=100&tz=100&theatre={_THEATRE}",
    )
    assert status == 400


def test_line_of_sight_theatre_mismatch_returns_400(
    running_server: WorldModelAPIServer,
) -> None:
    status, _body = _get(
        running_server,
        "/line_of_sight?ox=0&oz=0&oalt=1000&tx=100&tz=100&talt=1000&theatre=WrongTheatre",
    )
    assert status == 400


def test_unknown_path_returns_404(running_server: WorldModelAPIServer) -> None:
    status, _body = _get(running_server, "/nope")
    assert status == 404
