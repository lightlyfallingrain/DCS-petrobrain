"""Tests for `stt_engine.WhisperCliEngine`.

`WhisperCliEngine` is exercised against the **real** `whisper-cli` binary
and a committed short WAV fixture, following `test_tts_engine.py`'s
real-binary posture -- but unlike `say`, whisper.cpp is **not** guaranteed
present on every dev machine, so every test in that class skips cleanly
(`pytest.skip`, not a failure) when the binary or a model file is absent,
via `--whisper-binary`/`--whisper-model` pytest options with documented
directly (no subprocess call needed for that part); its real
`powershell.exe` path is untestable from this Mac-only dev environment and
is not exercised here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from stt_engine import (
    GRAMMAR_ROOT_RULE,
    STTRecognitionError,
    Transcript,
    WhisperCliEngine,
    _parse_whisper_json,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_SAMPLE_WAV_PATH = _FIXTURES_DIR / "sample.wav"

#: Overridable via environment variables so a dev machine that has
#: whisper.cpp installed somewhere non-standard can point at it without
#: editing this file -- mirrors `--whisper-binary`/`--whisper-model`
#: (`audio-adapter/src/audio_adapter/__main__.py`'s later flags), kept
#: independent of argparse here since pytest doesn't parse this project's
#: own CLI args.
_WHISPER_BINARY = os.environ.get("AUDIO_ADAPTER_WHISPER_BINARY", "whisper-cli")
_WHISPER_MODEL = os.environ.get("AUDIO_ADAPTER_WHISPER_MODEL", "")


def _whisper_ready() -> bool:
    return WhisperCliEngine.is_available(_WHISPER_BINARY) and bool(_WHISPER_MODEL)


@pytest.mark.skipif(
    not _whisper_ready(),
    reason=(
        "whisper-cli binary and/or a model file not available -- set "
        "AUDIO_ADAPTER_WHISPER_BINARY/AUDIO_ADAPTER_WHISPER_MODEL to run this "
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


def test_parse_whisper_json_nondict_root_raises_recognition_error() -> None:
    with pytest.raises(STTRecognitionError, match="root is"):
        _parse_whisper_json(["oops"])


def test_parse_whisper_json_nondict_transcription_value_raises() -> None:
    with pytest.raises(STTRecognitionError, match="'transcription'"):
        _parse_whisper_json({"transcription": "not a list"})


def test_parse_whisper_json_nondict_segment_raises() -> None:
    with pytest.raises(STTRecognitionError, match="transcription.*entry"):
        _parse_whisper_json({"transcription": ["scan left"]})


def test_parse_whisper_json_nondict_token_raises() -> None:
    with pytest.raises(STTRecognitionError, match="tokens.*entry"):
        _parse_whisper_json(
            {"transcription": [{"text": "scan left", "tokens": ["not a token"]}]}
        )


def test_parse_whisper_json_with_token_probs_is_not_placeholder() -> None:
    transcript = _parse_whisper_json(
        {
            "transcription": [
                {
                    "text": "scan left",
                    "tokens": [{"p": 0.9}, {"p": 0.8}],
                }
            ]
        }
    )
    assert transcript.text == "scan left"
    assert transcript.confidence == pytest.approx(0.85)
    assert transcript.confidence_is_placeholder is False


def test_parse_whisper_json_without_token_probs_is_placeholder() -> None:
    transcript = _parse_whisper_json(
        {"transcription": [{"text": "scan left", "tokens": []}]}
    )
    assert transcript.confidence == 1.0
    assert transcript.confidence_is_placeholder is True


def test_grammar_run_passes_grammar_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--grammar` alone does not constrain decoding; the rule name is required.

    Verified against whisper.cpp 1.9.4: passing `--grammar` without
    `--grammar-rule` loads and echoes the grammar but leaves decoding
    completely unconstrained, and silently so -- an out-of-vocabulary
    clip transcribes byte-identically with and without the flag. That
    failure mode is invisible in the bench's own output: the with-grammar
    row would simply duplicate the without-grammar row, and the run would
    be read as "constrained decoding makes no difference here" rather
    than "constrained decoding never ran."

    So this asserts the flag pairing directly, without needing a binary.
    """
    captured: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured.append(command)
        raise AssertionError("stop after capturing the command line")

    monkeypatch.setattr(subprocess, "run", fake_run)

    grammar = tmp_path / "v.gbnf"
    grammar.write_text('root ::= "scan left"\n')
    engine = WhisperCliEngine(
        model_path=str(tmp_path / "model.bin"),
        grammar_path=str(grammar),
    )
    with pytest.raises((AssertionError, STTRecognitionError)):
        engine.transcribe(b"\x00" * 64)

    assert captured, "whisper-cli was never invoked"
    command = captured[0]
    assert "--grammar" in command
    assert "--grammar-rule" in command, (
        "--grammar without --grammar-rule leaves decoding unconstrained"
    )
    assert command[command.index("--grammar-rule") + 1] == GRAMMAR_ROOT_RULE
