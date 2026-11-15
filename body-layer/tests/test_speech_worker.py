"""Tests for `belief.speech_worker.SpeechWorker` (`[[BL-B106]]`,
`plans/async-speech/plan.md`). Exercises the class directly against a
fake `SpeechClient` double (and, for the non-blocking-enqueue test, a
real `AudioAdapterClient` against a genuinely wedged socket) -- never
through `CrewConsole`, which has its own tests in `test_crew_console.py`
for the wiring (worker-vs-fallback split, `drain_speech_results`,
`reset_for_new_mission`/`stop_talking` routing)."""

from __future__ import annotations

import itertools
import logging
import socket
import threading
import time
from collections.abc import Callable
from typing import Self

import pytest

from belief.audio_client import AudioAdapterClient, AudioAdapterError
from belief.speech_worker import SpeechWorker, _SpeechResult
from connection_reporter import ConnectionReporter


class _FakeSpeechClient:
    """Records every `push_speech` call (text, urgent, correlation_id)
    plus its own wall-clock start/end, so tests can assert both call
    order and non-overlap. `fail_on` names texts whose `push_speech`
    raises `AudioAdapterError` instead of recording a success.

    `blocker`, when given, makes the *first* `push_speech` call wait on
    it before doing anything else -- the one hook every test below that
    needs "the worker is busy with an earlier item" uses to get there
    deterministically, without a real sleep/wedge."""

    def __init__(
        self,
        fail_on: frozenset[str] = frozenset(),
        blocker: threading.Event | None = None,
    ) -> None:
        self.calls: list[tuple[str, bool, str | None]] = []
        self.intervals: list[tuple[float, float]] = []
        self.stop_calls = 0
        self._fail_on = fail_on
        self._blocker = blocker
        self._blocked_once = False
        self._lock = threading.Lock()

    def push_speech(
        self, text: str, urgent: bool, correlation_id: str | None = None
    ) -> None:
        if self._blocker is not None and not self._blocked_once:
            self._blocked_once = True
            self._blocker.wait()
        start = time.monotonic()
        with self._lock:
            self.calls.append((text, urgent, correlation_id))
        try:
            if text in self._fail_on:
                raise AudioAdapterError("simulated push failure")
        finally:
            with self._lock:
                self.intervals.append((start, time.monotonic()))

    def stop(self) -> None:
        self.stop_calls += 1


def _wait_until(predicate: Callable[[], bool], timeout_s: float = 2.0) -> None:
    """Polls `predicate()` until it is truthy or `timeout_s` elapses --
    used instead of a fixed `sleep` wherever a test needs to wait for the
    background worker thread to catch up."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met within timeout")


def _drain_until_nonempty(
    worker: SpeechWorker, timeout_s: float = 2.0
) -> list[_SpeechResult]:
    """Polls `worker.drain_results()` until it returns something, then
    returns that batch. Each poll both checks and consumes, so a result
    landing between two polls is never missed."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        drained = worker.drain_results()
        if drained:
            return drained
        time.sleep(0.01)
    raise AssertionError("no result drained within timeout")


# -- enqueue / order / serialization -----------------------------------


def test_enqueue_preserves_order() -> None:
    client = _FakeSpeechClient()
    worker = SpeechWorker(client)
    worker.open()
    try:
        for i in range(5):
            worker.enqueue(f"line {i}", False, None, None)
        _wait_until(lambda: len(client.calls) == 5)
    finally:
        worker.close()
    assert [text for text, _, _ in client.calls] == [f"line {i}" for i in range(5)]


def test_pushes_never_overlap_in_wall_time() -> None:
    client = _FakeSpeechClient()
    worker = SpeechWorker(client)
    worker.open()
    try:
        for i in range(8):
            worker.enqueue(f"line {i}", False, None, None)
        _wait_until(lambda: len(client.intervals) == 8)
    finally:
        worker.close()
    intervals = sorted(client.intervals)
    for (_, end), (next_start, _) in itertools.pairwise(intervals):
        assert next_start >= end, "two pushes overlapped in wall time"


def test_drain_results_returns_real_timings_then_empties() -> None:
    client = _FakeSpeechClient()
    worker = SpeechWorker(client)
    worker.open()
    try:
        worker.enqueue("hello", False, "corr-1", {"attack_run_tier": 1})
        results = _drain_until_nonempty(worker)
    finally:
        worker.close()
    assert len(results) == 1
    result = results[0]
    assert result.line == "hello"
    assert result.bypass_gate is False
    assert result.correlation_id == "corr-1"
    assert result.attack_run_fields == {"attack_run_tier": 1}
    assert result.push_duration_s is not None and result.push_duration_s >= 0.0
    assert result.push_acked_wall >= result.push_sent_wall
    # A second drain with nothing new returns empty.
    assert worker.drain_results() == []


