"""Tests for `vocabulary.py`'s internal consistency.

This module cannot assert equality against `aircraft-layer`'s
`ALLOWED_COMMANDS` or `body-layer`'s token tables directly -- `srs-adapter`
must stand alone (root `CLAUDE.md` module-independence rule), which is
exactly why `vocabulary.py` is a hand-synced duplicate rather than a
shared import. What *is* testable here is that this file's own two tables
(`TOKENS`, `PHRASES`) stay internally consistent, and that its helpers
behave as `stt_engine.py`/`tools/stt_bench.py` need them to.
"""

from __future__ import annotations

from vocabulary import (
    LEGACY_F10_TOKENS,
    LEGAL_BEARINGS_DEG,
    PHRASES,
    ROUTING_TOKENS,
    TOKENS,
    VOICE_ONLY_TOKENS,
    bearing_digits,
    bearing_phrase,
    normalize_for_match,
    normalized_phrase_index,
    parse_bearing,
    spoken_phrases,
    to_gbnf,
    token_for_phrase,
)


def test_tokens_is_the_groups_with_no_overlap() -> None:
    """No assertion on how many tokens exist, deliberately.

    An earlier version pinned the count at 15 to guard a mirror of the
    F10 menu. That obligation is gone -- voice is the primary command
    surface and the F10 path is being retired, so this vocabulary is
    expected to grow past it and diverge from it. A count assertion here
    would now be a counter someone bumps on every addition, which tests
    nothing. What still matters is structural: the groups are disjoint
    and nothing is duplicated.
    """
    assert TOKENS == LEGACY_F10_TOKENS + VOICE_ONLY_TOKENS + ROUTING_TOKENS
    assert not set(LEGACY_F10_TOKENS) & set(VOICE_ONLY_TOKENS)
    assert len(set(TOKENS)) == len(TOKENS), "TOKENS must not contain duplicates"


def test_report_and_scan_share_bearings_under_different_verbs() -> None:
    """The scan/report bearing pair is the confusion the bench must expose.

    These eight pairs differ by one word, and mishearing that word swaps
    one action for a different one rather than garbling a phrase. Pinning
    the pairing here means a later edit cannot quietly drop one side and
    leave the bench unable to measure it.
    """
    for suffix in ("n", "ne", "e", "se", "s", "sw", "w", "nw"):
        assert f"scan_bearing_{suffix}" in LEGACY_F10_TOKENS
        assert f"report_bearing_{suffix}" in VOICE_ONLY_TOKENS


def test_every_token_has_phrases() -> None:
    assert set(PHRASES) == set(TOKENS)
    for token in TOKENS:
        assert len(PHRASES[token]) >= 1


def test_no_phrase_belongs_to_two_tokens() -> None:
    seen: dict[str, str] = {}
    for token, phrasings in PHRASES.items():
        for phrase in phrasings:
            assert phrase not in seen, (
                f"phrase {phrase!r} claimed by both {seen.get(phrase)!r} and {token!r}"
            )
            seen[phrase] = token


def test_spoken_phrases_covers_every_phrase() -> None:
    all_phrases = spoken_phrases()
    for phrasings in PHRASES.values():
        for phrase in phrasings:
            assert phrase in all_phrases


def test_token_for_phrase_round_trips() -> None:
    for token, phrasings in PHRASES.items():
        for phrase in phrasings:
            assert token_for_phrase(phrase) == token


def test_token_for_phrase_unknown_returns_none() -> None:
    assert token_for_phrase("this is not a command") is None


def test_to_gbnf_contains_every_phrase() -> None:
    grammar = to_gbnf()
    assert grammar.startswith("root ::=")
    for phrase in spoken_phrases():
        assert f'"{phrase}"' in grammar


def test_normalization_bridges_digits_and_number_words() -> None:
    """The failure this exists to prevent is a silent one.

    Recognizers return "report 3 o'clock"; `PHRASES` spells "report three
    o'clock". Without bridging, every clock clip scores as a miss while
    having been heard perfectly -- and on a bench report that is
    indistinguishable from a recognition failure, which is the wrong
    conclusion to hand someone judging whether recognition works on their
    voice.
    """
    assert normalize_for_match(" Report 3 o'clock.") == "report three o'clock"
    assert normalize_for_match("report 12 o’clock") == "report twelve o'clock"
    assert normalize_for_match("report 8 oclock") == "report eight o'clock"


def test_normalization_folds_case_punctuation_and_compass_spelling() -> None:
    assert normalize_for_match("SCAN LEFT") == "scan left"
    assert normalize_for_match(" Scan left.") == "scan left"
    assert normalize_for_match("Scan bearing north-west.") == "scan bearing northwest"
    assert normalize_for_match("scan north west") == "scan northwest"


def test_normalization_does_not_repair_a_wrong_verb() -> None:
    """Normalization must not do the matcher's job.

    "record" for "report" is a real mishearing observed from ggml-base.en.
    Folding it away here would hide the single most consequential error
    class in this vocabulary -- verbs select the action, so a wrong verb
    runs a different command rather than garbling a word. Whether to
    forgive it is the matcher's decision, made with a verb anchor; this
    step only removes differences that carry no meaning.
    """
    assert normalize_for_match("record three o'clock") != normalize_for_match(
        "report three o'clock"
    )


def test_every_phrase_normalizes_to_a_unique_token() -> None:
    index = normalized_phrase_index()
    assert len(index) == len(spoken_phrases())
    for token in TOKENS:
        for phrase in PHRASES[token]:
            assert index[normalize_for_match(phrase)] == token


