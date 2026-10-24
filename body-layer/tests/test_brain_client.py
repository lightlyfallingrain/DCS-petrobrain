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
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Self

import pytest

from belief.brain_client import BrainLayerClient
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


class _WedgedServer:
    """A TCP listener that accepts every connection and then never reads
    from or writes to it -- the "up but wedged" case
    `plans/brain-layer/performance-review.md` actually measured (5015ms
    per `poll_replies()` call, every call, no backoff), as opposed to a
    refused connection (nothing listening, fails fast) or a healthy 404.
    Built on raw `socket` rather than `http.server` so no HTTP-level
    machinery can accidentally answer the request."""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._accepted: list[socket.socket] = []

    def __enter__(self) -> Self:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self._sock.settimeout(0.2)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        return self

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            # Accepted and kept open -- deliberately never read from or
            # written to, so the client's request sits waiting forever.
            self._accepted.append(conn)

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        assert self._thread is not None
        self._thread.join(timeout=2)
        for conn in self._accepted:
            conn.close()
        assert self._sock is not None
        self._sock.close()

    @property
    def base_url(self) -> str:
        assert self._sock is not None
        port = self._sock.getsockname()[1]
        return f"http://127.0.0.1:{port}"


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


def _poll_until(client: BrainLayerClient, deadline_s: float = 2.0) -> list[object]:
    """Repeatedly calls `poll_replies()` (each call is instant and never
    blocks, per its own docstring) until it returns something non-empty
    or `deadline_s` elapses -- the background poll thread needs at least
    one `_POLL_LOOP_INTERVAL_S`-scale iteration to have actually reached
    the fake server, mirroring `test_handle_posts_the_payload`'s own
    wait-loop pattern for `handle()`'s background worker."""
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        replies = client.poll_replies()
        if replies:
            return list(replies)
        time.sleep(0.01)
    return []


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

    replies = _poll_until(client)

    assert len(replies) == 1
    assert replies[0].utterance_id == "U1"
    assert replies[0].kind == "pick"
    assert replies[0].contact_id == "CONTACT_1"
    assert replies[0].because == "near Gemerek"


def test_poll_replies_empty_when_nothing_pending(fake_server: _FakeBrainServer) -> None:
    assert fake_server.replies == []
    client = BrainLayerClient(base_url=fake_server.base_url)
    assert client.poll_replies() == []
    # Give the background worker a moment to actually poll the (empty)
    # server, so this exercises the real round trip, not just the
    # immediate-return guarantee.
    time.sleep(0.1)
    assert client.poll_replies() == []


def test_poll_replies_skips_malformed_items(fake_server: _FakeBrainServer) -> None:
    fake_server.replies = [
        {"utterance_id": "U1", "kind": "unable", "reason": "NO_MATCH"},
        {"kind": "unable"},  # missing utterance_id
        {"utterance_id": "U2", "kind": "not_a_real_kind"},
        "not even a dict",  # type: ignore[list-item]
    ]
    client = BrainLayerClient(base_url=fake_server.base_url)

    replies = _poll_until(client)

    assert len(replies) == 1
    assert replies[0].utterance_id == "U1"  # type: ignore[attr-defined]


def test_poll_replies_never_blocks_or_raises_when_the_server_is_unreachable() -> None:
    """The Stage 2 prerequisite this client exists to satisfy
    (`plans/brain-layer/performance-review.md`, user direction 2026-09-25:
    "brain must not block any other functionality") -- `poll_replies()`
    must return immediately and never raise, however unreachable the far
    side is, since it is called every tick from the shared crew-text poll
    thread."""
    client = BrainLayerClient(base_url="http://127.0.0.1:1")  # nothing listening
    start = time.monotonic()
    replies = client.poll_replies()
    elapsed = time.monotonic() - start
    assert replies == []
    assert elapsed < 0.2


