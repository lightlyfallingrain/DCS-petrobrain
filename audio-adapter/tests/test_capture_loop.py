"""The press-to-talk loop's edge handling, with every collaborator faked.

No microphone, no joystick, no network. That is the point of
`CaptureLoop` being its own class: the sequencing bugs it can have --
starting a clip twice, a release that never stops the recorder, a failure
that takes the process down -- are all reproducible here in milliseconds.
"""

from __future__ import annotations

import pytest

from audio_capture import Clip, ClipGate
from capture_loop import CaptureLoop


class FakePTT:
    """A scripted PTT: `down` is set by the test between ticks."""

    def __init__(self) -> None:
        self.down = False

    def is_down(self) -> bool:
        return self.down


class FakeRecorder:
    def __init__(self, clip: Clip | None = None) -> None:
        self.clip = clip or Clip(wav=b"RIFFfake", duration_s=1.2, peak=0.4)
        self.starts = 0
        self.stops = 0
        self.start_error: Exception | None = None
        self.stop_error: Exception | None = None

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.starts += 1

    def stop(self) -> Clip:
        self.stops += 1
        if self.stop_error is not None:
            raise self.stop_error
        return self.clip


class FakeSink:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.error: Exception | None = None

    def __call__(self, wav: bytes) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(wav)


def build(
    recorder: FakeRecorder | None = None,
    sink: FakeSink | None = None,
    gate: ClipGate | None = None,
) -> tuple[CaptureLoop, FakePTT, FakeRecorder, FakeSink, list[float]]:
    ptt = FakePTT()
    rec = recorder or FakeRecorder()
    snk = sink or FakeSink()
    slept: list[float] = []
    loop = CaptureLoop(
        ptt=ptt,
        recorder=rec,
        gate=gate or ClipGate(),
        sink=snk,
        tail_s=0.4,
        sleep=slept.append,
    )
    return loop, ptt, rec, snk, slept


def test_press_starts_recording_once_and_release_sends() -> None:
    loop, ptt, rec, sink, _ = build()

    ptt.down = True
    assert [event.kind for event in loop.tick()] == ["press"]
    assert loop.recording

    # Held across several polls: exactly one start, nothing sent yet.
    assert loop.tick() == []
    assert loop.tick() == []
    assert rec.starts == 1
    assert sink.sent == []

    ptt.down = False
    events = loop.tick()
    assert [event.kind for event in events] == ["sent"]
    assert sink.sent == [b"RIFFfake"]
    assert not loop.recording


def test_idle_polls_do_nothing() -> None:
    loop, _, rec, sink, _ = build()
    for _ in range(5):
        assert loop.tick() == []
    assert rec.starts == 0
    assert sink.sent == []


def test_tail_is_slept_before_stopping() -> None:
    """The tail exists to keep the last syllable -- so it must happen
    before the recorder is stopped, not after."""
    loop, ptt, _, _, slept = build()
    ptt.down = True
    loop.tick()
    ptt.down = False
    loop.tick()
    assert slept == [0.4]


def test_short_clip_is_dropped_with_a_reason() -> None:
    recorder = FakeRecorder(Clip(wav=b"x", duration_s=0.1, peak=0.5))
    loop, ptt, _, sink, _ = build(recorder=recorder)
    ptt.down = True
    loop.tick()
    ptt.down = False
    events = loop.tick()
    assert [event.kind for event in events] == ["dropped"]
    assert "too short" in events[0].detail
    assert sink.sent == []


def test_quiet_clip_is_dropped_and_names_the_input_device() -> None:
    """A silent clip is a wrong-microphone symptom, and saying so is the
    whole reason the gate returns a reason rather than a bool -- it would
    otherwise be diagnosed as a recognition failure."""
    recorder = FakeRecorder(Clip(wav=b"x", duration_s=2.0, peak=0.001))
    loop, ptt, _, sink, _ = build(recorder=recorder)
    ptt.down = True
    loop.tick()
    ptt.down = False
    events = loop.tick()
    assert [event.kind for event in events] == ["dropped"]
    assert "too quiet" in events[0].detail
    assert "input device" in events[0].detail
    assert sink.sent == []


def test_send_failure_is_reported_not_raised() -> None:
    sink = FakeSink()
    sink.error = RuntimeError("adapter unreachable")
    loop, ptt, _, _, _ = build(sink=sink)
    ptt.down = True
    loop.tick()
    ptt.down = False
    events = loop.tick()
    assert [event.kind for event in events] == ["error"]
    assert "adapter unreachable" in events[0].detail
    # And the loop is still usable afterwards: one lost command must not
    # cost the process.
    assert not loop.recording
    ptt.down = True
    assert [event.kind for event in loop.tick()] == ["press"]


def test_capture_failure_is_reported_and_clears_recording_state() -> None:
    recorder = FakeRecorder()
    recorder.stop_error = RuntimeError("sox produced nothing")
    loop, ptt, _, _, _ = build(recorder=recorder)
    ptt.down = True
    loop.tick()
    ptt.down = False
    events = loop.tick()
    assert [event.kind for event in events] == ["error"]
    assert not loop.recording


def test_start_failure_leaves_the_loop_idle() -> None:
    recorder = FakeRecorder()
    recorder.start_error = RuntimeError("no such device")
    loop, ptt, _, _, _ = build(recorder=recorder)
    ptt.down = True
    events = loop.tick()
    assert [event.kind for event in events] == ["error"]
    assert not loop.recording
    # Still down on the next poll: it retries rather than latching off.
    assert [event.kind for event in loop.tick()] == ["error"]


def test_shutdown_stops_an_in_flight_recording() -> None:
    loop, ptt, rec, sink, _ = build()
    ptt.down = True
    loop.tick()
    loop.shutdown()
    assert rec.stops == 1
    assert sink.sent == []
    assert not loop.recording


def test_shutdown_is_a_no_op_when_idle() -> None:
    loop, _, rec, _, _ = build()
    loop.shutdown()
    assert rec.stops == 0


def test_shutdown_swallows_a_recorder_failure() -> None:
    recorder = FakeRecorder()
    recorder.stop_error = RuntimeError("already gone")
    loop, ptt, _, _, _ = build(recorder=recorder)
    ptt.down = True
    loop.tick()
    loop.shutdown()  # must not raise on the way out


def test_ptt_failure_propagates() -> None:
    """A PTT that cannot be read at all is not an ordinary bad clip --
    the talk control is gone, and silently polling a dead device would
    look identical to nobody speaking."""

    class DeadPTT:
        def is_down(self) -> bool:
            raise RuntimeError("unplugged")

    loop = CaptureLoop(
        ptt=DeadPTT(),
        recorder=FakeRecorder(),
        gate=ClipGate(),
        sink=FakeSink(),
    )
    with pytest.raises(RuntimeError, match="unplugged"):
        loop.tick()
