"""Tests for `tts_engine.MacSayEngine`.

Run against the real `say` binary rather than a mock, mirroring
`aircraft-layer/tests/test_text_sender.py`'s "real socket, not a double"
posture for anything cheap enough to exercise directly -- `say` is a
standard macOS CLI and this repo's development machine is a Mac (root
`CLAUDE.md` compute-topology note), so this test class only runs where the
engine itself will actually run.
"""

from __future__ import annotations

import pytest

from tts_engine import MacSayEngine, TTSSynthesisError

#: WAV files start with the RIFF/WAVE header regardless of content.
_WAV_MAGIC = b"RIFF"


def test_synthesize_returns_wav_bytes() -> None:
    engine = MacSayEngine()
    audio = engine.synthesize("Watching Charlie one seven.")
    assert audio.startswith(_WAV_MAGIC)
    assert len(audio) > 100


def test_synthesize_different_text_returns_different_audio() -> None:
    engine = MacSayEngine()
    short = engine.synthesize("Contact.")
    long = engine.synthesize(
        "Enemy armor spotted at the crossroad east of the village."
    )
    assert len(long) > len(short)


def test_synthesize_empty_text_raises() -> None:
    engine = MacSayEngine()
    with pytest.raises(TTSSynthesisError):
        engine.synthesize("")


def test_synthesize_whitespace_only_text_raises() -> None:
    engine = MacSayEngine()
    with pytest.raises(TTSSynthesisError):
        engine.synthesize("   ")


def test_synthesize_unknown_voice_falls_back_without_raising() -> None:
    # `say -v <unknown>` silently falls back to the system default voice
    # rather than erroring (confirmed live in this sandbox) -- documented
    # here rather than assumed, since it's the opposite of what a
    # command-line tool typically does with an invalid argument.
    engine = MacSayEngine(voice="Definitely Not A Real Voice Name")
    audio = engine.synthesize("hello")
    assert audio.startswith(_WAV_MAGIC)
