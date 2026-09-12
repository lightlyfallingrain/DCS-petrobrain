"""Tests for `synth.ollama_client.OllamaClient`.

Exercised against a real loopback `http.server` instance (hand-rolled
here, not shared with `test_world_model_client.py`, per module
independence -- root `CLAUDE.md`), mirroring that file's own pattern: a
fake `POST /api/chat` double, not a mocked `urllib`.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from synth.ollama_client import (
    OllamaClient,
    OllamaOutputError,
    OllamaUnavailableError,
)

_HAPPY_MESSAGE_CONTENT = json.dumps({"purpose": "escort the convoy"})


def _make_handler() -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            request = json.loads(raw_body) if raw_body else {}
            model = request.get("model")

            if self.path != "/api/chat":
                self._respond(404, {"error": "not found"})
                return

            if model == "bad-envelope":
                payload = b"not json"
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if model == "bad-content":
                self._respond(200, {"message": {"content": "not json"}})
                return

            if model == "non-object-content":
                self._respond(200, {"message": {"content": json.dumps([1, 2])}})
                return

            if model == "missing-message":
                self._respond(200, {"done": True})
                return

            if model == "server-error":
                self._respond(500, {"error": "boom"})
                return

            self._respond(200, {"message": {"content": _HAPPY_MESSAGE_CONTENT}})

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


def test_chat_json_returns_parsed_message_content(server_url: str) -> None:
    client = OllamaClient(model="happy-model", base_url=server_url)

    result = client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})

    assert result == {"purpose": "escort the convoy"}


def test_chat_json_raises_unavailable_on_connection_failure() -> None:
    client = OllamaClient(
        model="whatever", base_url="http://127.0.0.1:1", timeout_s=0.5
    )

    with pytest.raises(OllamaUnavailableError):
        client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_chat_json_raises_output_error_on_malformed_envelope(server_url: str) -> None:
    client = OllamaClient(model="bad-envelope", base_url=server_url)

    with pytest.raises(OllamaOutputError):
        client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_chat_json_raises_output_error_on_malformed_content(server_url: str) -> None:
    client = OllamaClient(model="bad-content", base_url=server_url)

    with pytest.raises(OllamaOutputError):
        client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_chat_json_raises_output_error_on_non_object_content(server_url: str) -> None:
    client = OllamaClient(model="non-object-content", base_url=server_url)

    with pytest.raises(OllamaOutputError):
        client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_chat_json_raises_output_error_on_missing_message(server_url: str) -> None:
    client = OllamaClient(model="missing-message", base_url=server_url)

    with pytest.raises(OllamaOutputError):
        client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_chat_json_raises_output_error_on_http_error_status(server_url: str) -> None:
    client = OllamaClient(model="server-error", base_url=server_url)

    with pytest.raises(OllamaOutputError):
        client.chat_json([{"role": "user", "content": "hi"}], {"type": "object"})
