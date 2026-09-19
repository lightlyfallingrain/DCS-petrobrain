"""Tests for `stt_engine.WhisperCliEngine`/`WindowsSpeechEngine`.

`WhisperCliEngine` is exercised against the **real** `whisper-cli` binary
and a committed short WAV fixture, following `test_tts_engine.py`'s
real-binary posture -- but unlike `say`, whisper.cpp is **not** guaranteed
present on every dev machine, so every test in that class skips cleanly
(`pytest.skip`, not a failure) when the binary or a model file is absent,
via `--whisper-binary`/`--whisper-model` pytest options with documented
fallbacks. `WindowsSpeechEngine`'s platform-gated behaviour is tested
directly (no subprocess call needed for that part); its real
`powershell.exe` path is untestable from this Mac-only dev environment and
is not exercised here.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from stt_engine import (
    STTRecognitionError,
    Transcript,
    WhisperCliEngine,
    WindowsSpeechEngine,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_SAMPLE_WAV_PATH = _FIXTURES_DIR / "sample.wav"

#: Overridable via environment variables so a dev machine that has
#: whisper.cpp installed somewhere non-standard can point at it without
#: editing this file -- mirrors `--whisper-binary`/`--whisper-model`
#: (`srs-adapter/src/srs_adapter/__main__.py`'s later flags), kept
#: independent of argparse here since pytest doesn't parse this project's
#: own CLI args.
_WHISPER_BINARY = os.environ.get("SRS_ADAPTER_WHISPER_BINARY", "whisper-cli")
_WHISPER_MODEL = os.environ.get("SRS_ADAPTER_WHISPER_MODEL", "")


def _whisper_ready() -> bool:
    return WhisperCliEngine.is_available(_WHISPER_BINARY) and bool(_WHISPER_MODEL)


@pytest.mark.skipif(
    not _whisper_ready(),
    reason=(
        "whisper-cli binary and/or a model file not available -- set "
        "SRS_ADAPTER_WHISPER_BINARY/SRS_ADAPTER_WHISPER_MODEL to run this "
        "test class for real"
    ),
)
class TestWhisperCliEngineReal:
    def test_transcribe_returns_transcript(self) -> None:
        engine = WhisperCliEngine(
            binary_path=_WHISPER_BINARY, model_path=_WHISPER_MODEL
        )
        wav = _SAMPLE_WAV_PATH.read_bytes()
        transcript = engine.transcribe(wav)
        assert isinstance(transcript, Transcript)
        assert transcript.engine == "whisper-cli"
        assert 0.0 <= transcript.confidence <= 1.0


def test_is_available_false_for_unknown_binary() -> None:
    assert WhisperCliEngine.is_available("definitely-not-a-real-binary") is False


def test_is_available_true_for_known_binary_on_path() -> None:
    # Any binary guaranteed present is enough to prove the PATH-resolution
    # branch works -- doesn't need to be whisper-cli itself.
    known = shutil.which("python3") or shutil.which("sh")
    assert known is not None
    assert WhisperCliEngine.is_available(known) is True


def test_transcribe_without_model_path_raises() -> None:
    engine = WhisperCliEngine(binary_path=_WHISPER_BINARY, model_path="")
    with pytest.raises(STTRecognitionError):
        engine.transcribe(_SAMPLE_WAV_PATH.read_bytes())


def test_transcribe_empty_audio_raises() -> None:
    engine = WhisperCliEngine(binary_path=_WHISPER_BINARY, model_path="dummy.bin")
    with pytest.raises(STTRecognitionError):
        engine.transcribe(b"")


def test_transcribe_missing_binary_raises_actionable_error() -> None:
    engine = WhisperCliEngine(
        binary_path="definitely-not-a-real-binary", model_path="dummy.bin"
    )
    with pytest.raises(STTRecognitionError, match="not found"):
        engine.transcribe(_SAMPLE_WAV_PATH.read_bytes())


def test_windows_speech_engine_requires_phrases() -> None:
    with pytest.raises(ValueError):
        WindowsSpeechEngine(phrases=())


def test_windows_speech_engine_not_available_on_this_platform() -> None:
    # This test suite runs on macOS/Linux dev machines; on any such host
    # WindowsSpeechEngine must report itself unavailable rather than a
    # caller discovering that only after a failed subprocess call.
    assert WindowsSpeechEngine.is_available() is False


def test_windows_speech_engine_transcribe_raises_off_windows() -> None:
    engine = WindowsSpeechEngine(phrases=("scan left", "scan right"))
    with pytest.raises(STTRecognitionError, match="Windows"):
        engine.transcribe(_SAMPLE_WAV_PATH.read_bytes())
