"""`LocalPlaybackSink`/`_WinsoundLocalSink` -- `--target local`'s
`server.AudioSink` implementations (`plans/tts-voice-output/plan.md`
Decision 8, `plans/audio-adapter-os-independent/plan.md` Decision 2/6):
play synthesized WAV bytes directly on this machine, via `afplay` on
macOS/Linux and the stdlib `winsound` module on Windows. `make_local_sink()`
is the platform-dispatching factory `__main__.py` calls instead of
hardcoding either class, exactly as `aircraft-layer/src/collector/
audio_sender.py` already does for `WavPlayer`.

Pulled out of `audio_adapter/__main__.py` into its own module (review,
`plans/inbound-speech/plan.md` Stage 3 follow-up, 2026-09-20) specifically
so `_InFlightTracker` -- ordinary, deterministic class logic, no subprocess,
no I/O, directly analogous to `aircraft-layer`'s tested `AudioPlaybackSender.
interrupt()` -- gets its own tests instead of inheriting `__main__.py`'s
"no automated test, live-process entrypoint" exemption purely by
co-location. That exemption was never meant to cover this: it only ever
applied to the CLI wiring (`argparse`, `main()`) that genuinely cannot be
unit tested without a live process. `LocalPlaybackSink.__init__` also
gained an injectable `spawn` callable for exactly this reason -- tests can
hand it a fake `_PlaybackProcess` and drive the exact interleaving below
without a real `afplay` anywhere.

**The bug this module fixes (review finding, 2026-09-20).** Killing
`afplay` via `interrupt()` leaves `process.returncode` non-zero (`-9`),
indistinguishable at that point from a genuine `afplay` crash -- so
`deliver()` needs a way to tell "we did this on purpose" apart from "it
actually failed" before deciding whether to raise `AudioDeliveryError`.
The first version of that fix (2026-09-20, same day) tracked at most one
"currently interrupted" process in a single field, which a **second**
`interrupt()` -- against a **second** in-flight `deliver()` call, both
served concurrently because `TTSAdapterServer` runs `ThreadingHTTPServer`
-- silently overwrote before the first `deliver()`'s own `finally` block
had read it. The first process would then be misread as a genuine failure
and its `/speak` call would 500, reproducing the exact bug the fix was
meant to remove, just under concurrency the live single-request test that
first caught the bug could not have exercised. `_InFlightTracker` fixes
this by tracking every interrupted process **by identity**
(`id(process)`, in a `set`, per the review's own suggestion), not in a
slot a later interrupt can clobber -- see its own docstring for the full
account and why entries are guaranteed to be removed rather than growing
unbounded across a long session."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading
import wave
from collections.abc import Callable
from typing import Protocol

from server import AudioDeliveryError

logger = logging.getLogger(__name__)

#: `afplay` should never hang the process indefinitely on a malformed file
#: -- generous headroom over the longest callout this project speaks.
PLAYBACK_TIMEOUT_S = 30.0


class _PlaybackProcess(Protocol):
    """Structural subset of `subprocess.Popen[bytes]` this module needs --
    exists so tests can inject a fake process without spawning a real
    `afplay` binary."""

    returncode: int | None

    def communicate(
        self, *, timeout: float | None = None
    ) -> tuple[bytes | None, bytes | None]: ...

    def kill(self) -> None: ...


def _spawn_afplay(tmp_path: str) -> subprocess.Popen[bytes]:
    """The real `spawn` `LocalPlaybackSink` uses by default -- a thin
    wrapper so it can be swapped for a fake `_PlaybackProcess` factory in
    tests. Raises `FileNotFoundError` exactly as a direct `Popen(...)`
    call would when `afplay` isn't on `PATH` (not macOS, most likely) --
    `deliver()` is what turns that into `AudioDeliveryError`."""
    return subprocess.Popen(
        ["afplay", tmp_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


class _InFlightTracker:
    """Owns the concurrency-critical bookkeeping `LocalPlaybackSink` needs
    to answer one question, once a subprocess it started exits non-zero:
    "did *we* kill this, or did it fail on its own?" Deliberately separated
    from the actual `Popen`/`afplay` mechanics so this state machine can be
    unit tested directly -- including the exact interleaving the review
    that added this class found (see module docstring) -- with no real
    subprocess, no threads, and no timing involved at all: `start`/
    `interrupt`/`finish` are plain synchronous calls a test can sequence
    by hand to reproduce any interleaving it wants.

    Every process is tracked **by identity** (`id(process)`), not in a
    single slot -- `ThreadingHTTPServer` genuinely allows two `deliver()`
    calls (and so two live processes) at once, and a single "last
    interrupted process" field silently loses an earlier intentional kill
    the moment a second interrupt happens before the first is consumed.
    `id()` rather than the process object itself per the review's own
    suggestion; safe here specifically because `deliver()` keeps a live
    reference to its own `process` on its call stack for the entire window
    between `start()` and `finish()`, so that object cannot be garbage
    collected and its id cannot be reused by anything else during that
    window. Entries are removed the moment they're consumed (`finish`), so
    the set cannot grow unbounded across a long session."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: _PlaybackProcess | None = None
        self._interrupted_ids: set[int] = set()

    def start(self, process: _PlaybackProcess) -> None:
        """Called once, right after a new process is spawned -- records it
        as the currently in-flight process `interrupt()` should target."""
        with self._lock:
            self._current = process

    def interrupt(self) -> _PlaybackProcess | None:
        """Marks whatever process is currently in flight as an
        intentional-kill target and returns it, so the caller can actually
        call `.kill()` on it outside this lock -- `None` if nothing is in
        flight (a clean no-op, mirroring `AudioPlaybackSender.interrupt`'s
        posture on the aircraft-layer side)."""
        with self._lock:
            process = self._current
            if process is not None:
                self._interrupted_ids.add(id(process))
            return process

    def finish(self, process: _PlaybackProcess) -> bool:
        """Called once, from `deliver()`'s own `finally`, for the process
        it just ran. Returns whether *this* process was the target of a
        prior `interrupt()` call, and forgets it either way (so the set
        above never grows unbounded)."""
        with self._lock:
            if self._current is process:
                self._current = None
            was_interrupted = id(process) in self._interrupted_ids
            self._interrupted_ids.discard(id(process))
            return was_interrupted


