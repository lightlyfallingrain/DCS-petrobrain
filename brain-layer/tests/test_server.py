"""Tests for `server.BrainLayerServer` -- structurally a copy of
`audio-adapter/tests/test_server.py`'s real-loopback-server pattern.

The two tests most tied to the plan's own Stage 1 acceptance criteria are
`test_escalate_returns_202_immediately_even_with_a_slow_decider` (the POST
itself must never block, regardless of `Decider.decide`'s own latency) and
`test_superseded_job_reply_is_discarded_not_delivered` (D3's newest-wins,
proven end to end through the real HTTP surface rather than only at
`job.JobSlot`'s own unit level)."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from decider import StubDecider
from server import BrainLayerServer


@pytest.fixture
def running_server() -> Iterator[BrainLayerServer]:
    server = BrainLayerServer(StubDecider(), host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.close()
        thread.join(timeout=5)


def _post(server: BrainLayerServer, path: str, body: object) -> tuple[int, Any]:
    url = f"http://127.0.0.1:{server.port}{path}"
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _get(server: BrainLayerServer, path: str) -> tuple[int, Any]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_health_ok(running_server: BrainLayerServer) -> None:
    status, body = _get(running_server, "/health")
    assert status == 200
    assert body == {"ok": True}


def test_escalate_valid_returns_202(running_server: BrainLayerServer) -> None:
    status, body = _post(
        running_server,
        "/escalate",
        {"utterance_id": "U1", "t_sim": 100.0, "partial_parse": {}},
    )
    assert status == 202
    assert body == {"ok": True}


def test_escalate_missing_utterance_id_returns_400(
    running_server: BrainLayerServer,
) -> None:
    status, body = _post(running_server, "/escalate", {"partial_parse": {}})
    assert status == 400
    assert "error" in body


def test_replies_poll_drains_a_decided_reply() -> None:
    server = BrainLayerServer(StubDecider(delay_s=0.0), host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _post(
            server,
            "/escalate",
            {"utterance_id": "U1", "t_sim": 100.0, "partial_parse": {}},
        )
        # No model, no artificial delay -- the worker thread should have
        # already published by the time we poll, but retry briefly rather
        # than asserting on thread-scheduling timing directly.
        deadline = time.monotonic() + 2.0
        replies: list[dict[str, Any]] = []
        while time.monotonic() < deadline and not replies:
            _status, replies = _get(server, "/replies/poll")
            if not replies:
                time.sleep(0.01)
        assert len(replies) == 1
        assert replies[0]["utterance_id"] == "U1"
        assert replies[0]["kind"] == "unable"
        assert replies[0]["reason"] == "NO_SUCH_COMMAND"
    finally:
        server.close()
        thread.join(timeout=5)


def test_replies_poll_empty_when_nothing_decided(
    running_server: BrainLayerServer,
) -> None:
    status, body = _get(running_server, "/replies/poll")
    assert status == 200
    assert body == []


def test_escalate_returns_202_immediately_even_with_a_slow_decider() -> None:
    """The plan's own acceptance framing: 'with the stub at 8s, ... proven
    at the REPL without Ollama running.' Here it's proven over the real
    HTTP surface: the POST must return long before an 8s (stood in here by
    a shorter but still clearly-blocking delay) decider call finishes."""
    server = BrainLayerServer(StubDecider(delay_s=1.0), host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        start = time.monotonic()
        status, _body = _post(
            server,
            "/escalate",
            {"utterance_id": "U1", "t_sim": 100.0, "partial_parse": {}},
        )
        elapsed = time.monotonic() - start
        assert status == 202
        assert elapsed < 0.5  # well under the 1.0s decider delay
    finally:
        server.close()
        thread.join(timeout=5)


class _HangingDecider:
    """A `Decider` that never returns -- stands in for a wedged Ollama
    daemon (`plans/brain-layer/performance-review.md`'s second finding)
    without an actual model dependency. `time.sleep` rather than a real
    blocking network call, but the effect on `_run_job` is identical:
    `decide()` simply never comes back on its own."""

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        time.sleep(100.0)
        return {"kind": "ask"}  # pragma: no cover -- never reached


def test_decider_timeout_drops_the_job_without_blocking_new_escalations() -> None:
    """The pre-Stage-2 prerequisite this bounds: a `Decider.decide()` call
    that never returns must not leak an unbounded per-utterance wait.
    `decide_timeout_s` is set far below the decider's own (simulated)
    hang, so the job is dropped (no reply ever reaches `/replies/poll`)
    and, critically, a *later* escalation is still handled promptly --
    proving the timed-out worker's own daemon thread actually returned
    rather than piling up behind the hang."""
    server = BrainLayerServer(
        _HangingDecider(), host="127.0.0.1", port=0, decide_timeout_s=0.2
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _body = _post(
            server,
            "/escalate",
            {"utterance_id": "U1", "t_sim": 100.0, "partial_parse": {}},
        )
        assert status == 202

        time.sleep(0.6)  # well past decide_timeout_s
        _status, replies = _get(server, "/replies/poll")
        assert replies == []  # dropped, never published

        # A second escalation, posted after the first has already timed
        # out, must still be accepted promptly.
        start = time.monotonic()
        status2, _body2 = _post(
            server,
            "/escalate",
            {"utterance_id": "U2", "t_sim": 101.0, "partial_parse": {}},
        )
        elapsed = time.monotonic() - start
        assert status2 == 202
        assert elapsed < 0.5
    finally:
        server.close()
        thread.join(timeout=5)


def test_superseded_job_reply_is_discarded_not_delivered() -> None:
    """D3: 'the abandoned job's reply is discarded ... when it lands.'
    U1's decider call is still sleeping when U2 supersedes it; once both
    finish, only U2's reply should ever reach /replies/poll."""
    server = BrainLayerServer(StubDecider(delay_s=0.2), host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _post(
            server,
            "/escalate",
            {"utterance_id": "U1", "t_sim": 100.0, "partial_parse": {}},
        )
        _post(
            server,
            "/escalate",
            {"utterance_id": "U2", "t_sim": 100.1, "partial_parse": {}},
        )
        time.sleep(0.6)  # both StubDecider calls have long since finished
        _status, replies = _get(server, "/replies/poll")
        utterance_ids = [reply["utterance_id"] for reply in replies]
        assert utterance_ids == ["U2"]
    finally:
        server.close()
        thread.join(timeout=5)
