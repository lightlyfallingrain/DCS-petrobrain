"""The 15-token scan/watch/cancel command vocabulary, mirrored for
`srs-adapter`'s own use (`plans/inbound-speech/plan.md` Stage 1).

This is a **deliberate, hand-synced duplicate**, not a shared import.
`srs-adapter` must stand alone (root `CLAUDE.md`'s module-independence
rule -- the body-layer<->world-model in-process import is the sole
sanctioned exception, and this is not it), so it cannot import
`body-layer/src/belief/crew_console.py`'s `_RELATIVE_SCAN_TOKENS`/
`_BEARING_SCAN_TOKENS` tables directly. `aircraft-layer/src/collector/
f10_command_receiver.py`'s `ALLOWED_COMMANDS` tuple is the same 15 tokens,
hand-synced with that same crew_console.py source and with the Hook
script's F10 menu -- this file follows that established precedent (a third
hand-synced copy) rather than inventing a shared-constants mechanism.

**Keep `TOKENS` and `PHRASES` in sync with `crew_console.py`/
`f10_command_receiver.py` by hand.** There is no automated check tying the
three together.

`PHRASES` is this file's own addition, not mirrored from anywhere -- it is
the recogniser **bias hint list**: the spoken phrasings a constrained
grammar (whisper.cpp `--grammar`, `System.Speech`'s `Choices`) should steer
decoding toward, and the prompt list `tools/stt_bench.py` and the corpus
recording instructions are built from. Several phrasings per token,
matching the examples in `plans/inbound-speech/plan.md` Decision 4 --
deliberately not exhaustive; Stage 1's bench is what will show which
phrasings this user actually says and which get misheard.
"""

from __future__ import annotations

#: The 15-token vocabulary, in the same order as `aircraft-layer`'s
#: `ALLOWED_COMMANDS` and `crew_console.py`'s two lookup tables
#: concatenated (`_RELATIVE_SCAN_TOKENS` then `_BEARING_SCAN_TOKENS`, then
#: the two watch tokens and `cancel_task`).
TOKENS: tuple[str, ...] = (
    "scan_ahead",
    "scan_left",
    "scan_right",
    "scan_full",
    "scan_bearing_n",
    "scan_bearing_ne",
    "scan_bearing_e",
    "scan_bearing_se",
    "scan_bearing_s",
    "scan_bearing_sw",
    "scan_bearing_w",
    "scan_bearing_nw",
    "watch_nearest",
    "watch_nearest_air_defence",
    "cancel_task",
)

#: Spoken phrasings per token. Every token has at least two phrasings so
#: the bench (and later, Stage 2's matcher) sees more than one way of
#: saying the same command -- a single canonical phrase per token would
#: understate how a player actually talks.
PHRASES: dict[str, tuple[str, ...]] = {
    "scan_ahead": ("scan ahead", "look ahead"),
    "scan_left": ("scan left", "look left", "scan to the left"),
    "scan_right": ("scan right", "look right", "scan to the right"),
    "scan_full": ("scan full", "full scan", "scan all around"),
    "scan_bearing_n": ("scan north", "scan bearing north"),
    "scan_bearing_ne": ("scan northeast", "scan bearing northeast"),
    "scan_bearing_e": ("scan east", "scan bearing east"),
    "scan_bearing_se": ("scan southeast", "scan bearing southeast"),
    "scan_bearing_s": ("scan south", "scan bearing south"),
    "scan_bearing_sw": ("scan southwest", "scan bearing southwest"),
    "scan_bearing_w": ("scan west", "scan bearing west"),
    "scan_bearing_nw": ("scan northwest", "scan bearing northwest"),
    "watch_nearest": ("watch nearest", "watch the nearest"),
    "watch_nearest_air_defence": (
        "watch nearest air defence",
        "watch nearest air defense",
    ),
    "cancel_task": ("cancel task", "cancel the task", "cancel"),
}

assert set(PHRASES) == set(TOKENS), "PHRASES and TOKENS have drifted apart"


def spoken_phrases() -> tuple[str, ...]:
    """Every phrasing for every token, flattened, in `TOKENS` order. This
    is the flat list both engines' grammars are built from and the list
    `tools/stt_bench.py` prints as recording prompts."""
    phrases: list[str] = []
    for token in TOKENS:
        phrases.extend(PHRASES[token])
    return tuple(phrases)


def token_for_phrase(phrase: str) -> str | None:
    """The token a known, exact phrasing belongs to, or `None` if `phrase`
    is not one of `PHRASES`' entries verbatim. A simple reverse lookup --
    fuzzy matching against unknown recognizer output is the bench's own
    job (`tools/stt_bench.py`), not this module's."""
    for token, phrasings in PHRASES.items():
        if phrase in phrasings:
            return token
    return None


def to_gbnf() -> str:
    """A minimal GBNF grammar restricting decoding to exactly this
    vocabulary's phrasings, for whisper.cpp's `--grammar` flag.

    whisper.cpp (and llama.cpp, which it shares grammar sampling with)
    accepts a GBNF grammar file with a `root` rule; a flat alternation of
    quoted literals is the simplest grammar that admits only our phrases
    and nothing else. **Unverified against a real `whisper-cli` run** --
    no whisper.cpp binary was available while writing this (see Stage 1's
    implementation notes) -- this is written from whisper.cpp's public
    `--grammar` documentation and llama.cpp's GBNF spec, not confirmed
    live. Bench with `--grammar` vs. without is exactly the run that
    validates (or corrects) this.
    """
    alternatives = " | ".join(f'"{phrase}"' for phrase in spoken_phrases())
    return f"root ::= {alternatives}\n"
