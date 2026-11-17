"""Pattern grammar v1 and the typed slot-type registry for rule files
(`plans/speech-rules/plan.md` D7, Stage 1b item 1) -- the adapter-side
half of `[[BL-17]]`: body-layer loads `*.lua` and pushes `(id, pattern)`
pairs here over `PUT /rules`; this module parses, compiles, matches, and
runs the load-time collision check (D9) over them. Handlers run only in
body-layer -- nothing here ever executes Lua.

**Grammar** (D7): a pattern is a sequence of elements, each either

- a bare literal word the pilot must say,
- `[ ... ]`, an optional group that may itself contain literals and/or
  slots (not nested optionals -- no shipped rule needs that yet),
- `<name:type>`, a slot of a type in `SLOT_TYPES` below,
- `<name:w1|w2>`, a word-set slot -- the value is the exact word heard.

**Matching**: a rule matches a transcript only on **full consumption** --
every element must consume its words and nothing may be left over. A
`LiteralElement` accepts the heard word on exact equality, or (`[[BL-17]]`
D13, Stage 3a) on a `_WORD_REPAIR_FLOOR`-or-better character ratio against
it -- the same per-word repair floor the legacy matcher's own
`_phrase_match_ratio` already uses, not a second hand-tuned number
(`vocabulary._WORD_REPAIR_FLOOR`, relocated there specifically so both
matching modules can import the one value, see that constant's own
comment). **A `SlotElement`/`WordSetElement` never gets this fallback**:
its own typed `consume`/exact-word check either succeeds exactly or the
rule does not match at that position -- this is what keeps a rule's
*values* (a number, "left"/"right", an hour) heard exactly while its
*wording* tolerates STT noise (goal check E12, "fuzziness forgives the
words, never the values"). A match's own ratio is therefore no longer
always `1.0` -- see `match_pattern_with_ratio`.

**`heading`/`bearing` (user direction, 2026-11-17, mid-Stage-1b):**
*"Until I provide decisions about how to handle 'bearing', treat
'heading' as the unit we mainly use. It is always a world compass three
digit number in degrees 000-360."* So `heading` is built now (word
"heading" + exactly 3 digits, 0-359, 360 normalises to 0, no checksum);
`bearing` stays unbuilt. Neither rename nor change the meaning of any
*existing* spoken command (`"scan bearing"`/`"report bearing"` keep
today's behaviour unchanged -- this module has no reader of either yet).
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass

from vocabulary import _WORD_DIGITS, _WORD_REPAIR_FLOOR

__all__ = [
    "SLOT_TYPES",
    "CachedRulePromptProvider",
    "CompiledRule",
    "Element",
    "LegacyProbe",
    "LegacyProbeResult",
    "LiteralElement",
    "OptionalElement",
    "PatternError",
    "RuleRegistry",
    "RuleRejection",
    "SlotElement",
    "SlotType",
    "WordSetElement",
    "compile_rules",
    "generate_samples",
    "match_pattern",
    "match_pattern_with_ratio",
    "parse_pattern",
    "rule_anchor_words",
    "rule_words",
]


class PatternError(Exception):
    """A pattern string is not valid grammar -- bad brackets, a slot with
    no name, or an unknown slot type."""


@dataclass(frozen=True)
class LiteralElement:
    word: str


@dataclass(frozen=True)
class SlotElement:
    name: str
    type_name: str


@dataclass(frozen=True)
class WordSetElement:
    name: str
    words: tuple[str, ...]


@dataclass(frozen=True)
class OptionalElement:
    elements: tuple[Element, ...]


Element = LiteralElement | SlotElement | WordSetElement | OptionalElement


# ---------------------------------------------------------------------------
# Slot types (D7's table). Each type's `consume` sees the already-
# normalised, filler-stripped, lowercase word list a transcript becomes
# (`vocabulary.normalize_for_match`'s own pipeline -- the same words the
# legacy matcher scores against), and the index of its own first word.
# Returns `(value, next_index)` on a successful parse, `None` if nothing
# at `idx` fits this type -- which means the *rule* did not match, not an
# error. `sample` returns one concrete spoken form, for `generate_samples`
# below.
# ---------------------------------------------------------------------------


def _consume_digit_run(
    words: list[str], idx: int, min_digits: int, max_digits: int
) -> tuple[str, int] | None:
    """Consumes consecutive digit tokens starting at `idx` -- a digit
    word ("three") or a whole numeral string ("315") each contribute
    their own digit characters to one concatenated run, mirroring
    `vocabulary._read_digits_after`'s own number-collapse convention
    ("315" = "3 1 5" = "three one five"), but also returning how many
    *words* were consumed (that function only returns the integer).
    `None` if the resulting digit count falls outside
    `[min_digits, max_digits]`, or nothing numeric is at `idx` at all."""
    digits: list[str] = []
    i = idx
    while i < len(words):
        word = words[i]
        if word in _WORD_DIGITS:
            digits.append(_WORD_DIGITS[word])
            i += 1
        elif word.isdigit():
            digits.append(word)
            i += 1
        else:
            break
    if not digits:
        return None
    digit_str = "".join(digits)
    if not (min_digits <= len(digit_str) <= max_digits):
        return None
    return digit_str, i


#: Units (0-9) for the composed natural-number grammar below (D14) --
#: deliberately its own table rather than reusing `_WORD_DIGITS` (whose
#: values are *digit characters* for `_consume_digit_run`'s concatenation,
#: not integers for arithmetic).
_UNITS_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}

#: Teens (10-19), for the composed natural-number grammar (D14).
_TEENS_WORDS: dict[str, int] = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

#: Tens (20-90), for the composed natural-number grammar (D14) -- each
#: optionally followed by a units word ("twenty two").
_TENS_WORDS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _consume_small_number_word(words: list[str], idx: int) -> tuple[int, int] | None:
    """One grammar unit of the composed natural-number phrase (D14): a
    bare unit (0-9), a teen (10-19), or a tens word optionally followed
    by a non-zero unit ("twenty two"). Used both standalone (a plain
    10-99 word) and as the hundreds group's own multiplier/remainder in
    `_consume_number_word_phrase` below."""
    if idx >= len(words):
        return None
    word = words[idx]
    if word in _TENS_WORDS:
        value = _TENS_WORDS[word]
        next_idx = idx + 1
        if next_idx < len(words) and words[next_idx] in _UNITS_WORDS:
            unit = _UNITS_WORDS[words[next_idx]]
            if unit != 0:
                return value + unit, next_idx + 1
        return value, next_idx
    if word in _TEENS_WORDS:
        return _TEENS_WORDS[word], idx + 1
    if word in _UNITS_WORDS:
        return _UNITS_WORDS[word], idx + 1
    return None


def _consume_number_word_phrase(words: list[str], idx: int) -> tuple[int, int] | None:
    """A composed English number word/phrase (D14): one small-number
    group (above), optionally extended into the hundreds by a **bare
    units** multiplier (1-9) + the literal "hundred" + an optional
    trailing small-number group ("three hundred twenty", "one hundred
    fifty three"). Only a bare units word multiplies "hundred" --
    "twenty hundred"/"thirteen hundred" are not forms Q10 names, and
    "thousand" composition is out of scope this stage (D14).

    **Terminates at the first complete number, never concatenates two**
    (D14's own design principle): a paired form like "three fifteen"
    parses only as far as "three" (a complete unit, 3) -- "fifteen" is
    a complete number in its own right, not a continuation, so this
    function stops and leaves it for the caller (full-consumption
    matching) to reject as unconsumed, rather than silently combining
    the two into 315 or 15."""
    small = _consume_small_number_word(words, idx)
    if small is None:
        return None
    value, next_idx = small
    if 1 <= value <= 9 and next_idx < len(words) and words[next_idx] == "hundred":
        after_hundred = next_idx + 1
        remainder = _consume_small_number_word(words, after_hundred)
        if remainder is not None:
            remainder_value, remainder_idx = remainder
            return value * 100 + remainder_value, remainder_idx
        return value * 100, after_hundred
    return value, next_idx


def _consume_natural_number(
    words: list[str], idx: int, digit_min: int, digit_max: int
) -> tuple[int, int] | None:
    """A digit run (`_consume_digit_run`, bounded `[digit_min,
    digit_max]` digits -- today's "315" = "3 1 5" = "three one five"
    collapse) or a composed natural-number word/phrase
    (`_consume_number_word_phrase`), whichever actually captures more of
    the utterance. Shared by `angle` and `quantity` (D14's "Corrected
    2026-11-17" note: `angle` gains the same number-word grammar as
    `quantity`, keeping its own digit bound and range check).

    **The one override**: a digit run that consumed a single bare
    *units word* (not a numeral literal like "3") immediately followed
    by the literal "hundred" defers to the word-phrase parse instead --
    "three" followed by "hundred" is one number composed across
    "hundred", not "three" cut short by a word the digit grammar does
    not know. Without this override, `_consume_digit_run` would
    (correctly, by its own rules) stop at "three" and hand back `(3, 1
    word)`, leaving "hundred" to break the rest of the pattern."""
    digit_result = _consume_digit_run(words, idx, digit_min, digit_max)
    word_result = _consume_number_word_phrase(words, idx)
    if (
        digit_result is not None
        and digit_result[1] - idx == 1
        and words[idx] in _UNITS_WORDS
        and word_result is not None
        and word_result[1] > digit_result[1]
    ):
        return word_result
    if digit_result is not None:
        digit_str, next_idx = digit_result
        return int(digit_str), next_idx
    return word_result


def _consume_angle(words: list[str], idx: int) -> tuple[object, int] | None:
    """1-3 digits or a composed number word, no anchor word of its own,
    value 1-359 (D7: the bare number in e.g. "turn left <degrees:angle>").
    Gained the number-word grammar in D14's own "Corrected 2026-11-17"
    note -- the user's own example for wanting number words at all is
    this slot ("turn left thirty")."""
    result = _consume_natural_number(words, idx, 1, 3)
    if result is None:
        return None
    value, next_idx = result
    if not (1 <= value <= 359):
        return None
    return value, next_idx


def _consume_quantity(words: list[str], idx: int) -> tuple[object, int] | None:
    """`quantity` (D14): a digit run (any count 1-4 digits) or a
    composed natural-number word/phrase -- see `_consume_natural_number`.
    No range check of its own; a command using this slot (e.g. an
    altitude/speed amount) applies whatever range makes sense for it."""
    result = _consume_natural_number(words, idx, 1, 4)
    if result is None:
        return None
    value, next_idx = result
    return value, next_idx


def _consume_speed_target(words: list[str], idx: int) -> tuple[object, int] | None:
    """`speed_target` (D14): a union slot, the literal word "max"
    (`{"kind": "max"}`) or else `quantity`'s own grammar (`{"kind":
    "number", "value": N}`) -- what lets "speed max" and "speed two
    hundred" share one pattern slot. The tagged-table wire convention is
    D7's own (pulled forward one stage early from the marks stage's
    `direction`/`origin` union types)."""
    if idx < len(words) and words[idx] == "max":
        return {"kind": "max"}, idx + 1
    quantity_result = _consume_quantity(words, idx)
    if quantity_result is None:
        return None
    value, next_idx = quantity_result
    return {"kind": "number", "value": value}, next_idx


def _consume_heading(words: list[str], idx: int) -> tuple[object, int] | None:
    """The word "heading" + exactly 3 digits, 0-360 inclusive (360
    normalises to 0) -- user direction, 2026-11-17 (module docstring).
    No checksum."""
    if idx >= len(words) or words[idx] != "heading":
        return None
    result = _consume_digit_run(words, idx + 1, 3, 3)
    if result is None:
        return None
    digit_str, next_idx = result
    value = int(digit_str)
    if value > 360:
        return None
    return (0 if value == 360 else value), next_idx


#: 1-12, for `oclock` -- deliberately a small table of its own rather than
#: reusing `vocabulary._RANGE_NUMBER_WORDS` (1-20, a different slot's own
#: range) or `vocabulary._CLOCK_WORD_TO_HOUR` (restricted to the forward
#: hemisphere, a domain restriction that belongs to the *commands* that
#: use a clock position, not to this generic grammar type).
_OCLOCK_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def _consume_oclock(words: list[str], idx: int) -> tuple[object, int] | None:
    """1-12 + "o'clock" (D7). `normalize_for_match` has already folded
    every apostrophe spelling onto `"o'clock"` before this ever runs."""
    if idx >= len(words):
        return None
    word = words[idx]
    hour: int | None = _OCLOCK_WORDS.get(word)
    if hour is None and word.isdigit():
        candidate = int(word)
        if 1 <= candidate <= 12:
            hour = candidate
    if hour is None:
        return None
    next_idx = idx + 1
    if next_idx >= len(words) or words[next_idx] != "o'clock":
        return None
    return hour, next_idx + 1


@dataclass(frozen=True)
class SlotType:
    name: str
    consume: Callable[[list[str], int], tuple[object, int] | None]
    #: One concrete spoken form, for `generate_samples`'s own collision
    #: probes (D9) -- not required to be the *only* legal form, just one
    #: this type's own `consume` is guaranteed to accept.
    sample: Callable[[], str]


SLOT_TYPES: dict[str, SlotType] = {
    "angle": SlotType("angle", _consume_angle, lambda: "two zero"),
    "heading": SlotType("heading", _consume_heading, lambda: "heading three one five"),
    "oclock": SlotType("oclock", _consume_oclock, lambda: "three o'clock"),
    "quantity": SlotType("quantity", _consume_quantity, lambda: "two zero zero"),
    "speed_target": SlotType(
        "speed_target", _consume_speed_target, lambda: "two zero zero"
    ),
}


# ---------------------------------------------------------------------------
# Parsing a pattern string into `Element`s.
# ---------------------------------------------------------------------------


def _tokenize_pattern(pattern: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c.isspace():
            i += 1
            continue
        if c == "[":
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if pattern[j] == "[":
                    depth += 1
                elif pattern[j] == "]":
                    depth -= 1
                j += 1
            if depth != 0:
                raise PatternError(f"unmatched '[' in pattern: {pattern!r}")
            tokens.append(pattern[i:j])
            i = j
        elif c == "<":
            j = pattern.find(">", i)
            if j == -1:
                raise PatternError(f"unmatched '<' in pattern: {pattern!r}")
            tokens.append(pattern[i : j + 1])
            i = j + 1
        else:
            j = i
            while j < n and not pattern[j].isspace() and pattern[j] not in "[<":
                j += 1
            tokens.append(pattern[i:j])
            i = j
    return tokens


def _parse_element(token: str) -> Element:
    if token.startswith("[") and token.endswith("]"):
        inner_tokens = _tokenize_pattern(token[1:-1])
        if not inner_tokens:
            raise PatternError(f"empty optional group: {token!r}")
        return OptionalElement(tuple(_parse_element(t) for t in inner_tokens))
    if token.startswith("<") and token.endswith(">"):
        inner = token[1:-1]
        if ":" not in inner:
            raise PatternError(f"slot missing ':' in pattern element: {token!r}")
        name, spec = inner.split(":", 1)
        if not name:
            raise PatternError(f"slot missing a name: {token!r}")
        if "|" in spec:
            words = tuple(w for w in spec.split("|") if w)
            if len(words) < 2:
                raise PatternError(f"word-set needs at least two words: {token!r}")
            return WordSetElement(name, words)
        if spec not in SLOT_TYPES:
            raise PatternError(f"unknown slot type {spec!r} in {token!r}")
        return SlotElement(name, spec)
    if not token:
        raise PatternError("empty literal in pattern")
    return LiteralElement(token.lower())


def parse_pattern(pattern: str) -> tuple[Element, ...]:
    """Raises `PatternError` on bad grammar or an unknown slot type (D6:
    the adapter rejects the one rule, not the whole push)."""
    tokens = _tokenize_pattern(pattern)
    if not tokens:
        raise PatternError("pattern has no elements")
    return tuple(_parse_element(t) for t in tokens)


# ---------------------------------------------------------------------------
# Matching.
# ---------------------------------------------------------------------------


def _literal_ratio(heard: str, literal: str) -> float | None:
    """`1.0` on an exact hit; otherwise the character ratio against
    `literal`, or `None` if it fails to clear `_WORD_REPAIR_FLOOR`
    (`[[BL-17]]` D13) -- the one place a `LiteralElement` tolerates a
    mis-transcribed word."""
    if heard == literal:
        return 1.0
    ratio = difflib.SequenceMatcher(None, heard, literal).ratio()
    if ratio < _WORD_REPAIR_FLOOR:
        return None
    return ratio


def _match_elements(
    elements: tuple[Element, ...], words: list[str], idx: int
) -> tuple[dict[str, object], int, list[float]] | None:
    """Returns `(slots, next_index, literal_ratios)` -- `literal_ratios`
    is every `LiteralElement`'s own match ratio encountered along the
    way (including inside an `OptionalElement`), for
    `match_pattern_with_ratio` to average (D13)."""
    slots: dict[str, object] = {}
    literal_ratios: list[float] = []
    i = idx
    for element in elements:
        if isinstance(element, LiteralElement):
            if i >= len(words):
                return None
            ratio = _literal_ratio(words[i], element.word)
            if ratio is None:
                return None
            literal_ratios.append(ratio)
            i += 1
        elif isinstance(element, WordSetElement):
            # **Never fuzzy** (E12, "fuzziness forgives the words, never
            # the values") -- a word-set value is heard exactly or the
            # rule does not match at this position.
            if i >= len(words) or words[i] not in element.words:
                return None
            slots[element.name] = words[i]
            i += 1
        elif isinstance(element, SlotElement):
            # **Never fuzzy either** -- a slot type's own `consume`
            # either succeeds exactly or returns `None`; no ratio is
            # ever computed for a slot value (E12, same as `WordSetElement`
            # above).
            slot_type = SLOT_TYPES.get(element.type_name)
            if slot_type is None:
                return None
            result = slot_type.consume(words, i)
            if result is None:
                return None
            value, i = result
            slots[element.name] = value
        elif isinstance(element, OptionalElement):
            # Greedy, no backtracking across the rest of the pattern: try
            # matching the optional's own content first, fall back to
            # skipping it entirely on failure. No shipped rule (Stage 1b/
            # 2) exercises an optional group, so this is a documented
            # limitation for a later grammar author, not a gap this
            # stage's own tests can expose.
            sub = _match_elements(element.elements, words, i)
            if sub is not None:
                sub_slots, i, sub_ratios = sub
                slots.update(sub_slots)
                literal_ratios.extend(sub_ratios)
        else:  # pragma: no cover -- exhaustive by construction
            raise TypeError(f"unknown pattern element {element!r}")
    return slots, i, literal_ratios


def match_pattern_with_ratio(
    elements: tuple[Element, ...], words: list[str]
) -> tuple[dict[str, object], float] | None:
    """Full-consumption match from word 0, plus the match's own ratio
    (`[[BL-17]]` D13) -- `None` if any element fails or words remain
    unconsumed at the end. The ratio is the mean of every `LiteralElement`
    position's own word-repair ratio (`1.0` for an exact hit), or `1.0`
    if the pattern has no literal at all (nothing to be fuzzy about --
    e.g. a rule whose whole pattern is `<degrees:angle>`)."""
    result = _match_elements(elements, words, 0)
    if result is None:
        return None
    slots, end, literal_ratios = result
    if end != len(words):
        return None
    ratio = sum(literal_ratios) / len(literal_ratios) if literal_ratios else 1.0
    return slots, ratio


def match_pattern(
    elements: tuple[Element, ...], words: list[str]
) -> dict[str, object] | None:
    """`match_pattern_with_ratio`, discarding the ratio -- every caller
    that only needs "did it match" (the collision checks below)."""
    result = match_pattern_with_ratio(elements, words)
    return result[0] if result is not None else None


# ---------------------------------------------------------------------------
# Compiled rules, sample generation, the collision check (D9).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledRule:
    """`category` (`[[BL-17]]` D16/Stage 3b) rides along on `PUT /rules`'s
    per-rule dict and is attached here by `server.py`'s `_handle_put_
    rules` *after* `compile_rules` returns -- `compile_rules`'s own
    matching/collision-check logic (id, pattern, elements only) is
    unchanged, since nothing in this stage reads category for matching.
    Defaults to `"always"` only so this module's own tests, which build
    `CompiledRule` directly for matcher/collision fixtures that predate
    categories, do not need to supply one."""

    id: str
    pattern: str
    elements: tuple[Element, ...]
    category: str = "always"

    def first_literal(self) -> str | None:
        """The word that joins the verb-anchor set (D8) -- only when this
        rule's own *first* element is a plain literal. A rule beginning
        with a slot/word-set/optional contributes no anchor word; it is
        still matchable (`match_pattern` needs no anchor), it just never
        widens `VERB_ANCHOR_WORDS`."""
        if self.elements and isinstance(self.elements[0], LiteralElement):
            return self.elements[0].word
        return None


@dataclass(frozen=True)
class RuleRejection:
    id: str
    reason: str


def _sample_elements(elements: tuple[Element, ...], include_optionals: bool) -> str:
    words: list[str] = []
    for element in elements:
        if isinstance(element, LiteralElement):
            words.append(element.word)
        elif isinstance(element, WordSetElement):
            words.append(element.words[0])
        elif isinstance(element, SlotElement):
            words.append(SLOT_TYPES[element.type_name].sample())
        elif isinstance(element, OptionalElement) and include_optionals:
            words.append(_sample_elements(element.elements, include_optionals))
    return " ".join(w for w in words if w)


def generate_samples(rule: CompiledRule) -> list[str]:
    """One or two concrete utterances this rule's pattern can produce --
    every optional group included, and every optional group excluded
    (D9's own "one per optional branch", collapsed to these two extremes
    rather than the full combinatorial cross product: no rule shipped by
    Stage 1b/2 has more than the implicit "included/excluded" choice to
    make)."""
    samples = {
        _sample_elements(rule.elements, include_optionals=True),
        _sample_elements(rule.elements, include_optionals=False),
    }
    return sorted(s for s in samples if s)


#: A small, fixed set of ordinary short words -- the same "fixed list,
#: not generated" posture `vocabulary.FREE_SPEECH_GUARD` already has --
#: used to probe whether a *mis-transcribed* variant of a rule's own
#: literal could collide with a different rule or an existing legacy
#: phrase (D13's widened D9 collision check, `_perturbed_sample` below).
#: Deliberately generic rather than hand-picked near-misses of any one
#: rule's own wording: a later rule's literal is unknown in advance, and
#: this list only needs to contain *some* word landing in
#: `[_WORD_REPAIR_FLOOR, 1.0)` against whichever literal is being probed
#: -- `_perturbed_sample` skips a literal with no hit at all (module
#: docstring's own "Collision check (D9), widened").
_COLLISION_PROBE_WORDS: tuple[str, ...] = (
    "scam",
    "turn",
    "burn",
    "learn",
    "term",
    "right",
    "light",
    "write",
    "night",
    "left",
    "lift",
    "list",
    "set",
    "sit",
    "say",
    "stay",
    "span",
    "watch",
    "what",
    "wash",
    "report",
    "repeat",
    "support",
    "engage",
    "engaged",
    "mark",
    "mart",
    "dark",
    "speed",
    "speak",
    "heading",
    "level",
    "lever",
    "climb",
    "clime",
)


def _best_probe_word(literal: str) -> str | None:
    """The first `_COLLISION_PROBE_WORDS` entry scoring in
    `[_WORD_REPAIR_FLOOR, 1.0)` against `literal` -- `None` if none does."""
    for candidate in _COLLISION_PROBE_WORDS:
        if candidate == literal:
            continue
        ratio = difflib.SequenceMatcher(None, candidate, literal).ratio()
        if _WORD_REPAIR_FLOOR <= ratio < 1.0:
            return candidate
    return None


def _sample_words_with_literal_flags(
    elements: tuple[Element, ...], include_optionals: bool
) -> list[tuple[str, bool]]:
    """Like `_sample_elements`, but keeping each produced word tagged
    with whether it came from a `LiteralElement` -- only those positions
    are candidates for `_perturbed_sample`'s substitution; a slot/
    word-set sample word is never perturbed (E12, same as the matcher
    itself)."""
    result: list[tuple[str, bool]] = []
    for element in elements:
        if isinstance(element, LiteralElement):
            result.append((element.word, True))
        elif isinstance(element, WordSetElement):
            result.append((element.words[0], False))
        elif isinstance(element, SlotElement):
            result.append((SLOT_TYPES[element.type_name].sample(), False))
        elif isinstance(element, OptionalElement) and include_optionals:
            result.extend(
                _sample_words_with_literal_flags(element.elements, include_optionals)
            )
    return result


def _perturbed_sample(rule: CompiledRule) -> str | None:
    """One sample for `rule` (D9/D13's "one perturbed sample per rule")
    with exactly one literal word replaced by a near-miss probe word --
    tries each literal position in turn and stops at the first one with
    a usable probe word (module docstring's "the perturbed probe is
    skipped for that word" is per-literal, not per-rule: the next
    literal, if any, still gets a chance). `None` if the rule has no
    literal at all, or none of its literals has a usable probe word."""
    parts = _sample_words_with_literal_flags(rule.elements, include_optionals=True)
    for i, (word, is_literal) in enumerate(parts):
        if not is_literal:
            continue
        probe = _best_probe_word(word)
        if probe is None:
            continue
        perturbed_words = [w for w, _ in parts]
        perturbed_words[i] = probe
        return " ".join(w for w in perturbed_words if w)
    return None


def rule_anchor_words(rules: tuple[CompiledRule, ...]) -> frozenset[str]:
    """Every active rule's own `first_literal()` (D8) -- `()` gives the
    empty set, so `VERB_ANCHOR_WORDS | rule_anchor_words(())` is exactly
    `VERB_ANCHOR_WORDS`, the "no rules pushed" no-op D7/Stage 1b's own
    acceptance test pins.

    **Lives here, not in `command_matcher.py` (its original home)**,
    because it is a pure function of `CompiledRule` alone (D15) --
    moving it next to `CompiledRule` is what lets `RuleRegistry.swap`
    below compute it once, at the `PUT /rules` swap point, rather than
    `command_matcher.match_transcript` rebuilding it from `rules` on
    every transcript."""
    words: set[str] = set()
    for rule in rules:
        literal = rule.first_literal()
        if literal is not None:
            words.add(literal)
    return frozenset(words)


@dataclass(frozen=True)
class LegacyProbeResult:
    """What the legacy matcher says about one collision-check probe
    sentence -- `command_matcher`'s own `MatchResult` narrowed to the two
    fields D9 needs, so this module never imports `command_matcher`
    (which imports *this* module for its own D8 rule-matching branch --
    importing it back here would be a real import cycle, not a style
    preference). `legacy_probe`, injected by the caller, is what actually
    runs the real legacy pipeline."""

    token: str | None
    verb_anchored: bool


LegacyProbe = Callable[[str], LegacyProbeResult]


def _samples_with_perturbation(rule: CompiledRule) -> list[str]:
    """`generate_samples(rule)` plus (D13) one perturbed sample, if the
    rule has a usable one -- see `_perturbed_sample`'s own docstring."""
    samples = generate_samples(rule)
    perturbed = _perturbed_sample(rule)
    if perturbed is not None:
        samples = [*samples, perturbed]
    return samples


def _rules_collide(rule_a: CompiledRule, rule_b: CompiledRule) -> bool:
    for sample in _samples_with_perturbation(rule_a):
        if match_pattern(rule_b.elements, sample.split()) is not None:
            return True
    for sample in _samples_with_perturbation(rule_b):
        if match_pattern(rule_a.elements, sample.split()) is not None:
            return True
    return False


def _collides_with_legacy(rule: CompiledRule, legacy_probe: LegacyProbe) -> bool:
    for sample in _samples_with_perturbation(rule):
        if legacy_probe(sample).token is not None:
            return True
    return False


def _collides_with_free_speech(
    rule: CompiledRule, free_speech_guard: tuple[str, ...]
) -> bool:
    for sentence in free_speech_guard:
        words = sentence.split()
        if match_pattern(rule.elements, words) is not None:
            return True
    return False


def _words_in(elements: tuple[Element, ...]) -> list[str]:
    words: list[str] = []
    for element in elements:
        if isinstance(element, LiteralElement):
            words.append(element.word)
        elif isinstance(element, WordSetElement):
            words.extend(element.words)
        elif isinstance(element, OptionalElement):
            words.extend(_words_in(element.elements))
    return words


def rule_words(rule: CompiledRule) -> list[str]:
    """Every literal/word-set word this rule's pattern can produce --
    what `server.py` adds to the whisper prompt bias (D10) alongside the
    existing vocabulary. A slot's own *value* words (digits, "o'clock")
    are not included -- those are already covered by `vocabulary.py`'s
    own digit/time words; a slot type's one fixed anchor word, where it
    has one (`heading`'s "heading"), is a `LiteralElement` in nobody's
    pattern string today (it lives inside the slot type's own `consume`,
    not the grammar), so it is not picked up here either -- a later
    stage that ships a rule using `heading` should add that one word by
    hand to whichever rule file's own bias list needs it, the same way
    any other fixed vocabulary word is added."""
    return _words_in(rule.elements)


@dataclass
class RuleRegistry:
    """The adapter's own mutable holder for its currently-accepted rule
    set -- shared between `server.py`'s `PUT /rules` handler (writes it
    on every successful push) and the whisper prompt provider (reads it
    on every `/transcribe` call, D10). `rules` is swapped in with one
    assignment on each push (D8: "The compiled rule table is an
    immutable object swapped in with one assignment"), never mutated in
    place -- `ThreadingHTTPServer` can run `PUT /rules` and `/transcribe`
    concurrently, and a reader must always see either the old tuple or
    the new one, never a partially-built one.

    `anchor_words` (`[[BL-17]]` D15) is `rule_anchor_words(rules)`,
    computed once by `swap` below rather than by every caller that
    reads `rules` -- `command_matcher.match_transcript`'s own hot path
    passes it straight through instead of rebuilding it per transcript."""

    rules: tuple[CompiledRule, ...] = ()
    version: str | None = None
    anchor_words: frozenset[str] = frozenset()

    def swap(self, rules: tuple[CompiledRule, ...], version: str) -> None:
        """The one state transition `PUT /rules` performs (D8/D15):
        sets `rules`/`version` and recomputes `anchor_words` here, once,
        so it is never stale relative to `rules` and never recomputed
        anywhere else."""
        self.rules = rules
        self.version = version
        self.anchor_words = rule_anchor_words(rules)


def compile_rules(
    raw: list[tuple[str, str]],
    legacy_probe: LegacyProbe,
    free_speech_guard: tuple[str, ...],
) -> tuple[list[CompiledRule], list[RuleRejection]]:
    """Parses every `(id, pattern)` pair, then runs the three collision
    checks in order (D9): rule x rule, rule x legacy, the free-speech
    guard. A hit in any of the three disables every rule it names --
    checked against the still-standing candidate set as each pass
    narrows it, so a rule already disabled by an earlier pass is not
    re-reported in a later one.

    `legacy_probe`/`free_speech_guard` are injected (not imported) --
    see `LegacyProbeResult`'s own docstring for why.

    A duplicate id within `raw` is rejected defensively here too, even
    though body-layer's own loader should already have deduped it
    (D6) -- costs nothing, and this module must never silently pick one
    of two same-named rules."""
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for rule_id, _ in raw:
        if rule_id in seen_ids:
            duplicate_ids.add(rule_id)
        seen_ids.add(rule_id)

    accepted: dict[str, CompiledRule] = {}
    rejected: list[RuleRejection] = []
    for rule_id, pattern in raw:
        if rule_id in duplicate_ids:
            rejected.append(RuleRejection(rule_id, "duplicate rule id"))
            continue
        try:
            elements = parse_pattern(pattern)
        except PatternError as exc:
            rejected.append(RuleRejection(rule_id, f"bad grammar: {exc}"))
            continue
        accepted[rule_id] = CompiledRule(id=rule_id, pattern=pattern, elements=elements)

    disabled: set[str] = set()
    ids = sorted(accepted)
    for i, id_a in enumerate(ids):
        if id_a in disabled:
            continue
        for id_b in ids[i + 1 :]:
            if id_b in disabled:
                continue
            if _rules_collide(accepted[id_a], accepted[id_b]):
                disabled.add(id_a)
                disabled.add(id_b)

    for rule_id in ids:
        if rule_id in disabled:
            continue
        if _collides_with_legacy(accepted[rule_id], legacy_probe):
            disabled.add(rule_id)

    for rule_id in ids:
        if rule_id in disabled:
            continue
        if _collides_with_free_speech(accepted[rule_id], free_speech_guard):
            disabled.add(rule_id)

    for rule_id in disabled:
        rejected.append(
            RuleRejection(
                rule_id,
                "collides with another rule, an existing command, or free speech",
            )
        )
        del accepted[rule_id]

    return [accepted[rid] for rid in sorted(accepted)], rejected


class CachedRulePromptProvider:
    """A whisper-prompt provider (`server.py`'s `stt_engine` prompt
    callable) that only rebuilds the prompt when `registry.version`
    actually changes (`[[BL-17]]` D15) -- the static legacy-vocabulary
    word list the prompt walks never changes at runtime, and the active
    rule set only changes when a `PUT /rules` swaps `registry.rules`
    (via `RuleRegistry.swap`), so rebuilding on every `/transcribe` call
    (one per utterance) bought nothing.

    `build_prompt` is injected -- the actual `vocabulary.to_prompt(...)`
    call plus `server.py`'s own 224-token-cap warning stay there, where
    the warning's own constant is declared; this class owns only the
    version-keyed caching, so it is testable with a plain call-count
    spy rather than needing a live server."""

    def __init__(
        self, registry: RuleRegistry, build_prompt: Callable[[list[str]], str]
    ) -> None:
        self._registry = registry
        self._build_prompt = build_prompt
        self._initialized = False
        self._cached_version: str | None = None
        self._cached_prompt = ""

    def __call__(self) -> str:
        version = self._registry.version
        if not self._initialized or version != self._cached_version:
            extra_words = [
                word for rule in self._registry.rules for word in rule_words(rule)
            ]
            self._cached_prompt = self._build_prompt(extra_words)
            self._cached_version = version
            self._initialized = True
        return self._cached_prompt
