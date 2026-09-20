"""`LocalPlaybackSink` -- `--target local`'s `server.AudioSink` implementation
(`plans/tts-voice-output/plan.md` Decision 8): plays synthesized WAV bytes
directly on this machine via `afplay`, an already-present macOS CLI (the
same "external binary, not a package" rule `tts_engine.MacSayEngine`
follows for `say`).

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
import tempfile
import threading
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

    def deliver(self, audio: bytes, urgent: bool) -> None:
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
