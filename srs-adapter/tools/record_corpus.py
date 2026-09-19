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

Requires `sox` (Homebrew: `brew install sox`), an external binary in the
same sense whisper-cli is -- deliberately not a Python package, since
this subproject is stdlib-only (`srs-adapter/CLAUDE.md`).

    PYTHONPATH=src .venv/bin/python tools/record_corpus.py --corpus-dir <dir>

Controls per take: Enter records, `r` redoes the take just recorded, `s`
skips the phrase, `q` saves and quits. Progress is resumable -- an
existing corpus directory is counted on startup, and phrases that already
have the requested number of takes are skipped, so the corpus can be
built across several sittings.

Record the way you will actually fly: the headset you use in the
cockpit, at a normal speaking level rather than an over-enunciated one.
An over-articulated corpus flatters the recogniser and produces a pass
that does not survive the aircraft.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import vocabulary

DEFAULT_TAKES = 4
DEFAULT_SECONDS = 2.5
#: whisper.cpp wants 16 kHz mono 16-bit PCM; recording it directly avoids
#: a resampling step between here and the bench.
SAMPLE_RATE = 16000


def _sox_available() -> bool:
    return shutil.which("rec") is not None


def _record(path: Path, seconds: float) -> bool:
    """Record one fixed-length take to `path`. False if sox failed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "rec",
            "-q",
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
        default=DEFAULT_SECONDS,
        help=f"length of each recording window (default {DEFAULT_SECONDS})",
    )
    args = parser.parse_args()

    if not _sox_available():
        print(
            "`rec` (from sox) not found. Install it with:\n"
            "    brew install sox\n"
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
        f"{total} takes to record ({args.takes} per phrasing, "
        f"{args.seconds}s each).\n"
        "Enter = record, r = redo last, s = skip, q = quit (progress is kept).\n"
        "Use the headset you fly with, and speak as you would in the cockpit.\n"
    )

    index = 0
    while index < len(work):
        token, phrase, take = work[index]
        path = args.corpus_dir / token / f"{_slug(phrase)}_{take}.wav"
        prompt = f'[{index + 1}/{total}] {token}  say: "{phrase}"  > '
        try:
            choice = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nStopped. Progress kept.")
            return 0

        if choice == "q":
            print("Stopped. Progress kept.")
            return 0
        if choice == "s":
            index += 1
            continue
        if choice == "r":
            index = max(0, index - 1)
            continue

        print("  recording...", end="", flush=True)
        if _record(path, args.seconds):
            print(" saved")
            index += 1
        else:
            print("  (not saved -- press Enter to try again)")

    print(f"\nDone. Corpus at {args.corpus_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