def test_drain_results_records_a_failed_push_too() -> None:
    client = _FakeSpeechClient(fail_on=frozenset({"bad line"}))
    reporter = ConnectionReporter(logging.getLogger("test"), label="test")
    worker = SpeechWorker(client, reporter=reporter)
    worker.open()
    try:
        worker.enqueue("bad line", False, None, None)
        results = _drain_until_nonempty(worker)
    finally:
        worker.close()
    assert len(results) == 1
    assert results[0].line == "bad line"
    # A failed push still gets a real (non-None) duration -- matches
    # `CrewConsole._print`'s own fallback-path semantics, see
    # `_SpeechResult`'s own docstring.
    assert results[0].push_duration_s is not None


# -- overflow (mirrors BL-B87's one-time-warned shape) -------------------


def test_overflow_drops_oldest_with_exactly_one_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    blocker = threading.Event()
    client = _FakeSpeechClient(blocker=blocker)
    worker = SpeechWorker(client)
    worker.open()
    try:
        # The worker picks this one up immediately and blocks on it,
        # so every subsequent enqueue below piles up in the queue
        # (never dequeued) until we release `blocker`.
        worker.enqueue("item 0 (blocks the worker)", False, None, None)
        _wait_until(lambda: client._blocked_once)

        total_routine = 64 + 5  # exceed the cap (64) by 5
        with caplog.at_level("WARNING"):
            for i in range(1, total_routine + 1):
                worker.enqueue(f"item {i}", False, None, None)
    finally:
        blocker.set()
        worker.close()

    overflow_warnings = [
        r for r in caplog.records if "speech worker queue full" in r.message
    ]
    assert len(overflow_warnings) == 1


# -- urgent interrupt ------------------------------------------------------


def test_urgent_enqueue_clears_queue_and_calls_stop() -> None:
    blocker = threading.Event()
    client = _FakeSpeechClient(blocker=blocker)
    worker = SpeechWorker(client)
    worker.open()
    try:
        worker.enqueue("item 0 (blocks the worker)", False, None, None)
        _wait_until(lambda: client._blocked_once)

        # These pile up behind the blocked worker, never dequeued yet.
        worker.enqueue("routine A", False, None, None)
        worker.enqueue("routine B", False, None, None)

        worker.enqueue("urgent line", True, None, None)
        assert client.stop_calls == 1

        blocker.set()
        _wait_until(lambda: len(client.calls) == 2)
    finally:
        worker.close()

    texts = [text for text, _, _ in client.calls]
    # Item 0 (already dequeued before the urgent push) still plays out;
    # "routine A"/"routine B" were dropped by the interrupt, so the
    # urgent line speaks immediately after.
    assert texts == ["item 0 (blocks the worker)", "urgent line"]


def test_interrupt_directly_clears_queue_and_calls_stop() -> None:
    """Calling `interrupt()` directly (not via an urgent `enqueue`) --
    the shape `_handle_stop_talking` uses -- must drop whatever is
    queued and call `client.stop()`, deterministically: a routine line
    queued behind a blocked item must never play once `interrupt()` has
    run."""
    blocker = threading.Event()
    client = _FakeSpeechClient(blocker=blocker)
    worker = SpeechWorker(client)
    worker.open()
    try:
        worker.enqueue("item 0 (blocks the worker)", False, None, None)
        _wait_until(lambda: client._blocked_once)
        worker.enqueue("will be cleared", False, None, None)

        worker.interrupt()
        assert client.stop_calls == 1

        blocker.set()
        _wait_until(lambda: len(client.calls) == 1)
        time.sleep(0.05)  # nothing more should arrive after this
    finally:
        worker.close()
    assert [text for text, _, _ in client.calls] == ["item 0 (blocks the worker)"]


def test_interrupt_is_a_safe_no_op_when_client_stop_raises() -> None:
    class _RaisingStopClient(_FakeSpeechClient):
        def stop(self) -> None:
            raise RuntimeError("simulated stop failure")

    worker = SpeechWorker(_RaisingStopClient())
    worker.open()
    try:
        worker.interrupt()  # must not raise
    finally:
        worker.close()


