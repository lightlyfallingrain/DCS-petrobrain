"""Tests for `world_enrich.world_model_client.WorldModelClient`.

Exercised against a real loopback `http.server` instance rather than a
mocked `urllib`, mirroring `body-layer/tests/test_aircraft_client.py`'s
own pattern -- cheap to spin up and catches real wire-format mismatches a
mock would paper over. Per module independence
(root `CLAUDE.md`), this test double is hand-rolled here rather than
importing world-model's real `api.server.WorldModelAPIServer` -- see
`world-model/tests/test_api.py` for that server's own tests.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from world_enrich.world_model_client import WorldModelClient, WorldModelClientError

_THEATRE = "TestTheatre"

_DESCRIBE_POSITION_BODY = {
    "theatre": _THEATRE,
    "x": 10.0,
    "z": 20.0,
    "lat": 1.0,
    "lon": 2.0,
    "nearest_settlement": None,
}
_FIND_PLACE_BY_NAME_BODY = [
    {"name": "Jablah", "kind": "settlement", "feature_id": 1, "x": 10.0, "z": 20.0}
]


def _make_handler() -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            if parsed.path == "/describe_position":
                if params.get("theatre") != _THEATRE:
                    self._respond(400, {"error": "theatre mismatch"})
                    return
                self._respond(200, _DESCRIBE_POSITION_BODY)
            elif parsed.path == "/find_place_by_name":
                if params.get("text") == "badshape":
                    self._respond(200, ["not-a-dict"])
                else:
                    self._respond(200, _FIND_PLACE_BY_NAME_BODY)
            elif parsed.path == "/line_of_sight":
                if params.get("theatre") != _THEATRE:
                    self._respond(400, {"error": "theatre mismatch"})
                    return
                self._respond(200, {"clear": True})
            elif parsed.path == "/not-json":
                payload = b"not json"
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self._respond(404, {"error": "not found"})

        def _respond(self, status: int, body: object) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler


@pytest.fixture
def server_url() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler())
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_get_describe_position_returns_parsed_dict(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre=_THEATRE)

    result = client.get_describe_position(10.0, 20.0)

    assert result == _DESCRIBE_POSITION_BODY


def test_get_find_place_by_name_returns_parsed_list(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre=_THEATRE)

    result = client.get_find_place_by_name("Jablah")

    assert result == _FIND_PLACE_BY_NAME_BODY


def test_get_line_of_sight_clear_returns_bool(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre=_THEATRE)

    result = client.get_line_of_sight_clear((0.0, 0.0, 100.0), (10.0, 10.0, 100.0))

    assert result is True


def test_get_describe_position_raises_on_theatre_mismatch(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre="WrongTheatre")

    with pytest.raises(WorldModelClientError):
        client.get_describe_position(10.0, 20.0)


def test_get_json_raises_on_unreachable_host() -> None:
    client = WorldModelClient(
        base_url="http://127.0.0.1:1", theatre=_THEATRE, timeout_s=0.5
    )

    with pytest.raises(WorldModelClientError):
        client.get_describe_position(0.0, 0.0)


def test_get_json_raises_on_invalid_json_body(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre=_THEATRE)

    with pytest.raises(WorldModelClientError):
        client._get_json("/not-json")


def test_get_json_raises_on_404(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre=_THEATRE)

    with pytest.raises(WorldModelClientError):
        client._get_json("/no-such-path")


def test_get_find_place_by_name_raises_on_wrong_element_shape(server_url: str) -> None:
    client = WorldModelClient(base_url=server_url, theatre=_THEATRE)

    with pytest.raises(WorldModelClientError):
        client.get_find_place_by_name("badshape")
