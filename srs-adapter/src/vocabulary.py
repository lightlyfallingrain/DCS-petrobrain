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
    (
        "report_all",
        "stop_talking",
        "say_again",
        "scan_bearing_deg",
        "report_bearing_deg",
    )
    + tuple(f"report_bearing_{d}" for d in ("n", "ne", "e", "se", "s", "sw", "w", "nw"))
    + tuple(f"report_clock_{p}" for p in FORWARD_CLOCK_POSITIONS)
)

#: Numeric bearings are a **slot, not an enumeration** (user direction,
#: 2026-09-19: *"'<verb> bearing <south/etc>' is something I'll never
#: actually say. Just '<verb> south'. On the other hand '<verb> bearing
#: 320' is entirely possible."*). The compass words keep their bare form
#: and lose the "bearing" form entirely; degrees arrive as a parsed
#: number instead.
#:
#: Spoken digit by digit, always three digits ("bearing three two zero",
#: "bearing zero zero five"), which is standard readback form and removes
#: the ambiguity between 50, 350 and 005 by construction.
BEARING_RESOLUTION_DEG = 5

#: Every legal bearing: 0, 5, 10 ... 355.
LEGAL_BEARINGS_DEG: tuple[int, ...] = tuple(range(0, 360, BEARING_RESOLUTION_DEG))

_DIGIT_NAMES: tuple[str, ...] = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)

#: Bearings sampled for the recording corpus. Not the legal set -- 72
#: values times two verbs is not a thing anybody should record, and the
#: matcher accepts all of them regardless. These are chosen so that
#: **every digit 0-9 is spoken at least once**, which is what the bench
#: actually needs to measure: numbers are the accent-fragile part, and
#: what matters is per-digit reliability rather than per-bearing.
_SAMPLED_SCAN_BEARINGS: tuple[int, ...] = (0, 45, 60, 90, 135, 180, 225, 270, 315)
_SAMPLED_REPORT_BEARINGS: tuple[int, ...] = (5, 180, 355)


def bearing_digits(degrees: int) -> str:
    """ "three two zero" for 320 -- always three digit words."""
    return " ".join(_DIGIT_NAMES[int(d)] for d in f"{degrees % 360:03d}")


def bearing_phrase(verb: str, degrees: int) -> str:
    return f"{verb} bearing {bearing_digits(degrees)}"


#: Tokens that route or retract a transmission rather than commanding
#: anything (user direction, 2026-09-19). They are listed here because the
#: recogniser must hear them and the bench must measure them, but nothing
#: downstream should ever dispatch them as commands -- see each entry's
#: phrasing note below, and `plans/inbound-speech/plan.md` for the tiering
#: design they belong to.
#:
#: `wake_petrovich` is the tier discriminator: a transmission beginning
#: with it is free speech for the brain layer, and one without it is a
#: command matched against this vocabulary. **Its two failure modes are
#: not symmetric.** A false wake sends a command to the brain, which can
#: interpret a command phrasing perfectly well -- the cost is latency. A
#: missed wake sends free speech to the command matcher, which will
#: fuzzy-match it onto *something* and execute a wrong action. So
#: detection should lean toward waking, and the bench's job is to say how
#: often this word survives at all: it is a Russian name spoken with a
#: Finnish accent, which is the least favourable case in the whole
#: vocabulary.
#:
#: `cancel_nevermind` retracts the transmission it ends. Its existence is
#: what forbids acting on anything before the transmission closes, since
#: the last word can withdraw everything before it. Every decision
#: therefore happens at PTT release, with no exceptions -- including
#: `stop_talking`, which an earlier draft had firing mid-stream for
#: barge-in latency.
ROUTING_TOKENS: tuple[str, ...] = ("wake_petrovich", "cancel_nevermind")

#: Every token the recogniser should admit. This, not any subgroup, is
#: what the grammar, the bench and Stage 2's matcher are built from.
TOKENS: tuple[str, ...] = LEGACY_F10_TOKENS + VOICE_ONLY_TOKENS + ROUTING_TOKENS

