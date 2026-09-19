"""The spoken command vocabulary (`plans/inbound-speech/plan.md` Stage 1).

**This file is the primary command vocabulary, not a mirror of the F10
menu.** It began as a hand-synced duplicate of that menu, and the
docstrings and tests here said so; the user's direction on 2026-09-19
inverted the relationship: *"The F10 menu is only a temporary solution.
Voice is primary. It's alright if F10 menu goes stale, we'll remove it at
some point."* So the F10 command set is now the derived, legacy thing,
and this vocabulary is free to grow past it.

The split below is kept, but only as history rather than an obligation.
`LEGACY_F10_TOKENS` are the 15 that happen to coincide with the F10 menu
today, and `VOICE_ONLY_TOKENS` are the ones that never existed there.
**Divergence between the two is expected and is not a bug** -- do not
"fix" a mismatch against `aircraft-layer`'s `ALLOWED_COMMANDS` by
deleting anything here. When the F10 path is removed the split collapses
and both tuples fold into `TOKENS`.
`srs-adapter` must stand alone (root `CLAUDE.md`'s module-independence
rule -- the body-layer<->world-model in-process import is the sole
sanctioned exception, and this is not it), so it cannot import
`body-layer/src/belief/crew_console.py`'s `_RELATIVE_SCAN_TOKENS`/
`_BEARING_SCAN_TOKENS` tables directly. `aircraft-layer/src/collector/
f10_command_receiver.py`'s `ALLOWED_COMMANDS` tuple is the same 15 tokens,
hand-synced with that same crew_console.py source and with the Hook
script's F10 menu -- this file follows that established precedent (a third
hand-synced copy) rather than inventing a shared-constants mechanism.

Nothing here is synced automatically, and as of the direction above
nothing here needs to be synced at all. Stage 2's matcher and the
body-layer command path are where these tokens acquire behaviour; that
path is the one that must cover `TOKENS`, and it is independent of
whatever the F10 menu still offers.

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

#: The 15 tokens that also exist in the legacy F10 radio menu, in that
#: menu's own order. Kept as a named group for traceability while the F10
#: path still runs; it carries no obligation to match, since that path is
#: being retired (see this module's docstring). Expect it to fold into
#: `TOKENS` when F10 is removed.
LEGACY_F10_TOKENS: tuple[str, ...] = (
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

#: Clock positions worth recognising: 8 through 4 the short way round,
#: i.e. the forward hemisphere. Deliberately not all twelve (user
#: direction, 2026-09-19). The reason is not recording time but the
#: project's own no-omniscience rule: Petrovich cannot see behind the
#: aircraft, so "report six o'clock" names a direction he has nothing to
#: report about. A command whose only honest answer is "I can't see
#: there" is not worth teaching a recogniser.
FORWARD_CLOCK_POSITIONS: tuple[int, ...] = (8, 9, 10, 11, 12, 1, 2, 3, 4)

#: Spoken number words for `FORWARD_CLOCK_POSITIONS`, since a recogniser
#: transcribes words rather than digits.
_CLOCK_WORDS: dict[int, str] = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}

#: `report_all` and `stop_talking` are flat commands. The `report_bearing_*`
#: and `report_clock_*` families are the `report <target>` form, enumerated
#: rather than parsed as a slot because a closed grammar has to list what it
#: admits. Unit- and group-named targets ("report the tanks") are
#: deliberately absent: that target set is open, so it cannot be enumerated
#: into a grammar, and it belongs to free speech once the brain layer exists.
#: Commands with no F10 equivalent -- the first vocabulary this project
#: added for voice on its own terms rather than by transcribing a menu.
VOICE_ONLY_TOKENS: tuple[str, ...] = (
    ("report_all", "stop_talking")
    + tuple(f"report_bearing_{d}" for d in ("n", "ne", "e", "se", "s", "sw", "w", "nw"))
    + tuple(f"report_clock_{p}" for p in FORWARD_CLOCK_POSITIONS)
)

#: Every token the recogniser should admit. This, not either subgroup, is
#: what the grammar, the bench and Stage 2's matcher are built from.
TOKENS: tuple[str, ...] = LEGACY_F10_TOKENS + VOICE_ONLY_TOKENS

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
    # Voice-only. `report` carries three phrasings because it is the
    # command most likely to be said casually and differently each time.
    "report_all": ("report", "report contacts", "what do you see"),
    # `stop` is the shortest and most safety-critical word here -- it
    # aborts speech mid-sentence, so a miss leaves Petrovich talking over
    # something the player needs to hear, and a false positive silences
    # him for no reason. A single short syllable is also the hardest
    # thing for a recogniser to catch reliably. The alternates are
    # recorded so the bench can say which of them actually survives,
    # rather than committing to "stop" and discovering the problem in
    # the cockpit.
    "stop_talking": ("stop", "stop talking", "quiet"),
}

#: `report <compass>` -- the same eight directions `scan_bearing_*` uses,
#: under a different verb. The pairing is deliberate: "scan north" and
#: "report north" differ only in the verb, and confusing them swaps one
#: action for another rather than merely garbling a word. If the bench
#: finds that pair unreliable, the fix is a vocabulary change, and Stage 1
#: is when that is still cheap.
for _direction, _word in (
    ("n", "north"),
    ("ne", "northeast"),
    ("e", "east"),
    ("se", "southeast"),
    ("s", "south"),
    ("sw", "southwest"),
    ("w", "west"),
    ("nw", "northwest"),
):
    PHRASES[f"report_bearing_{_direction}"] = (
        f"report {_word}",
        f"report bearing {_word}",
    )

#: `report <clock>` -- one phrasing each, unlike every other token here.
#: The discriminating content is the number word itself, which one carrier
#: phrase already isolates; a second carrier would multiply recording time
#: without adding evidence about the number. Numbers are the accent-fragile
#: part of this vocabulary, so what matters is takes per number, not
#: phrasings per number.
for _position in FORWARD_CLOCK_POSITIONS:
    PHRASES[f"report_clock_{_position}"] = (
        f"report {_CLOCK_WORDS[_position]} o'clock",
    )

assert set(PHRASES) == set(TOKENS), "PHRASES and TOKENS have drifted apart"
assert not set(LEGACY_F10_TOKENS) & set(VOICE_ONLY_TOKENS), "a token cannot be both"


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
    and nothing else.

    **Verified against whisper.cpp 1.9.4 (Homebrew, arm64), 2026-09-19.**
    This grammar parses and constrains decoding as intended -- but only
    when the caller also passes `--grammar-rule root`, which
    `stt_engine.WhisperCliEngine` now does. The rule name here and
    `stt_engine.GRAMMAR_ROOT_RULE` must stay in agreement; a mismatch
    fails silently, leaving decoding unconstrained rather than erroring.
    """
    alternatives = " | ".join(f'"{phrase}"' for phrase in spoken_phrases())
    return f"root ::= {alternatives}\n"
