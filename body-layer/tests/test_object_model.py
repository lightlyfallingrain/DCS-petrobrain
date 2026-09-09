"""Tests for `perception.object_model.profile_for`.

Mirrors `test_association.py`'s fixture-only, no-network-I/O posture --
`object_model.py` is pure data plus a lookup function.
"""

from __future__ import annotations

import json
from pathlib import Path

from perception.object_model import (
    DEFAULT_OP_CLASS,
    DEFAULT_SIZE_M,
    profile_for,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Measured against this fixture (78/92, see
# test_coverage_floor_against_real_type_sample below) -- a floor a bit below
# that so a future keyword edit has some room to shuffle individual matches
# without failing, while still catching an actual regression (e.g. the
# OP_SHIP or SA-3/6/8/9/13/15 fix in this commit being silently reverted or
# broken). Not a claim about coverage of the full real DCS type catalogue --
# see aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md
# for that (measured separately against all 595 real types, not this curated
# sample).
_MIN_COVERAGE_FRACTION = 0.8


def test_unmatched_object_type_falls_back_to_default_profile() -> None:
    profile = profile_for("SomeUnrecognizedUnit-99")

    assert profile.size_m == DEFAULT_SIZE_M
    assert profile.op_class == DEFAULT_OP_CLASS


def test_truck_keyword_matches_ural() -> None:
    # Worked example table in plans/pb1.5-naked-eye-detection/plan.md's
    # Proposed Defaults section: Ural truck -> 6 m / OP_TRUCK.
    profile = profile_for("Ural-4320")

    assert profile.size_m == 6.0
    assert profile.op_class == "OP_TRUCK"


def test_armored_keyword_matches_t72() -> None:
    # Worked example table: T-72 -> 7 m / OP_ARMORED.
    profile = profile_for("T-72B")

    assert profile.size_m == 7.0
    assert profile.op_class == "OP_ARMORED"


def test_infantry_keyword() -> None:
    # Worked example table: infantry -> 1.8 m.
    profile = profile_for("Infantry AK-74")

    assert profile.size_m == 1.8
    assert profile.op_class == "OP_INFANTRY"


def test_sa3_keyword() -> None:
    # Worked example table: SA-3 launcher -> 9 m. "SA-3 Launcher" is not a
    # real DCS object_type (that was the bug this test used to mask, see
    # test_ship_keyword below) -- "5p73 s-125 ln" is the real SA-3 launcher
    # type name from ED's own type list (aircraft-layer/research/
    # 2026-09-09-object-model-keyword-coverage.md).
    profile = profile_for("5p73 s-125 ln")

    assert profile.size_m == 9.0
    assert profile.op_class == "OP_SRSAM"


def test_sa6_keyword_is_mrsam_not_srsam() -> None:
    # SA-6 (Kub) is the table's one OP_MRSAM entry, distinct from the other
    # SA-*/OP_SRSAM rows -- worth a direct check since it's easy to
    # copy-paste the wrong class when re-deriving a keyword. Real DCS type
    # name: "Kub 2P25 ln" (launcher component).
    profile = profile_for("Kub 2P25 ln")

    assert profile.op_class == "OP_MRSAM"


def test_sa6_keyword_does_not_match_unrelated_kubelwagen() -> None:
    # "kub " (with trailing space) was chosen specifically to avoid matching
    # "Kubelwagen_82" (a real DCS type -- a WWII-era civilian car, nothing to
    # do with the Kub/SA-6 SAM system). Regression guard against a future
    # edit narrowing this back to a bare "kub" substring.
    profile = profile_for("Kubelwagen_82")

    assert profile.op_class == DEFAULT_OP_CLASS


def test_lookup_is_case_insensitive() -> None:
    profile = profile_for("ural-4320")

    assert profile.op_class == "OP_TRUCK"


def test_hyphenated_zu23_keyword_is_not_split_by_a_word_tokenizer() -> None:
    # This is the reason object_model.py uses substring containment rather
    # than association.py's word-tokenized ([a-z0-9]+) overlap: a tokenizer
    # would split "ZU-23" into "zu"/"23" and lose the compound identifier.
    profile = profile_for("ZU-23 Emplacement")

    assert profile.op_class == "OP_ZU23"


def test_shilka_keyword_takes_precedence_over_generic_class() -> None:
    profile = profile_for("ZSU-23-4 Shilka")

    assert profile.op_class == "OP_SPAAG"


def test_ship_keyword() -> None:
    # "Grisha corvette" (the string this test used to assert against) is not
    # a real DCS object_type -- it's Petrovich's *reporting name* for the
    # real type "ALBATROS" (aircraft-layer/research/
    # 2026-09-09-object-model-keyword-coverage.md). It matched the old
    # keyword table ("corvette" was one of six English hull-class words) by
    # construction, which is exactly why the table's real defect --
    # `object_type` never carries an English hull-class word, so OP_SHIP was
    # unreachable against real data -- went undetected. "MOSCOW" (the real
    # DCS type for the Slava-class cruiser) is used here instead so this
    # test would actually fail if OP_SHIP regresses to keying on
    # reporting-name-shaped words again.
    profile = profile_for("MOSCOW")

    assert profile.size_m == 100.0
    assert profile.op_class == "OP_SHIP"


def test_ship_keyword_matches_second_real_type_name() -> None:
    # A second, differently-shaped real ship object_type (a hyphenated,
    # lowercase, multi-word compound rather than a single uppercase token)
    # so this category isn't anchored on only one naming style.
    profile = profile_for("leander-gun-achilles")

    assert profile.op_class == "OP_SHIP"


def test_coverage_floor_against_real_type_sample() -> None:
    """Per-entry regression guard plus an aggregate coverage floor, against
    `tests/fixtures/object_type_coverage_sample.json`'s committed sample of
    real DCS `object_type` strings (see that file's `_comment` and
    `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`
    for provenance). This is the test the review required: a measurement
    against real data, not a fabricated string that would pass even if the
    underlying keyword table stopped matching anything real (exactly how
    the old `test_ship_keyword` masked the OP_SHIP domain-mismatch bug this
    fix addresses).

    Every entry is checked individually (both the "should classify" and the
    "should legitimately fall back" cases -- object_model.py does not
    attempt air/building/full-SAM-catalogue coverage, so some fallbacks in
    the fixture are the *correct*, expected outcome, not a gap), so this
    also catches a keyword accidentally over-matching an out-of-scope type.
    """
    fixture = json.loads(
        (_FIXTURES_DIR / "object_type_coverage_sample.json").read_text()
    )
    entries = fixture["entries"]

    mismatches: list[str] = []
    classified_count = 0
    for entry in entries:
        object_type = entry["object_type"]
        expected_op_class = entry["expected_op_class"] or DEFAULT_OP_CLASS
        actual_op_class = profile_for(object_type).op_class
        if actual_op_class != expected_op_class:
            mismatches.append(
                f"{object_type!r}: expected {expected_op_class!r}, got {actual_op_class!r}"
            )
        if actual_op_class != DEFAULT_OP_CLASS:
            classified_count += 1

    assert not mismatches, "\n".join(mismatches)

    coverage_fraction = classified_count / len(entries)
    assert coverage_fraction >= _MIN_COVERAGE_FRACTION, (
        f"coverage against real-type sample dropped to {coverage_fraction:.3f} "
        f"({classified_count}/{len(entries)}), below floor {_MIN_COVERAGE_FRACTION}"
    )
