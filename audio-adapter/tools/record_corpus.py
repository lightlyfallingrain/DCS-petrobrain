#!/usr/bin/env python3
"""Prompting recorder for Stage 1's bench corpus.

The bench (`tools/stt_bench.py`) reads `<corpus-dir>/<token>/*.wav`.
Building that by hand means 34 phrasings times several repetitions --
well over a hundred separate files, each named and filed correctly. The
predictable failure of doing that in a GUI recorder is not that it is
unpleasant but that it quietly biases the result: repetitions get cut
short, the later tokens get recorded with less care than the early ones,
and the corpus ends up thinnest exactly where confusions are most likely.
So this prompts for each phrase in turn, records a fixed window, writes
the file to the right place, and lets a bad take be redone on the spot.

Requires `sox` (Homebrew: `brew install sox`; on Windows, the installer
from sox.sourceforge.net), an external binary in the same sense
whisper-cli is -- deliberately not a Python package, since
this subproject is stdlib-only (`audio-adapter/CLAUDE.md`).

    # Mac
    PYTHONPATH=src .venv/bin/python tools/record_corpus.py --corpus-dir <dir>

    # Windows -- stdlib-only and `vocabulary` is too, so no venv is
    # needed here, unlike most of this repo's entry points
    set PYTHONPATH=src
    python tools\\record_corpus.py --corpus-dir <dir>

**Record on the box whose headset you actually fly with.** For this
project that means Windows, even though the bench that consumes the
corpus runs on the Mac. The corpus is raw audio -- recording and
recognition are separate steps joined only by a directory of `.wav`
files, so they need not happen on the same machine, and the microphone,
its preamp and the headset's own response are part of what the bench is
measuring. A corpus captured through a different microphone would score
a signal chain that never flies.

Recording on the box you fly from is still the point: the microphone, its
preamp and the headset's own response are part of what the bench measures.
(An earlier note here promised a fair engine comparison by benching the same
corpus on both machines. That is gone with the Windows recognizer, removed
2026-09-19 -- see `stt_engine.py`. Recognition now happens on the Mac
regardless of where the audio was captured.)

**Space is the push-to-talk key**: press it to start the take, say the
phrase, press it again to stop. Single keypresses, no Enter. `r` redoes
the take just recorded, `s` skips the phrase, `q` saves and quits.

Press-to-start/press-to-stop rather than a true hold, because a terminal
receives no key-release event -- there is no portable way to detect a
held key. The recording boundaries are what matter and these are the
same: the clip starts and ends where the speaker decides, not on a timer.
That is also what makes the corpus resemble live operation, where PTT
delimits every transmission (`plans/inbound-speech/plan.md`).

A fixed-length window is still available via `--seconds` for anyone who
prefers it; `--max-seconds` caps a PTT take so a forgotten second press
cannot record forever.

Progress is resumable -- an existing corpus directory is counted on
startup, and phrases that already have the requested number of takes are
skipped, so the corpus can be built across several sittings.

Record the way you will actually fly: the headset you use in the
cockpit, at a normal speaking level rather than an over-enunciated one.
An over-articulated corpus flatters the recogniser and produces a pass
that does not survive the aircraft.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import vocabulary

DEFAULT_TAKES = 4
DEFAULT_SECONDS = 2.5
#: Hard cap on a push-to-talk take, so a forgotten second keypress cannot
#: record until the disk fills.
DEFAULT_MAX_SECONDS = 15.0

#: Keep recording for this long after the stop key. A speaker presses the
#: key as the last syllable ends, not after it, so stopping instantly
#: clips the final word -- and the final word is often the one that
#: carries the meaning ("scan EAST", "hey PETROVICH").
DEFAULT_TAIL_SECONDS = 0.6

#: Wait this long after starting sox before telling the speaker to go.
#: Opening an audio device is not instant -- measured at roughly 0.15s
#: here -- and anything said during that window is simply not captured.
#: A clipped first syllable is exactly as fatal as a clipped last one and
#: harder to spot, since the transcript still looks like a plausible
#: mishearing rather than an obvious fragment.
DEFAULT_PREROLL_SECONDS = 0.35

#: sox output buffer, in bytes. **Not a performance tuning knob.** sox
#: writes in whole buffers, so terminating it discards whatever is still
#: in the current one; at the default 8192 bytes that is 0.256s of 16 kHz
#: mono audio silently missing from the end of every take. This cost a
#: whole corpus once: the first recording session produced clips whose
#: durations were all exact multiples of 0.256s, ending mid-word with the
#: trailing energy still above the clip average, and the bench read the
#: resulting truncations as recognition failures. 1024 bytes caps the
#: worst-case loss at 0.032s.
SOX_BUFFER_BYTES = 1024
#: whisper.cpp wants 16 kHz mono 16-bit PCM; recording it directly avoids
#: a resampling step between here and the bench.
SAMPLE_RATE = 16000


def _sox_available() -> bool:
    return shutil.which("sox") is not None


@contextlib.contextmanager
def _raw_key_mode() -> Iterator[None]:
    """Read single keypresses without waiting for Enter.

    `termios`/`tty` on POSIX, nothing needed on Windows (`msvcrt.getch`
    already reads one key). Uses `cbreak` rather than `raw` deliberately:
    cbreak leaves signal generation on, so Ctrl-C still interrupts a
    recording session instead of being swallowed as an ordinary byte.
    """
    if sys.platform == "win32" or not sys.stdin.isatty():
        yield
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _read_key() -> str:
    """One keypress, lowercased. `" "` for space, `""` at EOF."""
    if sys.platform == "win32":
        import msvcrt

        return msvcrt.getch().decode("latin-1", "replace").lower()
    char = sys.stdin.read(1)
    return char.lower() if char else ""


def _repair_truncated_wav(path: Path) -> bool:
    """Rewrite `path`'s header after sox was stopped mid-write.

    Terminating sox leaves the RIFF length field describing a recording
    that never finished, which some readers reject outright. `sox
    --ignore-length` exists for exactly this: it reads to end-of-file
    rather than trusting the header, so re-encoding through it produces a
    correct one. Cheaper and far more portable than trying to stop sox
    gracefully -- Windows has no SIGINT to send it.
    """
    temp = path.with_suffix(".repair.wav")
    result = subprocess.run(
        ["sox", "--ignore-length", str(path), str(temp)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not temp.exists():
        temp.unlink(missing_ok=True)
        return False
    temp.replace(path)
    return True


#: A clip still carrying this fraction of its own peak amplitude in its
#: last 0.15s was probably cut mid-word. Calibrated against real clips
#: rather than guessed: the truncated first corpus measured 0.067-0.125,
#: a cleanly-ended clip 0.017.
_TRUNCATION_TAIL_RATIO = 0.05

#: Below this peak amplitude, effectively nothing was captured -- the
#: wrong input device, a muted headset, or a mic that never opened.
_SILENT_CLIP_PEAK = 0.05


def _clip_stats(path: Path) -> tuple[float, float] | None:
    """`(peak_amplitude, rms_of_last_0.15s)`, or None if sox failed."""

    def stat(args: list[str], field: str) -> float | None:
        result = subprocess.run(
            ["sox", str(path), "-n", *args, "stat"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stderr.splitlines():
            if field in line:
                try:
                    return float(line.split()[-1])
                except ValueError:
                    return None
        return None

    peak = stat([], "Maximum amplitude")
    tail = stat(["trim", "-0.15"], "RMS     amplitude")
    if peak is None or tail is None:
        return None
    return peak, tail


def _clip_warning(path: Path) -> str | None:
    """A human-readable problem with the take just recorded, or None.

    Two checks, both learned the expensive way. The first corpus was lost
    to clips cut mid-word, and nothing noticed until bench time -- by
    which point the session was over and the truncations arrived looking
    like recognition failures rather than recording ones. Checking here
    costs milliseconds and catches it while the speaker is still sitting
    at the keyboard.

    The silence check guards the other way a session can be wasted: this
    tool cannot tell a headset from a webcam microphone, and a corpus
    recorded off the wrong input is indistinguishable from bad luck until
    far too late.
    """
    stats = _clip_stats(path)
    if stats is None:
        return None
    peak, tail_rms = stats
    if peak < _SILENT_CLIP_PEAK:
        return (
            "almost no audio in this clip -- is the right microphone "
            "selected? (--input-device)"
        )
    if tail_rms / peak > _TRUNCATION_TAIL_RATIO:
        return (
            "this clip still has speech at its very end -- probably cut "
            "short. Press r to redo, and leave a beat before pressing space."
        )
    return None


def _record_ptt(
    path: Path,
    max_seconds: float,
    driver: str | None = None,
    device: str | None = None,
    tail_seconds: float = DEFAULT_TAIL_SECONDS,
    preroll_seconds: float = DEFAULT_PREROLL_SECONDS,
) -> bool:
    """Record until the next keypress, capped at `max_seconds`.

    Keeps capturing for `tail_seconds` past the keypress: the speaker
    releases as the last syllable ends rather than after it, so stopping
    on the key itself clips the final word. Waits `preroll_seconds`
    before prompting, so the device is actually open by the time anyone
    speaks.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            "sox",
            "-q",
            "--buffer",
            str(SOX_BUFFER_BYTES),
            *_input_args(driver, device),
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
            str(max_seconds),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(preroll_seconds)
    print("  \u25cf REC  -- press space to stop", end="", flush=True)
    _read_key()
    time.sleep(tail_seconds)

    if process.poll() is None:
        process.terminate()
        process.wait()
        truncated = True
    else:
        truncated = False

    if not path.exists() or path.stat().st_size == 0:
        stderr = (process.stderr.read() if process.stderr else "") or ""
        print(f"\r  sox produced nothing: {stderr.strip()[:160]}", file=sys.stderr)
        return False

    if truncated and not _repair_truncated_wav(path):
        print("\r  could not repair the clip header", file=sys.stderr)
        return False

    warning = _clip_warning(path)
    if warning is not None:
        print(f"\n  WARNING: {warning}", file=sys.stderr)
    return True