# -- lifecycle --------------------------------------------------------------


def test_close_joins_the_worker_thread_cleanly() -> None:
    worker = SpeechWorker(_FakeSpeechClient())
    worker.open()
    worker.close()
    assert worker._worker is None


def test_reporter_is_told_about_push_failure_and_success() -> None:
    """The connection-reporter calls `_print` used to make directly
    (BL-B96 Stage 4) now happen on the worker thread instead -- see
    `_process`'s own call sites. By the time a result is drained, the
    reporter transition it caused has already happened on the same
    thread (sequential within `_process`), so draining is a safe
    synchronization point for this assertion."""
    client = _FakeSpeechClient(fail_on=frozenset({"bad"}))
    reporter = ConnectionReporter(logging.getLogger("test"), label="test")
    worker = SpeechWorker(client, reporter=reporter)
    worker.open()
    try:
        worker.enqueue("bad", False, None, None)
        _drain_until_nonempty(worker)
        assert reporter._connected is False
        worker.enqueue("good", False, None, None)
        _drain_until_nonempty(worker)
        assert reporter._connected is True
    finally:
        worker.close()


# -- non-blocking enqueue under a wedged client (mirrors the --------------
# performance-reviewer's own measured technique for BrainLayerClient,
# `test_drain_brain_tick_rate_unaffected_by_a_wedged_brain`) --------------


class _WedgedSpeechServer:
    """A TCP listener that accepts every connection and never answers it
    -- a genuinely wedged `audio-adapter`, not merely a slow one. Own
    local copy of `test_crew_console.py`'s `_WedgedBrainServer` (test
    files in this project are self-contained, no shared `conftest.py`
    helper for this yet): raw `socket`, not `http.server`, so nothing
    can accidentally answer the request."""

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
            self._accepted.append(conn)  # kept open, never read or written

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


def test_enqueue_never_blocks_caller_even_with_a_wedged_client() -> None:
    """The actual acceptance criterion end to end: `enqueue()` -- what
    `CrewConsole._print` calls -- must return in microseconds regardless
    of how long the real `push_speech` HTTP call is taking on the
    worker's own background thread."""
    with _WedgedSpeechServer() as server:
        client = AudioAdapterClient(base_url=server.base_url, timeout_s=1.5)
        worker = SpeechWorker(client)
        worker.open()
        try:
            # The worker thread picks this up and blocks for up to
            # `timeout_s` against the wedged server.
            worker.enqueue("first line (will wedge)", False, None, None)

            start = time.monotonic()
            for i in range(20):
                worker.enqueue(f"line {i}", False, None, None)
            elapsed = time.monotonic() - start

            # 21 enqueues while the worker is stuck on the first one,
            # well under the 1.5s per-call timeout -- `enqueue()` only
            # ever does a bounded `queue.put_nowait`, never touching the
            # network itself.
            assert elapsed < 1.0
        finally:
            worker.close()


def test_interrupt_wall_time_is_bounded_well_under_push_speechs_timeout_against_a_wedged_client() -> (
    None
):
    """`[[BL-B106]]` performance-review NOW finding
    (`plans/async-speech/performance-review.md`): `interrupt()` calls
    `client.stop()` synchronously, on whichever thread calls it
    (`SpeechWorker.interrupt`'s own docstring) -- reached from the poll
    thread itself via `stop_talking`/mission-restart detection, not just
    from a background worker. Before the fix, `stop()` shared `push_
    speech`'s 5.0s `_DEFAULT_TIMEOUT_S`, so a wedged (not merely down)
    audio-adapter stalled the poll thread for the full 5s on `interrupt()`.
    `AudioAdapterClient.stop_timeout_s` now bounds `/stop` separately and
    short -- this measures `interrupt()`'s real wall time against the
    same genuinely-wedged-socket technique as the enqueue test above, and
    asserts it stays well under `push_speech`'s own 5.0s default, not
    merely under some arbitrary larger number."""
    with _WedgedSpeechServer() as server:
        client = AudioAdapterClient(base_url=server.base_url)
        worker = SpeechWorker(client)
        worker.open()
        try:
            start = time.monotonic()
            worker.interrupt()
            elapsed = time.monotonic() - start

            # Well under push_speech's 5.0s default timeout -- the whole
            # point of giving `/stop` its own short, dedicated bound.
            assert elapsed < 2.0
        finally:
            worker.close()
