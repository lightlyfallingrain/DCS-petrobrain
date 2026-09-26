"""Tests for `collector.server.CollectorServer.serve_forever`'s `accept()`
guard (2026-09-26 security review, "no supervision/restart for the
collector's four background daemon threads" -- the `accept()` half of that
finding).

Before this guard, an `OSError` from `accept()` itself (as opposed to from
a connection already in hand, which `_handle_connection` already caught)
was unguarded: it would end `serve_forever`'s loop silently, killing
Export.lua ingestion for the rest of the sortie with no cockpit-visible
symptom. These tests inject that failure directly -- no live trigger for it
has ever been observed -- to confirm the loop now (a) logs it loudly enough
to show up in a default, non-`--debug` run, and (b) keeps accepting
connections afterward rather than dying.
"""

from __future__ import annotations

import logging
import socket
import threading
import time

import pytest

import collector.server as server_module
from collector.cache import (
    PetrovichIndicationCache,
    PetrovichWheelCache,
    PttCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer


class _FlakyAcceptSocket:
    """Stands in for `CollectorServer`'s real listening socket. `accept()`
    replays a fixed script of results in order -- an `OSError` to simulate
    an unexpected failure, then a real `(conn, addr)` pair (from a
    `socket.socketpair()`) to prove the loop is still alive afterward. Once
    the script is exhausted, `accept()` blocks until `trigger_shutdown()` is
    called (from the test, after it has swapped the server's `_socket` back
    to `None` to simulate `close()` having already run), then raises
    `OSError` -- deterministically exercising the intended-shutdown path
    rather than racing a real script-exhaustion error against the test's
    own cleanup."""

    def __init__(
        self, script: list[BaseException | tuple[socket.socket, tuple[str, int]]]
    ) -> None:
        self._script = list(script)
        self._shutdown = threading.Event()

    def accept(self) -> tuple[socket.socket, tuple[str, int]]:
        if self._script:
            result = self._script.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        self._shutdown.wait()
        raise OSError("simulated listening socket closed")

    def trigger_shutdown(self) -> None:
        self._shutdown.set()


def test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Shrink the retry backoff so the test doesn't wait a full second.
    monkeypatch.setattr(server_module, "_ACCEPT_ERROR_BACKOFF_S", 0.05)

    ptt_cache = PttCache()
    server = CollectorServer(
        TelemetryCache(),
        WorldObjectsCache(),
        PetrovichIndicationCache(),
        PetrovichWheelCache(),
        ptt_cache=ptt_cache,
    )
    server.open()

    client_sock, server_conn = socket.socketpair()
    fake = _FlakyAcceptSocket(
        [OSError("simulated accept() failure"), (server_conn, ("127.0.0.1", 12345))]
    )
    # Swap in the fake socket after open() has already bound the real one --
    # this test only exercises serve_forever's own accept()-handling logic,
    # not socket binding.
    server._socket = fake  # type: ignore[assignment]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    try:
        with caplog.at_level(logging.ERROR, logger="collector.server"):
            thread.start()

            # First accept() raises; the loop should log it at ERROR and
            # retry, reaching the second (real) accept() result on its own.
            client_sock.sendall(b'{"t":1.0,"ptt":0.5}\n')
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and ptt_cache.latest() is None:
                time.sleep(0.01)

            client_sock.close()
            # Simulate close() having already run (as it would from
            # another thread during real shutdown) so the loop's next
            # accept() -- the fake's script is now exhausted -- is treated
            # as intended shutdown rather than another unexpected failure.
            server._socket = None
            fake.trigger_shutdown()
            thread.join(timeout=5)

        assert not thread.is_alive()
        latest = ptt_cache.latest()
        assert latest is not None
        assert latest.intercom is True

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("accept()" in r.getMessage() for r in error_records)
    finally:
        # server._socket is already None (set above); avoid double-closing
        # the fake.
        server._socket = None


def test_close_during_a_blocked_accept_ends_the_loop_cleanly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The existing, already-relied-upon shutdown path: a plain `OSError`
    from `accept()` (this codebase's own shape for "the listening socket
    was just closed") ends the loop without logging it as a failure --
    `close()` sets `self._shutting_down` before it closes the socket, so
    `serve_forever`'s `except` clause classifies this as intended shutdown
    rather than an unexpected failure, exactly like
    `F10CommandReceiver.serve_forever`'s own close()-during-recvfrom
    shutdown path.

    Run several times in a row with fresh server instances rather than
    once: an earlier version of this guard classified shutdown correctly
    only when `self._socket` happened to already be `None` by the time the
    `except` block ran, which is a race, not a guarantee -- it logged the
    false failure on 161/~230 real runs outside pytest. A single pass here
    would have had a good chance of landing in the lucky ~30% and shipping
    anyway; repeating it makes a reintroduced race show up reliably instead
    of intermittently.
    """
    for _ in range(20):
        server = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        server.open()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        with caplog.at_level(logging.ERROR, logger="collector.server"):
            thread.start()
            time.sleep(0.02)

            server.close()
            thread.join(timeout=5)

            assert not thread.is_alive()
            error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
            assert not error_records, (
                "clean shutdown must not be logged as an accept() failure: "
                f"{[r.getMessage() for r in error_records]}"
            )
        caplog.clear()