def test_unreachable_brain_logs_one_line_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Connection refused is an expected state (brain-layer not started
    yet), so the retry warning carries no traceback -- one spewed every
    `_POLL_RETRY_BACKOFF_S` buried everything else in the terminal.

    Filters `caplog.records` down to **this client's own poll-worker
    thread** (`BL-B92`) -- `caplog.at_level(level, logger=name)` only
    scopes the *level* of the named logger, not which records land in
    `caplog.records`. Any other `BrainLayerClient` pointed at an
    unreachable or malformed-reply server elsewhere in this suite leaves
    its own `_poll_loop` daemon thread running forever (nothing stops a
    `daemon=True` thread -- see `_run_plain_logger_main_for_n_polls`'s
    docstring in `tests/test_body.py`), retrying on its own clock and
    logging via the *same* `belief.brain_client` logger name -- so an
    unfiltered `caplog.records[0]` can be a stray record from a
    completely different, already-leaked client instance (one whose
    failure carries a traceback, e.g. `test_invalid_reply_still_logs_a_
    traceback`'s), not this test's own connection-refused one. Logger
    name alone cannot discriminate between two instances of the same
    client class, unlike `BL-B92`'s fix on `test_body.py`'s
    `_ConnectionReporter` tests (one logger, one call site) -- thread
    identity can.

    The connection-refused condition itself is injected, not produced by
    a real bound-but-unlistened socket: on at least one host this test
    has run on, `connect()` against such a socket does not refuse
    instantly -- it blocks for this client's whole 5.0s `poll_timeout_s`,
    past the 2.0s deadline below, which previously made this test fail
    *always* on that host rather than flake. Monkeypatching
    `urllib.request.urlopen` (the one call site `_poll_once` makes,
    `belief/brain_client.py`) to raise the same `URLError`-wrapping-
    `OSError` shape a real refused connection produces reproduces
    `_poll_loop`'s `exc_info=not isinstance(exc.__cause__, (URLError,
    OSError))` split exactly, deterministically, on every host."""

    def _refused(url: str, timeout: float = 0.0) -> object:
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    monkeypatch.setattr(urllib.request, "urlopen", _refused)
    with caplog.at_level("WARNING", logger="belief.brain_client"):
        client = BrainLayerClient(
            base_url="http://127.0.0.1:1"
        )  # never dialled; urlopen is faked
        client.poll_replies()
        worker = client._poll_worker
        assert worker is not None, "poll_replies() must start the worker synchronously"
        own_records = [r for r in caplog.records if r.thread == worker.ident]
        deadline = time.monotonic() + 2.0
        while not own_records and time.monotonic() < deadline:
            time.sleep(0.01)
            own_records = [r for r in caplog.records if r.thread == worker.ident]
    assert own_records
    record = own_records[0]
    assert record.getMessage() == "background brain reply poll failed (retrying)"
    assert not record.exc_info


def test_invalid_reply_still_logs_a_traceback(
    fake_server: _FakeBrainServer, caplog: pytest.LogCaptureFixture
) -> None:
    """Not a connection loss -- a defect on one side or the other -- so
    the traceback stays."""
    fake_server.replies = {"not": "a list"}  # type: ignore[assignment]
    with caplog.at_level("WARNING", logger="belief.brain_client"):
        BrainLayerClient(base_url=fake_server.base_url).poll_replies()
        deadline = time.monotonic() + 2.0
        while not caplog.records and time.monotonic() < deadline:
            time.sleep(0.01)
    assert caplog.records
    assert caplog.records[0].exc_info is not None


def test_poll_replies_tick_rate_unaffected_by_a_wedged_server() -> None:
    """The exact failure mode the performance review measured: a
    TCP-accepted server that never answers `/replies/poll` used to cost
    `poll_timeout_s` (5s) on *every single call* on whatever thread called
    it. Proves many consecutive `poll_replies()` calls stay fast even
    while the background thread's own in-flight round trip is stuck
    inside that wedge."""
    with _WedgedServer() as server:
        client = BrainLayerClient(base_url=server.base_url, poll_timeout_s=5.0)
        start = time.monotonic()
        for _ in range(20):
            replies = client.poll_replies()
            assert replies == []
        elapsed = time.monotonic() - start
        # 20 calls at well under the per-call 5s wedge timeout -- each
        # `poll_replies()` call only ever drains a local buffer, it never
        # itself performs the network round trip.
        assert elapsed < 1.0


def test_awaiting_reply_id_is_none_in_stage_1(fake_server: _FakeBrainServer) -> None:
    client = BrainLayerClient(base_url=fake_server.base_url)
    assert client.awaiting_reply_id() is None
