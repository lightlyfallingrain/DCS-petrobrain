"""Tests for `perception.object_model.profile_for`.

Mirrors `test_association.py`'s fixture-only, no-network-I/O posture --
`object_model.py` is pure data plus a lookup function.
"""

from __future__ import annotations

from perception.object_model import (
    DEFAULT_OP_CLASS,
    DEFAULT_SIZE_M,
    profile_for,
)


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
    # Worked example table: SA-3 launcher -> 9 m.
    profile = profile_for("SA-3 Launcher")

    assert profile.size_m == 9.0
    assert profile.op_class == "OP_SRSAM"


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
    profile = profile_for("Grisha corvette")

    assert profile.op_class == "OP_SHIP"
