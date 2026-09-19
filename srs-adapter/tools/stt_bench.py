#!/usr/bin/env python3
"""Stage 1's recognition bench (`plans/inbound-speech/plan.md`) -- the
stop/go gate for the whole inbound-speech slice.

**The question this script exists to answer is "would I fly with this?",
not "is 91% enough?"** (settled decision 2, 2026-09-19: the user
deliberately did not set a pass bar in advance, because he cannot know
what will feel acceptable until he sees results). So this prints, per
engine: top-1 token accuracy, every confusion pair with actual sample
misheard text, and the confidence distribution split by correct/incorrect
-- concrete evidence to judge, not a single statistic to compare against a
threshold.

Runs three recognizer configurations over a recorded corpus of the user's
own voice, whichever are available on this host:

1. `whisper-cli` without a grammar (free decoding).
2. `whisper-cli` with `--grammar` built from `vocabulary.to_gbnf()`
   (constrained decoding) -- reported as a **separate row**, since the
   plan explicitly wants to know whether constrained decoding helps or
   hurts, not just whichever one this script happened to run.
3. `WindowsSpeechEngine` -- only attempted when running on Windows; on the
   Mac this row is skipped with a clear message, never a traceback.

## Recording the corpus

Directory layout this script reads:

    <corpus-dir>/<token>/*.wav

One subdirectory per vocabulary token (see `vocabulary.TOKENS` for the
exact 15 names, e.g. `scan_left`, `scan_bearing_ne`, `watch_nearest`,
`cancel_task`), any number of `.wav` files inside each, any filenames.
Every clip in a token's directory is scored against that token as the
expected answer.

Run `stt_bench.py --list-prompts` to print exactly what to say for every
token (all of `vocabulary.PHRASES`' phrasings) and where to save each
recording.

`tools/record_corpus.py` builds that layout for you -- it prompts for each
phrase in turn, records a fixed window via `sox`, and files the result
under the right token. Preferred over recording by hand: the corpus is
over a hundred clips, and hand-recording them reliably thins out toward
the end, which is where the bearing tokens (the most confusable group)
happen to sit.

**What to record and how many repetitions:** every phrasing listed for
every token, at least 3-5 times each, spread across more than one sitting
if convenient. Ideally with the headset that will actually be used in the
cockpit, and with some background noise present in at least a few takes
(engine/environment noise, not silence) -- a bench recorded in a silent
room says less about in-flight conditions than one that isn't. More
repetitions make the accuracy number and the confusion pairs more
trustworthy; there is no hard minimum this script enforces.

**Recording on the Mac**, no extra tooling beyond what ships or is a
one-line install:

    # QuickTime Player: File -> New Audio Recording, save as .m4a, then:
    afconvert -f WAVE -d LEI16@16000 -c 1 input.m4a output.wav

    # or, with sox installed (`brew install sox`):
    rec -r 16000 -b 16 -c 1 output.wav

Whisper's native input rate is 16 kHz mono 16-bit PCM (Decision 2) --
recording directly at that rate avoids a resampling step, though
`whisper-cli` itself will also accept other WAV rates.

## Running this script

From `srs-adapter/`:

    PYTHONPATH=src .venv/bin/python tools/stt_bench.py \\
        --corpus-dir /path/to/corpus \\
        --whisper-binary whisper-cli \\
        --whisper-model /path/to/ggml-base.en.bin

Stdlib only, like the rest of this subproject. `--whisper-model` is
required for the whisper.cpp rows to run at all (a GGUF/GGML model file
downloaded separately -- not bundled, not a package dependency); omit it
(or omit `whisper-cli` itself) and this script reports those two rows as
skipped rather than failing.
"""

from __future__ import annotations

import argparse
import difflib
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from stt_engine import (
    STTEngine,
    STTRecognitionError,
    WhisperCliEngine,
    WindowsSpeechEngine,
)
from vocabulary import (
    PHRASES,
    TOKENS,
    normalize_for_match,
    normalized_phrase_index,
    spoken_phrases,
    to_gbnf,
    to_prompt,
)

#: `difflib.get_close_matches`' cutoff for mapping raw recognizer text back
#: onto a known phrase, for scoring purposes only. This is deliberately a
#: much simpler, single-shot match than Stage 2's future `belief.
#: voice_commands.py` matcher (no verb anchor, no separation check, no
#: confidence bands) -- this script only needs to know "which token does
#: this text look most like," not decide whether to act on it.
_MATCH_CUTOFF = 0.6

