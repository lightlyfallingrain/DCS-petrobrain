"""Microphone capture, gated by push-to-talk.

`plans/inbound-speech/plan.md` Stage 4. The chain this sits in is
mic -> gate -> LAN -> recognise -> command -> readback, and everything
downstream of the gate already exists and is tested; this module is the
front of it.

**sox, not ffmpeg.** The plan named `ffmpeg -f dshow`, and part of Stage
4's stated job was proving the dshow device name for the user's headset.
That work is already done in a different currency: `tools/record_corpus.py`
recorded 252 corpus clips through this exact headset with `sox`, which
means the input arguments, the driver name on Windows, the buffer size
and the truncation repair are all *already* settled against the hardware
that matters. Introducing a second audio binary to re-learn them would
add a dependency and a discovery step to buy nothing. Everything below
that looks like a detail -- the 1024-byte buffer, the flag ordering, the
`--ignore-length` repair -- is a scar from that recording session and is
explained where it appears.

**What capture does not do.** No recognition, no matching, no decision
about whether speech was a command. A clip either passes the gate and is
posted, or it does not. Recognition lives on the Mac behind
`POST /transcribe`; this half can run on a machine with no model on it.
"""

from __future__ import annotations

import array
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

#: whisper.cpp wants 16 kHz mono 16-bit PCM; recording it directly
#: avoids a resampling step between here and recognition.
SAMPLE_RATE = 16000

#: sox output buffer, in bytes. **Not a performance knob.** sox writes
#: whole buffers, so terminating it discards whatever is still in the
#: current one -- at the default 8192 bytes that is 0.256 s of 16 kHz
#: mono silently missing from the end of every clip. That cost a whole
#: corpus once (`tools/record_corpus.py`'s own note): every take ended
#: mid-word and the bench read the truncations as recognition failures,
#: scoring 55.6% where the fixed recorder scored 90.5%. 1024 bytes caps
#: the worst-case loss at 0.032 s. A PTT release is exactly the same
#: mid-write stop, so the same value applies here.
SOX_BUFFER_BYTES = 1024

#: **Measured device-open latency: the first ~0.14 s after `start()` is
#: not captured.** sox returns from `Popen` in about 2 ms but the audio
#: device is not open yet, and the gap is remarkably constant -- four
#: runs on the Mac at hold lengths from 0.6 s to 2.0 s lost 0.134-0.144 s
#: every time, so it is a fixed open cost rather than anything
#: proportional. `tools/record_corpus.py` met the same thing and solved
#: it by waiting 0.35 s before prompting the speaker, which a
#: press-to-talk gate cannot do: the press *is* the prompt.
#:
#: Left uncorrected deliberately, for now. A player pressing a talk
#: control and then speaking naturally leaves more than 0.14 s, and
#: radio discipline teaches exactly that gesture. The alternative -- a
#: permanently hot microphone with the pressed interval trimmed out of a
#: rolling recording -- removes the latency completely but runs sox and
#: writes ~32 kB/s continuously, needs file rotation, and would be built
#: before any evidence that the gesture is actually a problem. If Stage 6
#: shows first words being clipped in flight, that is the fix; the
#: measurement is here so the decision is not re-derived from scratch.
FRONT_LATENCY_S = 0.14

#: Keep recording this long past the release. The player lets go as the
#: last syllable ends rather than after it, so stopping on the release
#: itself clips the final word -- and the final word is often the one
#: carrying the meaning ("scan EAST", "watch NEAREST").
DEFAULT_TAIL_S = 0.4

#: A hard ceiling on one clip, so a stuck button cannot record forever
#: or post a multi-megabyte WAV across the LAN.
DEFAULT_MAX_CLIP_S = 12.0

#: Shorter than this and nothing was said -- a brushed button, or a
#: press-and-immediate-release while reaching for something else.
DEFAULT_MIN_CLIP_S = 0.35

#: Below this peak amplitude (0-1) effectively nothing was captured:
#: wrong input device, muted headset, or a mic that never opened. Same
#: value `tools/record_corpus.py` calibrated against real clips.
DEFAULT_MIN_PEAK = 0.05


