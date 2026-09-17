"""Tests for `collector.audio_sender.AudioPlaybackSender`'s queue/preempt
logic, against a fake `WavPlayer` -- no real `winsound` call, per that
module's own docstring on why (Windows-only, unverified live behavior)."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

from collector.audio_sender import AudioPlaybackSender, WavPlayer


class _FakePlayer:
    """Records every `play`/`stop` call. `play` blocks on `play_gate` (an
    `Event`) when set, so a test can hold playback "in flight" long enough
    to exercise urgent-preemption against it."""

    def __init__(self) -> None:
        self.played: list[str] = []
        self.stop_calls = 0
        self.play_gate: threading.Event | None = None

    def play(self, path: str) -> None:
        if self.play_gate is not None:
            self.play_gate.wait(timeout=5)
        # Record the file's own contents, not its (throwaway) temp path --
        # tests assert on what was played, matching what play_audio(audio,
        # ...) was actually called with.
        with open(path, "rb") as f:
            self.played.append(f.read().decode("ascii"))

    def stop(self) -> None:
        self.stop_calls += 1
        if self.play_gate is not None:
            self.play_gate.set()


class _FlakyPlayer:
    """`play` raises on its first call, then succeeds for every call after
    -- used to confirm one bad line never kills the worker loop."""

    def __init__(self) -> None:
        self.calls = 0
        self.played: list[str] = []

    def play(self, path: str) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("simulated failure on first line")
        self.played.append(path)

    def stop(self) -> None:
        pass


class _CapturingPlayer:
    """Records the exact bytes written to each temp file it's asked to
    play, so a test can confirm `play_audio` wrote what it was given."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.contents: list[bytes] = []

    def play(self, path: str) -> None:
        self.paths.append(path)
        with open(path, "rb") as f:
            self.contents.append(f.read())

    def stop(self) -> None:
        pass


def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_routine_lines_play_fifo_in_order() -> None:
    player = _FakePlayer()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        sender.play_audio(b"AAA", urgent=False)
        sender.play_audio(b"BBB", urgent=False)
        sender.play_audio(b"CCC", urgent=False)
        assert _wait_until(lambda: len(player.played) == 3)
    finally:
        sender.close()

    assert player.played == ["AAA", "BBB", "CCC"]


def test_temp_file_written_with_correct_bytes_then_cleaned_up() -> None:
    player = _CapturingPlayer()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        sender.play_audio(b"HELLO-WAV", urgent=False)
        assert _wait_until(lambda: len(player.paths) == 1)
    finally:
        sender.close()

    assert player.contents == [b"HELLO-WAV"]
    assert not os.path.exists(player.paths[0])


def test_urgent_preempted_lines_are_never_played() -> None:
    player = _FakePlayer()
    player.play_gate = threading.Event()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        # FIRST starts playing and blocks on the gate -- give the worker
        # thread a moment to actually dequeue it and enter the blocking
        # play() call before queueing anything else, so it's genuinely
        # "in flight" (not still sitting in the queue) when URGENT arrives.
        sender.play_audio(b"FIRST", urgent=False)
        time.sleep(0.1)

        # SECOND/THIRD queue up behind the blocked FIRST.
        sender.play_audio(b"SECOND", urgent=False)
        sender.play_audio(b"THIRD", urgent=False)

        # URGENT clears SECOND/THIRD from the queue and interrupts FIRST
        # (the fake player's stop() releases the gate).
        sender.play_audio(b"URGENT", urgent=True)
        assert _wait_until(lambda: player.stop_calls >= 1)
        assert _wait_until(lambda: len(player.played) == 2, timeout=3.0)
    finally:
        sender.close()

    # FIRST (already in flight when preempted) finishes, then URGENT plays
    # -- SECOND/THIRD were dropped entirely, never reaching the player.
    assert player.played == ["FIRST", "URGENT"]


def test_playback_failure_does_not_stop_the_worker_loop() -> None:
    player = _FlakyPlayer()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        sender.play_audio(b"ONE", urgent=False)
        sender.play_audio(b"TWO", urgent=False)
        assert _wait_until(lambda: player.calls == 2)
        assert _wait_until(lambda: len(player.played) == 1)
    finally:
        sender.close()


def test_open_close_without_any_play_is_clean() -> None:
    player = _FakePlayer()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    sender.close()
    assert player.played == []


def test_default_player_is_constructible_on_non_windows() -> None:
    # No real playback call made -- just confirms the default construction
    # path (no player= arg) doesn't blow up on import/instantiation on a
    # non-Windows dev machine.
    sender = AudioPlaybackSender()
    assert isinstance(sender, AudioPlaybackSender)


def test_wav_player_protocol_is_satisfied_by_fake() -> None:
    player: WavPlayer = _FakePlayer()
    assert hasattr(player, "play")
    assert hasattr(player, "stop")
