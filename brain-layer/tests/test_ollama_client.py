"""Tests for `ollama_client.OllamaClient` -- a small fake HTTP server
standing in for Ollama's own `/api/generate` (not a live Ollama daemon,
per `brain-layer/CLAUDE.md`'s "Testing" section), mirroring
`test_brain_client.py`'s own fake-server pattern in `body-layer`."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Self

import pytest

from ollama_client import OllamaClient, OllamaRequestError


class _FakeOllamaServer:
    """Records every `/api/generate` request body it receives and answers
    with a configurable, mutable `response` string."""

    def __init__(self) -> None:
        self.received: list[dict[str, object]] = []
        self.response_text = "ASK"
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        server_self = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/api/generate":
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length > 0 else b""
                server_self.received.append(json.loads(body))
                payload = json.dumps({"response": server_self.response_text}).encode(
                    "utf-8"
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        assert self._httpd is not None
        self._httpd.shutdown()
        self._httpd.server_close()
        assert self._thread is not None
        self._thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        assert self._httpd is not None
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"


@pytest.fixture
def fake_ollama() -> Iterator[_FakeOllamaServer]:
    with _FakeOllamaServer() as server:
        yield server


def test_generate_posts_model_prompt_and_options(
    fake_ollama: _FakeOllamaServer,
) -> None:
    fake_ollama.response_text = "PICK CONTACT_7 BECAUSE near the village"
    client = OllamaClient(base_url=fake_ollama.base_url)

    result = client.generate(
        model="test-model", prompt="pick one", num_ctx=2048, num_predict=40
    )

    assert result == "PICK CONTACT_7 BECAUSE near the village"
    assert len(fake_ollama.received) == 1
    request = fake_ollama.received[0]
    assert request["model"] == "test-model"
    assert request["prompt"] == "pick one"
    assert request["stream"] is False
    assert request["options"] == {"num_ctx": 2048, "num_predict": 40}


def test_generate_raises_on_unreachable_server() -> None:
    client = OllamaClient(base_url="http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(OllamaRequestError):
        client.generate(model="test-model", prompt="x", num_ctx=2048, num_predict=40)


def test_warm_up_sends_num_predict_one(fake_ollama: _FakeOllamaServer) -> None:
    client = OllamaClient(base_url=fake_ollama.base_url)
    client.warm_up(model="test-model", num_ctx=2048)
    assert len(fake_ollama.received) == 1
    assert fake_ollama.received[0]["options"] == {"num_ctx": 2048, "num_predict": 1}