def _input_args(driver: str | None, device: str | None) -> list[str]:
    """sox input-source arguments, defaulted per platform.

    Uses `sox` rather than `rec`, which is the same program with the
    input pre-set to the default device -- **the Windows sox
    distribution ships only `sox.exe`**, so depending on `rec` made the
    recorder Unix-only for no gain. Naming the input explicitly works
    identically on both platforms.

    `-d` is the default input device. Windows additionally needs the
    `waveaudio` driver named, and often a specific device, since the
    system default on a box with a webcam and a monitor microphone is
    rarely the headset. `sox -h` lists the drivers; a device can be given
    by index or name substring (`--input-device 1`,
    `--input-device Headset`).
    """
    if driver is None and sys.platform == "win32":
        driver = "waveaudio"
    args: list[str] = []
    if driver is not None:
        args += ["-t", driver]
    args += [device] if device is not None else ["-d"]
    return args


def _record(
    path: Path, seconds: float, driver: str | None = None, device: str | None = None
) -> bool:
    """Record one fixed-length take to `path`. False if sox failed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Argument order is load-bearing: everything before the input spec
    # applies to the input, everything after it applies to the output
    # file. The rate/channel/width flags therefore sit AFTER `-d` so they
    # describe what gets written, not what the device must produce.
    # Microphones commonly refuse 16 kHz -- sox warns and captures at the
    # device rate -- and this ordering is what makes it resample down to
    # the 16 kHz mono PCM whisper.cpp requires instead of writing a
    # 48 kHz file whisper will reject.
    result = subprocess.run(
        [
            "sox",
            "-q",
            "--buffer",
            str(SOX_BUFFER_BYTES),
            *_input_args(driver, device),
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
            str(seconds),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"  sox failed: {result.stderr.strip()[:200]}", file=sys.stderr)
        return False
    return True


def _existing_takes(token_dir: Path, slug: str) -> int:
    if not token_dir.is_dir():
        return 0
    return len(list(token_dir.glob(f"{slug}_*.wav")))


def _slug(phrase: str) -> str:
    return phrase.replace(" ", "_")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument(
        "--takes",
        type=int,
        default=DEFAULT_TAKES,
        help=f"repetitions per phrasing (default {DEFAULT_TAKES})",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="use a fixed-length window of this many seconds instead of "
        f"push-to-talk (suggested {DEFAULT_SECONDS})",
    )
    parser.add_argument(
        "--tail-seconds",
        type=float,
        default=DEFAULT_TAIL_SECONDS,
        help="keep recording this long after the stop key "
        f"(default {DEFAULT_TAIL_SECONDS}) so the last word is not clipped",
    )
    parser.add_argument(
        "--preroll-seconds",
        type=float,
        default=DEFAULT_PREROLL_SECONDS,
        help="wait this long for the audio device to open before "
        f"prompting (default {DEFAULT_PREROLL_SECONDS})",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=DEFAULT_MAX_SECONDS,
        help=f"cap on a push-to-talk take (default {DEFAULT_MAX_SECONDS})",
    )
    parser.add_argument(
        "--input-driver",
        default=None,
        help="sox input driver; defaults to waveaudio on Windows, "
        "sox's own default elsewhere",
    )
    parser.add_argument(
        "--input-device",
        default=None,
        help="sox input device (index or name substring). Use when the "
        "system default input is not the headset you fly with",
    )
    args = parser.parse_args()

    if not _sox_available():
        print(
            "`sox` not found. Install it with:\n"
            "    macOS:   brew install sox\n"
            "    Windows: the installer from sox.sourceforge.net, then\n"
            "             add its directory to PATH\n"
            "It is an external binary, not a Python dependency.",
            file=sys.stderr,
        )
        return 1

    work: list[tuple[str, str, int]] = []
    for token, phrases in vocabulary.PHRASES.items():
        for phrase in phrases:
            done = _existing_takes(args.corpus_dir / token, _slug(phrase))
            for take in range(done, args.takes):
                work.append((token, phrase, take))

    if not work:
        print(f"Corpus already complete at {args.takes} takes per phrasing.")
        return 0

    total = len(work)
    print(
        f"{total} takes to record, {args.takes} per phrasing.\n"
        + (
            f"Fixed {args.seconds}s window per take.\n"
            if args.seconds is not None
            else "SPACE = push-to-talk: press to start, say it, press to stop.\n"
        )
        + "r = redo last, s = skip, q = quit (progress is kept).\n"
        "Use the headset you fly with, and speak as you would in the cockpit.\n"
        "Check your first clip plays back from the right microphone before\n"
        "recording the rest -- this tool cannot tell a headset from a webcam.\n"
    )

    index = 0
    with _raw_key_mode():
        while index < len(work):
            token, phrase, take = work[index]
            path = args.corpus_dir / token / f"{_slug(phrase)}_{take}.wav"
            print(
                f'[{index + 1}/{total}] {token}  say: "{phrase}"  > ',
                end="",
                flush=True,
            )
            try:
                choice = _read_key()
            except KeyboardInterrupt:
                print("\nStopped. Progress kept.")
                return 0

            if choice in ("q", "", "\x03"):
                print("\nStopped. Progress kept.")
                return 0
            if choice == "s":
                print("skipped")
                index += 1
                continue
            if choice == "r":
                print("redo previous")
                index = max(0, index - 1)
                continue
            if choice != " ":
                print("(space to record, r redo, s skip, q quit)")
                continue

            if args.seconds is not None:
                print("  recording...", end="", flush=True)
                ok = _record(path, args.seconds, args.input_driver, args.input_device)
            else:
                ok = _record_ptt(
                    path,
                    args.max_seconds,
                    args.input_driver,
                    args.input_device,
                    args.tail_seconds,
                    args.preroll_seconds,
                )
            if ok:
                print("  saved")
                index += 1
            else:
                print("  not saved -- press space to try again")

    print(f"\nDone. Corpus at {args.corpus_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
