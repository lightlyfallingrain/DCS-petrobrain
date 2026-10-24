"""Tests for `aircraft_client.AircraftLayerClient`.

Exercised against a real loopback `http.server` instance rather than a
mocked `urllib`, mirroring `aircraft-layer/tests/test_api.py`'s own pattern
-- cheap to spin up and catches real wire-format mismatches a mock would
paper over.
"""

from __future__ import annotations

import contextlib
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
_F10_COMMANDS_BODY = [
    {"command": "watch_nearest", "received_wall_clock_s": 999.0},
    {"command": "cancel_task", "received_wall_clock_s": 1000.0},
]
_SPU8_STATE_BODY = {
    "t": 123.5,
    "received_wall_clock_s": 1000.0,
    "net1": 1.0,
    "ics_power": 1.0,
    "vol": 0.8,
    "net1_on": True,
    "ics_power_on": True,
    "gate_open": True,
}


_WATCHED_ARGS_BODY = {
    "t": 123.5,
    "received_wall_clock_s": 1000.0,
    "watch_id": "abc123",
    "args": {"886": 1.0},
}


def _make_handler(
    pushed_lines: list[str],
    triggered_searches: list[str] | None = None,
    watch_args_calls: list[tuple[str, list[int]]] | None = None,
    read_args_response: object | None = None,
    read_args_status: int = 200,
) -> type[BaseHTTPRequestHandler]:
    if triggered_searches is None:
        triggered_searches = []
    if watch_args_calls is None:
        watch_args_calls = []

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
            elif self.path == "/f10_commands/poll":
                self._respond(200, _F10_COMMANDS_BODY)
            elif self.path == "/spu8/state":
                self._respond(200, _SPU8_STATE_BODY)
            elif self.path == "/watched_args/latest":
                self._respond(200, _WATCHED_ARGS_BODY)
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
            elif self.path == "/command/watch_args":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                watch_args_calls.append((body["watch_id"], body["args"]))
                self._respond(200, {"ok": True})
            elif self.path == "/query/read_args":
                self._respond(
                    read_args_status,
                    read_args_response
                    if read_args_response is not None
                    else {"t": 5.0, "values": {}},
                )
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


def test_get_f10_commands_returns_parsed_list(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_f10_commands()

    assert result == _F10_COMMANDS_BODY


def test_get_f10_commands_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.get_f10_commands()


def test_get_spu8_state_latest_returns_parsed_dict(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_spu8_state_latest()

    assert result == _SPU8_STATE_BODY


def test_get_spu8_state_latest_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.get_spu8_state_latest()


def test_get_watched_args_latest_returns_parsed_dict(server_url: str) -> None:
    client = AircraftLayerClient(base_url=server_url)

    result = client.get_watched_args_latest()

    assert result == _WATCHED_ARGS_BODY


@pytest.fixture
def server_url_with_watch_args_calls() -> Iterator[
    tuple[str, list[tuple[str, list[int]]]]
]:
    calls: list[tuple[str, list[int]]] = []
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler([], watch_args_calls=calls))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", calls
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_set_watch_args_posts_to_command_endpoint(
    server_url_with_watch_args_calls: tuple[str, list[tuple[str, list[int]]]],
) -> None:
    url, calls = server_url_with_watch_args_calls
    client = AircraftLayerClient(base_url=url)

    client.set_watch_args("abc123", [886, 898, 960])

    assert calls == [("abc123", [886, 898, 960])]


def test_set_watch_args_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.set_watch_args("abc", [886])


@contextlib.contextmanager
def _read_args_server(response: object, status: int = 200) -> Iterator[str]:
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        _make_handler([], read_args_response=response, read_args_status=status),
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_read_args_returns_validated_values() -> None:
    with _read_args_server({"t": 12.5, "values": {"773": 1.0, "761": 0.0}}) as url:
        client = AircraftLayerClient(base_url=url)
        result = client.read_args([773, 761])
        assert result == {"773": 1.0, "761": 0.0}


def test_read_args_raises_on_unreachable_host() -> None:
    client = AircraftLayerClient(base_url="http://127.0.0.1:1", timeout_s=0.5)

    with pytest.raises(AircraftLayerError):
        client.read_args([886])


@pytest.mark.parametrize(
    "bad_values",
    [
        {"886": float("nan")},
        {"886": float("inf")},
        {"886": True},
        {"abc": 1.0},
        {"-1": 1.0},
        {"4096": 1.0},
        {"898": 1.0},  # not one of the args requested ([886])
    ],
)
def test_read_args_rejects_a_malformed_response(bad_values: dict[str, object]) -> None:
    """*Mutation* (security plan review, E9): drop `math.isfinite` and a
    NaN value would reach the caller rather than raising -- `belief.
    effector_engine`'s own `_matches` would then read a NaN as "differs"
    and write on it."""
    with _read_args_server({"t": 1.0, "values": bad_values}) as url:
        client = AircraftLayerClient(base_url=url)
        with pytest.raises(AircraftLayerError):
            client.read_args([886])


def test_read_args_65_keys_is_rejected() -> None:
    values = {str(n): 0.0 for n in range(65)}
    with _read_args_server({"t": 1.0, "values": values}) as url:
        client = AircraftLayerClient(base_url=url)
        with pytest.raises(AircraftLayerError):
            client.read_args(list(range(65)))


def test_read_args_values_not_an_object_is_rejected() -> None:
    with _read_args_server({"t": 1.0, "values": [1, 2]}) as url:
        client = AircraftLayerClient(base_url=url)
        with pytest.raises(AircraftLayerError):
            client.read_args([886])


def test_read_args_504_raises() -> None:
    with _read_args_server({"error": "timeout"}, status=504) as url:
        client = AircraftLayerClient(base_url=url)
        with pytest.raises(AircraftLayerError):
            client.read_args([886])
