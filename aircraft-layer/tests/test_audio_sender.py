"""Tests for `collector.audio_sender.AudioPlaybackSender`'s queue/preempt
logic, against a fake `WavPlayer` -- no real `winsound` call, per that
module's own docstring on why (Windows-only, unverified live behavior)."""

from __future__ import annotations

import io
import os
import threading
import time
import wave
from array import array
from collections.abc import Callable
from pathlib import Path

import pytest

from collector.audio_sender import (
    _MAX_QUEUE_LEN,
    AudioPlaybackSender,
    WavPlayer,
    scale_wav_volume,
    wav_duration_s,
)
from collector.cache import Spu8GateState


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


# --- queue bound (2026-09-26 performance review) ----------------------------
#
# Parity with collector.cache.F10CommandQueue: a producer bug (or just a
# long, dense-traffic sortie) must not grow this queue -- and its backing
# temp .wav files -- without limit.


def test_queue_is_bounded_and_drops_the_oldest_queued_line() -> None:
    player = _FakePlayer()
    player.play_gate = threading.Event()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        # FIRST starts playing and blocks the worker on the gate, so every
        # subsequent push queues up behind it instead of draining
        # immediately (same synchronization technique as the
        # urgent-preemption test above).
        sender.play_audio(b"FIRST", urgent=False)
        time.sleep(0.1)

        # Queue more routine lines than the bound allows.
        total = _MAX_QUEUE_LEN + 5
        for i in range(total):
            sender.play_audio(f"L{i:03d}".encode("ascii"), urgent=False)

        # Release FIRST so the worker drains everything that survived.
        player.play_gate.set()
        assert _wait_until(
            lambda: len(player.played) == 1 + _MAX_QUEUE_LEN, timeout=5.0
        )
    finally:
        sender.close()

    # FIRST (already in flight, never subject to the bound) plays, then
    # exactly _MAX_QUEUE_LEN routine lines -- the *oldest* 5 of the `total`
    # queued were dropped to stay within the bound, not the newest, so the
    # survivors are the last _MAX_QUEUE_LEN lines pushed, in FIFO order.
    expected_survivors = [f"L{i:03d}" for i in range(total - _MAX_QUEUE_LEN, total)]
    assert player.played == ["FIRST"] + expected_survivors


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


# --- interrupt() (plans/inbound-speech/plan.md Stage 3 follow-up) ----------
#
# The interrupt-only path `stop_talking` needs: stop whatever's playing and
# drop whatever's queued, without enqueueing anything new.


def test_interrupt_clears_queued_lines_and_stops_in_flight_playback() -> None:
    player = _FakePlayer()
    player.play_gate = threading.Event()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        sender.play_audio(b"FIRST", urgent=False)
        time.sleep(0.1)  # let the worker actually dequeue and block on FIRST

        sender.play_audio(b"SECOND", urgent=False)
        sender.play_audio(b"THIRD", urgent=False)

        sender.interrupt()
        assert _wait_until(lambda: player.stop_calls >= 1)
        assert _wait_until(lambda: len(player.played) == 1, timeout=3.0)
    finally:
        sender.close()

    # FIRST (already in flight) finishes; SECOND/THIRD were dropped and
    # nothing new was ever enqueued by interrupt() itself.
    assert player.played == ["FIRST"]


def test_interrupt_with_nothing_playing_or_queued_is_a_clean_no_op() -> None:
    player = _FakePlayer()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        sender.interrupt()
    finally:
        sender.close()
    assert player.played == []


# --- wav_duration_s (stage 5 fix, 2026-09-18) -------------------------------
#
# `_WinsoundPlayer` now plays asynchronously and waits out the file's own
# duration in an interruptible sleep, because synchronous `PlaySound` cannot
# be purged from another thread (observed live on Windows: the routine line
# played to its end before the urgent one was heard). That makes this duration
# calculation load-bearing -- if it reads short, a line is cut off; if it reads
# long, a silent gap opens between queued lines. The real `winsound` call still
# cannot be tested off-Windows, but this can.


