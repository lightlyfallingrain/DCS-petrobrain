"""Tests for `belief.brain_client.BrainLayerClient` -- `plans/brain-layer/
plan.md` D2's non-blocking HTTP client.

Uses a small fake HTTP server built directly on `http.server` (not an
import of `brain-layer/`'s own `server.py` -- module independence, the
seam is HTTP/JSON only) so `handle()`'s non-blocking guarantee and
`poll_replies()`'s wire parsing are proven against a real loopback socket,
mirroring `tests/test_aircraft_client.py`'s existing pattern for this
project's other HTTP clients."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Self

import pytest

from belief.brain_client import BrainLayerClient, BrainLayerError
from belief.escalation import EscalationPayload
from belief.utterance import PartialParse, ReferenceCandidate


class _FakeBrainServer:
    """A minimal stand-in for `brain-layer/src/server.py`'s `POST
    /escalate` / `GET /replies/poll` -- records every escalate body it
    receives, sleeps `escalate_delay_s` before responding to `/escalate`
    (to prove `handle()` does not wait on it), and serves a
    configurable, mutable `replies` list from `/replies/poll`."""

    def __init__(self, escalate_delay_s: float = 0.0) -> None:
        self.escalate_delay_s = escalate_delay_s
        self.received: list[dict[str, object]] = []
        self.replies: list[dict[str, object]] = []
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        server_self = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/escalate":
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length > 0 else b""
                server_self.received.append(json.loads(body))
                if server_self.escalate_delay_s > 0:
                    time.sleep(server_self.escalate_delay_s)
                payload = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:
                if self.path != "/replies/poll":
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = json.dumps(server_self.replies).encode("utf-8")
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
def fake_server() -> Iterator[_FakeBrainServer]:
    with _FakeBrainServer() as server:
        yield server


def _payload(utterance_id: str = "U1") -> EscalationPayload:
    return EscalationPayload(
        utterance_id=utterance_id,
        transcript="watch that bmp",
        transcript_confidence=1.0,
        t_sim=100.0,
        partial_parse=PartialParse(
            matched_intent="set_attention",
            confidence=0.5,
            disposition="escalated",
            reason_escalated="ambiguous_reference",
            attention_level="watch",
            referenced_contact_candidates=(
                ReferenceCandidate(id="CONTACT_1", why="a T-72, near Gemerek"),
                ReferenceCandidate(id="CONTACT_2", why="a T-72, on the road"),
            ),
        ),
        situational_header={"contact_counts": 2, "estimated_units": 2},
    )


def test_handle_posts_the_payload(fake_server: _FakeBrainServer) -> None:
    client = BrainLayerClient(base_url=fake_server.base_url)
    client.handle(_payload())

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not fake_server.received:
        time.sleep(0.01)

    assert len(fake_server.received) == 1
    posted = fake_server.received[0]
    assert posted["utterance_id"] == "U1"
    assert posted["transcript"] == "watch that bmp"
    candidates = posted["partial_parse"]["referenced_contact_candidates"]  # type: ignore[index]
    assert candidates == [
        {"id": "CONTACT_1", "why": "a T-72, near Gemerek"},
        {"id": "CONTACT_2", "why": "a T-72, on the road"},
    ]


def test_handle_returns_immediately_even_when_the_server_is_slow() -> None:
    """D2's core guarantee, proven at the client level: `handle()` never
    waits on the network, however long the server takes to respond."""
    with _FakeBrainServer(escalate_delay_s=1.0) as server:
        client = BrainLayerClient(base_url=server.base_url)
        start = time.monotonic()
        client.handle(_payload())
        elapsed = time.monotonic() - start
        assert elapsed < 0.2


def test_handle_never_raises_when_the_server_is_unreachable() -> None:
    client = BrainLayerClient(base_url="http://127.0.0.1:1")  # nothing listening
    client.handle(_payload())  # must not raise
    # Give the background worker a moment to actually attempt (and fail)
    # the POST, so this test exercises the failure path, not just the
    # hand-off.
    time.sleep(0.2)


def test_poll_replies_parses_a_valid_reply(fake_server: _FakeBrainServer) -> None:
    fake_server.replies = [
        {
            "utterance_id": "U1",
            "kind": "pick",
            "t_sim": 100.0,
            "contact_id": "CONTACT_1",
            "because": "near Gemerek",
        }
    ]
    client = BrainLayerClient(base_url=fake_server.base_url)

    replies = client.poll_replies()

    assert len(replies) == 1
    assert replies[0].utterance_id == "U1"
    assert replies[0].kind == "pick"
    assert replies[0].contact_id == "CONTACT_1"
    assert replies[0].because == "near Gemerek"


def test_poll_replies_empty_when_nothing_pending(fake_server: _FakeBrainServer) -> None:
    assert fake_server.replies == []
    client = BrainLayerClient(base_url=fake_server.base_url)
    assert client.poll_replies() == []


def test_poll_replies_skips_malformed_items(fake_server: _FakeBrainServer) -> None:
    fake_server.replies = [
        {"utterance_id": "U1", "kind": "unable", "reason": "NO_MATCH"},
        {"kind": "unable"},  # missing utterance_id
        {"utterance_id": "U2", "kind": "not_a_real_kind"},
        "not even a dict",  # type: ignore[list-item]
    ]
    client = BrainLayerClient(base_url=fake_server.base_url)

    replies = client.poll_replies()

    assert len(replies) == 1
    assert replies[0].utterance_id == "U1"


def test_poll_replies_raises_on_unreachable_server() -> None:
    client = BrainLayerClient(base_url="http://127.0.0.1:1")
    with pytest.raises(BrainLayerError):
        client.poll_replies()


def test_awaiting_reply_id_is_none_in_stage_1(fake_server: _FakeBrainServer) -> None:
    client = BrainLayerClient(base_url=fake_server.base_url)
    assert client.awaiting_reply_id() is None
