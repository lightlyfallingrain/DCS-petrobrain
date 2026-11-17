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

**Matching** (this module's own scoping choice, not a literal
implementation of D8's fuzzy-score description): a rule matches a
transcript only on **full, exact-literal consumption** -- every element
must consume its words and nothing may be left over. This is
deliberately simpler than the legacy matcher's fuzzy phrase-sequence
score (`command_matcher._phrase_match_ratio`): `[[BL-17]]`'s own guiding
decision is "fixed wording is the fast path" (U1), and a deterministic
grammar is what that means for a rule's own words -- tolerance for STT
noise on a rule's literals is left for a later stage to add if real
flights show it is needed, rather than building a second fuzzy engine
now for the one rule this stage ships.

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

from collections.abc import Callable
from dataclasses import dataclass

from vocabulary import _WORD_DIGITS

__all__ = [
    "SLOT_TYPES",
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
    "parse_pattern",
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


def _consume_angle(words: list[str], idx: int) -> tuple[object, int] | None:
    """1-3 digits, no anchor word of its own, value 1-359 (D7: the bare
    number in e.g. "turn left <degrees:angle>")."""
    result = _consume_digit_run(words, idx, 1, 3)
    if result is None:
        return None
    digit_str, next_idx = result
    value = int(digit_str)
    if not (1 <= value <= 359):
        return None
    return value, next_idx


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


def _match_elements(
    elements: tuple[Element, ...], words: list[str], idx: int
) -> tuple[dict[str, object], int] | None:
    slots: dict[str, object] = {}
    i = idx
    for element in elements:
        if isinstance(element, LiteralElement):
            if i >= len(words) or words[i] != element.word:
                return None
            i += 1
        elif isinstance(element, WordSetElement):
            if i >= len(words) or words[i] not in element.words:
                return None
            slots[element.name] = words[i]
            i += 1
        elif isinstance(element, SlotElement):
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
                sub_slots, i = sub
                slots.update(sub_slots)
        else:  # pragma: no cover -- exhaustive by construction
            raise TypeError(f"unknown pattern element {element!r}")
    return slots, i


def match_pattern(
    elements: tuple[Element, ...], words: list[str]
) -> dict[str, object] | None:
    """Full-consumption match only, from word 0 -- `None` if any element
    fails or words remain unconsumed at the end (module docstring's own
    scoping choice: exact-literal, not fuzzy)."""
    result = _match_elements(elements, words, 0)
    if result is None:
        return None
    slots, end = result
    if end != len(words):
        return None
    return slots


# ---------------------------------------------------------------------------
# Compiled rules, sample generation, the collision check (D9).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledRule:
    id: str
    pattern: str
    elements: tuple[Element, ...]

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


def _rules_collide(rule_a: CompiledRule, rule_b: CompiledRule) -> bool:
    for sample in generate_samples(rule_a):
        if match_pattern(rule_b.elements, sample.split()) is not None:
            return True
    for sample in generate_samples(rule_b):
        if match_pattern(rule_a.elements, sample.split()) is not None:
            return True
    return False


def _collides_with_legacy(rule: CompiledRule, legacy_probe: LegacyProbe) -> bool:
    for sample in generate_samples(rule):
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
    the new one, never a partially-built one."""

    rules: tuple[CompiledRule, ...] = ()
    version: str | None = None


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
