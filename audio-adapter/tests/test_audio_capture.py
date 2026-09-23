"""Clip measurement and the gate, plus the sox argument ordering.

`SoxRecorder` itself is not exercised against a real microphone -- there
is no device in CI and no way to assert on what it heard. What *is*
tested is everything around it that can be wrong silently: the peak and
duration a clip is judged on, the gate's two rejections, and the input
argument order, which is load-bearing (flags after the input spec
describe the output file, and that is what makes sox resample a 48 kHz
mic down to the 16 kHz whisper.cpp requires).
"""

from __future__ import annotations

import io
import math
import struct
import wave

import pytest

from audio_capture import (
    SAMPLE_RATE,
    CaptureError,
    Clip,
    ClipGate,
    SoxRecorder,
    input_args,
    sox_available,
    wav_peak_and_duration,
)


def make_wav(duration_s: float, amplitude: float, rate: int = SAMPLE_RATE) -> bytes:
    """A mono 16-bit PCM sine at a known amplitude and length."""
    frames = int(duration_s * rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(
            b"".join(
                struct.pack(
                    "<h",
                    int(amplitude * 32767 * math.sin(2 * math.pi * 440 * n / rate)),
                )
                for n in range(frames)
            )
        )
    return buffer.getvalue()


def test_peak_and_duration_read_back_what_was_written() -> None:
    wav = make_wav(duration_s=1.0, amplitude=0.5)
    peak, duration = wav_peak_and_duration(wav)
    assert duration == 1.0
    assert 0.48 < peak < 0.52


def test_duration_follows_the_sample_rate_not_the_byte_count() -> None:
    wav = make_wav(duration_s=0.5, amplitude=0.3, rate=8000)
    _, duration = wav_peak_and_duration(wav)
    assert 0.49 < duration < 0.51


def test_silence_reads_as_zero_peak() -> None:
    peak, duration = wav_peak_and_duration(make_wav(duration_s=0.8, amplitude=0.0))
    assert peak == 0.0
    assert 0.79 < duration < 0.81


def test_gate_accepts_an_ordinary_utterance() -> None:
    verdict = ClipGate().assess(Clip(wav=b"", duration_s=1.4, peak=0.35))
    assert verdict.accepted
    assert verdict.reason is None


def test_gate_rejects_a_brushed_button() -> None:
    verdict = ClipGate().assess(Clip(wav=b"", duration_s=0.12, peak=0.4))
    assert not verdict.accepted
    assert "too short" in (verdict.reason or "")


def test_gate_rejects_a_dead_microphone() -> None:
    verdict = ClipGate().assess(Clip(wav=b"", duration_s=2.0, peak=0.004))
    assert not verdict.accepted
    assert "too quiet" in (verdict.reason or "")


def test_gate_checks_duration_before_level() -> None:
    """A clip that fails both should report the one the player can act
    on: a press too short to contain speech is also too short to have
    measured a fair level from."""
    verdict = ClipGate().assess(Clip(wav=b"", duration_s=0.05, peak=0.0))
    assert "too short" in (verdict.reason or "")


def test_gate_thresholds_are_configurable() -> None:
    gate = ClipGate(min_duration_s=0.05, min_peak=0.0)
    assert gate.assess(Clip(wav=b"", duration_s=0.1, peak=0.0)).accepted


def test_input_args_default_to_the_default_device() -> None:
    assert input_args(None, None)[-1] == "-d"


def test_input_args_name_a_driver_before_the_device() -> None:
    """Order matters to sox: `-t <driver>` describes the input that
    follows it."""
    assert input_args("waveaudio", "Headset") == ["-t", "waveaudio", "Headset"]


def test_input_args_take_a_device_without_a_driver() -> None:
    assert input_args(None, "2") == ["2"]


def test_sox_available_accepts_an_absolute_path() -> None:
    """`shutil.which` resolves an absolute path as well as a bare name, so
    one check covers both -- which is what lets `--sox-binary` take a full
    Windows path without a second code path."""
    import sys

    assert sox_available(sys.executable) is True


def test_sox_available_reports_a_missing_binary() -> None:
    assert sox_available("definitely-not-a-real-binary-name") is False


def test_the_recorder_reports_which_binary_it_could_not_find() -> None:
    """The error names the binary rather than saying "sox": when the path
    was passed explicitly and is wrong, the wrong path is the thing worth
    seeing."""
    recorder = SoxRecorder(sox_binary="/nonexistent/sox")
    with pytest.raises(CaptureError, match="/nonexistent/sox"):
        recorder.start()


def test_the_recorder_hints_at_the_wsl_path_trap() -> None:
    """A Windows Python launched from WSL inherits WSL's PATH, so sox is
    installed, working, and invisible. Without the hint that reads as "sox
    is broken"."""
    recorder = SoxRecorder(sox_binary="/nonexistent/sox")
    with pytest.raises(CaptureError, match="WSL"):
        recorder.start()