def _write_wav(path: Path, *, seconds: float, rate: int = 22050) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def test_wav_duration_matches_the_written_length(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_wav(path, seconds=1.5)

    duration = wav_duration_s(str(path))

    assert duration is not None
    assert duration == pytest.approx(1.5, abs=0.01)


def test_wav_duration_handles_a_non_default_sample_rate(tmp_path: Path) -> None:
    path = tmp_path / "tone48.wav"
    _write_wav(path, seconds=0.75, rate=48000)

    duration = wav_duration_s(str(path))

    assert duration is not None
    assert duration == pytest.approx(0.75, abs=0.01)


def test_wav_duration_returns_none_for_a_malformed_file(tmp_path: Path) -> None:
    """The worker falls back to a fixed wait rather than either returning
    immediately (which would overlap the next line) or blocking forever."""
    path = tmp_path / "not-audio.wav"
    path.write_bytes(b"this is not a RIFF header at all")

    assert wav_duration_s(str(path)) is None


def test_wav_duration_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    assert wav_duration_s(str(tmp_path / "absent.wav")) is None


# --- SPU-8 gate/volume (plans/spu8-intercom/plan.md Stage 3) --------------
#
# Consulted once per queued item, in the worker thread, immediately before
# play() -- not at play_audio()/enqueue time (plan Decision 2). Closed
# drops silently (no play() call, no special-casing for urgent); open
# scales the WAV's PCM by the current volume via scale_wav_volume
# (stdlib wave + array, not audioop -- see that function's own docstring).


def _write_16bit_wav(path: Path, samples: list[int], *, rate: int = 22050) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(array("h", samples).tobytes())


def _read_16bit_samples(path: str) -> list[int]:
    with wave.open(path, "rb") as r:
        data = array("h")
        data.frombytes(r.readframes(r.getnframes()))
        return list(data)


def test_gate_closed_drops_the_queued_line_without_playing() -> None:
    player = _CapturingPlayer()
    sender = AudioPlaybackSender(
        player=player, gate_state=lambda: Spu8GateState(gate_open=False, volume=1.0)
    )
    sender.open()
    try:
        sender.play_audio(b"RIFF....fake wav bytes....", urgent=False)
        time.sleep(0.2)
    finally:
        sender.close()

    assert player.paths == []


def test_gate_open_plays_the_queued_line() -> None:
    player = _CapturingPlayer()
    sender = AudioPlaybackSender(
        player=player, gate_state=lambda: Spu8GateState(gate_open=True, volume=1.0)
    )
    sender.open()
    try:
        sender.play_audio(b"HELLO", urgent=False)
        assert _wait_until(lambda: len(player.paths) == 1)
    finally:
        sender.close()

    assert player.contents == [b"HELLO"]


def test_gate_closed_drops_the_line_even_when_urgent() -> None:
    """An off switch means off, unconditionally -- no special-casing for
    urgent (plan Stage 3)."""
    player = _CapturingPlayer()
    sender = AudioPlaybackSender(
        player=player, gate_state=lambda: Spu8GateState(gate_open=False, volume=1.0)
    )
    sender.open()
    try:
        sender.play_audio(b"URGENT-BUT-GATED", urgent=True)
        time.sleep(0.2)
    finally:
        sender.close()

    assert player.paths == []


def test_default_gate_state_is_always_open_full_volume() -> None:
    """The constructor default (`_always_open`) is a backward-compatibility
    value for pre-existing call sites/tests, not a production path --
    `AudioPlaybackSender()` with no `gate_state=` keeps playing exactly as
    it did before this feature existed."""
    player = _CapturingPlayer()
    sender = AudioPlaybackSender(player=player)
    sender.open()
    try:
        sender.play_audio(b"NOT-GATED", urgent=False)
        assert _wait_until(lambda: len(player.paths) == 1)
    finally:
        sender.close()

    assert player.contents == [b"NOT-GATED"]


def test_scale_wav_volume_scales_16bit_pcm_samples(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    original = [1000, -2000, 32000, -32000, 0]
    _write_16bit_wav(path, original)

    scale_wav_volume(str(path), 0.5)

    scaled = _read_16bit_samples(str(path))
    assert scaled == [500, -1000, 16000, -16000, 0]


def test_scale_wav_volume_clamps_to_int16_range(tmp_path: Path) -> None:
    path = tmp_path / "loud.wav"
    _write_16bit_wav(path, [32767, -32768])

    # volume > 1.0 is not a value Export.lua is expected to send, but the
    # clamp is defensive: this code never trusts the cockpit value blindly.
    scale_wav_volume(str(path), 1.5)

    scaled = _read_16bit_samples(str(path))
    assert scaled == [32767, -32768]


def test_scale_wav_volume_is_a_no_op_at_full_volume(tmp_path: Path) -> None:
    """Skips the wave round-trip entirely at volume == 1.0 -- also what
    keeps this module's own non-WAV fake-player test fixtures (plain ASCII
    bytes, not real WAV files) working unchanged, since the default
    gate_state provider reports full volume."""
    path = tmp_path / "plain.wav"
    path.write_bytes(b"not a real wav file at all")

    scale_wav_volume(str(path), 1.0)  # must not raise

    assert path.read_bytes() == b"not a real wav file at all"


def test_scale_wav_volume_plays_unscaled_for_non_16bit_pcm(tmp_path: Path) -> None:
    """8-bit PCM (sampwidth=1) is not guessed at -- left untouched, logged,
    and played as-is."""
    path = tmp_path / "eight-bit.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(22050)
        w.writeframes(bytes([10, 20, 30]))
    before = path.read_bytes()

    scale_wav_volume(str(path), 0.5)

    assert path.read_bytes() == before


def test_scale_wav_volume_handles_a_malformed_file(tmp_path: Path) -> None:
    path = tmp_path / "garbage.wav"
    path.write_bytes(b"this is not a RIFF header at all")
    before = path.read_bytes()

    scale_wav_volume(str(path), 0.5)  # must not raise

    assert path.read_bytes() == before


def _write_truncated_odd_length_pcm_wav(path: Path) -> None:
    """A WAV whose header declares more frames than the file actually
    holds, truncated to an *odd* byte count -- the specific shape Security
    reproduced (deep analysis, SPU-8 intercom, 2026-10-05): `wave.open`
    parses the header cleanly, `readframes` does not raise on the
    short read, but the odd byte count makes `array("h").frombytes()`
    raise `ValueError` two lines later, outside the original guard."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(array("h", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]).tobytes())

    full = path.read_bytes()
    header_len = len(full) - 20  # 20 bytes of 16-bit PCM data were written
    path.write_bytes(full[: header_len + 15])  # keep only 15 (odd) data bytes


def test_scale_wav_volume_handles_truncated_odd_length_pcm(tmp_path: Path) -> None:
    """The `array("h").frombytes()` step sits outside the original
    `except (wave.Error, OSError, EOFError)` guard -- this is the path
    Security's crafted WAV exploited to kill the playback worker thread
    permanently. Reverting the widened `except` clause (removing
    `ValueError`, or narrowing the `try` back to just the `wave.open`
    block) makes this test fail with an uncaught `ValueError`."""
    path = tmp_path / "truncated.wav"
    _write_truncated_odd_length_pcm_wav(path)
    before = path.read_bytes()

    scale_wav_volume(str(path), 0.5)  # must not raise

    # Played unscaled, same posture as every other malformed-input case:
    # the file is left exactly as it was found, not rewritten.
    assert path.read_bytes() == before


def test_run_survives_scale_wav_volume_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defense in depth, independent of the `scale_wav_volume` parse fix
    above: even if something inside `scale_wav_volume` raises, the worker
    thread in `_run()` must keep processing the queue rather than dying.
    Removing `_run()`'s own `try`/`except` around the `scale_wav_volume`
    call (leaving only the fix inside `scale_wav_volume` itself) makes
    this test fail -- the worker loop exits on the first raise and the
    second queued line is never played."""
    import collector.audio_sender as audio_sender_module

    call_count = 0
    real_scale_wav_volume = audio_sender_module.scale_wav_volume

    def _raise_once(path: str, volume: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("simulated scale_wav_volume failure")
        real_scale_wav_volume(path, volume)

    monkeypatch.setattr(audio_sender_module, "scale_wav_volume", _raise_once)

    player = _CapturingPlayer()
    sender = AudioPlaybackSender(
        player=player, gate_state=lambda: Spu8GateState(gate_open=True, volume=0.5)
    )
    sender.open()
    try:
        sender.play_audio(b"RIFF-FAKE-ONE", urgent=False)
        sender.play_audio(b"RIFF-FAKE-TWO", urgent=False)
        assert _wait_until(lambda: len(player.paths) == 2)
    finally:
        sender.close()

    assert call_count == 2
    assert player.contents == [b"RIFF-FAKE-ONE", b"RIFF-FAKE-TWO"]


def test_run_applies_volume_scaling_before_playback(tmp_path: Path) -> None:
    """End-to-end through the worker thread: a real 16-bit WAV handed to
    play_audio comes out scaled by the time the player sees it."""
    player = _CapturingPlayer()
    sender = AudioPlaybackSender(
        player=player, gate_state=lambda: Spu8GateState(gate_open=True, volume=0.5)
    )
    sender.open()
    try:
        wav_path = tmp_path / "source.wav"
        _write_16bit_wav(wav_path, [1000, -2000])
        sender.play_audio(wav_path.read_bytes(), urgent=False)
        assert _wait_until(lambda: len(player.contents) == 1)
    finally:
        sender.close()

    with wave.open(io.BytesIO(player.contents[0]), "rb") as r:
        data = array("h")
        data.frombytes(r.readframes(r.getnframes()))
    assert list(data) == [500, -1000]
