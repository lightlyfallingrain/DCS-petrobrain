"""Tests for `api.server`'s `GET /f10_commands/poll` endpoint --
`plans/f10-crew-commands/plan.md`. Mirrors `test_petrovich_search_api.py`'s
GET-endpoint structure, plus the drain-on-GET behavior this endpoint has
that no other `/latest`-style endpoint does."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import F10CommandQueue, TelemetryCache
from schema import F10CommandEvent


def _get(server: TelemetryAPIServer, path: str) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture
def running_server_with_queue() -> Iterator[tuple[TelemetryAPIServer, F10CommandQueue]]:
    cache = TelemetryCache()
    queue = F10CommandQueue()
    server = TelemetryAPIServer(
        cache, host="127.0.0.1", port=0, f10_command_queue=queue
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, queue
    finally:
        server.close()
        thread.join(timeout=5)


def test_f10_commands_poll_empty_queue_returns_empty_list(
    running_server_with_queue: tuple[TelemetryAPIServer, F10CommandQueue],
) -> None:
    server, _queue = running_server_with_queue
    status, body = _get(server, "/f10_commands/poll")
    assert status == 200
    assert body == []


def test_f10_commands_poll_drains_queue_oldest_first(
    running_server_with_queue: tuple[TelemetryAPIServer, F10CommandQueue],
) -> None:
    server, queue = running_server_with_queue
    queue.push(F10CommandEvent(command="watch_nearest", received_wall_clock_s=1.0))
    queue.push(F10CommandEvent(command="scan_ahead", received_wall_clock_s=2.0))

    status, body = _get(server, "/f10_commands/poll")

    assert status == 200
    assert body == [
        {"command": "watch_nearest", "received_wall_clock_s": 1.0},
        {"command": "scan_ahead", "received_wall_clock_s": 2.0},
    ]


def test_f10_commands_poll_drains_only_once(
    running_server_with_queue: tuple[TelemetryAPIServer, F10CommandQueue],
) -> None:
    server, queue = running_server_with_queue
    queue.push(F10CommandEvent(command="cancel_task", received_wall_clock_s=1.0))

    first_status, first_body = _get(server, "/f10_commands/poll")
    second_status, second_body = _get(server, "/f10_commands/poll")

    assert first_status == 200
    assert len(first_body) == 1  # type: ignore[arg-type]
    assert second_status == 200
    assert second_body == []


def test_f10_commands_poll_without_configured_queue_returns_empty_list() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _get(server, "/f10_commands/poll")
        assert status == 200
        assert body == []
    finally:
        server.close()
        thread.join(timeout=5)