#: Spoken phrasings per token. Every token has at least two phrasings so
#: the bench (and later, Stage 2's matcher) sees more than one way of
#: saying the same command -- a single canonical phrase per token would
#: understate how a player actually talks.
PHRASES: dict[str, tuple[str, ...]] = {
    "scan_ahead": ("scan ahead", "look ahead"),
    "scan_left": ("scan left", "look left", "scan to the left"),
    "scan_right": ("scan right", "look right", "scan to the right"),
    "scan_full": ("scan full", "full scan", "scan all around"),
    "scan_bearing_n": ("scan north",),
    "scan_bearing_ne": ("scan northeast",),
    "scan_bearing_e": ("scan east",),
    "scan_bearing_se": ("scan southeast",),
    "scan_bearing_s": ("scan south",),
    "scan_bearing_sw": ("scan southwest",),
    "scan_bearing_w": ("scan west",),
    "scan_bearing_nw": ("scan northwest",),
    "watch_nearest": ("watch nearest", "watch the nearest"),
    "watch_nearest_air_defence": (
        "watch nearest air defence",
        "watch nearest air defense",
    ),
    "cancel_task": ("cancel task", "cancel the task", "cancel"),
    # Voice-only. `report` carries three phrasings because it is the
    # command most likely to be said casually and differently each time.
    "report_all": ("report", "report contacts", "what do you see"),
    # **Exactly one phrasing, and it counts only when it is the entire
    # transmission** (user direction, 2026-09-19: "Let's just use 'stop'
    # for this purpose. It's simple."). A "stop" inside a sentence --
    # "stop scanning north" -- is not the stop rule.
    #
    # The single phrasing is not an oversight. Admitting "stop talking"
    # or "quiet" as command phrasings while routing only on a bare "stop"
    # would contradict itself: the longer forms would trigger the same
    # behaviour through the command matcher, by the back door, and the
    # whole-transmission rule would no longer mean what it says.
    #
    # The known risk of that simplicity: `stop` aborts Petrovich's speech,
    # so a miss leaves him talking over something the player needs to
    # hear. It is a single short syllable, the hardest thing for a
    # recogniser to catch, and on clean synthetic speech it already came
    # back as "cloud" and "stock". With the alternates gone there is no
    # fallback word -- so if Stage 1's bench shows this token unreliable
    # on the user's own voice, the decision genuinely needs revisiting
    # rather than tuning around. Revisiting is cheap: adding a phrasing
    # is a handful of clips, not a re-recorded corpus.
    "stop_talking": ("stop",),
    # Standard aviation practice, and deliberately bidirectional: the
    # player says it when he missed what Petrovich said, and Petrovich
    # says it when recognition confidence falls below the band Stage 1's
    # bench measures. Asking beats both guessing and silence -- a crew
    # member who did not catch something says so.
    "say_again": ("say again", "repeat", "repeat that"),
    # Routing, not commands -- see ROUTING_TOKENS.
    #
    # The wake word carries both the bare and the greeted form because a
    # player says both, often in the same sortie. It is also the one
    # entry here whose *misses* matter more than its confusions, so the
    # bench's per-clip listing is worth reading for this token even if
    # the headline accuracy looks acceptable.
    "wake_petrovich": ("petrovich", "hey petrovich"),
    # "disregard" is the formal radio equivalent and costs one more
    # recording to find out which of the three actually survives this
    # speaker's accent.
    "cancel_nevermind": ("nevermind", "never mind", "disregard"),
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
    PHRASES[f"report_bearing_{_direction}"] = (f"report {_word}",)

#: `report <clock>` -- one phrasing each, unlike every other token here.
#: The discriminating content is the number word itself, which one carrier
#: phrase already isolates; a second carrier would multiply recording time
#: without adding evidence about the number. Numbers are the accent-fragile
#: part of this vocabulary, so what matters is takes per number, not
#: phrasings per number.
PHRASES["scan_bearing_deg"] = tuple(
    bearing_phrase("scan", d) for d in _SAMPLED_SCAN_BEARINGS
)
PHRASES["report_bearing_deg"] = tuple(
    bearing_phrase("report", d) for d in _SAMPLED_REPORT_BEARINGS
)

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


#: Digit -> number-word, for the clock positions this vocabulary uses.
#: Recognizers transcribe "report three o'clock" as "report 3 o'clock"
#: (observed on both `ggml-base.en` and `ggml-small.en`, see
#: `research/2026-09-19-whisper-contract-and-grammar-probe.md`). `PHRASES`
#: spells the words out because that is what a person says, so something
#: has to bridge the two representations.
_DIGIT_WORDS: dict[str, str] = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "11": "eleven",
    "12": "twelve",
}

#: Compass words a recognizer may split or hyphenate ("north west",
#: "north-west") where this vocabulary writes them solid ("northwest").
_COMPASS_JOINS: tuple[tuple[str, str], ...] = (
    ("north east", "northeast"),
    ("north west", "northwest"),
    ("south east", "southeast"),
    ("south west", "southwest"),
)

#: Apostrophe variants in "o'clock". A recognizer may emit a typographic
#: apostrophe, a straight one, or drop it entirely.
_OCLOCK_VARIANTS: tuple[str, ...] = (
    "o’clock",
    "o clock",
    "oclock",
)