class LocalPlaybackSink:
    """`server.AudioSink` that plays synthesized WAV bytes directly on this
    machine via `afplay` -- `--target local`'s delivery mechanism (plan
    Decision 8). `urgent` is accepted but unused here: preemption (plan
    Decision 4) is decided in the aircraft-layer's queueing sender, which
    this dev-only local path deliberately has none of.

    **Concurrent `/speak` calls do not serialise.** `deliver()` spawns its
    own `afplay` process per call and `ThreadingHTTPServer` gives each
    request its own thread, so two overlapping `/speak` calls genuinely
    play at once rather than queueing behind one another -- there is no
    FIFO here, unlike `AudioPlaybackSender` on the aircraft-layer side.
    (An earlier version of this docstring claimed `afplay`'s own process
    serialised overlapping calls; that was true only while `deliver()`
    ran `afplay` via the blocking `subprocess.run`, and stopped being true
    the moment it moved to `Popen` so `interrupt()` could reach the live
    process -- corrected 2026-09-20, review.) `interrupt()` only ever
    targets the *most recently started* process -- fine for this path's
    actual use (one debug "stop" reaching whatever Petrovich is saying
    right now), not a general multi-stream mixer.

    `interrupt()` (`plans/inbound-speech/plan.md` Stage 3 follow-up) is
    `--target local`'s own answer to `POST /stop`: kill whatever `afplay`
    process is currently in flight. `_InFlightTracker` (this module, see
    its own docstring) is what lets `deliver()` tell that intentional kill
    apart from a genuine `afplay` failure once it observes the resulting
    non-zero return code, rather than raising `AudioDeliveryError` either
    way.

    Live-verified 2026-09-20 (Mac, local target, single request): `POST
    /stop` against an in-flight `POST /speak` returned `200` in ~6ms and
    playback stopped -- the interrupt mechanism itself is effectively
    free. That single-request measurement could not have caught the
    concurrency bug above (only one `/speak` was ever in flight); it
    remains the only live number available.

    **Only serviceable because `TTSAdapterServer.open()` runs
    `ThreadingHTTPServer`.** `deliver()` blocks the handling thread until
    `afplay` exits; a single-threaded `HTTPServer` would leave `POST /stop`
    queued behind that same blocked thread and never reach `interrupt()`
    until playback finished on its own -- silently defeating the whole
    point of this method, and the very fact that makes the concurrency bug
    above possible in the first place. Not obvious from this class alone,
    since nothing here chooses the server class; recorded here because
    this is the method load-bearing on that choice, in both directions."""

    def __init__(
        self, spawn: Callable[[str], _PlaybackProcess] = _spawn_afplay
    ) -> None:
        self._spawn = spawn
        self._tracker = _InFlightTracker()

    def deliver(
        self, audio: bytes, urgent: bool, correlation_id: str | None = None
    ) -> None:
        """`correlation_id` is accepted for `AudioSink` protocol parity
        (`plans/voice-latency-instrumentation/plan.md`) and unused here --
        this dev-only local target has no cross-process log for it to
        anchor; `AircraftLayerAudioSink` is the implementation that
        actually forwards it."""
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="audio-adapter-play-")
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio)

            try:
                process = self._spawn(tmp_path)
            except FileNotFoundError as exc:
                raise AudioDeliveryError(
                    "'afplay' binary not found (not on macOS?)"
                ) from exc

            self._tracker.start(process)
            was_interrupted = False
            try:
                _stdout, stderr = process.communicate(timeout=PLAYBACK_TIMEOUT_S)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                process.communicate()
                raise AudioDeliveryError(
                    f"'afplay' timed out after {PLAYBACK_TIMEOUT_S}s"
                ) from exc
            finally:
                was_interrupted = self._tracker.finish(process)

            if process.returncode != 0:
                if was_interrupted:
                    # Expected outcome, not a failure -- interrupt() itself
                    # did this kill. Logged at info, not warning, and never
                    # raised: a normal POST /stop must not surface as a
                    # speech-delivery error on the body-layer side
                    # (AudioAdapterClient.push_speech's caller,
                    # CrewConsole._print, logs any AudioDeliveryError-
                    # turned-500 as a failure it isn't).
                    logger.info(
                        "afplay interrupted by POST /stop (expected, not a failure)"
                    )
                    return
                stderr_text = (stderr or b"").decode("utf-8", errors="replace")
                raise AudioDeliveryError(
                    f"'afplay' exited {process.returncode}: {stderr_text.strip()}"
                )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("could not remove temp file %s", tmp_path, exc_info=True)

    def interrupt(self) -> None:
        """Kill whatever `afplay` process is currently in flight, if any,
        and record it (`_InFlightTracker.interrupt`) so `deliver()` can
        tell that kill apart from a genuine `afplay` failure once it
        observes the resulting non-zero return code. Never raises (same
        posture as `AudioPlaybackSender.interrupt` on the aircraft-layer
        side)."""
        process = self._tracker.interrupt()
        if process is None:
            return
        try:
            process.kill()
        except OSError:
            logger.debug("failed to kill in-flight afplay process", exc_info=True)


