"""The press-to-talk loop: edges in, clips out.

`plans/inbound-speech/plan.md` Stage 4. Everything this module does is
edge detection and sequencing, which is exactly why it is its own class
rather than a `while True` in the entrypoint: the sequencing is where the
bugs are (a clip started twice, a release that never stops the recorder,
a tail that swallows the next press), and none of it needs a microphone,
a joystick or a network to test.

The collaborators are all injected and all have fakes in the tests: a
`PTTSource`, a recorder, a `ClipGate`, and something that ships the WAV.
The loop itself never imports sox, winmm or `urllib`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from audio_capture import DEFAULT_MAX_CLIP_S, DEFAULT_TAIL_S, Clip, ClipGate
from ptt_source import PTTSource


class Recorder(Protocol):
    """What the loop needs from a recorder. `SoxRecorder` satisfies it."""

    def start(self) -> None: ...

    def stop(self) -> Clip: ...

    def abort(self) -> None: ...


class ClipSink(Protocol):
    """Where an accepted clip goes. `TranscribeClient.transcribe` fits."""

    def __call__(self, wav: bytes) -> None: ...


@dataclass(frozen=True)
class CaptureEvent:
    """One thing that happened, for the entrypoint to print.

    The loop reports rather than prints, so the tests can assert on what
    happened without capturing stdout, and so a future caller (a GUI, a
    log file) is not forced through a console.
    """

    kind: str  # "press" | "sent" | "dropped" | "error"
    detail: str = ""


class CaptureLoop:
    """Turns PTT edges into posted clips.

    **The tail is the one piece of real timing knowledge here.** Recording
    continues briefly past the release because a speaker lets go as the
    final syllable ends, not after it -- and the final word is usually the
    one carrying the meaning ("scan EAST"). Its cost is that a very fast
    second press lands inside the previous clip's tail; at 0.4 s that is
    not a gesture anyone makes deliberately, and the alternative -- losing
    the last word of every command -- is far worse.

    **A failure to send is reported, never raised.** A clip that cannot
    reach the adapter must not take the capture process down with it: the
    player is flying, and the recovery for one lost command is to say it
    again, not to alt-tab and restart a process.
    """

    def __init__(
        self,
        ptt: PTTSource,
        recorder: Recorder,
        gate: ClipGate,
        sink: ClipSink,
        tail_s: float = DEFAULT_TAIL_S,
        sleep: Callable[[float], None] = time.sleep,
        discard_if: Callable[[], bool] | None = None,
        max_hold_s: float = DEFAULT_MAX_CLIP_S + 3.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ptt = ptt
        self._recorder = recorder
        self._gate = gate
        self._sink = sink
        self._tail_s = tail_s
        self._sleep = sleep
        # Asked once, at release: "was this clip addressed to the crew
        # after all?" Only `DcsPTT` supplies it, and only for one case --
        # the player took the trigger to its full-press stop mid-utterance.
        # **What that stop does depends on the setup, and the invariant
        # holds for both**: with VOIP it transmits to someone else, and
        # without it it opens the DCS radio menu. Either way it is not
        # speech aimed at the crew, which is all this hook needs to be
        # true. It is a separate hook
        # rather than part of `PTTSource` because the joystick and keyboard
        # sources have nothing to say about it, and widening the protocol
        # for one implementation would make both of them carry a method
        # that always answers False.
        self._discard_if = discard_if
        # The guard for a release that never arrives (user, 2026-09-23).
        # sox stops itself at `max_clip_s` via its own `trim`, so the audio
        # device is never held open forever -- but this loop would still
        # believe it was recording, and would then post whatever sox left
        # behind as if the player had finished speaking. A wedged PTT feed,
        # a DCS crash mid-press, or a trigger that sticks all produce
        # exactly that. The ceiling sits above `max_clip_s` deliberately:
        # the ordinary end of a long press is sox's own limit, and this
        # only fires when the *release* is what went missing.
        self._max_hold_s = max_hold_s
        self._monotonic = monotonic
        self._started_at: float | None = None
        self._recording = False

    @property
    def recording(self) -> bool:
        return self._recording

    def tick(self) -> list[CaptureEvent]:
        """Poll the PTT once and act on any edge. Never raises for an
        ordinary failure -- capture failures and send failures both come
        back as `error` events, so one bad clip costs one command."""
        events: list[CaptureEvent] = []
        down = self._ptt.is_down()

        if down and not self._recording:
            try:
                self._recorder.start()
            except Exception as exc:  # noqa: BLE001 -- see class docstring
                return [CaptureEvent("error", f"could not start recording: {exc}")]
            self._recording = True
            self._started_at = self._monotonic()
            return [CaptureEvent("press", "recording")]

        if down and self._recording and self._started_at is not None:
            held = self._monotonic() - self._started_at
            if held >= self._max_hold_s:
                self._recording = False
                self._started_at = None
                self._recorder.abort()
                return [
                    CaptureEvent(
                        "error",
                        f"held {held:.0f}s with no release -- clip discarded, "
                        "talk control may be stuck",
                    )
                ]
            return []

        if not down and self._recording:
            # The tail runs before the stop, inside the loop's own tick,
            # so nothing else can start a new clip during it.
            self._sleep(self._tail_s)
            self._recording = False
            self._started_at = None
            try:
                clip = self._recorder.stop()
            except Exception as exc:  # noqa: BLE001 -- see class docstring
                return [CaptureEvent("error", f"capture failed: {exc}")]
            if self._discard_if is not None and self._discard_if():
                return [
                    CaptureEvent("dropped", "full press -- not addressed to the crew")
                ]
            verdict = self._gate.assess(clip)
            if not verdict.accepted:
                return [CaptureEvent("dropped", verdict.reason or "rejected")]
            try:
                self._sink(clip.wav)
            except Exception as exc:  # noqa: BLE001 -- see class docstring
                return [CaptureEvent("error", f"send failed: {exc}")]
            events.append(
                CaptureEvent("sent", f"{clip.duration_s:.2f}s, peak {clip.peak:.2f}")
            )

        return events

    def shutdown(self) -> None:
        """Stop any in-flight recording and discard it. Called on exit --
        a clip the player never finished is not a command."""
        if not self._recording:
            return
        self._recording = False
        self._started_at = None
        try:
            self._recorder.stop()
        except Exception:  # noqa: BLE001 -- nothing useful to do while exiting
            return