def normalize_for_match(text: str) -> str:
    """Fold recognizer output and a known phrasing onto common ground.

    Applied to **both sides** of a comparison -- raw recognizer text and
    the `PHRASES` entry it is being matched against -- so the two meet in
    the middle rather than one being bent toward the other.

    What it folds away is everything observed to differ without carrying
    meaning: surrounding whitespace and case, trailing punctuation
    (whisper returns `" Scan left."` where the phrase is `"scan left"`),
    typographic apostrophes, hyphenated or split compass words, and
    digits written where this vocabulary spells number words.

    **The digit case is the one that matters.** Without it every
    `report_clock_*` clip scores as a miss while having been heard
    perfectly, which on a bench report is indistinguishable from a
    recognition failure -- precisely the wrong conclusion to hand
    someone judging whether recognition works on their voice.

    Deliberately conservative: it does not stem, drop filler words, or
    reorder. Those are matching decisions, and they belong to the matcher
    that has to decide whether to *act* on a phrase, not to a
    normalization step shared with scoring.
    """
    normalized = text.strip().lower()
    for variant in _OCLOCK_VARIANTS:
        normalized = normalized.replace(variant, "o'clock")
    normalized = normalized.replace("-", " ")
    normalized = "".join(char for char in normalized if char.isalnum() or char in " '")
    normalized = " ".join(normalized.split())
    for split_form, solid in _COMPASS_JOINS:
        normalized = normalized.replace(split_form, solid)
    words = [_DIGIT_WORDS.get(word, word) for word in normalized.split()]
    return " ".join(words)


def normalized_phrase_index() -> dict[str, str]:
    """`normalize_for_match`ed phrasing -> token, for scoring lookups.

    A collision here would mean two tokens becoming indistinguishable
    after normalization, which would silently make one of them
    unreachable, so it is an error rather than a last-write-wins dict.
    """
    index: dict[str, str] = {}
    for token in TOKENS:
        for phrase in PHRASES[token]:
            key = normalize_for_match(phrase)
            existing = index.get(key)
            if existing is not None and existing != token:
                raise ValueError(
                    f"normalization collapses {token!r} and {existing!r} "
                    f"onto the same text {key!r}"
                )
            index[key] = token
    return index


#: Number words a recognizer may return in place of digits, for the
#: bearing parser. Wider than `_DIGIT_NAMES` because whisper writes some
#: digits as words and others numerically in the same sentence.
_WORD_DIGITS: dict[str, str] = {name: str(i) for i, name in enumerate(_DIGIT_NAMES)}


class BearingParse:
    """Outcome of reading a numeric bearing out of a transcript.

    Three outcomes rather than two, and the third is the useful one.
    `degrees` set means a legal bearing was read. `degrees is None` with
    `heard` set means digits were found but they do not name a legal
    bearing -- which is a *detected* recognition error, not a silent one.
    Both `None` means no bearing was spoken at all.
    """

    __slots__ = ("degrees", "heard")

    def __init__(self, degrees: int | None, heard: int | None) -> None:
        self.degrees = degrees
        self.heard = heard

    def __repr__(self) -> str:
        return f"BearingParse(degrees={self.degrees}, heard={self.heard})"


def parse_bearing(text: str) -> BearingParse:
    """Read a bearing from recognizer output after the word "bearing".

    Accepts digits and number words interchangeably ("bearing 320",
    "bearing three two zero", "bearing 3 2 0"), because recognizers mix
    the two freely -- whisper returned "3" for a spoken "three" in one
    clip and spelled it out in another.

    **The 5 degree resolution is a checksum, and that is the point.**
    Bearings are constrained to multiples of five, so roughly four out of
    five possible mishearings land on a value that cannot be a real
    bearing. Those are returned as `heard` without `degrees`, so the
    caller can ask the player to say again rather than turning to a
    number nobody said. A wrong heading flown confidently is a far worse
    failure than one more readback, and this makes most of that class
    detectable for free.

    It cannot catch everything: a mishearing that lands on another
    multiple of five ("three two zero" heard as "three three zero") is
    indistinguishable from a correct reading here, and only the readback
    protects against it.
    """
    normalized = normalize_for_match(text)
    words = normalized.split()
    if "bearing" not in words:
        return BearingParse(None, None)

    digits: list[str] = []
    for word in words[words.index("bearing") + 1 :]:
        if word in _WORD_DIGITS:
            digits.append(_WORD_DIGITS[word])
        elif word.isdigit():
            digits.extend(word)
        else:
            break
    if not digits:
        return BearingParse(None, None)

    value = int("".join(digits))
    if value > 359 or value % BEARING_RESOLUTION_DEG != 0:
        return BearingParse(None, value)
    return BearingParse(value, value)