# -- Windows sink (`plans/audio-adapter-os-independent/plan.md` Decision 2) --

#: Added to a WAV's own computed duration before `_WinsoundLocalSink.deliver`
#: gives up waiting on asynchronous playback -- `winsound` offers no "is it
#: still playing" query, so this covers device start-up latency and
#: rounding. Own copy of `aircraft-layer/src/collector/audio_sender.py`'s
#: constant of the same name/value (module independence forbids importing
#: it): a hand-synced duplicate, not a precedent to extend elsewhere.
_WIN_PLAYBACK_MARGIN_S: float = 0.25

#: Used when a file's duration cannot be read (a malformed or non-PCM WAV).
#: Own copy of `audio_sender.py`'s constant of the same name/value, same
#: reasoning: wait this long rather than return immediately (which would
#: overlap the next line) or block forever.
_WIN_PLAYBACK_FALLBACK_S: float = 10.0


def _wav_duration_s(path: str) -> float | None:
    """Playback duration of the WAV at `path`, or `None` if it cannot be
    read. Own copy of `audio_sender.py`'s `wav_duration_s` (module
    independence forbids importing it) -- pure stdlib `wave` header read,
    needed for the same reason: `winsound` plays asynchronously, so
    something has to tell the caller how long to wait."""
    try:
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            if rate <= 0:
                return None
            return w.getnframes() / float(rate)
    except (wave.Error, OSError, EOFError):
        return None


class _WinsoundLike(Protocol):
    """Structural subset of `winsound`'s `PlaySound` calls
    `_WinsoundLocalSink` needs -- exists so tests can inject a fake
    implementation and drive deterministic interleaving with no real
    `winsound` call and no real Windows machine (mirrors `_PlaybackProcess`'s
    role for `LocalPlaybackSink` above, and `ptt_source.py`'s fake-`winmm`
    precedent for testing Windows-only logic from a Mac)."""

    def play_async(self, path: str) -> None:
        """Start playing the WAV at `path` asynchronously
        (`winsound.PlaySound(path, SND_FILENAME | SND_ASYNC)`)."""
        ...

    def purge(self) -> None:
        """Stop whatever is currently playing
        (`winsound.PlaySound(None, SND_PURGE)`)."""
        ...


if sys.platform == "win32":
    import winsound

    class _RealWinsound:
        """The real `_WinsoundLike` -- only ever constructed on Windows
        (`_WinsoundLocalSink`'s default), per the static `sys.platform`
        guard this module follows throughout (see `_WinsoundLike`'s
        docstring and `aircraft-layer/src/collector/audio_sender.py`'s own
        `_WinsoundPlayer` for why this must be a static guard, not a
        runtime `try`/`except ImportError`, for `mypy --strict` to pass on
        the Mac dev machine)."""

        def play_async(self, path: str) -> None:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

        def purge(self) -> None:
            winsound.PlaySound(None, winsound.SND_PURGE)

