# whisper.cpp CLI contract, and what a grammar actually does

**Date:** 2026-09-19 · **whisper.cpp 1.9.4** (Homebrew, arm64) · models `ggml-base.en`, `ggml-small.en`

Probed while setting up Stage 1's bench, before any corpus existed. All clips here are macOS `say`
output, **not the user's voice** — so nothing below says anything about accent. What it does settle
is the tool contract and the behaviour of constrained decoding, both of which were assumptions
`stt_engine.py` was written against and neither of which had been run.

## The contract is as assumed, with one exception

`-ojf` emits `transcription[].text` and per-token `tokens[].p`. `Transcript.confidence` therefore
reads real probabilities, and the placeholder-confidence fallback is a guard against future schema
drift rather than the expected path.

**The exception: `--grammar` alone does nothing.** whisper-cli loads the grammar, echoes it to
stderr, and ignores it unless `--grammar-rule` names the top-level rule — despite `--help` showing
an empty default. `--grammar-penalty` is inert alongside it.

| clip | `--grammar` | `--grammar` + `--grammar-rule root` |
|---|---|---|
| "the weather is quite nice today" (out of vocabulary) | unchanged, verbatim | constrained immediately |

This mattered more than an ordinary flag bug. Stage 1 exists to answer a stop/go question, and one
of its two axes is whether constrained decoding helps or hurts. With the rule name missing, the
with-grammar row would have silently duplicated the without-grammar row and the run would have read
as *"constrained decoding makes no difference for me"* — a wrong answer with no visible symptom.
Fixed in `stt_engine.py`, with a test asserting the flag pairing rather than the behaviour, since
the pairing needs no binary.

## `--grammar-penalty` is a real dial with a usable middle, not a switch

Same clip ("report three o'clock"), grammar active, penalty swept:

| penalty | output |
|---|---|
| 1 | `" Record 3 o'clock."` — grammar effectively inert |
| 10 | `" Record 3 o'clock."` — still inert |
| 50 | `"sto"` — collapse |
| 100 (whisper's default) | `"sto"` — collapse |

Longer phrases collapse to a fragment at high penalty while short ones come back clean: under
grammar at default penalty, "scan left" → `"scan left"` and "watch nearest" → `"watch nearest"`
(exact matches, none of the capitalisation or trailing-period noise free decoding produces), but
"scan bearing northwest" → `"f"` and "report three o'clock" → `"sto"`.

**Consequence for the bench:** whisper's default penalty of 100 sits in the collapse region for
this vocabulary's longer phrases, so a single with-grammar row at the default would understate
constrained decoding rather than measure it. The useful figure is a sweep — somewhere between 10
and 50 there is a penalty that constrains without collapsing, and finding it is what sets the
constant Decision 4 needs. Run the bench at several `--grammar-penalty` values rather than once.

## Two findings that affect the vocabulary, not the tooling

**1. "report" is misheard as "record" by `base.en`, and correctly by `small.en`.**

| model | "report three o'clock", free decoding |
|---|---|
| `base.en` | `" Record 3 o'clock."` |
| `small.en` | `" Report 3 o'clock."` |

The newly-added `report` verb is exactly where the two models diverge, on synthetic speech with no
accent at all. Whatever happens on the real corpus, `small.en` needs to be in the comparison — a
base-only run could reject the `report` vocabulary for a reason that is the model's, not the
speaker's.

**2. Both models transcribe the number as a digit: `"3"`, not `"three"`.**

`vocabulary.PHRASES` spells clock positions as words, because that is what a person says. The
recogniser returns digits. Nothing is wrong with either, but the matcher has to bridge them:
**Stage 2's matcher must normalise digits and number words to each other before comparing.** Left
unhandled, every clock command would score as a miss while being heard perfectly — and on the bench
that would look like a recognition failure rather than a normalisation gap. `stt_bench.py`'s own
scoring matcher needs the same treatment, or the corpus's clock tokens will read as a wall of
confusions.

## What this does not tell us

Nothing here involves the user's voice, his headset, or his accent, and synthetic `say` audio is
unrealistically clean. The accent question — the entire point of Stage 1's gate — remains open
until the real corpus is recorded on the Windows box.