#: How many misheard samples to print per confusion pair -- enough to read
#: a pattern, not a full dump of every clip.
_SAMPLES_PER_CONFUSION_PAIR = 5


@dataclass(frozen=True)
class ClipResult:
    expected_token: str
    file: Path
    raw_text: str
    matched_token: str | None
    confidence: float
    correct: bool
    #: `True` when `confidence` is `WhisperCliEngine`'s placeholder `1.0`
    #: rather than a measured per-token probability (`Transcript.
    #: confidence_is_placeholder`) -- surfaced in `print_report` so a
    #: whisper.cpp JSON-schema mismatch is visible in the report instead
    #: of silently inflating the confidence columns (review finding).
    #: Wall-clock seconds for this clip's recognition. Reported because
    #: "how light can we go" is a question about latency as much as
    #: accuracy: a model is only worth dropping to if it buys response
    #: time the player would notice.
    seconds: float = 0.0
    confidence_is_placeholder: bool = False
    #: `True` when the normalized text was a known phrasing verbatim;
    #: `False` when it only matched after fuzzy repair. See
    #: `_match_token` for why the difference is reported rather than
    #: folded into "correct".
    exact_match: bool = False


def _match_token(raw_text: str) -> tuple[str | None, bool]:
    """`(token, was_exact)` for `raw_text`, or `(None, False)`.

    Normalization (`vocabulary.normalize_for_match`) runs on both sides
    first, so digits-vs-number-words, trailing punctuation, case and
    hyphenated compass words do not count as errors -- they are
    representation differences, not mishearings.

    The fuzzy fallback then does what `_MATCH_CUTOFF`'s docstring
    describes, but **whether it was needed is reported rather than
    hidden**. That distinction earns its keep on exactly one case, and it
    is the most consequential one in this vocabulary: "record three
    o'clock" is one character-edit from "report three o'clock", so
    difflib repairs it and scores it correct -- concealing a verb error.
    Verbs select the action here ("scan north" versus "report north"), so
    a matcher forgiving enough to repair one would act on the wrong
    command while the bench reported success. Stage 2's real matcher
    anchors on the verb and will not make that repair, so counting it as
    a clean hit here would overstate what the live path can do.
    """
    normalized = normalize_for_match(raw_text)
    if not normalized:
        return None, False

    index = normalized_phrase_index()
    exact = index.get(normalized)
    if exact is not None:
        return exact, True

    matches = difflib.get_close_matches(
        normalized, tuple(index), n=1, cutoff=_MATCH_CUTOFF
    )
    if not matches:
        return None, False
    return index[matches[0]], False