else:

    class _RealWinsound:
        """Non-Windows stand-in -- `winsound` does not exist on this
        platform. Both methods raise `RuntimeError`, caught by
        `_WinsoundLocalSink.deliver`/`interrupt` like any other playback
        failure, so a Mac-run adapter process (never a real deploy target
        for this sink, but useful for tests/dev) degrades rather than
        crashing."""

        def play_async(self, path: str) -> None:
            raise RuntimeError("winsound is only available on Windows")

        def purge(self) -> None:
            raise RuntimeError("winsound is only available on Windows")


class _WinsoundLocalSink:
    """`server.AudioSink` backed by the stdlib `winsound` module -- the
    Windows `--target local` sink (plan Decision 2), a hand-synced copy of
    `aircraft-layer`'s already-verified `_WinsoundPlayer` pattern (module
    independence forbids importing it directly): `SND_FILENAME | SND_ASYNC`
    to start, block the calling thread on a `threading.Event.wait(timeout=
    duration+margin)`, `interrupt()` purges the sound and sets the event so
    the wait ends immediately instead of sitting out the remaining duration.

    **No `_InFlightTracker` equivalent needed** (simplification found while
    reading the code, not assumed -- plan Decision 2): `_InFlightTracker`
    exists solely to disambiguate "we killed `afplay` on purpose" from
    "`afplay` genuinely crashed," because both look like the same non-zero
    exit code. `winsound.PlaySound` has no such ambiguity -- there is no
    subprocess exit code at all, just `Event.wait()` returning either
    because the timeout elapsed (normal completion) or because
    `interrupt()` set it early (interrupted). Both are a clean return from
    `deliver()`; nothing needs to be raised or suppressed.

    Every in-flight wait is tracked in a `set`, not a single slot -- the
    same concurrency reasoning `_InFlightTracker` documents above:
    `ThreadingHTTPServer` allows two `deliver()` calls at once, and a
    single "the" event would let a second `deliver()` silently replace the
    first's event before `interrupt()` could ever reach it.

    **Known, accepted limitation** (recon Finding 5, plan Decision 2):
    `winsound`'s Win32 API has a single global sound slot -- a second
    overlapping `play_async` silently replaces whatever the first was
    playing, unlike `afplay` (independent per process). The pre-empted
    call's own `deliver()` is not told its audio was cut short (nothing
    sets *its* event), so it waits out its own full duration before
    returning -- slower than necessary, never wrong. Accepted because
    `--target local` is the dev-only guaranteed-deliverable path, never the
    live-cockpit path (that is always `--target aircraft-layer`)."""

    def __init__(self, winsound_api: _WinsoundLike | None = None) -> None:
        self._winsound: _WinsoundLike = (
            winsound_api if winsound_api is not None else _RealWinsound()
        )
        self._lock = threading.Lock()
        self._events: set[threading.Event] = set()

    def deliver(
        self, audio: bytes, urgent: bool, correlation_id: str | None = None
    ) -> None:
        """`correlation_id` is accepted for `AudioSink` protocol parity and
        unused here -- see `LocalPlaybackSink.deliver`'s identical note."""
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="audio-adapter-play-")
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(audio)

            done = threading.Event()
            with self._lock:
                self._events.add(done)
            try:
                try:
                    self._winsound.play_async(tmp_path)
                except RuntimeError as exc:
                    raise AudioDeliveryError(str(exc)) from exc
                duration = _wav_duration_s(tmp_path)
                wait_s = (
                    duration + _WIN_PLAYBACK_MARGIN_S
                    if duration is not None
                    else _WIN_PLAYBACK_FALLBACK_S
                )
                done.wait(timeout=wait_s)
            finally:
                with self._lock:
                    self._events.discard(done)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("could not remove temp file %s", tmp_path, exc_info=True)

    def interrupt(self) -> None:
        """Purge whatever `winsound` is currently playing (if anything --
        a clean no-op otherwise, same posture as `LocalPlaybackSink.
        interrupt`) and release every in-flight `deliver()` call's wait
        immediately instead of letting it sit out its own duration."""
        try:
            self._winsound.purge()
        except RuntimeError:
            logger.debug("winsound purge failed (not on Windows?)", exc_info=True)
            return
        with self._lock:
            events = list(self._events)
        for event in events:
            event.set()


def make_local_sink() -> LocalPlaybackSink | _WinsoundLocalSink:
    """Platform-dispatching factory for the `--target local` `AudioSink`
    (plan Decision 2/6) -- `afplay` on macOS/Linux, `winsound` on Windows,
    exactly as `aircraft-layer/src/collector/audio_sender.py` already does
    for `WavPlayer`. `__main__.py` calls this instead of hardcoding either
    class so sink selection stays automatic, not a new `--target` value."""
    if sys.platform == "win32":
        return _WinsoundLocalSink()
    return LocalPlaybackSink()
