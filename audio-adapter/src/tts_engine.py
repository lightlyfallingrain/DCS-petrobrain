"""Text-to-speech synthesis for `audio-adapter` (`plans/tts-voice-output/plan.md`
Decision 2).

`TTSEngine` is a small `Protocol` -- one method, `synthesize(text) -> bytes`
returning a WAV file's raw bytes -- so `server.py` never has to know which
engine is behind it. The plan's stated reason for the seam: measured macOS
`say` latency (~0.6-0.8s) is fine for this slice, but Windows SAPI is
unmeasured, and a `WindowsSapiEngine` (or any future engine) should drop in
without touching the HTTP layer.

`MacSayEngine` is this slice's only implementation, an external-binary
subprocess call (`say`), not a package dependency -- consistent with this
project's stdlib-only-code / external-binaries-for-real-work policy (the
same reasoning `text_sender.py` and `command_sender.py` follow for UDP, and
`__main__.py`'s `--target local` mode follows for `afplay`).
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Protocol

logger = logging.getLogger(__name__)

#: `say`'s own voice selection -- a generic English voice for this slice
#: (plan Decision 7: a Russian-accented character voice is an explicit,
#: deferred future item, not scoped here).
DEFAULT_VOICE = "Daniel"

#: `say --data-format=LEI16@22050` writes 16-bit PCM mono WAV directly --
#: no conversion step needed before the bytes reach a Windows `winsound`
#: playback path (recon finding, `research/2026-09-17-tts-audio-transport-
#: recon.md`).
_DATA_FORMAT = "LEI16@22050"

#: `say`'s own subprocess should never hang the server indefinitely --
#: recon measured ~0.6-0.8s for short callouts, so this is generous
#: headroom, not a tight budget.
_SYNTHESIS_TIMEOUT_S = 10.0


class TTSSynthesisError(RuntimeError):
    """Raised when a `TTSEngine` cannot produce audio for the given text
    (missing binary, non-zero exit, unreadable/empty output)."""


class TTSEngine(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Return WAV file bytes for `text`. Raises `TTSSynthesisError` on
        any failure -- never returns empty/partial bytes silently."""
        ...


class MacSayEngine:
    """`TTSEngine` backed by macOS's `say` CLI, per the plan's Decision 2.

    Each call spawns `say -v <voice> -o <tmp>.wav --data-format=LEI16@22050
    <text>`, then reads the written file back into memory and removes it --
    `say` only writes to a real file path, it has no stdout-WAV mode."""

    def __init__(self, voice: str = DEFAULT_VOICE) -> None:
        self._voice = voice

    def synthesize(self, text: str) -> bytes:
        if not text.strip():
            raise TTSSynthesisError("cannot synthesize empty text")

        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="audio-adapter-")
        os.close(fd)
        try:
            result = subprocess.run(
                [
                    "say",
                    "-v",
                    self._voice,
                    "-o",
                    tmp_path,
                    f"--data-format={_DATA_FORMAT}",
                    text,
                ],
                capture_output=True,
                timeout=_SYNTHESIS_TIMEOUT_S,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise TTSSynthesisError(
                    f"'say' exited {result.returncode}: {stderr.strip()}"
                )
            try:
                with open(tmp_path, "rb") as f:
                    audio = f.read()
            except OSError as exc:
                raise TTSSynthesisError(f"could not read 'say' output: {exc}") from exc
            if not audio:
                raise TTSSynthesisError("'say' produced an empty WAV file")
            return audio
        except FileNotFoundError as exc:
            raise TTSSynthesisError("'say' binary not found (not on macOS?)") from exc
        except subprocess.TimeoutExpired as exc:
            raise TTSSynthesisError(
                f"'say' timed out after {_SYNTHESIS_TIMEOUT_S}s"
            ) from exc
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("could not remove temp file %s", tmp_path, exc_info=True)
