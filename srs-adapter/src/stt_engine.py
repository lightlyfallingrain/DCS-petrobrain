"""Speech-to-text recognition for `srs-adapter`
(`plans/inbound-speech/plan.md` Decision 1).

`STTEngine` is a small `Protocol` -- the mirror image of
`tts_engine.TTSEngine`: one method, WAV bytes in, a `Transcript` out,
raising `STTRecognitionError` on any failure rather than returning an
empty/partial transcript silently. The implementation writes its input to
a temp file and shells out to an **external binary, never a package**
(`srs-adapter/CLAUDE.md` "Tech stack"), exactly as `MacSayEngine` does --
whisper-cli does not read WAV reliably from stdin.

`WhisperCliEngine` is the only implementation. **The protocol is kept
despite having one** for two concrete reasons rather than on the
speculation that another engine might appear: Stage 3 needs a seam to
inject a fake engine into tests without a binary, and whisper model and
decoding variants swap behind it -- the model sweep
(`research/2026-09-19-whisper-model-sweep.md`) is four configurations of
one class.

**A Windows implementation was removed on 2026-09-19, and is not coming
back.** `WindowsSpeechEngine` shelled out to `System.Speech` with a
`Choices` grammar; it was written but never once executed. The reason it
went is structural, not a measurement: `System.Speech` is a
command-and-control recognizer with no real free-dictation mode, and this
project's design is two-tier -- a transmission opening with the wake word
is free speech for the brain layer. Free speech therefore has to reach
whisper regardless, so the LAN audio hop in Decision 2 exists either way,
and a Windows recognizer could only ever have optimised the command tier
while adding a second engine, a second vocabulary to keep in sync, and a
second incompatible confidence scale feeding one set of behaviour bands.

The whisper CLI/JSON contract **is** verified against a real binary
(whisper.cpp 1.9.4, 2026-09-19) -- see
`research/2026-09-19-whisper-contract-and-grammar-probe.md`, and note the
`--grammar-rule` finding recorded in `WhisperCliEngine.transcribe`.
Constrained decoding via `--grammar` exists here but **is not the
project's chosen path**: a grammar cannot decline, so its failures are
confident wrong commands rather than detectable misses. `--prompt` biasing
is what Stage 1 settled on.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class STTRecognitionError(RuntimeError):
    """Raised when an `STTEngine` cannot produce a transcript for the given
    WAV bytes (missing binary, non-zero exit, unparsable output, wrong
    platform). Always carries an actionable message -- what is missing and
    what to do about it -- never a bare traceback from the subprocess
    layer."""


@dataclass(frozen=True)
class Transcript:
    """One recognition result. `confidence` is in `[0.0, 1.0]`; its exact
    meaning is engine-specific (`WhisperCliEngine`'s is an average
    per-token probability if the binary reports one, else a documented
    placeholder) -- `engine` is carried
    precisely so a confidence value is never read without knowing which
    engine produced it.

    `confidence_is_placeholder` is `True` only for `WhisperCliEngine`
    results where no per-token probability was found in the JSON output
    and `confidence` is therefore the documented `1.0` fallback, not a
    real measurement (review finding: this must be visible to a caller,
    not just a debug log line, since Decision 4's confidence-band
    constants are meant to be set from *measured* confidence)."""

    text: str
    confidence: float
    engine: str
    confidence_is_placeholder: bool = False


class STTEngine(Protocol):
    def transcribe(self, wav: bytes) -> Transcript:
        """Return a `Transcript` for `wav` (raw WAV file bytes). Raises
        `STTRecognitionError` on any failure."""
        ...


#: Neither engine's subprocess should hang the bench (or, later, the
#: `/transcribe` server) indefinitely. Generous headroom for a short
#: command clip plus model load time, not a tight budget -- mirrors
#: `tts_engine._SYNTHESIS_TIMEOUT_S`'s reasoning.
_RECOGNITION_TIMEOUT_S = 30.0

#: Default `whisper-cli` binary name, resolved via `PATH` unless an
#: absolute/relative path is supplied.
DEFAULT_WHISPER_BINARY = "whisper-cli"

#: Top-level GBNF rule name passed as whisper-cli's `--grammar-rule`.
#: Must match the rule `vocabulary.to_gbnf()` emits. whisper-cli does not
#: default this to "root" despite its `--help` implying an empty default
#: is fine -- see `WhisperCliEngine.transcribe`.
GRAMMAR_ROOT_RULE = "root"


class WhisperCliEngine:
    """`STTEngine` backed by whisper.cpp's `whisper-cli` CLI.

    Each call writes `wav` to a temp file and runs:

        whisper-cli -m <model> -f <clip.wav> -l en -ojf -of <out>
            --no-timestamps [--grammar <g> --grammar-rule root
                             --grammar-penalty <p>]

    **This command line is verified against whisper.cpp 1.9.4 (Homebrew,
    arm64), 2026-09-19** -- it was written from public documentation and
    flagged unverified when this module was first authored. `-ojf`
    ("output JSON, full") is confirmed to emit `transcription[].text` and
    per-token `tokens[].p`, which is what `Transcript.confidence` reads,
    so the placeholder-confidence fallback below is a guard against a
    future schema change rather than the expected path. `-of <out>`
    writes `<out>.json`, read back and then removed.

    `grammar_path`, when set, is passed as `--grammar` **together with
    `--grammar-rule`** -- see the note at the call site for why the rule
    name is mandatory rather than defaulted. Stage 1's bench runs this
    class both with and without a grammar path and reports them as
    separate rows, since constrained decoding can convert obvious garbage
    into a confident wrong answer (plan's stated risk) rather than only
    helping. That risk is now observed, not hypothetical: on a live
    probe, "scan left" and "watch nearest" came back as exact vocabulary
    matches under grammar (no capitalisation or trailing-period noise),
    while the longer "scan bearing northwest" collapsed to the single
    character "f" -- grammar helping short phrases and destroying a long
    one in the same run. Which effect dominates on the user's own voice
    is exactly what the bench exists to measure.
    """

    def __init__(
        self,
        binary_path: str = DEFAULT_WHISPER_BINARY,
        model_path: str = "",
        grammar_path: str | None = None,
        grammar_penalty: float | None = None,
        prompt: str | None = None,
    ) -> None:
        self._binary_path = binary_path
        self._model_path = model_path
        self._grammar_path = grammar_path
        self._grammar_penalty = grammar_penalty
        self._prompt = prompt

    @staticmethod
    def is_available(binary_path: str = DEFAULT_WHISPER_BINARY) -> bool:
        """Whether `binary_path` resolves to a real executable -- checked
        before instantiating/running, so a bench can skip this engine with
        a clear message instead of a traceback when whisper.cpp is not
        installed."""
        if os.path.isabs(binary_path) or os.sep in binary_path:
            return os.access(binary_path, os.X_OK)
        return shutil.which(binary_path) is not None

    def transcribe(self, wav: bytes) -> Transcript:
        if not self._model_path:
            raise STTRecognitionError(
                "WhisperCliEngine requires a model_path (a GGUF/GGML "
                "whisper.cpp model file, e.g. ggml-base.en.bin)"
            )
        if not wav:
            raise STTRecognitionError("cannot transcribe empty audio")

        wav_fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="srs-adapter-in-")
        out_fd, out_base = tempfile.mkstemp(prefix="srs-adapter-out-")
        os.close(out_fd)
        out_json_path = out_base + ".json"
        try:
            with os.fdopen(wav_fd, "wb") as f:
                f.write(wav)

            command = [
                self._binary_path,
                "-m",
                self._model_path,
                "-f",
                wav_path,
                "-l",
                "en",
                "-ojf",
                "-of",
                out_base,
                "--no-timestamps",
            ]
            if self._prompt is not None:
                # Soft bias, unlike --grammar: makes these words more
                # likely without making anything else impossible, so a
                # mishearing still comes back looking wrong instead of
                # arriving as a confident in-vocabulary command.
                command += ["--prompt", self._prompt]
            if self._grammar_path is not None:
                # `--grammar-rule` is NOT optional, despite whisper-cli's
                # own `--help` showing an empty default. Verified against
                # whisper.cpp 1.9.4: with `--grammar` alone the grammar is
                # loaded and echoed to stderr but never applied to
                # decoding, and `--grammar-penalty` is inert with it. An
                # out-of-vocabulary clip ("the weather is quite nice
                # today") transcribed byte-identically with and without
                # `--grammar`; adding `--grammar-rule root` constrained it
                # immediately. Omitting this makes the bench's
                # with-grammar row a silent duplicate of its without-
                # grammar row -- the run would report "constrained
                # decoding changes nothing" when it was never enabled.
                command += [
                    "--grammar",
                    self._grammar_path,
                    "--grammar-rule",
                    GRAMMAR_ROOT_RULE,
                ]
                if self._grammar_penalty is not None:
                    command += ["--grammar-penalty", str(self._grammar_penalty)]

            result = subprocess.run(
                command,
                capture_output=True,
                timeout=_RECOGNITION_TIMEOUT_S,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise STTRecognitionError(
                    f"'{self._binary_path}' exited {result.returncode}: "
                    f"{stderr.strip()}"
                )
            try:
                with open(out_json_path, encoding="utf-8") as f:
                    payload = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                raise STTRecognitionError(
                    f"could not read/parse '{self._binary_path}' JSON "
                    f"output at {out_json_path}: {exc}"
                ) from exc
            return _parse_whisper_json(payload)
        except FileNotFoundError as exc:
            raise STTRecognitionError(
                f"'{self._binary_path}' binary not found -- install "
                "whisper.cpp and pass --whisper-binary, or add it to PATH"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise STTRecognitionError(
                f"'{self._binary_path}' timed out after {_RECOGNITION_TIMEOUT_S}s"
            ) from exc
        finally:
            for path in (wav_path, out_json_path):
                try:
                    os.remove(path)
                except OSError:
                    logger.debug("could not remove temp file %s", path, exc_info=True)


def _parse_whisper_json(payload: object) -> Transcript:
    """Extract `Transcript` from whisper.cpp's `-ojf` JSON shape --
    `{"transcription": [{"text": ..., "tokens": [{"p": ...}, ...]}, ...]}`
    per whisper.cpp's public output-format docs. **Unverified against a
    real binary run** (module docstring). Falls back to a placeholder
    confidence of `1.0` if no per-token probabilities are present, rather
    than raising -- a missing confidence figure should degrade the bench's
    numbers, not crash it, but it is surfaced via
    `Transcript.confidence_is_placeholder` so a caller (`tools/
    stt_bench.py`'s `print_report`) can warn rather than silently trust it.

    Every level of `payload` is `isinstance`-checked before use (review
    finding: a non-dict root, or a non-dict segment/token, used to raise a
    bare `AttributeError` from `.get()` instead of a clear
    `STTRecognitionError` -- exactly the kind of failure that could be
    misread as "the recognizer did badly" rather than "the JSON shape
    assumption was wrong")."""
    if not isinstance(payload, dict):
        raise STTRecognitionError(
            f"unexpected whisper.cpp JSON shape: root is {type(payload).__name__}, "
            f"not an object: {payload!r}"
        )
    segments = payload.get("transcription", [])
    if not isinstance(segments, list):
        raise STTRecognitionError(
            "unexpected whisper.cpp JSON shape: 'transcription' is "
            f"{type(segments).__name__}, not a list: {segments!r}"
        )

    texts: list[str] = []
    token_probs: list[float] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise STTRecognitionError(
                "unexpected whisper.cpp JSON shape: a 'transcription' "
                f"entry is {type(segment).__name__}, not an object: {segment!r}"
            )
        text = segment.get("text", "")
        if isinstance(text, str):
            texts.append(text)
        for token in segment.get("tokens", []):
            if not isinstance(token, dict):
                raise STTRecognitionError(
                    "unexpected whisper.cpp JSON shape: a 'tokens' entry "
                    f"is {type(token).__name__}, not an object: {token!r}"
                )
            p = token.get("p")
            if isinstance(p, (int, float)):
                token_probs.append(float(p))

    full_text = " ".join(t.strip() for t in texts if t.strip()).strip()
    confidence_is_placeholder = not token_probs
    confidence = sum(token_probs) / len(token_probs) if token_probs else 1.0
    if confidence_is_placeholder:
        logger.debug(
            "whisper.cpp JSON carried no per-token probabilities; "
            "using placeholder confidence 1.0"
        )
    return Transcript(
        text=full_text,
        confidence=confidence,
        engine="whisper-cli",
        confidence_is_placeholder=confidence_is_placeholder,
    )