class CaptureError(RuntimeError):
    """Raised when capture itself fails -- sox missing, device refused,
    nothing written. Distinct from a clip that recorded fine and was
    rejected by the gate, which is normal and not an error."""


def sox_available() -> bool:
    return shutil.which("sox") is not None


def input_args(driver: str | None, device: str | None) -> list[str]:
    """sox input-source arguments, defaulted per platform.

    Uses `sox` rather than `rec` -- the same program with its input
    pre-set -- because **the Windows sox distribution ships only
    `sox.exe`**, so depending on `rec` would make capture Unix-only for
    no gain. `-d` is the default input device; Windows additionally needs
    the `waveaudio` driver named, and usually a specific device, since
    the system default on a box with a webcam and a monitor microphone is
    rarely the headset (`sox -h` lists drivers; a device can be given by
    index or name substring). Carried over verbatim from
    `tools/record_corpus.py`, which learned it on the real hardware.
    """
    if driver is None and sys.platform == "win32":
        driver = "waveaudio"
    args: list[str] = []
    if driver is not None:
        args += ["-t", driver]
    args += [device] if device is not None else ["-d"]
    return args


@dataclass(frozen=True)
class Clip:
    """One recorded utterance: the WAV bytes and how long it ran."""

    wav: bytes
    duration_s: float
    peak: float


@dataclass(frozen=True)
class GateVerdict:
    """Why a clip was kept or dropped. `reason` is `None` when accepted.

    A verdict rather than a bool because the two rejections mean opposite
    things to the person holding the button: too-short is "you didn't
    really press", too-quiet is "your microphone is not working". Both
    would be invisible as a silent drop, and the second is the one that
    would otherwise be diagnosed as a recognition problem.
    """

    accepted: bool
    reason: str | None = None


class ClipGate:
    """Decides whether a recorded clip is worth sending for recognition.

    Deliberately crude -- duration and peak amplitude, nothing spectral.
    The expensive judgement (is this speech, is it a command, is it
    confident enough) already happens downstream in `command_matcher` and
    body-layer's bands. This gate exists only to stop obvious non-events
    from spending a whisper run and a LAN round trip.
    """

    def __init__(
        self,
        min_duration_s: float = DEFAULT_MIN_CLIP_S,
        min_peak: float = DEFAULT_MIN_PEAK,
    ) -> None:
        self._min_duration_s = min_duration_s
        self._min_peak = min_peak

    def assess(self, clip: Clip) -> GateVerdict:
        if clip.duration_s < self._min_duration_s:
            return GateVerdict(
                accepted=False,
                reason=(
                    f"too short ({clip.duration_s:.2f}s < {self._min_duration_s:.2f}s) "
                    "-- button brushed rather than held"
                ),
            )
        if clip.peak < self._min_peak:
            return GateVerdict(
                accepted=False,
                reason=(
                    f"too quiet (peak {clip.peak:.3f} < {self._min_peak:.3f}) "
                    "-- check the input device is the headset"
                ),
            )
        return GateVerdict(accepted=True)


def wav_peak_and_duration(wav: bytes) -> tuple[float, float]:
    """`(peak_amplitude_0_to_1, duration_s)` for 16-bit PCM WAV bytes.

    Stdlib only, and deliberately not `sox stat` in a subprocess: this
    runs once per press on the capture box's hot path, and spawning a
    process to learn the loudness of audio already in memory would be the
    most expensive part of the gate. `audioop` would have done it in one
    call but was removed in Python 3.13, so the peak is computed over an
    `array` directly.
    """
    with contextlib.closing(wave.open(io.BytesIO(wav), "rb")) as reader:
        frames = reader.getnframes()
        rate = reader.getframerate()
        width = reader.getsampwidth()
        raw = reader.readframes(frames)
    duration_s = frames / rate if rate else 0.0
    if width != 2 or not raw:
        # Only 16-bit PCM is produced by the recorder below; anything
        # else is reported as silent rather than guessed at, so the gate
        # rejects it loudly instead of passing unknown audio on.
        return (0.0, duration_s)
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if not samples:
        return (0.0, duration_s)
    peak = max(abs(int(sample)) for sample in samples) / 32768.0
    return (peak, duration_s)


