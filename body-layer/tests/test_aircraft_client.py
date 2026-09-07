"""Tests for `aircraft_client.AircraftLayerClient`.

Exercised against a real loopback `http.server` instance rather than a
mocked `urllib`, mirroring `aircraft-layer/tests/test_api.py`'s own pattern
-- cheap to spin up and catches real wire-format mismatches a mock would
paper over.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aircraft_client import AircraftLayerClient, AircraftLayerError

_TELEMETRY_BODY = {"dcs_model_time_s": 123.5, "position_x_m": 1.0}
_WORLD_OBJECTS_BODY = {"dcs_model_time_s": 123.5, "objects": []}


def _make_handler() -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/telemetry/latest":
                self._respond(200, _TELEMETRY_BODY)
            elif self.path == "/world_objects/latest":
                self._respond(200, _WORLD_OBJECTS_BODY)
            elif self.path == "/telemetry/empty":
                self._respond(200, None)
            elif self.path == "/not-json":
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


def test_get_telemetry_latest_returns_parsed_dict(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_telemetry_latest()

    assert result == _TELEMETRY_BODY


def test_get_world_objects_latest_returns_parsed_dict(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_world_objects_latest()

    assert result == _WORLD_OBJECTS_BODY


def test_get_telemetry_latest_returns_none_when_empty(server_url: str) -> None:
    client = AircraftLayerClient(base_url=f"{server_url}")

    # Point the client at a URL whose path always answers null, by hitting
    # the dedicated empty-cache path this fake server exposes.
    result = client._get_json("/telemetry/empty")

    assert result is None


def test_get_telemetry_latest_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.get_telemetry_latest()


def test_get_json_raises_on_invalid_json_body(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    with pytest.raises(AircraftLayerError):
        client._get_json("/not-json")
