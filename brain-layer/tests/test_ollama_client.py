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

from ollama_client import (
    ChatResult,
    OllamaClient,
    OllamaRequestError,
    OllamaUsage,
    ToolCall,
)


class _FakeOllamaServer:
    """Records every `/api/generate` and `/api/chat` request body it
    receives and answers with a configurable, mutable `response`
    string (`/api/generate`) or `chat_message` dict (`/api/chat`)."""

    def __init__(self) -> None:
        self.received: list[dict[str, object]] = []
        self.response_text = "ASK"
        self.chat_message: dict[str, object] = {"content": "ASK", "tool_calls": []}
        self.usage: dict[str, object] = {"prompt_eval_count": 10, "eval_count": 2}
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        server_self = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path not in ("/api/generate", "/api/chat"):
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length > 0 else b""
                server_self.received.append(json.loads(body))
                if self.path == "/api/generate":
                    reply: dict[str, object] = {"response": server_self.response_text}
                else:
                    reply = {"message": server_self.chat_message}
                reply.update(server_self.usage)
                payload = json.dumps(reply).encode("utf-8")
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


# --- generate_with_usage (brain-tool-calls Stage 0) -------------------


def test_generate_with_usage_returns_text_and_token_counts(
    fake_ollama: _FakeOllamaServer,
) -> None:
    fake_ollama.response_text = "ASK"
    fake_ollama.usage = {"prompt_eval_count": 155, "eval_count": 6}
    client = OllamaClient(base_url=fake_ollama.base_url)

    text, usage = client.generate_with_usage(
        model="test-model", prompt="pick one", num_ctx=2048, num_predict=40
    )

    assert text == "ASK"
    assert usage == OllamaUsage(prompt_tokens=155, eval_tokens=6)


def test_generate_with_usage_defaults_to_zero_when_counts_absent(
    fake_ollama: _FakeOllamaServer,
) -> None:
    fake_ollama.usage = {}
    client = OllamaClient(base_url=fake_ollama.base_url)

    _text, usage = client.generate_with_usage(
        model="test-model", prompt="pick one", num_ctx=2048, num_predict=40
    )

    assert usage == OllamaUsage(prompt_tokens=0, eval_tokens=0)


def test_generate_unchanged_by_the_usage_refactor(
    fake_ollama: _FakeOllamaServer,
) -> None:
    """`generate()` itself keeps its original two-line contract (text
    only) -- the refactor that added `generate_with_usage` must not
    change what `decider.OllamaDecider` already depends on."""
    fake_ollama.response_text = "PICK CONTACT_7 BECAUSE near the village"
    client = OllamaClient(base_url=fake_ollama.base_url)

    result = client.generate(
        model="test-model", prompt="pick one", num_ctx=2048, num_predict=40
    )

    assert result == "PICK CONTACT_7 BECAUSE near the village"


# --- chat (brain-tool-calls Stage 0, native tool-call form) ------------


def test_chat_posts_messages_and_tools_and_parses_tool_calls(
    fake_ollama: _FakeOllamaServer,
) -> None:
    fake_ollama.chat_message = {
        "content": "",
        "tool_calls": [
            {"function": {"name": "find_contact", "arguments": {"text": "shilka"}}}
        ],
    }
    fake_ollama.usage = {"prompt_eval_count": 200, "eval_count": 15}
    client = OllamaClient(base_url=fake_ollama.base_url)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "find it"},
    ]
    tools = [
        {"type": "function", "function": {"name": "find_contact", "parameters": {}}}
    ]

    result = client.chat(
        model="test-model",
        messages=messages,
        tools=tools,
        num_ctx=4096,
        num_predict=200,
    )

    assert result == ChatResult(
        content="",
        tool_calls=(ToolCall(name="find_contact", arguments={"text": "shilka"}),),
        usage=OllamaUsage(prompt_tokens=200, eval_tokens=15),
    )
    request = fake_ollama.received[0]
    assert request["model"] == "test-model"
    assert request["messages"] == messages
    assert request["tools"] == tools
    assert request["options"] == {"num_ctx": 4096, "num_predict": 200}


def test_chat_with_no_tool_call_returns_final_content(
    fake_ollama: _FakeOllamaServer,
) -> None:
    fake_ollama.chat_message = {
        "content": "FINAL unable CANNOT_ANSWER",
        "tool_calls": [],
    }
    client = OllamaClient(base_url=fake_ollama.base_url)

    result = client.chat(
        model="test-model", messages=[], tools=[], num_ctx=2048, num_predict=200
    )

    assert result.content == "FINAL unable CANNOT_ANSWER"
    assert result.tool_calls == ()


def test_chat_raises_on_malformed_tool_call(fake_ollama: _FakeOllamaServer) -> None:
    fake_ollama.chat_message = {
        "content": "",
        "tool_calls": [{"function": {"name": "find_contact"}}],  # missing "arguments"
    }
    client = OllamaClient(base_url=fake_ollama.base_url)

    with pytest.raises(OllamaRequestError):
        client.chat(
            model="test-model", messages=[], tools=[], num_ctx=2048, num_predict=200
        )


def test_chat_raises_on_missing_message_content(fake_ollama: _FakeOllamaServer) -> None:
    fake_ollama.chat_message = {"tool_calls": []}  # no "content" at all
    client = OllamaClient(base_url=fake_ollama.base_url)

    with pytest.raises(OllamaRequestError):
        client.chat(
            model="test-model", messages=[], tools=[], num_ctx=2048, num_predict=200
        )


def test_chat_raises_on_unreachable_server() -> None:
    client = OllamaClient(base_url="http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(OllamaRequestError):
        client.chat(
            model="test-model", messages=[], tools=[], num_ctx=2048, num_predict=200
        )
