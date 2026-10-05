"""Collector-side player for the audio-playback channel (BL-10 first slice,
`plans/tts-voice-output/plan.md` stages 2/4/5).

Unlike `text_sender.py`/`command_sender.py` (UDP datagrams to a DCS-side
listener), this sender plays audio **directly on the Windows box** via the
stdlib `winsound` module -- no DCS process involvement needed for this
channel, per the plan's recon (`audio-adapter/research/2026-09-17-tts-audio-
transport-recon.md`): the collector alone can play a WAV file.

**Queueing/preemption (plan Decision 4), decided here, not in
`audio-adapter` or `body-layer`.** `winsound` (like any audio API) plays one
sound at a time, and `logger.py`'s `--crew-text` poll loop can emit several
lines in one poll -- garbled overlapping speech is worse than a short queue
delay, so routine lines queue FIFO and play in order. A single background
worker thread draining a `queue.Queue` of temp `.wav` paths naturally
serializes playback (`WavPlayer.play` blocks). An **urgent** push instead
clears whatever routine lines are queued and interrupts whatever is
currently playing (`_interrupt_playback`, kept as one small function per the
plan's "make it a single clearly-named function so stage 5 can change it
after a live test without touching the queue logic") before its own file is
enqueued -- "missile launch, break right" must not wait behind a routine
contact report (plan Decision 3's `bypass_gate` framing on the body-layer
side).

**The queue is bounded (`_MAX_QUEUE_LEN`), dropping the oldest queued line
on overflow** (2026-09-26 performance review) -- added as parity with
`collector.cache.F10CommandQueue`, this codebase's other queue of the same
risk class, which was already bounded with the same reasoning: a producer
bug or a long, dense-traffic sortie must not grow this queue (and its
backing temp `.wav` files on disk) without limit. Oldest-dropped, not
newest-rejected, because a stale queued callout is worth less than a fresh
one -- see `_enqueue`.

**SPU-8 gating and volume (`plans/spu8-intercom/plan.md` Stage 3)** are
both consulted at one point: immediately before `self._player.play(path)`,
in the worker thread (`_run`), via an injected
`gate_state: Callable[[], Spu8GateState]` provider -- not at `play_audio`/
enqueue time (plan Decision 2). A line sitting briefly behind another in
the FIFO is re-checked against current switch/volume state right before it
actually plays. If the gate is closed, the queued line is dropped silently
(logged, temp file cleaned up, `play()` never called) with no special-
casing for `urgent` -- an off switch means off, unconditionally. If open,
the WAV's 16-bit PCM samples are scaled by the current volume (0..1
linear) with stdlib `wave` + `array` before playback -- **not `audioop`**
(main-loop amendment 2026-10-05): it was deprecated in Python 3.11 and
removed in 3.13, and this project's `requires-python = ">=3.11"` does not
pin below 3.13, so `import audioop` would fail outright on a 3.13 Windows
interpreter. A WAV that is not 16-bit PCM plays unscaled (logged once)
rather than guessing at its format. The real production wiring
(`collector/__main__.py`) passes `Spu8Cache.gate_state`, fail-safe-closed
when no SPU-8 sample has arrived yet (plan Decision 3); the constructor
default below (`_always_open`) is a backward-compatibility value only, for
every pre-existing call site/test that doesn't care about gating.

**`winsound` is Windows-only stdlib -- the first Windows-only import this
codebase has needed.** Guarded with a static `sys.platform == "win32"`
check (not a runtime `try`/`except ImportError`): mypy specially recognizes
`sys.platform` comparisons and skips type-checking the branch that is
statically unreachable for the platform it's run on, so `mypy --strict`
passes on the Mac dev machine without needing `# type: ignore` on every
`winsound.*` reference (confirmed locally -- the `try`/`except ImportError`
alternative does *not* get this treatment: `winsound`'s typeshed stub
exists on every platform but reports "no attribute" for every member
outside `sys.platform == "win32"`, so referencing `winsound.PlaySound`
inside a bare `try` block still fails `--strict` on the Mac). On a non-
Windows machine, `_WinsoundPlayer.play`/`.stop` raise `RuntimeError` --
caught and logged by the worker loop / `_interrupt_playback` like any other
playback failure (plan Decision 5), never crashing the process. Automated
tests exercise the queue/preempt logic against a fake `WavPlayer`, never
the real `winsound` call -- this module's own live behavior (including
Decision 4's unverified `SND_PURGE`/stop-then-play interrupt mechanism) is
a stage 5 live-Windows verification item, not something these tests can
confirm.
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import tempfile
import threading
import wave
from array import array
from collections.abc import Callable
from typing import Protocol

from collector.cache import Spu8GateState

logger = logging.getLogger(__name__)

#: 16-bit PCM signed sample bounds -- `_scale_volume` clamps to these after
#: multiplying, since `volume` is nominally 0..1 but a defensive clamp costs
#: nothing and the real cockpit value is never verified by this code.
_INT16_MIN = -32768
_INT16_MAX = 32767


#: `AudioPlaybackSender`'s own constructor default (plan Decision 3) -- a
#: backward-compatibility value for every pre-existing call site/test that
#: never wires a real gate/volume provider, not a production path. The real
#: wiring (`collector/__main__.py`) passes `Spu8Cache.gate_state`, which is
#: fail-safe-closed instead.
def _always_open() -> Spu8GateState:
    return Spu8GateState(gate_open=True, volume=1.0)


#: Sentinel put on the queue by `close()` to unblock the worker thread's
#: blocking `queue.get()` call.
_SENTINEL: str | None = None


class WavPlayer(Protocol):
    def play(self, path: str) -> None:
        """Play the WAV file at `path`, blocking until playback completes
        (or raises). The worker loop's own blocking `queue.get()`/`play()`
        sequence is what serializes routine playback -- see module
        docstring."""
        ...

    def stop(self) -> None:
        """Interrupt whatever is currently playing, if anything. Called
        only for an urgent push (plan Decision 4); must not raise for "no
        current playback" -- an implementation with nothing to stop should
        simply no-op."""
        ...


#: Bounded so a producer bug (or simply a long, dense-traffic sortie) cannot
#: grow this queue -- and its backing temp `.wav` files on disk -- without
#: limit (2026-09-26 performance review, "Audio playback queue has no upper
#: bound, unlike its F10 sibling"). Mirrors `collector.cache.F10CommandQueue`'s
#: `_MAX_QUEUE_LEN` reasoning and value: generous relative to any plausible
#: callout rate (seconds of speech per line), so this is insurance against a
#: bug, not a limit ever expected to bind in normal use.
_MAX_QUEUE_LEN = 64

#: Added to a WAV's own computed duration before the worker gives up
#: waiting on asynchronous playback, covering device start-up latency and
#: rounding. Small enough not to add an audible gap between queued lines.
_PLAYBACK_MARGIN_S: float = 0.25

#: Used when a file's duration cannot be read (a malformed or non-PCM WAV).
#: The worker waits this long rather than either returning immediately --
#: which would overlap the next line -- or blocking forever.
_PLAYBACK_FALLBACK_S: float = 10.0


def wav_duration_s(path: str) -> float | None:
    """Playback duration of the WAV at `path`, or `None` if it cannot be
    read (malformed file, unsupported/compressed format).

    Needed because the interrupt mechanism below plays asynchronously: the
    worker thread has to know how long to wait in an interruptible sleep,
    since `winsound` offers no "is it still playing" query. Pure stdlib
    `wave` parsing, no dependency, and cheap -- it reads the header only."""
    try:
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            if rate <= 0:
                return None
            return w.getnframes() / float(rate)
    except (wave.Error, OSError, EOFError):
        return None


def scale_wav_volume(path: str, volume: float) -> None:
    """Scale the WAV at `path` by `volume` (0..1 linear) in place --
    `plans/spu8-intercom/plan.md` Stage 3's playback-volume mechanism.

    A no-op for `volume == 1.0` (the common case: gate open, knob at full,
    or the constructor's `_always_open` default) -- skipping both the
    `wave` round-trip and, just as importantly, leaving any non-WAV file a
    test double hands this module untouched, since nothing needs scaling.

    Only 16-bit PCM is scaled. A WAV that is not 16-bit PCM (or cannot be
    read as a WAV at all) is left exactly as it was and logged once --
    "play it unscaled rather than guess" (plan Stage 3) -- the caller then
    plays the original file. Samples are read via stdlib `array('h')`
    (**not `audioop`**, removed in Python 3.13 -- main-loop amendment
    2026-10-05), byteswapped on a big-endian host since a WAV's own PCM
    data is always little-endian, multiplied by `volume`, clamped to the
    16-bit signed range, and written back to the same file."""
    if volume == 1.0:
        return

    try:
        with wave.open(path, "rb") as reader:
            params = reader.getparams()
            if params.sampwidth != 2:
                logger.warning(
                    "SPU-8 volume: %s is not 16-bit PCM (sampwidth=%d) -- "
                    "playing unscaled",
                    path,
                    params.sampwidth,
                )
                return
            raw_frames = reader.readframes(params.nframes)

        samples = array("h")
        samples.frombytes(raw_frames)
    except (wave.Error, OSError, EOFError, ValueError):
        # ValueError covers a WAV whose declared `nframes` exceeds the
        # file's real size: `readframes` does not raise on a truncated
        # `data` chunk -- it just returns however many bytes are actually
        # there -- and if that byte count is odd, `array("h").frombytes()`
        # raises. Same posture as this function's other malformed-input
        # cases: play it unscaled rather than guess (Security deep
        # analysis, SPU-8 intercom, 2026-10-05).
        logger.warning(
            "SPU-8 volume: %s could not be read as a WAV -- playing unscaled",
            path,
            exc_info=True,
        )
        return

    if sys.byteorder == "big":
        samples.byteswap()

    for i, sample in enumerate(samples):
        scaled = int(sample * volume)
        if scaled > _INT16_MAX:
            scaled = _INT16_MAX
        elif scaled < _INT16_MIN:
            scaled = _INT16_MIN
        samples[i] = scaled

    if sys.byteorder == "big":
        samples.byteswap()

    try:
        with wave.open(path, "wb") as writer:
            writer.setparams(params)
            writer.writeframes(samples.tobytes())
    except (wave.Error, OSError) as exc:
        logger.warning("SPU-8 volume: failed to write scaled %s: %s", path, exc)


if sys.platform == "win32":
    import winsound

    class _WinsoundPlayer:
        """`WavPlayer` backed by the stdlib `winsound` module.

        **Plays asynchronously and waits, rather than playing
        synchronously** -- this is the stage 5 live-Windows finding
        (2026-09-18) and the reason Decision 4's original mechanism did not
        work. `PlaySound(path, SND_FILENAME)` blocks *inside* the Win32
        call until the sound finishes, and `PlaySound(None, SND_PURGE)`
        issued from another thread cannot interrupt it: Windows only purges
        sounds that were started asynchronously. Observed live: the queue
        cleared correctly (pure Python) while the in-flight line played
        stubbornly to its end, then the urgent line followed.

        So `play` now starts the sound with `SND_ASYNC` and blocks on an
        interruptible `threading.Event` for the file's own duration
        (`wav_duration_s`) plus a small margin. `stop` purges the sound
        *and* sets that event, so the worker stops waiting immediately
        instead of sitting out the remaining duration. The blocking
        contract `WavPlayer.play` promises is preserved -- the worker still
        serializes routine lines -- but the block is now one this process
        can break."""

        def __init__(self) -> None:
            self._done = threading.Event()

        def play(self, path: str) -> None:
            self._done.clear()
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            duration = wav_duration_s(path)
            wait_s = (
                duration + _PLAYBACK_MARGIN_S
                if duration is not None
                else _PLAYBACK_FALLBACK_S
            )
            self._done.wait(timeout=wait_s)

        def stop(self) -> None:
            winsound.PlaySound(None, winsound.SND_PURGE)
            self._done.set()

else:

    class _WinsoundPlayer:
        """Non-Windows stand-in -- `winsound` does not exist on this
        platform. Both methods raise `RuntimeError`, caught by the worker
        loop / `_interrupt_playback` like any other playback failure
        (plan Decision 5), so a Mac-run collector process (never a real
        deploy target, but useful for tests/dev) degrades rather than
        crashing."""

        def play(self, path: str) -> None:
            raise RuntimeError("winsound is only available on Windows")

        def stop(self) -> None:
            raise RuntimeError("winsound is only available on Windows")


class AudioPlaybackSender:
    """Owns a background worker thread + `queue.Queue` of temp `.wav`
    paths, playing them one at a time via a `WavPlayer`. Mirrors
    `TextOverlaySender`/`CommandSender`'s open()/close() lifecycle shape,
    though the underlying resource here is a thread, not a socket."""

    def __init__(
        self,
        player: WavPlayer | None = None,
        gate_state: Callable[[], Spu8GateState] = _always_open,
    ) -> None:
        self._player: WavPlayer = player if player is not None else _WinsoundPlayer()
        self._gate_state = gate_state
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=_MAX_QUEUE_LEN)
        self._worker: threading.Thread | None = None

    def open(self) -> None:
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def close(self) -> None:
        self._queue.put(_SENTINEL)
        if self._worker is not None:
            self._worker.join(timeout=5)
            self._worker = None

    def play_audio(self, audio: bytes, urgent: bool) -> None:
        """Write `audio` (WAV bytes) to a temp file and enqueue it for
        playback. `urgent=True` clears any currently-queued routine lines
        and interrupts in-flight playback before this file is enqueued
        (plan Decision 4) -- otherwise it joins the FIFO queue behind
        whatever is already queued. Never raises: a failure to write the
        temp file is logged and the line is dropped, matching
        `TextOverlaySender.send_line`'s never-raises posture (plan
        Decision 5 -- playback is best-effort, display-equivalent output,
        not a verifiable command)."""
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="aircraft-layer-audio-")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(audio)
        except OSError:
            logger.warning("failed to write temp audio file", exc_info=True)
            self._cleanup(path)
            return

        if urgent:
            self.interrupt()

        self._enqueue(path)

    def _enqueue(self, path: str) -> None:
        """Put `path` on the playback queue, dropping the **oldest** queued
        (not-yet-playing) file if the queue is already at `_MAX_QUEUE_LEN`
        -- a stale queued callout is worth less than a fresh one, and the
        alternative (a blocking `put`) would stall whatever called
        `play_audio` (the HTTP request thread, in practice), violating this
        method's own never-raises/never-hangs posture. `urgent=True`
        already clears the whole queue via `interrupt()` above before
        reaching here, so this bound is only ever exercised by a flood of
        routine lines outpacing playback -- mirrors
        `collector.cache.F10CommandQueue`'s oldest-dropped overflow policy
        and its reasoning."""
        while True:
            try:
                self._queue.put_nowait(path)
                return
            except queue.Full:
                try:
                    stale_path = self._queue.get_nowait()
                except queue.Empty:
                    continue
                logger.warning(
                    "audio queue full (%d) -- dropping oldest queued line",
                    _MAX_QUEUE_LEN,
                )
                if stale_path is not None:
                    self._cleanup(stale_path)

    def interrupt(self) -> None:
        """Stop whatever is currently playing and drop everything queued,
        without enqueueing anything new -- the interrupt-only path
        `stop_talking` needs (`plans/inbound-speech/plan.md` Stage 3
        follow-up, "'Stop' -- no readback or confirmation, just stop
        talking", a stated exception to this project's usual readback/
        confirm rule). `play_audio(..., urgent=True)` already reaches this
        exact pair of calls on its way to enqueueing its own urgent line;
        this method is that same preemption with the enqueue dropped, so a
        caller that only wants silence never has to push audio to get it.
        Never raises -- `_clear_queue`/`_interrupt_playback` already don't,
        same posture as `play_audio` itself."""
        self._clear_queue()
        self._interrupt_playback()

    def _clear_queue(self) -> None:
        """Drops every currently-queued routine `.wav` path (an urgent push
        preempts them entirely, per plan Decision 4 -- not "queue-jump but
        let queued lines still eventually play")."""
        while True:
            try:
                stale_path = self._queue.get_nowait()
            except queue.Empty:
                break
            if stale_path is not None:
                self._cleanup(stale_path)

    def _interrupt_playback(self) -> None:
        """Stops whatever is currently playing (plan Decision 4). Kept as
        this one small, clearly-named function -- see module docstring --
        so stage 5's live-Windows verification can change the mechanism
        without touching any queue logic above or below it."""
        try:
            self._player.stop()
        except Exception:
            logger.warning("failed to interrupt in-flight playback", exc_info=True)

    def _run(self) -> None:
        while True:
            path = self._queue.get()
            if path is None:
                return

            # SPU-8 gate/volume, consulted once per item, right here --
            # "next-utterance granularity" per the plan: whatever is
            # current when this item reaches the front of the queue, not
            # re-checked mid-playback.
            state = self._gate_state()
            if not state.gate_open:
                logger.debug(
                    "SPU-8 gate closed -- dropping queued line %s without playing",
                    path,
                )
                self._cleanup(path)
                continue

            try:
                scale_wav_volume(path, state.volume)
            except Exception:
                # Defense in depth, independent of scale_wav_volume's own
                # guard: a future unguarded parse path in there must not
                # be able to kill this worker thread for the rest of the
                # sortie (Security deep analysis, SPU-8 intercom,
                # 2026-10-05). Play the file unscaled rather than skip it.
                logger.warning(
                    "SPU-8 volume scaling failed for %s (playing unscaled)",
                    path,
                    exc_info=True,
                )
            try:
                self._player.play(path)
            except Exception:
                logger.warning(
                    "playback failed for %s (continuing)", path, exc_info=True
                )
            finally:
                self._cleanup(path)

    def _cleanup(self, path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            logger.debug("could not remove temp audio file %s", path, exc_info=True)
