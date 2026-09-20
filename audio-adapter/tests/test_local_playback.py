"""Tests for `local_playback` -- `LocalPlaybackSink`'s `--target local`
`AudioSink` implementation, and `_InFlightTracker`, the interrupted-vs-
failed bookkeeping it depends on (`plans/inbound-speech/plan.md` Stage 3
follow-up, review 2026-09-20).

`_InFlightTracker` is tested directly, with no real subprocess and no
threads at all -- `start`/`interrupt`/`finish` are plain synchronous calls,
so the exact interleaving that broke the first version of this fix (a
second `interrupt()`, against a second in-flight process, landing before
the first process's own `finish()` runs) can be reproduced deterministically
by simply calling the methods in that order, rather than racing real
threads and hoping the scheduler cooperates.

`LocalPlaybackSink` itself is tested against a fake `_PlaybackProcess`
double, injected via the `spawn` constructor parameter -- no real `afplay`
call, mirroring `aircraft-layer/tests/test_audio_sender.py`'s fake-
`WavPlayer` posture for the analogous `AudioPlaybackSender.interrupt`."""

from __future__ import annotations

import subprocess
import threading
import time

import pytest

from local_playback import LocalPlaybackSink, _InFlightTracker, _PlaybackProcess
from server import AudioDeliveryError


class _FakeProcess:
    """A `_PlaybackProcess` double. `communicate()` blocks on an internal
    `Event` until either `finish()` (simulating a normal exit) or `kill()`
    is called -- mirroring real `Popen.communicate()`'s "blocks until the
    process ends" contract closely enough to exercise `deliver()` for real,
    without spawning anything."""

    def __init__(self) -> None:
        self._done = threading.Event()
        self.returncode: int | None = None
        self.kill_calls = 0
        self.stdout = b""
        self.stderr = b""

    def communicate(
        self, *, timeout: float | None = None
    ) -> tuple[bytes | None, bytes | None]:
        if not self._done.wait(timeout=timeout):
            raise subprocess.TimeoutExpired(cmd="afplay", timeout=timeout or 0)
        return self.stdout, self.stderr

    def finish(self, returncode: int = 0, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self._done.set()

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9
        self._done.set()


# -- _InFlightTracker (direct, deterministic, no threads) -------------------


def test_finish_without_a_prior_interrupt_is_not_flagged() -> None:
    tracker = _InFlightTracker()
    process = _FakeProcess()
    tracker.start(process)
    assert tracker.finish(process) is False


def test_interrupt_then_finish_is_flagged_and_then_forgotten() -> None:
    tracker = _InFlightTracker()
    process = _FakeProcess()
    tracker.start(process)

    killed = tracker.interrupt()
    assert killed is process
    assert tracker.finish(process) is True
    # Forgotten -- a second finish() call for the same (reused) identity
    # must not still read as interrupted.
    assert tracker.finish(process) is False


def test_interrupt_with_nothing_in_flight_returns_none() -> None:
    tracker = _InFlightTracker()
    assert tracker.interrupt() is None


def test_second_interrupt_does_not_clobber_the_first_pending_one() -> None:
    """Regression for the review-found bug: A is started and interrupted,
    then -- before A's own `finish()` runs -- B is started and interrupted
    too. Both kills must be tracked; the old single-slot version would
    have overwritten A's entry with B's, making A's own `finish()` return
    `False` (a genuine kill misread as a real failure)."""
    tracker = _InFlightTracker()
    process_a = _FakeProcess()
    process_b = _FakeProcess()

    tracker.start(process_a)
    assert tracker.interrupt() is process_a

    # B starts and is interrupted before A's finish() is ever called.
    tracker.start(process_b)
    assert tracker.interrupt() is process_b

    assert tracker.finish(process_a) is True
    assert tracker.finish(process_b) is True


def test_finish_clears_current_only_for_the_matching_process() -> None:
    tracker = _InFlightTracker()
    process_a = _FakeProcess()
    process_b = _FakeProcess()

    tracker.start(process_a)
    tracker.start(process_b)  # B is now "current"; A was never finish()ed

    # Finishing A (a stale reference) must not touch B's "current" slot.
    tracker.finish(process_a)
    assert tracker.interrupt() is process_b


# -- LocalPlaybackSink (against a fake _PlaybackProcess, no real afplay) ----


def test_deliver_success_does_not_raise() -> None:
    process = _FakeProcess()
    process.finish(0)
    sink = LocalPlaybackSink(spawn=lambda _path: process)

    sink.deliver(b"WAV-BYTES", urgent=False)

    assert process.kill_calls == 0


def test_deliver_genuine_nonzero_exit_raises() -> None:
    process = _FakeProcess()
    process.finish(1, stderr=b"boom")
    sink = LocalPlaybackSink(spawn=lambda _path: process)

    with pytest.raises(AudioDeliveryError):
        sink.deliver(b"WAV-BYTES", urgent=False)


def test_deliver_missing_binary_raises_audio_delivery_error() -> None:
    def spawn(_path: str) -> _PlaybackProcess:
        raise FileNotFoundError("afplay")

    sink = LocalPlaybackSink(spawn=spawn)

    with pytest.raises(AudioDeliveryError):
        sink.deliver(b"WAV-BYTES", urgent=False)


def test_interrupt_stops_in_flight_playback_without_raising_in_deliver() -> None:
    """The whole point of the fix: a `deliver()` call killed by `interrupt()`
    must complete cleanly, not raise `AudioDeliveryError`."""
    process = _FakeProcess()
    sink = LocalPlaybackSink(spawn=lambda _path: process)

    errors: list[BaseException] = []

    def run_deliver() -> None:
        try:
            sink.deliver(b"WAV-BYTES", urgent=False)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=run_deliver)
    thread.start()
    time.sleep(0.1)  # give deliver() time to spawn and reach communicate()
    sink.interrupt()
    thread.join(timeout=5)

    assert process.kill_calls == 1
    assert errors == []


def test_interrupt_with_nothing_playing_is_a_clean_no_op() -> None:
    sink = LocalPlaybackSink(spawn=lambda _path: _FakeProcess())
    sink.interrupt()  # no deliver() ever called -- must not raise


def test_two_concurrent_delivers_both_survive_being_interrupted() -> None:
    """The exact scenario the review flagged: two `/speak`-shaped
    `deliver()` calls in flight, each interrupted before the first one's
    own bookkeeping has settled. Both must complete without raising."""
    process_a = _FakeProcess()
    process_b = _FakeProcess()
    processes = iter([process_a, process_b])
    sink = LocalPlaybackSink(spawn=lambda _path: next(processes))

    errors: list[BaseException] = []
    lock = threading.Lock()

    def run_deliver(payload: bytes) -> None:
        try:
            sink.deliver(payload, urgent=False)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    thread_a = threading.Thread(target=run_deliver, args=(b"A",))
    thread_a.start()
    time.sleep(0.1)  # let A's spawn/start() run before interrupting it
    sink.interrupt()  # kills A

    thread_b = threading.Thread(target=run_deliver, args=(b"B",))
    thread_b.start()
    time.sleep(0.05)
    sink.interrupt()  # kills B

    thread_a.join(timeout=5)
    thread_b.join(timeout=5)

    assert process_a.kill_calls == 1
    assert process_b.kill_calls == 1
    assert errors == []
