"""Speech-to-text recognition for `srs-adapter`
(`plans/inbound-speech/plan.md` Decision 1).

`STTEngine` is a small `Protocol` -- the mirror image of
`tts_engine.TTSEngine`: one method, WAV bytes in, a `Transcript` out,
raising `STTRecognitionError` on any failure rather than returning an
empty/partial transcript silently. Both implementations write their input
to a temp file and shell out to an **external binary, never a package**
(`srs-adapter/CLAUDE.md` "Tech stack"), exactly as `MacSayEngine` does --
neither candidate binary reads WAV reliably from stdin.

- `WhisperCliEngine` -- the preferred implementation, on both hosts. Shells
  out to whisper.cpp's `whisper-cli`. Supports constrained decoding via
  `--grammar` (a GBNF grammar, e.g. `vocabulary.to_gbnf()`), which is the
  strongest form of vocabulary-biasing this project has available --
  restricting the decoder to admit only the 15-token vocabulary's
  phrasings, converting the task from open transcription to closed
  classification inside the recognizer itself.
- `WindowsSpeechEngine` -- the required Windows baseline, zero install.
  Shells out to `powershell.exe` driving `System.Speech.Recognition.
  SpeechRecognitionEngine` with a `Choices` grammar. Windows-only by
  construction -- `transcribe` raises `STTRecognitionError` immediately on
  any other platform rather than attempting (and failing) the subprocess
  call, so a bench run on the Mac can detect and skip it cleanly.

**Neither engine's exact CLI/JSON contract was verified against a live
binary while writing this** -- no `whisper-cli` binary and no Windows box
were available in this environment (`srs-adapter/tests/test_stt_engine.py`
skips for the same reason). Both are written from each tool's public,
documented CLI surface. This is precisely what Stage 1's bench
(`tools/stt_bench.py`) exists to validate once the user runs it against
real binaries -- see each class's own docstring for the specific
assumptions to check first if a real run behaves unexpectedly.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
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
    placeholder; `WindowsSpeechEngine`'s is `System.Speech`'s own
    `RecognitionResult.Confidence` verbatim) -- `engine` is carried
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


class WhisperCliEngine:
    """`STTEngine` backed by whisper.cpp's `whisper-cli` CLI.

    Each call writes `wav` to a temp file and runs:

        whisper-cli -m <model> -f <clip.wav> -l en -ojf -of <out>
            --no-timestamps [--grammar <grammar> --grammar-penalty <p>]

    `-ojf` ("output JSON, full") is requested rather than plain `-oj` so
    per-token probabilities are available for `Transcript.confidence` --
    **unverified flag name**, see module docstring. `-of <out>` writes
    `<out>.json`, read back and then removed, the same
    write-then-read-then-clean-up shape `MacSayEngine` uses for its WAV
    output.

    `grammar_path`, when set, is passed as `--grammar` -- constrained
    decoding (Decision 1, point 3). Stage 1's bench runs this class both
    with and without a grammar path and reports them as separate rows,
    since constrained decoding can convert obvious garbage into a
    confident wrong answer (plan's stated risk) rather than only helping.
    """

    def __init__(
        self,
        binary_path: str = DEFAULT_WHISPER_BINARY,
        model_path: str = "",
        grammar_path: str | None = None,
        grammar_penalty: float | None = None,
    ) -> None:
        self._binary_path = binary_path
        self._model_path = model_path
        self._grammar_path = grammar_path
        self._grammar_penalty = grammar_penalty

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
            if self._grammar_path is not None:
                command += ["--grammar", self._grammar_path]
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


#: The PowerShell script driving `System.Speech.Recognition.
#: SpeechRecognitionEngine` against a WAV file with a `Choices` grammar,
#: emitting `{"text": ..., "confidence": ...}` as JSON on stdout (or
#: `{"text": "", "confidence": 0.0}` if nothing in the grammar matched --
#: `System.Speech` raises no distinct "no match" exception, it simply
#: returns no result). **Unverified against a live Windows run** -- see
#: module docstring; `System.Speech`'s API shape (`SetInputToWaveFile`,
#: `LoadGrammar(new Grammar(new GrammarBuilder(new Choices(...))))`,
#: `Recognize()`, `.Text`/`.Confidence`) is documented Win32/.NET surface,
#: not confirmed live.
_WINDOWS_SPEECH_SCRIPT_TEMPLATE = r"""
Add-Type -AssemblyName System.Speech
$ErrorActionPreference = "Stop"
$phrases = @({phrases})
$choices = New-Object System.Speech.Recognition.Choices($phrases)
$builder = New-Object System.Speech.Recognition.GrammarBuilder($choices)
$grammar = New-Object System.Speech.Recognition.Grammar($builder)
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$engine.LoadGrammar($grammar)
$engine.SetInputToWaveFile("{wav_path}")
$result = $engine.Recognize()
if ($result -eq $null) {{
    Write-Output '{{"text": "", "confidence": 0.0}}'
}} else {{
    $obj = @{{ text = $result.Text; confidence = $result.Confidence }}
    Write-Output ($obj | ConvertTo-Json -Compress)
}}
"""


class WindowsSpeechEngine:
    """`STTEngine` backed by Windows's built-in `System.Speech.Recognition.
    SpeechRecognitionEngine`, driven via `powershell.exe -NoProfile
    -Command <script>`. `powershell.exe` is an OS-shipped external binary
    -- no download, no package, consistent with the external-binary rule.

    Windows-only by construction: `transcribe` raises immediately (never
    attempts a subprocess call) on any other platform, so a bench run on
    the Mac skips this engine cleanly rather than erroring.
    """

    def __init__(self, phrases: tuple[str, ...]) -> None:
        if not phrases:
            raise ValueError("WindowsSpeechEngine requires a non-empty phrase list")
        self._phrases = phrases

    @staticmethod
    def is_available() -> bool:
        """Whether this engine can run at all on the current host --
        platform-only check, no subprocess call. `False` on every non-
        Windows host, including this project's own Mac development
        machine."""
        return sys.platform == "win32"

    def transcribe(self, wav: bytes) -> Transcript:
        if not WindowsSpeechEngine.is_available():
            raise STTRecognitionError(
                "WindowsSpeechEngine only runs on Windows "
                f"(current platform: {platform.system()})"
            )
        if not wav:
            raise STTRecognitionError("cannot transcribe empty audio")

        wav_fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="srs-adapter-in-")
        try:
            with os.fdopen(wav_fd, "wb") as f:
                f.write(wav)

            phrase_literal = ", ".join(f'"{_ps_escape(p)}"' for p in self._phrases)
            script = _WINDOWS_SPEECH_SCRIPT_TEMPLATE.format(
                phrases=phrase_literal,
                wav_path=_ps_escape(wav_path),
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True,
                timeout=_RECOGNITION_TIMEOUT_S,
                check=False,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise STTRecognitionError(
                    f"'powershell.exe' exited {result.returncode}: {stderr.strip()}"
                )
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise STTRecognitionError(
                    f"could not parse powershell output as JSON: {stdout!r}"
                ) from exc
            if not isinstance(payload, dict):
                raise STTRecognitionError(
                    "unexpected powershell JSON shape: root is "
                    f"{type(payload).__name__}, not an object: {payload!r}"
                )
            text = payload.get("text", "")
            confidence = payload.get("confidence", 0.0)
            if not isinstance(text, str) or not isinstance(confidence, (int, float)):
                raise STTRecognitionError(
                    f"unexpected powershell JSON shape: {payload!r}"
                )
            return Transcript(
                text=text, confidence=float(confidence), engine="windows-speech"
            )
        except FileNotFoundError as exc:
            raise STTRecognitionError(
                "'powershell.exe' not found (not on Windows?)"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise STTRecognitionError(
                f"'powershell.exe' timed out after {_RECOGNITION_TIMEOUT_S}s"
            ) from exc
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                logger.debug("could not remove temp file %s", wav_path, exc_info=True)


def _ps_escape(value: str) -> str:
    """Escape a value for embedding inside a PowerShell double-quoted
    string literal -- doubling embedded double quotes and backticks is
    PowerShell's own escaping rule for that context."""
    return value.replace("`", "``").replace('"', '`"')