class SoxRecorder:
    """Records one clip per press, start to release, via `sox`.

    Start/stop rather than a fixed window because the whole point of a
    PTT gate is that the player decides the boundaries. `stop()` is where
    the two sox scars live: terminate discards the in-flight buffer
    (hence `SOX_BUFFER_BYTES`), and a terminated write leaves a RIFF
    length field describing a recording that never finished, which some
    readers reject outright -- `sox --ignore-length` re-reads to
    end-of-file and writes a correct header. Repairing afterwards is far
    more portable than stopping sox gracefully: Windows has no SIGINT to
    send it.
    """

    def __init__(
        self,
        driver: str | None = None,
        device: str | None = None,
        max_clip_s: float = DEFAULT_MAX_CLIP_S,
    ) -> None:
        self._driver = driver
        self._device = device
        self._max_clip_s = max_clip_s
        self._process: subprocess.Popen[bytes] | None = None
        self._path: Path | None = None
        self._started_at = 0.0

    def start(self) -> None:
        if self._process is not None:
            raise CaptureError("recorder already running")
        if not sox_available():
            raise CaptureError(
                "`sox` not found. macOS: brew install sox. "
                "Windows: the installer from sox.sourceforge.net."
            )
        # mkstemp rather than NamedTemporaryFile: sox writes this file
        # itself, so the handle is closed immediately and only the path
        # matters.
        fd, name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        path = Path(name)
        # Argument order is load-bearing: everything before the input
        # spec applies to the input, everything after it to the output
        # file. The rate/channel/width flags therefore sit AFTER the
        # input args, so they describe what gets written rather than what
        # the device must produce -- microphones commonly refuse 16 kHz,
        # and this ordering is what makes sox resample down to the mono
        # 16 kHz PCM whisper.cpp requires instead of writing a 48 kHz
        # file whisper will reject.
        self._process = subprocess.Popen(
            [
                "sox",
                "-q",
                "--buffer",
                str(SOX_BUFFER_BYTES),
                *input_args(self._driver, self._device),
                "-r",
                str(SAMPLE_RATE),
                "-c",
                "1",
                "-b",
                "16",
                "-e",
                "signed-integer",
                str(path),
                "trim",
                "0",
                str(self._max_clip_s),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._path = path
        self._started_at = time.monotonic()

    def stop(self) -> Clip:
        process, path = self._process, self._path
        self._process, self._path = None, None
        if process is None or path is None:
            raise CaptureError("recorder was not running")
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5.0)
            if not path.exists() or path.stat().st_size == 0:
                stderr = b""
                if process.stderr is not None:
                    stderr = process.stderr.read() or b""
                raise CaptureError(
                    f"sox produced nothing: {stderr.decode('utf-8', 'replace').strip()[:200]}"
                )
            _repair_truncated_wav(path)
            wav = path.read_bytes()
        finally:
            if process.stderr is not None:
                process.stderr.close()
            path.unlink(missing_ok=True)
        peak, duration_s = wav_peak_and_duration(wav)
        return Clip(wav=wav, duration_s=duration_s, peak=peak)

    def abort(self) -> None:
        """Stop and discard, for shutdown paths that want no clip."""
        with contextlib.suppress(CaptureError):
            self.stop()


def _repair_truncated_wav(path: Path) -> bool:
    """Rewrite `path`'s header after sox was stopped mid-write.

    Returns False when sox cannot repair it, leaving the original in
    place -- a slightly-wrong header still usually decodes, so a failed
    repair is not worth discarding audio the player actually spoke.
    """
    temp = path.with_suffix(".repair.wav")
    result = subprocess.run(
        ["sox", "--ignore-length", str(path), str(temp)],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not temp.exists():
        temp.unlink(missing_ok=True)
        return False
    temp.replace(path)
    return True
