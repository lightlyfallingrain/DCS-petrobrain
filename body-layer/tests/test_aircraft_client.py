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
_PETROVICH_INDICATION_BODY = {
    "dcs_model_time_s": 123.5,
    "received_wall_clock_s": 1000.0,
    "fields": {"middle_list_text": "Ural truck"},
}
_PETROVICH_WHEEL_BODY = {
    "dcs_model_time_s": 123.5,
    "received_wall_clock_s": 1000.0,
    "fields": {"state": "SEARCHING"},
}


def _make_handler(
    pushed_lines: list[str],
    triggered_searches: list[str] | None = None,
) -> type[BaseHTTPRequestHandler]:
    if triggered_searches is None:
        triggered_searches = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/telemetry/latest":
                self._respond(200, _TELEMETRY_BODY)
            elif self.path == "/world_objects/latest":
                self._respond(200, _WORLD_OBJECTS_BODY)
            elif self.path == "/petrovich_indication/latest":
                self._respond(200, _PETROVICH_INDICATION_BODY)
            elif self.path == "/petrovich_wheel/latest":
                self._respond(200, _PETROVICH_WHEEL_BODY)
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

        def do_POST(self) -> None:
            if self.path == "/text/push":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                pushed_lines.append(body["text"])
                self._respond(200, {"ok": True})
            elif self.path == "/command/petrovich_search":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                triggered_searches.append(body["mode"])
                self._respond(200, {"ok": True})
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
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler([]))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture
def server_url_with_pushed_lines() -> Iterator[tuple[str, list[str]]]:
    pushed_lines: list[str] = []
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(pushed_lines))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", pushed_lines
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture
def server_url_with_triggered_searches() -> Iterator[tuple[str, list[str]]]:
    triggered_searches: list[str] = []
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler([], triggered_searches))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", triggered_searches
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


def test_get_petrovich_indication_latest_returns_parsed_dict(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_petrovich_indication_latest()

    assert result == _PETROVICH_INDICATION_BODY


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


def test_push_text_line_posts_to_text_push(
    server_url_with_pushed_lines: tuple[str, list[str]],
) -> None:
    server_url, pushed_lines = server_url_with_pushed_lines
    client = AircraftLayerClient(base_url=server_url)

    client.push_text_line("CONTACT_DETECTED: BMP-2, observed, currently visible.")

    assert pushed_lines == ["CONTACT_DETECTED: BMP-2, observed, currently visible."]


def test_push_text_line_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.push_text_line("hello")


def test_get_petrovich_wheel_latest_returns_parsed_dict(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_petrovich_wheel_latest()

    assert result == _PETROVICH_WHEEL_BODY


def test_trigger_petrovich_search_posts_to_command_endpoint(
    server_url_with_triggered_searches: tuple[str, list[str]],
) -> None:
    server_url, triggered_searches = server_url_with_triggered_searches
    client = AircraftLayerClient(base_url=server_url)

    client.trigger_petrovich_search("forward")

    assert triggered_searches == ["forward"]


def test_trigger_petrovich_search_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.trigger_petrovich_search("boresight")