def load_corpus(corpus_dir: Path) -> dict[str, list[Path]]:
    """`<corpus-dir>/<token>/*.wav` -> `{token: [wav paths]}`. Unknown
    subdirectory names (not in `vocabulary.TOKENS`) are reported and
    skipped rather than silently ignored or treated as a fatal error --
    the corpus is hand-assembled by a human and a typo in a directory
    name should be visible, not swallowed."""
    corpus: dict[str, list[Path]] = {}
    if not corpus_dir.is_dir():
        raise SystemExit(f"corpus directory not found: {corpus_dir}")

    known_tokens = set(TOKENS)
    for child in sorted(corpus_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name not in known_tokens:
            print(
                f"warning: skipping directory {child.name!r} -- not one of "
                "the 15 known tokens (see vocabulary.TOKENS)",
                file=sys.stderr,
            )
            continue
        wavs = sorted(child.glob("*.wav"))
        if wavs:
            corpus[child.name] = wavs

    missing = known_tokens - set(corpus)
    if missing:
        print(
            f"warning: no recordings found for {len(missing)} token(s): "
            f"{', '.join(sorted(missing))}",
            file=sys.stderr,
        )
    return corpus


def run_engine(
    engine_label: str,
    engine: STTEngine,
    corpus: dict[str, list[Path]],
) -> list[ClipResult]:
    """Run one `STTEngine` over every clip in `corpus`. A single clip's
    recognition failure is recorded as a miss (empty text, `None` match)
    rather than aborting the whole bench run, so one bad clip never hides
    every other result."""
    results: list[ClipResult] = []
    for expected_token, files in corpus.items():
        for file in files:
            wav = file.read_bytes()
            confidence_is_placeholder = False
            started = time.monotonic()
            try:
                transcript = engine.transcribe(wav)
                raw_text = transcript.text
                confidence = transcript.confidence
                confidence_is_placeholder = transcript.confidence_is_placeholder
            except STTRecognitionError as exc:
                print(
                    f"  [{engine_label}] {file}: recognition failed: {exc}",
                    file=sys.stderr,
                )
                raw_text = ""
                confidence = 0.0
            matched, exact = _match_token(raw_text)
            elapsed = time.monotonic() - started
            results.append(
                ClipResult(
                    expected_token=expected_token,
                    file=file,
                    raw_text=raw_text,
                    matched_token=matched,
                    confidence=confidence,
                    correct=(matched == expected_token),
                    confidence_is_placeholder=confidence_is_placeholder,
                    exact_match=exact,
                    seconds=elapsed,
                )
            )
    return results


def print_report(engine_label: str, results: list[ClipResult]) -> None:
    print(f"\n=== {engine_label} ===")
    if not results:
        print("  (no clips scored)")
        return

    n = len(results)
    n_correct = sum(1 for r in results if r.correct)
    n_exact = sum(1 for r in results if r.correct and r.exact_match)
    print(f"Top-1 token accuracy: {n_correct}/{n} ({100.0 * n_correct / n:.1f}%)")
    print(
        f"  of which heard verbatim: {n_exact}/{n_correct}"
        f"  (repaired by fuzzy match: {n_correct - n_exact})"
    )

    times = sorted(r.seconds for r in results)
    if times and times[-1] > 0.0:
        p90 = times[min(len(times) - 1, int(0.9 * len(times)))]
        print(
            f"Recognition time per clip: median {statistics.median(times):.2f}s  "
            f"p90 {p90:.2f}s  max {times[-1]:.2f}s"
        )

    confusions: dict[tuple[str, str], list[ClipResult]] = {}
    for r in results:
        if r.correct:
            continue
        heard = r.matched_token if r.matched_token is not None else "NO MATCH"
        confusions.setdefault((r.expected_token, heard), []).append(r)

    if confusions:
        print("\nConfusion pairs (expected -> heard as), most frequent first:")
        for (expected, heard), clips in sorted(
            confusions.items(), key=lambda kv: len(kv[1]), reverse=True
        ):
            print(f"  {expected} -> {heard}  x{len(clips)}")
            for clip in clips[:_SAMPLES_PER_CONFUSION_PAIR]:
                print(
                    f"      {clip.file.name}: {clip.raw_text!r} "
                    f"(confidence={clip.confidence:.2f})"
                )
            if len(clips) > _SAMPLES_PER_CONFUSION_PAIR:
                print(f"      ... and {len(clips) - _SAMPLES_PER_CONFUSION_PAIR} more")
    else:
        print("\nNo confusions -- every clip matched its expected token.")

    repaired = [r for r in results if r.correct and not r.exact_match]
    if repaired:
        print(f"\nRepaired matches ({len(repaired)}) -- scored correct above, but the")
        print("  recognizer did not return a known phrasing; fuzzy matching bridged")
        print("  the gap. Read these before trusting the accuracy figure. A wrong")
        print('  VERB matters most: verbs select the action here ("scan north" vs')
        print('  "report north"), and Stage 2\'s matcher anchors on the verb, so it')
        print("  will not make a repair this bench just made:")
        for clip in repaired[:_SAMPLES_PER_CONFUSION_PAIR]:
            print(
                f"      {clip.expected_token}: {clip.raw_text!r} "
                f"(confidence={clip.confidence:.2f})"
            )
        if len(repaired) > _SAMPLES_PER_CONFUSION_PAIR:
            print(f"      ... and {len(repaired) - _SAMPLES_PER_CONFUSION_PAIR} more")

    correct_conf = [r.confidence for r in results if r.correct]
    incorrect_conf = [r.confidence for r in results if not r.correct]
    print("\nConfidence distribution:")
    print(f"  correct   (n={len(correct_conf)}): {_confidence_summary(correct_conf)}")
    print(
        f"  incorrect (n={len(incorrect_conf)}): {_confidence_summary(incorrect_conf)}"
    )

    n_placeholder = sum(1 for r in results if r.confidence_is_placeholder)
    if n_placeholder:
        print(
            f"\nWARNING: {n_placeholder}/{n} results used a placeholder "
            "confidence of 1.00 -- per-token probabilities were not found "
            "in the whisper.cpp JSON output (see stt_engine.py's module "
            "docstring: this engine's JSON contract is unverified against "
            "a real binary). Treat the confidence columns above as "
            "unreliable until this is checked."
        )


def _confidence_summary(values: list[float]) -> str:
    if not values:
        return "n/a"
    return (
        f"mean={statistics.mean(values):.2f} "
        f"min={min(values):.2f} max={max(values):.2f}"
    )


def _print_prompts() -> None:
    print("Record every phrasing below several times (3-5+), save each as:")
    print("  <corpus-dir>/<token>/<anything>.wav\n")
    for token in TOKENS:
        print(f"{token}:")
        for phrase in PHRASES[token]:
            print(f'  "{phrase}"')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, help="corpus root directory")
    parser.add_argument("--whisper-binary", default="whisper-cli")
    parser.add_argument("--whisper-model", default="")
    parser.add_argument(
        "--with-grammar",
        action="store_true",
        help="also run the constrained-decoding row. Off by default: a "
        "grammar cannot decline, so a mishearing arrives as a confident "
        "wrong command rather than a detectable miss (measured at 31.7%% "
        "on this project's corpus, including 'watch nearest air defence' "
        "read as 'what do you see' at confidence 0.82)",
    )
    parser.add_argument(
        "--grammar-penalty",
        type=float,
        default=None,
        help="whisper-cli --grammar-penalty for the constrained-decoding row",
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="print what to say for every token and exit, without running "
        "any recognizer",
    )
    args = parser.parse_args()

    if args.list_prompts:
        _print_prompts()
        return

    if args.corpus_dir is None:
        parser.error("--corpus-dir is required (or pass --list-prompts)")

    corpus = load_corpus(args.corpus_dir)
    total_clips = sum(len(files) for files in corpus.values())
    print(
        f"Loaded {total_clips} clip(s) across {len(corpus)} token(s) from "
        f"{args.corpus_dir}"
    )
    if total_clips == 0:
        print("Nothing to bench -- record a corpus first (--list-prompts).")
        return

    ran_any = False

    if WhisperCliEngine.is_available(args.whisper_binary) and args.whisper_model:
        no_grammar_engine = WhisperCliEngine(
            binary_path=args.whisper_binary, model_path=args.whisper_model
        )
        results = run_engine("whisper.cpp (plain)", no_grammar_engine, corpus)
        print_report("whisper.cpp (plain)", results)

        prompted_engine = WhisperCliEngine(
            binary_path=args.whisper_binary,
            model_path=args.whisper_model,
            prompt=to_prompt(),
        )
        results = run_engine("whisper.cpp (--prompt)", prompted_engine, corpus)
        print_report("whisper.cpp (--prompt)", results)
        ran_any = True

        if not args.with_grammar:
            return
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gbnf", delete=False
        ) as grammar_file:
            grammar_file.write(to_gbnf())
            grammar_path = grammar_file.name
        try:
            grammar_engine = WhisperCliEngine(
                binary_path=args.whisper_binary,
                model_path=args.whisper_model,
                grammar_path=grammar_path,
                grammar_penalty=args.grammar_penalty,
            )
            results = run_engine("whisper.cpp (grammar)", grammar_engine, corpus)
            print_report("whisper.cpp (grammar)", results)
        finally:
            Path(grammar_path).unlink(missing_ok=True)
    else:
        reason = (
            "whisper-cli binary not found"
            if not WhisperCliEngine.is_available(args.whisper_binary)
            else "--whisper-model not given"
        )
        print(f"\nSkipping whisper.cpp rows: {reason}.", file=sys.stderr)

    if WindowsSpeechEngine.is_available():
        windows_engine = WindowsSpeechEngine(phrases=spoken_phrases())
        results = run_engine("windows-speech", windows_engine, corpus)
        print_report("windows-speech", results)
        ran_any = True
    else:
        print(
            "\nSkipping windows-speech row: not running on Windows.",
            file=sys.stderr,
        )

    if not ran_any:
        print(
            "\nNo engine ran at all. Install whisper.cpp and pass "
            "--whisper-model to get any numbers out of this bench.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