def test_routing_tokens_are_not_commands() -> None:
    """Routing tokens must stay separable from dispatchable commands.

    `wake_petrovich` and `cancel_nevermind` are recognised and measured
    like any other token, but dispatching either as a command would be a
    bug -- one selects which interpreter handles the transmission, the
    other retracts it. Keeping them in their own tuple is what lets a
    consumer tell the two kinds apart without a name-prefix convention.
    """
    assert set(ROUTING_TOKENS).isdisjoint(LEGACY_F10_TOKENS)
    assert set(ROUTING_TOKENS).isdisjoint(VOICE_ONLY_TOKENS)
    for token in ROUTING_TOKENS:
        assert token in TOKENS
        assert PHRASES[token]


def test_wake_word_has_bare_and_greeted_forms() -> None:
    """Both forms get said, often in one sortie, so both must be heard."""
    phrasings = PHRASES["wake_petrovich"]
    assert any(p == "petrovich" for p in phrasings)
    assert any(p.endswith("petrovich") and p != "petrovich" for p in phrasings)


def test_stop_and_nevermind_are_distinct_tokens() -> None:
    """They look similar and behave oppositely in time.

    `stop_talking` interrupts Petrovich the moment it is recognised;
    `cancel_nevermind` retracts the player's own transmission and can
    only be acted on once that transmission closes. Collapsing them --
    or letting normalization fold one onto the other -- would make an
    interrupt retract a command, or a retraction silence the crew.
    """
    assert normalize_for_match("stop") != normalize_for_match("nevermind")
    index = normalized_phrase_index()
    assert index[normalize_for_match("stop")] == "stop_talking"
    assert index[normalize_for_match("nevermind")] == "cancel_nevermind"


def test_bearing_digits_are_always_three() -> None:
    assert bearing_digits(320) == "three two zero"
    assert bearing_digits(5) == "zero zero five"
    assert bearing_digits(0) == "zero zero zero"


def test_parse_bearing_accepts_digits_and_words_interchangeably() -> None:
    """Recognizers mix the two freely, sometimes within one clip."""
    for text in (
        "scan bearing three two zero",
        "scan bearing 320",
        "scan bearing 3 2 0",
    ):
        assert parse_bearing(text).degrees == 320


def test_bearing_resolution_rejects_impossible_values() -> None:
    """The 5 degree step is a checksum, and this is the property it buys.

    Roughly four out of five mishearings land on a number that cannot be
    a real bearing. Returning those as `heard` without `degrees` lets the
    caller ask the player to say again rather than turning to a heading
    nobody said -- a wrong heading flown confidently being much worse
    than one more readback.
    """
    parsed = parse_bearing("scan bearing three two one")
    assert parsed.degrees is None
    assert parsed.heard == 321

    assert parse_bearing("scan bearing nine nine nine").degrees is None
    assert parse_bearing("scan north").heard is None


def test_every_legal_bearing_round_trips() -> None:
    for degrees in LEGAL_BEARINGS_DEG:
        assert parse_bearing(bearing_phrase("scan", degrees)).degrees == degrees


def test_sampled_bearings_cover_every_digit() -> None:
    """The sample exists to measure per-digit reliability, not per-bearing.

    Numbers are the accent-fragile part of this vocabulary, so a sample
    that never says "six" would leave a gap the bench cannot see.
    """
    spoken = "".join(
        p for p in PHRASES["scan_bearing_deg"] + PHRASES["report_bearing_deg"]
    )
    for digit_name in (
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
    ):
        assert digit_name in spoken, f"no sampled bearing says {digit_name!r}"


def test_bearing_compass_phrasings_are_gone() -> None:
    """The user does not say "scan bearing north" -- only "scan north".

    Kept as a test because the phrasing looks natural in a table and
    could easily be reinstated by someone tidying up.
    """
    for phrase in spoken_phrases():
        if "bearing" in phrase:
            assert any(
                word in phrase
                for word in ("zero", "one", "two", "three", "four", "five")
            ), f"{phrase!r} pairs 'bearing' with a compass word"


def test_no_phrasing_carries_a_filler_article() -> None:
    """Phrasings are what this speaker says, not idiomatic English.

    "watch the nearest" and "scan to the right" were both dropped on
    direction. Each costs clips to record and gives a mishearing one more
    way to resolve to something legal, while adding no coverage, since
    the bench can only measure what actually gets uttered. Pinned as a
    test because articles read as natural and would slip back in the next
    time somebody extends this table.
    """
    for token, phrasings in PHRASES.items():
        for phrase in phrasings:
            words = phrase.split()
            for filler in ("the", "a", "an", "to"):
                assert filler not in words, (
                    f"{token}: {phrase!r} carries filler {filler!r}"
                )


def test_bearing_digit_runs_expand_back_to_words() -> None:
    """A heard "180" and a spoken "one eight zero" must compare equal.

    Whisper writes spoken digit sequences back as a numeral -- and
    sometimes as "1.8.0", whose punctuation normalization already
    removes. Left alone, a bearing heard perfectly scores as a complete
    miss, which is the same silent failure the clock bridging fixed: a
    representation difference presenting as a recognition failure, in the
    one part of the vocabulary where numbers are most fragile anyway.
    """
    spoken = normalize_for_match("scan bearing one eight zero")
    assert normalize_for_match("scan bearing 180") == spoken
    assert normalize_for_match("Screen bearing 1.8.0").endswith("one eight zero")


def test_digit_expansion_only_applies_after_bearing() -> None:
    """Clock positions stay whole; only bearings are digit sequences.

    "report 12 o'clock" means twelve, not one-two, so the expansion is
    anchored on the word "bearing" rather than applied to every numeral.
    """
    assert normalize_for_match("report 12 o'clock") == "report twelve o'clock"
